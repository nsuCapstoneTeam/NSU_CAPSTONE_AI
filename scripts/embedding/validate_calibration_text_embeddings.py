"""Generate and validate calibration v1 MSCLAP Text Embeddings."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

# Keep model/tokenizer downloads outside the repository and make their location explicit.
_MODEL_CACHE_ROOT = Path(tempfile.gettempdir()) / "nsuai-calibration-text-model-cache"
_MODEL_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(_MODEL_CACHE_ROOT))
os.environ.setdefault("HF_HUB_CACHE", str(_MODEL_CACHE_ROOT / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(_MODEL_CACHE_ROOT / "transformers"))
os.environ["HF_HUB_OFFLINE"] = "1"

from app.inference.clap_model import ClapModel

ACTIVE_COUNT = 16
APPROVED_STATUS = "approved_for_calibration_v1_experiment"
SEMANTIC_REVIEW_STATUS = "reviewed_for_semantic_fidelity"
MODEL_VERSION = "2023"
TOOL_PROFILE = "ClapModel.encode_text/msclap-default-v1"
CALIBRATION_ROOT = Path("docs/experiments/audio-similarity-calibration")
INPUT_PATH = CALIBRATION_ROOT / "event-queries.json"
DEFAULT_EVIDENCE_PATH = CALIBRATION_ROOT / "text-embedding-evidence.json"
DEFAULT_EMBEDDING_PATH = Path("tmp/calibration-v1-text-embeddings.npz")


class CalibrationTextEmbeddingError(ValueError):
    """Raised when calibration Text Embedding inputs or outputs are invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CalibrationTextEmbeddingError(message)


