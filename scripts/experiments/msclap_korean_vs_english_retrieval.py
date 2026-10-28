"""Paired Korean/English AudioCaps Multilingual retrieval experiment.

This experiment uses the repository-pinned MSCLAP 2023 implementation and
project raw-cosine helper. AudioCaps' ten-second clips intentionally use the
MSCLAP package's configured audio window rather than the service's 56-second
Audio Highlight policy.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import gzip
import hashlib
import importlib.metadata
import json
import os
import random
import statistics
import subprocess
import time
import platform
import sys
from ctypes import wintypes
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.embedding.text_embedding import CALIBRATION_CHECKPOINT_REVISION


DATASET_ID = "piyushsinghpasi/audiocaps-multilingual"
DATASET_REVISION = "6d74f0a52927fb4c776fb344de0b01db851b07d9"
DATASET_LICENSE = "cc-by-nc-4.0"
ENGLISH_COLUMN = "caption"
KOREAN_COLUMN = "kor_Hang_AYA"
EXPECTED_SAMPLE_RATE = 32_000
TOKEN_LIMIT = 77
TEXT_BATCH_SIZE = 32
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 20261025
AUDIO_SEED_VERSION = "sha256(dataset-revision:file-name)-first32-v1"
EVALUATION_PREPROCESSING = "msclap-2023-native-7s-window-on-10s-audiocaps-wav-v1"


class ExperimentError(RuntimeError):
    """Raised when frozen dataset or runtime identity cannot be verified."""


def resolve_repository_head() -> str:
    """Resolve the checkout revision for run provenance."""
    override = os.environ.get("NSU_CAPSTONE_AI_HEAD")
    if override:
        return override

    repository_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExperimentError("Unable to resolve repository HEAD with git rev-parse HEAD") from exc

    head = result.stdout.strip()
    if not head:
        raise ExperimentError("git rev-parse HEAD returned an empty revision")
    return head


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def memory_snapshot() -> dict[str, Any]:
    """Read system RAM and this process' working set without elevation."""
    if sys.platform != "win32":
        return {"available": False, "reason": "Windows counters unavailable"}
    result: dict[str, Any] = {"available": True}
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ctypes.WinError()
        result["system_total_bytes"] = int(status.ullTotalPhys)
        result["system_available_bytes"] = int(status.ullAvailPhys)
    except Exception as exc:
        result["system_ram_error"] = type(exc).__name__
    try:
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        result["process_working_set_bytes"] = int(counters.WorkingSetSize)
        result["process_peak_working_set_bytes"] = int(counters.PeakWorkingSetSize)
    except Exception as exc:
        result["process_memory_error"] = type(exc).__name__
    return result


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def safe_dataset_path(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts:
        raise ExperimentError(f"unsafe dataset relative path: {relative}")
    return root.joinpath(*posix.parts)


def read_metadata(metadata_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = list(reader.fieldnames or [])
        required = {"file_name", "audiocap_id", "youtube_id", "start_time", ENGLISH_COLUMN, KOREAN_COLUMN}
        missing = sorted(required.difference(columns))
        if missing:
            raise ExperimentError(f"metadata columns missing: {missing}")
        rows = list(reader)
    ids = [row["audiocap_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ExperimentError("duplicate audiocap_id in pinned metadata")
    return rows, columns


def _token_count(tokenizer: Any, text: str) -> tuple[int, int]:
    effective = text + " <|endoftext|>"
    encoded = tokenizer.encode_plus(
        text=effective,
        add_special_tokens=True,
        max_length=TOKEN_LIMIT,
        padding="max_length",
        return_tensors="pt",
    )
    count = int(encoded["attention_mask"].reshape(-1).sum().item())
    actual_length = int(encoded["input_ids"].shape[-1])
    return count, actual_length


def inspect_audio_file(path: Path) -> dict[str, Any]:
    """Decode and inspect a dataset clip without applying service preprocessing."""
    import torchaudio

    try:
        waveform, sample_rate = torchaudio.load(str(path))
    except Exception as exc:
        return {"status": "decode_failed", "reason": type(exc).__name__}
    if waveform.ndim != 2 or waveform.shape[0] < 1 or waveform.shape[1] < 1:
        return {"status": "damaged_audio", "reason": "invalid_decoded_shape"}
    duration = waveform.shape[1] / sample_rate
    if duration < 7.0:
        return {"status": "too_short_for_msclap_window", "duration_seconds": duration}
    return {
        "status": "usable",
        "duration_seconds": duration,
        "sample_rate": sample_rate,
        "channels": int(waveform.shape[0]),
        "frame_count": int(waveform.shape[1]),
        "file_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_cohort(metadata_path: Path, audio_root: Path, tokenizer: Any) -> dict[str, Any]:
    rows, columns = read_metadata(metadata_path)
    audio_status: dict[str, dict[str, Any]] = {}
    audio_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    excluded_audio: list[dict[str, Any]] = []

    for row in rows:
        file_name = row["file_name"]
        audio_rows[file_name].append(row)
        if file_name not in audio_status:
            path = safe_dataset_path(audio_root, file_name)
            if not path.is_file():
                audio_status[file_name] = {"status": "download_missing"}
            else:
                audio_status[file_name] = inspect_audio_file(path)

    usable_audio: list[dict[str, Any]] = []
    usable_names: set[str] = set()
    for file_name, status in audio_status.items():
        if status["status"] == "usable":
            usable_names.add(file_name)
            usable_audio.append({"file_name": file_name, **status})
        else:
            excluded_audio.append({"file_name": file_name, **status})

    paired_rows: list[dict[str, Any]] = []
    exclusions = Counter()
    all_token_lengths = {"english": [], "korean": []}
    overflows = {"english": 0, "korean": 0, "either_language": 0}
    for row in rows:
        en = row[ENGLISH_COLUMN]
        ko = row[KOREAN_COLUMN]
        if not en.strip() or not ko.strip():
            exclusions["missing_caption_pair"] += 1
            continue
        en_count, en_length = _token_count(tokenizer, en)
        ko_count, ko_length = _token_count(tokenizer, ko)
        all_token_lengths["english"].append(en_count)
        all_token_lengths["korean"].append(ko_count)
        overflows["english"] += int(en_count > TOKEN_LIMIT or en_length > TOKEN_LIMIT)
        overflows["korean"] += int(ko_count > TOKEN_LIMIT or ko_length > TOKEN_LIMIT)
        if en_count > TOKEN_LIMIT or en_length > TOKEN_LIMIT or ko_count > TOKEN_LIMIT or ko_length > TOKEN_LIMIT:
            exclusions["paired_token_overflow"] += 1
            overflows["either_language"] += 1
            continue
        if row["file_name"] not in usable_names:
            exclusions[audio_status[row["file_name"]]["status"]] += 1
            continue
        paired_rows.append({
            "audiocap_id": row["audiocap_id"],
            "audio_file_name": row["file_name"],
            "youtube_id": row["youtube_id"],
            "start_time": int(row["start_time"]),
            "english_caption": en,
            "korean_caption": ko,
            "english_caption_sha256": sha256_bytes(en.encode("utf-8")),
            "korean_caption_sha256": sha256_bytes(ko.encode("utf-8")),
            "english_token_count": en_count,
            "korean_token_count": ko_count,
        })

    paired_audio_names = {row["audio_file_name"] for row in paired_rows}
    for name in sorted(usable_names - paired_audio_names):
        excluded_audio.append({"file_name": name, "status": "no_usable_paired_caption"})
    usable_audio = [item for item in usable_audio if item["file_name"] in paired_audio_names]
    token_summaries = {}
    for language, values in all_token_lengths.items():
        token_summaries[language] = {
            "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "mean": statistics.mean(values) if values else None,
            "max": max(values) if values else None,
            "over_77_count": overflows[language],
        }
    return {
        "artifact_type": "msclap-korean-vs-english-paired-cohort",
        "cohort_version": "audiocaps-multilingual-ko-en-cohort-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "repo_id": DATASET_ID,
            "revision": DATASET_REVISION,
            "license": DATASET_LICENSE,
            "split": "test",
            "source": f"https://huggingface.co/datasets/{DATASET_ID}/tree/{DATASET_REVISION}/test",
            "metadata_file": "test/metadata.csv",
            "metadata_sha256": sha256_file(metadata_path),
            "metadata_columns": columns,
            "english_column": ENGLISH_COLUMN,
            "korean_column": KOREAN_COLUMN,
            "korean_caption_provenance": "AYA-generated translation per dataset card",
        },
        "selection": {
            "pairing_key": "audiocap_id; candidate audio identity=file_name",
            "audio_policy": "include only downloadable, decodable audio at least 7 seconds long",
            "caption_policy": "include only rows with nonempty English and Korean captions and both under 77 pinned MSCLAP tokens; no truncation",
            "audio_preprocessing_profile": EVALUATION_PREPROCESSING,
            "token_limit": TOKEN_LIMIT,
        },
        "counts": {
            "dataset_rows": len(rows),
            "unique_audio_references": len(audio_rows),
            "usable_audio_count": len(usable_audio),
            "excluded_audio_count": len(audio_rows) - len(usable_audio),
            "paired_query_count": len(paired_rows),
            "english_query_count": len(paired_rows),
            "korean_query_count": len(paired_rows),
            "dataset_complete_paired_caption_rows": len(all_token_lengths["english"]),
            "dataset_caption_token_overflow_counts": overflows,
            "excluded_caption_rows_by_reason": dict(sorted(exclusions.items())),
            "excluded_audio_by_reason": dict(sorted(Counter(item["status"] for item in excluded_audio).items())),
        },
        "token_lengths": {"all_dataset_caption_rows": token_summaries},
        "audio": sorted(usable_audio, key=lambda item: item["file_name"]),
        "excluded_audio": sorted(excluded_audio, key=lambda item: item["file_name"]),
        "paired_queries": paired_rows,
    }


def validate_frozen_cohort(cohort: dict[str, Any]) -> None:
    if cohort.get("dataset", {}).get("revision") != DATASET_REVISION:
        raise ExperimentError("cohort dataset revision does not match frozen revision")
    counts = cohort.get("counts", {})
    rows = cohort.get("paired_queries", [])
    audio = cohort.get("audio", [])
    if len(rows) != counts.get("paired_query_count") or len(audio) != counts.get("usable_audio_count"):
        raise ExperimentError("cohort count fields do not match artifact rows")
    if counts.get("english_query_count") != counts.get("korean_query_count"):
        raise ExperimentError("cohort is not paired 1:1")
    if len({row["audiocap_id"] for row in rows}) != len(rows):
        raise ExperimentError("duplicate paired query identity")
    audio_names = {item["file_name"] for item in audio}
    if any(row["audio_file_name"] not in audio_names for row in rows):
        raise ExperimentError("paired query references an audio outside candidate cohort")


def _l2_norm_rows(tensor: Any) -> Any:
    import torch.nn.functional as functional

    return functional.normalize(tensor, dim=1)


def _raw_cosines(text_vector: Any, audio_matrix: Any) -> Any:
    from app.matching.audio_search import audio_cosine_similarities

    return audio_cosine_similarities(text_vector.reshape(1, -1), audio_matrix)


def _rank_query(vector: Any, audio_matrix: Any, audio_ids: list[str], target_id: str, *, include_top10: bool = False) -> dict[str, Any]:
    scores = _raw_cosines(vector, audio_matrix).tolist()
    order = sorted(range(len(audio_ids)), key=lambda index: (-scores[index], audio_ids[index]))
    target_rank = next(index + 1 for index, candidate_index in enumerate(order) if audio_ids[candidate_index] == target_id)
    result = {"target_rank": target_rank, "target_raw_cosine": scores[audio_ids.index(target_id)]}
    if include_top10:
        result["top10"] = [{"audio_file_name": audio_ids[index], "raw_cosine": scores[index]} for index in order[:10]]
    return result


def retrieval_metrics(records: list[dict[str, Any]], rank_key: str) -> dict[str, Any]:
    ranks = [int(row[rank_key]) for row in records]
    if not ranks:
        raise ExperimentError("no paired retrieval records")
    return {
        "query_count": len(ranks),
        "recall_at_1": sum(rank <= 1 for rank in ranks) / len(ranks),
        "recall_at_5": sum(rank <= 5 for rank in ranks) / len(ranks),
        "recall_at_10": sum(rank <= 10 for rank in ranks) / len(ranks),
        "mrr": statistics.mean(1.0 / rank for rank in ranks),
        "median_rank": statistics.median(ranks),
        "mean_rank": statistics.mean(ranks),
    }


def paired_bootstrap(records: list[dict[str, Any]], *, replicates: int = BOOTSTRAP_REPLICATES, seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """Cluster-bootstrap audio IDs, preserving their five paired captions."""
    import numpy as np

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        groups[row["audio_file_name"]].append(row)
    audio_ids = sorted(groups)
    rng = np.random.default_rng(seed)
    metric_specs = {
        "recall_at_1": lambda ranks: (ranks <= 1).mean(),
        "recall_at_5": lambda ranks: (ranks <= 5).mean(),
        "recall_at_10": lambda ranks: (ranks <= 10).mean(),
        "mrr": lambda ranks: (1.0 / ranks).mean(),
    }
    values: dict[str, list[float]] = {name: [] for name in metric_specs}
    for _ in range(replicates):
        sample_ids = rng.choice(audio_ids, size=len(audio_ids), replace=True)
        sample = [row for audio_id in sample_ids for row in groups[str(audio_id)]]
        en = np.asarray([row["english_rank"] for row in sample], dtype=np.float64)
        ko = np.asarray([row["korean_rank"] for row in sample], dtype=np.float64)
        for name, metric in metric_specs.items():
            values[name].append(float(metric(ko) - metric(en)))
    return {
        "method": "paired cluster bootstrap by unique audio_file_name; captions within sampled audio remain grouped",
        "replicates": replicates,
        "seed": seed,
        "delta_definition": "Korean metric minus English metric",
        "confidence_level": 0.95,
        "intervals": {
            name: {
                "observed_delta": value,
                "lower": float(np.quantile(values[name], 0.025)),
                "upper": float(np.quantile(values[name], 0.975)),
            }
            for name, value in ((key, None) for key in metric_specs)
        },
    }


def _load_pinned_msclap():
    from app.embedding.text_embedding import TextEmbeddingGenerator

    generator = TextEmbeddingGenerator(expected_dimension=1024)
    model = generator._model
    return generator, model


def _audio_seed(file_name: str) -> int:
    value = f"{DATASET_REVISION}:{file_name}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:4], "big")


def _version(name: str) -> str:
    return importlib.metadata.version(name)


def _model_evidence(generator: Any) -> dict[str, Any]:
    return {
        "name": "MSCLAP", "version": "2023", "package": _version("msclap"),
        "checkpoint_revision": CALIBRATION_CHECKPOINT_REVISION,
        "checkpoint_sha256": generator._checkpoint_sha256,
        "implementation_identity": generator._msclap_implementation_identity,
        "text_encoder_identity": generator._text_encoder_identity,
        "dimension": 1024,
    }


def run_embeddings(cohort_path: Path, audio_root: Path, output_dir: Path) -> dict[str, Any]:
    import torch

    from app.embedding.text_embedding import _token_count_without_truncation

    cohort_bytes = cohort_path.read_bytes()
    cohort = json.loads(cohort_bytes.decode("utf-8"))
    validate_frozen_cohort(cohort)
    cohort_sha = sha256_bytes(cohort_bytes)
    output_dir.mkdir(parents=True, exist_ok=False)

    memory_before = memory_snapshot()
    load_started = time.perf_counter()
    generator, model = _load_pinned_msclap()
    model_load_seconds = time.perf_counter() - load_started
    memory_after_load = memory_snapshot()
    tokenizer = model.model.tokenizer
    audio_ids: list[str] = []
    audio_vectors: list[Any] = []
    audio_failures: list[dict[str, str]] = []
    audio_started = time.perf_counter()
    for item in cohort["audio"]:
        name = item["file_name"]
        path = safe_dataset_path(audio_root, name)
        try:
            if sha256_file(path) != item["sha256"]:
                raise ExperimentError("audio_sha256_changed_after_cohort_freeze")
            random.seed(_audio_seed(name))
            with torch.inference_mode():
                vector = model.encode_audio(str(path))
            if vector.shape != (1, 1024) or not bool(torch.isfinite(vector).all()) or not bool(vector.norm(dim=1).gt(0).all()):
                raise ExperimentError("invalid_audio_embedding")
            audio_ids.append(name)
            audio_vectors.append(vector.detach().cpu().to(dtype=torch.float32))
        except Exception as exc:
            audio_failures.append({"file_name": name, "reason": str(exc) or type(exc).__name__})
    audio_seconds = time.perf_counter() - audio_started
    memory_after_audio = memory_snapshot()
    if not audio_vectors:
        raise ExperimentError("no audio embeddings succeeded")
    audio_matrix = torch.cat(audio_vectors, dim=0)

    token_overflows: list[dict[str, Any]] = []
    text_rows = []
    for row in cohort["paired_queries"]:
        en_count, _, _ = _token_count_without_truncation(row["english_caption"], model)
        ko_count, _, _ = _token_count_without_truncation(row["korean_caption"], model)
        if en_count > TOKEN_LIMIT or ko_count > TOKEN_LIMIT:
            token_overflows.append({"audiocap_id": row["audiocap_id"], "english": en_count, "korean": ko_count})
            continue
        text_rows.append(row)

    en_vectors: list[Any] = []
    ko_vectors: list[Any] = []
    text_batch_failures: list[dict[str, Any]] = []
    text_started = time.perf_counter()
    for start in range(0, len(text_rows), TEXT_BATCH_SIZE):
        batch = text_rows[start:start + TEXT_BATCH_SIZE]
        try:
            with torch.inference_mode():
                en = model.encode_text([row["english_caption"] for row in batch])
                ko = model.encode_text([row["korean_caption"] for row in batch])
            if en.shape != (len(batch), 1024) or ko.shape != (len(batch), 1024):
                raise ExperimentError("invalid_text_embedding_shape")
            if not bool(torch.isfinite(en).all() and torch.isfinite(ko).all()):
                raise ExperimentError("non_finite_text_embedding")
            en_vectors.append(en.detach().cpu().to(dtype=torch.float32))
            ko_vectors.append(ko.detach().cpu().to(dtype=torch.float32))
        except Exception as exc:
            text_batch_failures.append({"audiocap_ids": [row["audiocap_id"] for row in batch], "reason": str(exc) or type(exc).__name__})
    text_seconds = time.perf_counter() - text_started
    memory_after_text = memory_snapshot()
    en_matrix = torch.cat(en_vectors, dim=0) if en_vectors else torch.empty((0, 1024))
    ko_matrix = torch.cat(ko_vectors, dim=0) if ko_vectors else torch.empty((0, 1024))

    audio_index = {name: index for index, name in enumerate(audio_ids)}
    rows_by_id = {row["audiocap_id"]: row for row in text_rows}
    successful_text_ids = [row["audiocap_id"] for start in range(0, len(text_rows), TEXT_BATCH_SIZE)
                           if not any(set(failure["audiocap_ids"]) == {item["audiocap_id"] for item in text_rows[start:start + TEXT_BATCH_SIZE]} for failure in text_batch_failures)
                           for row in text_rows[start:start + TEXT_BATCH_SIZE]]
    # Failed text batches are dropped symmetrically; preserve one shared 1:1 row list.
    successful_text_ids = [identity for identity in successful_text_ids
                           if rows_by_id[identity]["audio_file_name"] in audio_index]
    successful_row_set = set(successful_text_ids)
    embedded_text: dict[str, tuple[Any, Any]] = {}
    batch_cursor = 0
    for start in range(0, len(text_rows), TEXT_BATCH_SIZE):
        batch = text_rows[start:start + TEXT_BATCH_SIZE]
        failed = any(set(failure["audiocap_ids"]) == {item["audiocap_id"] for item in batch} for failure in text_batch_failures)
        if failed:
            continue
        en_batch = en_vectors[batch_cursor]
        ko_batch = ko_vectors[batch_cursor]
        batch_cursor += 1
        for index, row in enumerate(batch):
            if row["audiocap_id"] in successful_row_set:
                embedded_text[row["audiocap_id"]] = (en_batch[index:index + 1], ko_batch[index:index + 1])

    paired_results: list[dict[str, Any]] = []
    for row in text_rows:
        identity = row["audiocap_id"]
        audio_name = row["audio_file_name"]
        if identity not in embedded_text or audio_name not in audio_index:
            continue
        en_vector, ko_vector = embedded_text[identity]
        target_index = audio_index[audio_name]
        en_rank = _rank_query(en_vector, audio_matrix, audio_ids, audio_name)
        ko_rank = _rank_query(ko_vector, audio_matrix, audio_ids, audio_name)
        paired_results.append({
            "audiocap_id": identity,
            "audio_file_name": audio_name,
            "english_rank": en_rank["target_rank"],
            "korean_rank": ko_rank["target_rank"],
            "rank_difference_korean_minus_english": ko_rank["target_rank"] - en_rank["target_rank"],
            "english_target_raw_cosine": en_rank["target_raw_cosine"],
            "korean_target_raw_cosine": ko_rank["target_raw_cosine"],
            "english_reciprocal_rank": 1.0 / en_rank["target_rank"],
            "korean_reciprocal_rank": 1.0 / ko_rank["target_rank"],
        })

    en_metrics = retrieval_metrics(paired_results, "english_rank")
    ko_metrics = retrieval_metrics(paired_results, "korean_rank")
    paired_direction = Counter(
        "english_better" if row["rank_difference_korean_minus_english"] > 0
        else "korean_better" if row["rank_difference_korean_minus_english"] < 0
        else "tie"
        for row in paired_results
    )
    bootstrap = paired_bootstrap(paired_results)
    for metric in bootstrap["intervals"]:
        bootstrap["intervals"][metric]["observed_delta"] = ko_metrics[metric] - en_metrics[metric]

    records_path = output_dir / "paired-ranks.jsonl.gz"
    with gzip.open(records_path, "wt", encoding="utf-8", newline="\n") as stream:
        for row in paired_results:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    metrics = {
        "schema_version": "msclap-ko-en-retrieval-metrics-v1",
        "cohort_sha256": cohort_sha,
        "candidate_audio_count": len(audio_ids),
        "paired_query_count": len(paired_results),
        "english": en_metrics,
        "korean": ko_metrics,
        "paired_rank_direction_counts": dict(paired_direction),
        "paired_rank_difference": {
            "definition": "Korean target rank minus English target rank; positive favors English",
            "min": min(row["rank_difference_korean_minus_english"] for row in paired_results),
            "median": statistics.median(row["rank_difference_korean_minus_english"] for row in paired_results),
            "mean": statistics.mean(row["rank_difference_korean_minus_english"] for row in paired_results),
            "max": max(row["rank_difference_korean_minus_english"] for row in paired_results),
        },
        "paired_cluster_bootstrap": bootstrap,
    }
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_bytes(canonical_json_bytes(metrics))

    ordered = sorted(paired_results, key=lambda row: (row["rank_difference_korean_minus_english"], row["audiocap_id"]))
    examples_by_category = {
        "english_better": ordered[-5:][::-1],
        "korean_better": ordered[:5],
        "both_top10": [row for row in paired_results if row["english_rank"] <= 10 and row["korean_rank"] <= 10][:5],
        "both_outside_top10": [row for row in paired_results if row["english_rank"] > 10 and row["korean_rank"] > 10][:5],
    }
    example_ids = {row["audiocap_id"] for rows in examples_by_category.values() for row in rows}
    examples = {}
    for category, category_rows in examples_by_category.items():
        enriched = []
        for result in category_rows:
            source = rows_by_id[result["audiocap_id"]]
            en_vector, ko_vector = embedded_text[result["audiocap_id"]]
            en_rank = _rank_query(en_vector, audio_matrix, audio_ids, result["audio_file_name"], include_top10=True)
            ko_rank = _rank_query(ko_vector, audio_matrix, audio_ids, result["audio_file_name"], include_top10=True)
            enriched.append({**result, "english_caption": source["english_caption"], "korean_caption": source["korean_caption"],
                             "english_top10": en_rank["top10"], "korean_top10": ko_rank["top10"]})
        examples[category] = enriched
    examples_path = output_dir / "failure-cases.json"
    examples_path.write_bytes(canonical_json_bytes(examples))

    token_stats = {}
    for language, key in (("english", "english_token_count"), ("korean", "korean_token_count")):
        values = [int(row[key]) for row in cohort["paired_queries"]]
        token_stats[language] = {
            "min": min(values), "median": statistics.median(values), "mean": statistics.mean(values),
            "max": max(values), "over_77_count": sum(value > TOKEN_LIMIT for value in values),
        }
    token_stats["all_dataset_caption_rows"] = cohort["token_lengths"]["all_dataset_caption_rows"]
    evidence = {
        "schema_version": "msclap-ko-en-retrieval-run-evidence-v1",
        "status": "completed",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head": resolve_repository_head(),
        "cohort_path": str(cohort_path),
        "cohort_sha256": cohort_sha,
        "dataset": cohort["dataset"],
        "cohort_counts": cohort["counts"],
        "model": _model_evidence(generator),
        "runtime": {
            "python": platform.python_version(), "os": platform.platform(), "cpu": platform.processor(),
            "torch_threads": torch.get_num_threads(), "torch": _version("torch"), "torchaudio": _version("torchaudio"),
            "transformers": _version("transformers"), "tokenizers": _version("tokenizers"), "numpy": _version("numpy"),
            "device": "cpu", "torch_cuda_available": bool(torch.cuda.is_available()),
            "text_batch_size": TEXT_BATCH_SIZE,
            "audio_embedding_call": "ClapModel.encode_audio -> MSCLAP.get_audio_embeddings(resample=True)",
            "audio_crop_seed_version": AUDIO_SEED_VERSION,
            "evaluation_preprocessing": EVALUATION_PREPROCESSING,
            "audio_window_seconds": float(model.model.args.duration),
            "audio_source_sample_rate": EXPECTED_SAMPLE_RATE,
            "text_embedding_call": "TextEmbeddingGenerator pinned model.encode_text; raw unnormalized vectors",
            "text_tokenizer": "pinned MSCLAP GPT-2 tokenizer; EOS marker included; overflow rejected, no truncation",
            "normalization": "L2 at cosine calculation only; embedding artifacts remain raw",
            "similarity": "app.matching.audio_search.audio_cosine_similarities; raw cosine, no learned logit scale",
            "ranking_tie_break": "descending raw cosine then audio_file_name ascending",
            "model_load_seconds": model_load_seconds,
            "audio_embedding_seconds": audio_seconds,
            "text_embedding_seconds": text_seconds,
        },
        "memory_observations": {
            "before_model_load": memory_before,
            "after_model_load": memory_after_load,
            "after_audio_embeddings": memory_after_audio,
            "after_text_embeddings": memory_after_text,
            "after_retrieval": memory_snapshot(),
        },
        "token_lengths": token_stats,
        "results": {
            "metrics_path": metrics_path.name,
            "metrics_sha256": sha256_file(metrics_path),
            "paired_ranks_path": records_path.name,
            "paired_ranks_sha256": sha256_file(records_path),
            "failure_cases_path": examples_path.name,
            "failure_cases_sha256": sha256_file(examples_path),
            "audio_embedding_failures": audio_failures,
            "text_batch_failures": text_batch_failures,
            "post_freeze_token_overflows": token_overflows,
            "actual_candidate_audio_count": len(audio_ids),
            "actual_paired_query_count": len(paired_results),
        },
        "limitations": [
            "The Korean caption column is AYA-generated; English is the original AudioCaps caption. The paired result reflects language plus translation phrasing fidelity.",
            "AudioCaps contains five caption pairs per audio; confidence intervals cluster-bootstrap unique audio IDs.",
            "AudioCaps captions describe general sounds, not music recommendation requests.",
            "This CPU development-machine result is not a service-wide or production deployment evaluation.",
        ],
    }
    evidence_path = output_dir / "run-evidence.json"
    evidence_path.write_bytes(canonical_json_bytes(evidence))

    return evidence


def download_dataset(cache_dir: Path, metadata_path: Path) -> Path:
    from huggingface_hub import hf_hub_download, snapshot_download

    metadata = hf_hub_download(
        repo_id=DATASET_ID, repo_type="dataset", filename="test/metadata.csv",
        revision=DATASET_REVISION, local_dir=str(cache_dir),
    )
    audio_dir = Path(snapshot_download(
        repo_id=DATASET_ID, repo_type="dataset", revision=DATASET_REVISION,
        allow_patterns=["test/audio/*.wav"], local_dir=str(cache_dir), max_workers=4,
    )) / "test"
    target = metadata_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if Path(metadata).resolve() != target.resolve():
        target.write_bytes(Path(metadata).read_bytes())
    return audio_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download", help="download pinned metadata and audio files")
    download.add_argument("--cache-dir", type=Path, required=True)
    download.add_argument("--metadata-out", type=Path, required=True)
    prepare = commands.add_parser("prepare", help="inspect files and freeze paired cohort")
    prepare.add_argument("--metadata", type=Path, required=True)
    prepare.add_argument("--audio-root", type=Path, required=True)
    prepare.add_argument("--cohort-out", type=Path, required=True)
    run = commands.add_parser("run", help="generate embeddings and paired retrieval metrics")
    run.add_argument("--cohort", type=Path, required=True)
    run.add_argument("--audio-root", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "download":
        audio_dir = download_dataset(args.cache_dir, args.metadata_out)
        print(json.dumps({"metadata": str(args.metadata_out), "audio_root": str(audio_dir)}, ensure_ascii=False))
        return 0
    if args.command == "prepare":
        from app.embedding.text_embedding import TextEmbeddingGenerator

        generator = TextEmbeddingGenerator(expected_dimension=1024)
        cohort = build_cohort(args.metadata, args.audio_root, generator._model.model.tokenizer)
        content = canonical_json_bytes(cohort)
        args.cohort_out.parent.mkdir(parents=True, exist_ok=True)
        args.cohort_out.write_bytes(content)
        print(json.dumps({"cohort_path": str(args.cohort_out), "sha256": sha256_bytes(content), "counts": cohort["counts"]}, ensure_ascii=False))
        return 0
    evidence = run_embeddings(args.cohort, args.audio_root, args.output_dir)
    print(json.dumps({"status": evidence["status"], "output_dir": str(args.output_dir), "results": evidence["results"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