def require_non_blank_string(value: Any, field_name: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{field_name} is missing or blank")
    return value


def require_sha256(value: Any, field_name: str) -> str:
    digest = require_non_blank_string(value, field_name)
    require(re.fullmatch(r"[0-9a-fA-F]{64}", digest) is not None, f"{field_name} is not a SHA-256 digest")
    return digest.lower()


def require_full_git_sha(value: Any) -> str:
    commit = require_non_blank_string(value, "full Git commit SHA")
    require(re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", commit) is not None,
            "Git commit identity is not a full SHA")
    return commit.lower()


def require_positive_integer(value: Any, field_name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{field_name} is missing or not a positive integer")
    return value


def query_set_identity(document: dict[str, Any]) -> tuple[str, str]:
    query_set_version = require_non_blank_string(document.get("query_set_version"), "query_set_version")
    active_set_version = require_non_blank_string(document.get("active_set_version"), "active_set_version")
    return query_set_version, active_set_version


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tokenizer_snapshot_identity(text_model: str, cache_root: Path) -> dict[str, Any]:
    """Identify the exact cached Hugging Face snapshot and tokenizer bytes."""
    repo_cache = cache_root / f"models--{text_model.replace('/', '--')}"
    ref_path = repo_cache / "refs" / "main"
    require(ref_path.is_file(), f"Hugging Face tokenizer main revision is missing: {text_model}")
    revision = require_non_blank_string(ref_path.read_text(encoding="utf-8").strip(), "tokenizer snapshot revision")
    require(re.fullmatch(r"[0-9a-fA-F]{40,64}", revision) is not None,
            "tokenizer snapshot revision is not an immutable commit SHA")
    snapshot_path = repo_cache / "snapshots" / revision
    require(snapshot_path.is_dir(), f"tokenizer snapshot directory is missing for revision {revision}")

    tokenizer_names = (
        "tokenizer.json",
        "vocab.json",
        "merges.txt",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "config.json",
    )
    files = {
        name: sha256_file(snapshot_path / name)
        for name in tokenizer_names
        if (snapshot_path / name).is_file()
    }
    require("tokenizer.json" in files, "resolved tokenizer snapshot has no tokenizer.json")
    return {
        "repository_id": text_model,
        "resolved_revision": revision.lower(),
        "snapshot_files_sha256": files,
    }


def package_source_identity(package_root: Path) -> dict[str, Any]:
    """Hash installed MSCLAP Python/config sources, excluding model weights."""
    files = sorted(
        path for path in package_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".yml", ".yaml"}
    )
    require(bool(files), "installed MSCLAP source/config files are missing")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(package_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
        digest.update(b"\n")
    return {"file_count": len(files), "sha256": digest.hexdigest()}


def select_approved_queries(document: dict[str, Any]) -> list[dict[str, str]]:
    """Select only the 16 explicitly approved ACTIVE v1 model inputs."""
    rows = document.get("queries")
    require(isinstance(rows, list), "event-queries.json queries must be an array")
    active = [row for row in rows if row.get("selection_status") == "active_v1"]
    require(len(active) == ACTIVE_COUNT, f"expected exactly {ACTIVE_COUNT} active queries; found {len(active)}")

    selected = []
    for row in active:
        query_id = require_non_blank_string(row.get("query_id"), "query_id")
        model_input = row.get("msclap_model_input", {})
        require(
            row.get("structured_interpretation", {}).get("review_status") == "reviewed_for_raw_support",
            f"{query_id}: Structured Interpretation Raw-support review is incomplete",
        )
        require(
            model_input.get("human_review_status") == SEMANTIC_REVIEW_STATUS,
            f"{query_id}: semantic fidelity review is incomplete",
        )
        require(
            model_input.get("status") == APPROVED_STATUS,
            f"{query_id}: model input is not approved for calibration v1",
        )
        text = model_input.get("text")
        require(isinstance(text, str) and bool(text.strip()), f"{query_id}: English text is blank or not a string")
        draft_version = require_non_blank_string(model_input.get("draft_version"), f"{query_id}: draft_version")
        selected.append(
            {
                "query_id": query_id,
                "draft_version": draft_version,
                "text": text,
            }
        )

    inactive = [row for row in rows if row.get("selection_status") != "active_v1"]
    require(
        all(row.get("msclap_model_input", {}).get("status") != APPROVED_STATUS for row in inactive),
        "a RESERVE/REPLACE query is incorrectly approved for this experiment",
    )
    require(len({row["query_id"] for row in selected}) == ACTIVE_COUNT, "ACTIVE query_id values are not unique")
    return selected


def tokenizer_preflight(
    tokenizer: Any,
    queries: list[dict[str, str]],
    text_model: str,
    token_limit: int,
) -> list[dict[str, Any]]:
    """Mirror MSCLAP 1.3.3 preprocessing without truncating any input."""
    require(token_limit > 0, "MSCLAP text token limit must be positive")
    result = []
    for query in queries:
        text = query["text"]
        effective_text = text + " <|endoftext|>" if "gpt" in text_model else text
        encoded = tokenizer.encode_plus(
            text=effective_text,
            add_special_tokens=True,
            max_length=token_limit,
            padding="max_length",
            return_tensors="pt",
        )
        count = int(encoded["attention_mask"].reshape(-1).sum().item())
        padded_length = int(encoded["input_ids"].shape[-1])
        result.append(
            {
                "query_id": query["query_id"],
                "text": text,
                "token_count_including_model_end_marker_and_tokenizer_specials": count,
                "text_len_limit": token_limit,
                "effective_sequence_length_after_wrapper_padding": padded_length,
                "gpt_end_marker_appended_by_msclap": "<|endoftext|>" if "gpt" in text_model else None,
                "end_token_id": getattr(tokenizer, "eos_token_id", None),
                "tokenizer_special_tokens_added_count": int(tokenizer.num_special_tokens_to_add(pair=False)),
            }
        )

    over_limit = [
        row["query_id"]
        for row in result
        if row["token_count_including_model_end_marker_and_tokenizer_specials"] > token_limit
        or row["effective_sequence_length_after_wrapper_padding"] != token_limit
    ]
    require(not over_limit, f"token preflight failed without truncation; query IDs: {over_limit}")
    return result


def as_tensor(value: Any) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value.detach()
    return torch.as_tensor(value)


def validate_embedding_matrix(value: Any, expected_count: int, expected_dimension: int | None = None) -> torch.Tensor:
    tensor = as_tensor(value)
    require(tensor.ndim == 2, f"embedding output must be 2-D; got shape {tuple(tensor.shape)}")
    require(tensor.shape[0] == expected_count, f"expected {expected_count} vectors; got {tensor.shape[0]}")
    if expected_dimension is not None:
        require(tensor.shape[1] == expected_dimension, f"expected dimension {expected_dimension}; got {tensor.shape[1]}")
    require(bool(torch.isfinite(tensor).all()), "embedding output contains NaN or infinity")
    norms = torch.linalg.vector_norm(tensor.to(torch.float64), dim=1)
    require(bool(norms.gt(0).all()), "embedding output contains a zero vector")
    return tensor


def difference_report(first: Any, second: Any) -> dict[str, Any]:
    first_tensor, second_tensor = as_tensor(first), as_tensor(second)
    require(first_tensor.shape == second_tensor.shape, "embedding output shapes differ")
    validate_embedding_matrix(first_tensor, first_tensor.shape[0], first_tensor.shape[1])
    validate_embedding_matrix(second_tensor, second_tensor.shape[0], second_tensor.shape[1])
    delta = first_tensor.to(torch.float64) - second_tensor.to(torch.float64)
    return {
        "exact_equal": bool(torch.equal(first_tensor, second_tensor)),
        "max_absolute_difference": float(delta.abs().max().item()),
        "rms_difference": float(torch.sqrt(torch.mean(delta * delta)).item()),
        "allclose_default": bool(torch.allclose(first_tensor, second_tensor)),
        "allclose_default_rtol": 1e-5,
        "allclose_default_atol": 1e-8,
        "allclose_note": "diagnostic only; PyTorch defaults, not a project acceptance threshold",
    }


def require_exact_batch_repeat(repeated_batch: dict[str, Any]) -> None:
    """Require bitwise repeatability for the fixed-size canonical batch."""
    require(
        repeated_batch.get("exact_equal") is True,
        "repeated 16-query batch outputs are not bitwise identical; refusing canonical result",
    )


def experiment_result_status(
    repeated_batch: dict[str, Any], single_rows: list[dict[str, Any]]
) -> str:
    """Separate the hard batch-repeat gate from diagnostic batch/single differences."""
    require_exact_batch_repeat(repeated_batch)
    if any(not row["exact_equal"] for row in single_rows):
        return "PASS_WITH_BATCH_SINGLE_DIFFERENCE_RECORDED"
    return "PASS"


def write_canonical_artifact(
    path: Path,
    embeddings: np.ndarray,
    query_ids: list[str],
    repeated_batch: dict[str, Any],
) -> str:
    """Persist a verified artifact atomically and return its bytes SHA-256."""
    require_exact_batch_repeat(repeated_batch)
    require(embeddings.ndim == 2, "canonical artifact embeddings must be a 2-D matrix")
    require(embeddings.shape[0] == len(query_ids), "artifact row count does not match query_id count")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            np.savez_compressed(stream, embeddings=embeddings, query_ids=np.asarray(query_ids))

        with np.load(temporary_path, allow_pickle=False) as archive:
            stored_embeddings = archive["embeddings"]
            stored_query_ids = archive["query_ids"].tolist()
            require(stored_query_ids == query_ids, "artifact query_id order does not match selected query order")
            require(stored_embeddings.shape == embeddings.shape, "artifact embedding shape changed during serialization")
            require(stored_embeddings.dtype == embeddings.dtype, "artifact embedding dtype changed during serialization")
            require(np.array_equal(stored_embeddings, embeddings), "artifact embedding rows changed during serialization")

        temporary_hash = sha256_file(temporary_path)
        os.replace(temporary_path, path)
        temporary_path = None
        artifact_hash = sha256_file(path)
        require(artifact_hash == temporary_hash, "canonical artifact hash changed after finalization")
        return artifact_hash
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def validate_repeated_batch_outputs(
    first_raw: Any,
    repeated_raw: Any,
    expected_count: int,
    expected_dimension: int,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
    first = validate_embedding_matrix(first_raw, expected_count, expected_dimension)
    repeated = validate_embedding_matrix(repeated_raw, expected_count, expected_dimension)
    report = difference_report(first, repeated)
    require_exact_batch_repeat(report)
    return first, repeated, report


def _git_value(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8").strip()


def _run_calibration_validator(root: Path) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.matching.validate_calibration"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    require(completed.returncode == 0, f"integrated calibration validator failed: {completed.stderr.strip() or completed.stdout.strip()}")
    return completed.stdout.strip()


def run_experiment(
    root: Path,
    evidence_path: Path = DEFAULT_EVIDENCE_PATH,
    embedding_path: Path = DEFAULT_EMBEDDING_PATH,
) -> dict[str, Any]:
    root = root.resolve()
    input_path = root / INPUT_PATH
    input_bytes = input_path.read_bytes()
    input_hash = sha256_bytes(input_bytes)
    document = json.loads(input_bytes.decode("utf-8"))
    selected = select_approved_queries(document)
    query_set_version, active_set_version = query_set_identity(document)
    require_sha256(input_hash, "event-queries.json SHA-256")

    require(not _git_value(root, "status", "--porcelain", "--untracked-files=all"), "working tree is dirty; refusing Text Encoder run")
    commit = require_full_git_sha(_git_value(root, "rev-parse", "HEAD"))
    validator_output = _run_calibration_validator(root)
    validator_output = require_non_blank_string(validator_output, "calibration validator output")

    clap_model = ClapModel()
    wrapper = clap_model.model
    tokenizer = wrapper.tokenizer
    text_model = require_non_blank_string(getattr(wrapper.args, "text_model", None), "MSCLAP text model identity")
    token_limit = require_positive_integer(getattr(wrapper.args, "text_len", None), "MSCLAP token limit")
    token_rows = tokenizer_preflight(tokenizer, selected, text_model, token_limit)
    tokenizer_name = require_non_blank_string(
        getattr(tokenizer, "name_or_path", None), "tokenizer name_or_path"
    )
    require(tokenizer_name == text_model, "loaded tokenizer name does not match the configured MSCLAP text model")
    tokenizer_vocab_size = require_positive_integer(len(tokenizer), "tokenizer vocabulary size")
    transformers_cache = Path(require_non_blank_string(
        os.environ.get("TRANSFORMERS_CACHE"), "TRANSFORMERS_CACHE"
    ))
    tokenizer_snapshot = tokenizer_snapshot_identity(text_model, transformers_cache)
    model_config_hash = require_sha256(
        tokenizer_snapshot["snapshot_files_sha256"].get("config.json"),
        "Hugging Face model config SHA-256",
    )
    backend_tokenizer = getattr(tokenizer, "backend_tokenizer", None)
    backend_serializer = getattr(backend_tokenizer, "to_str", None)
    require(callable(backend_serializer), "runtime tokenizer backend serialization is unavailable")
    runtime_tokenizer_sha256 = sha256_bytes(backend_serializer().encode("utf-8"))
    pad_token = require_non_blank_string(getattr(tokenizer, "pad_token", None), "tokenizer padding token")
    pad_token_id = getattr(tokenizer, "pad_token_id", None)
    require(isinstance(pad_token_id, int) and pad_token_id >= 0, "tokenizer padding token ID is missing or invalid")
    require_non_blank_string(MODEL_VERSION, "MSCLAP model version")
    require_non_blank_string(TOOL_PROFILE, "embedding generation profile")
    clap_module = getattr(wrapper, "clap", None)
    require(clap_module is not None, "MSCLAP model mode is unavailable")
    training_mode = getattr(clap_module, "training", None)
    require(isinstance(training_mode, bool), "MSCLAP training/evaluation state is unavailable")
    model_eval_mode = not training_mode
    require(model_eval_mode, "MSCLAP model is in training mode; refusing canonical inference")

    checkpoint_value = require_non_blank_string(getattr(wrapper, "model_fp", None), "checkpoint path")
    checkpoint = Path(checkpoint_value)
    require(checkpoint.is_file(), f"MSCLAP checkpoint not found: {checkpoint.name}")
    checkpoint_file = require_non_blank_string(checkpoint.name, "checkpoint filename")
    checkpoint_hash_before = require_sha256(sha256_file(checkpoint), "checkpoint SHA-256")
    checkpoint_snapshot_revision = None
    checkpoint_parts = checkpoint.parts
    if "snapshots" in checkpoint_parts:
        revision_index = checkpoint_parts.index("snapshots") + 1
        if revision_index < len(checkpoint_parts):
            candidate_revision = checkpoint_parts[revision_index]
            require(re.fullmatch(r"[0-9a-fA-F]{40,64}", candidate_revision) is not None,
                    "checkpoint snapshot revision is malformed")
            checkpoint_snapshot_revision = candidate_revision.lower()
    package_versions = {
        package: require_non_blank_string(importlib.metadata.version(package), f"{package} package version")
        for package in ("msclap", "torch", "transformers", "numpy")
    }
    python_version = require_non_blank_string(platform.python_version(), "Python version")
    runner_path = Path(__file__).resolve()
    try:
        runner_relative_path = runner_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise CalibrationTextEmbeddingError("runner path is outside the repository root") from exc
    runner_relative_path = require_non_blank_string(runner_relative_path, "runner path")
    runner_hash = require_sha256(sha256_file(runner_path), "runner SHA-256")
    package_root = Path(require_non_blank_string(getattr(wrapper, "file_path", None), "MSCLAP package source path")).parent
    msclap_source_identity = package_source_identity(package_root)
    config_path = package_root / "configs" / f"config_{MODEL_VERSION}.yml"
    require(config_path.is_file(), "installed MSCLAP model configuration is missing")
    msclap_config_hash_before = require_sha256(sha256_file(config_path), "MSCLAP configuration SHA-256")
    eos_token_id = getattr(tokenizer, "eos_token_id", None)
    require(isinstance(eos_token_id, int) and eos_token_id >= 0, "tokenizer end-token identity is missing or invalid")

    texts = [row["text"] for row in selected]
    with torch.inference_mode():
        batch_first_raw = clap_model.encode_text(texts)
        batch_repeat_raw = clap_model.encode_text(texts)

    configured_dimension = require_positive_integer(
        getattr(wrapper.args, "d_proj", None), "configured embedding dimension"
    )
    batch_first, batch_repeat, repeated_batch = validate_repeated_batch_outputs(
        batch_first_raw, batch_repeat_raw, ACTIVE_COUNT, configured_dimension
    )

    single_rows = []
    for index, query in enumerate(selected):
        with torch.inference_mode():
            single_raw = clap_model.encode_text([query["text"]])
        single = validate_embedding_matrix(single_raw, 1, configured_dimension)
        single_rows.append({
            "query_id": query["query_id"],
            **difference_report(batch_first[index:index + 1], single),
        })

    checkpoint_hash = require_sha256(sha256_file(checkpoint), "checkpoint SHA-256 after inference")
    require(checkpoint_hash == checkpoint_hash_before, "MSCLAP checkpoint changed during inference")
    require(tokenizer_snapshot_identity(text_model, transformers_cache) == tokenizer_snapshot,
            "tokenizer snapshot changed during inference")
    require(sha256_bytes(backend_serializer().encode("utf-8")) == runtime_tokenizer_sha256,
            "runtime tokenizer state changed during inference")
    require(package_source_identity(package_root) == msclap_source_identity,
            "installed MSCLAP source/config changed during inference")
    require(sha256_file(config_path) == msclap_config_hash_before,
            "MSCLAP configuration changed during inference")
    require(sha256_file(runner_path) == runner_hash, "runner source changed during inference")
    embeddings = np.asarray(batch_first.cpu().numpy(), dtype="<f4", order="C")
    embedding_path = embedding_path if embedding_path.is_absolute() else root / embedding_path
    artifact_display_path = (
        embedding_path.relative_to(root).as_posix()
        if embedding_path.is_relative_to(root)
        else str(embedding_path)
    )
    artifact_display_path = require_non_blank_string(artifact_display_path, "artifact path")

    require(sha256_bytes(input_path.read_bytes()) == input_hash, "event-queries.json changed during inference")
    require(not _git_value(root, "status", "--porcelain", "--untracked-files=all"), "working tree changed during inference")

    norms = torch.linalg.vector_norm(batch_first.to(torch.float64), dim=1)
    vector_checks = [
        {
            "query_id": query["query_id"],
            "l2_norm": float(norms[index].item()),
            "finite": bool(torch.isfinite(batch_first[index]).all()),
            "zero_vector": bool(norms[index].item() == 0),
        }
        for index, query in enumerate(selected)
    ]
    require(all(row["finite"] and not row["zero_vector"] for row in vector_checks), "invalid text vector detected")

    result_status = experiment_result_status(repeated_batch, single_rows)
    artifact_hash = write_canonical_artifact(
        embedding_path,
        embeddings,
        [query["query_id"] for query in selected],
        repeated_batch,
    )

    result = {
        "schema_version": 1,
        "experiment": "NSUAI-36 calibration v1 Text Embedding",
        "result_status": result_status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_limitations": [
            "Text Embeddings only; Audio Embeddings were not generated",
            "No cosine calculation or ranking was performed",
            "No MSCLAP search-performance validation was performed",
            "Calibration input approval is not production query confirmation",
        ],
        "input_identity": {
            "git_commit_sha": commit,
            "working_tree_clean_before_and_after_inference": True,
            "query_set_version": query_set_version,
            "active_set_version": active_set_version,
            "event_queries_path": INPUT_PATH.as_posix(),
            "event_queries_bytes_sha256": input_hash,
            "active_query_count": len(selected),
            "queries": selected,
        },
        "preflight_validation": {
            "command": "python -m scripts.matching.validate_calibration",
            "status": "PASS",
            "output": validator_output,
        },
        "review_notes": [
            "The repeated fixed-size batch must be bitwise identical or the run fails before canonical artifact/evidence finalization.",
            "Batch-versus-single differences are diagnostic only; no project tolerance is established.",
            "If batch and single outputs differ, downstream cosine work must use the recorded fixed-batch artifact consistently.",
        ] if any(not row["exact_equal"] for row in single_rows) else [],
        "model_runtime": {
            "model": "MSCLAP",
            "model_version": MODEL_VERSION,
            "embedding_generation_profile": TOOL_PROFILE,
            "runner_path": runner_relative_path,
            "runner_sha256": runner_hash,
            "package_version": package_versions["msclap"],
            "checkpoint_file": checkpoint_file,
            "checkpoint_sha256": checkpoint_hash,
            "checkpoint_snapshot_revision": checkpoint_snapshot_revision,
            "msclap_package_source": msclap_source_identity,
            "msclap_config_sha256": msclap_config_hash_before,
            "text_model": text_model,
            "model_config_sha256": model_config_hash,
            "token_limit": token_limit,
            "projection_dimension_config": configured_dimension,
            "tokenizer_name_or_path": tokenizer_name,
            "tokenizer_snapshot": tokenizer_snapshot,
            "runtime_tokenizer_backend_sha256": runtime_tokenizer_sha256,
            "tokenizer_vocab_size": int(tokenizer_vocab_size),
            "eos_token_id": eos_token_id,
            "padding_token": pad_token,
            "padding_token_id": pad_token_id,
            "text_preprocessing": {
                "text_len": token_limit,
                "eos_marker_appended_by_msclap": " <|endoftext|>" if "gpt" in text_model else None,
                "add_special_tokens": True,
                "padding": "max_length",
                "truncation": "not enabled; over-limit inputs fail preflight",
            },
            "python_version": python_version,
            "torch_version": package_versions["torch"],
            "transformers_version": package_versions["transformers"],
            "numpy_version": package_versions["numpy"],
            "device": str(batch_first.device),
            "dtype": str(batch_first.dtype),
            "model_eval_mode": model_eval_mode,
            "torch_num_threads": torch.get_num_threads(),
        },
        "tokenizer_preflight": token_rows,
        "embedding_output": {
            "shape": list(batch_first.shape),
            "dimension": int(batch_first.shape[1]),
            "dtype": str(batch_first.dtype),
            "device": str(batch_first.device),
            "all_finite": bool(torch.isfinite(batch_first).all()),
            "zero_vector_count": sum(row["zero_vector"] for row in vector_checks),
            "l2_norms": vector_checks,
            "normalization_observation": "The raw get_text_embeddings output is unnormalized; no normalization was applied in this run.",
            "repeat_batch": repeated_batch,
            "batch_vs_single": single_rows,
            "reproducibility_status": (
                "repeated_batch_exact; batch_vs_single_difference_observed_no_acceptance_tolerance"
                if repeated_batch["exact_equal"] and any(not row["exact_equal"] for row in single_rows)
                else "repeated_batch_exact; no_batch_vs_single_difference_observed"
            ),
            "artifact": {
                "path": artifact_display_path,
                "sha256": artifact_hash,
                "format": "compressed NPZ: float32 little-endian embeddings and query_id order",
            },
        },
    }
    evidence_path = evidence_path if evidence_path.is_absolute() else root / evidence_path
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the approved calibration v1 MSCLAP Text Embeddings.")
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--embedding-output", type=Path, default=DEFAULT_EMBEDDING_PATH)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run_experiment(root, args.evidence_output, args.embedding_output)
    except Exception as exc:
        parser.exit(1, f"Calibration Text Embedding failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
