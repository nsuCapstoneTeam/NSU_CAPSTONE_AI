"""Generate and validate calibration v1 MSCLAP Text Embeddings."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
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

from app.inference.clap_model import ClapModel

ACTIVE_COUNT = 16
APPROVED_STATUS = "approved_for_calibration_v1_experiment"
SEMANTIC_REVIEW_STATUS = "reviewed_for_semantic_fidelity"
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_approved_queries(document: dict[str, Any]) -> list[dict[str, str]]:
    """Select only the 16 explicitly approved ACTIVE v1 model inputs."""
    rows = document.get("queries")
    require(isinstance(rows, list), "event-queries.json queries must be an array")
    active = [row for row in rows if row.get("selection_status") == "active_v1"]
    require(len(active) == ACTIVE_COUNT, f"expected exactly {ACTIVE_COUNT} active queries; found {len(active)}")

    selected = []
    for row in active:
        query_id = row.get("query_id", "<missing query_id>")
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
        selected.append(
            {
                "query_id": query_id,
                "draft_version": str(model_input.get("draft_version", "")),
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

    require(not _git_value(root, "status", "--porcelain", "--untracked-files=all"), "working tree is dirty; refusing Text Encoder run")
    commit = _git_value(root, "rev-parse", "HEAD")
    validator_output = _run_calibration_validator(root)

    clap_model = ClapModel()
    wrapper = clap_model.model
    tokenizer = wrapper.tokenizer
    text_model = str(wrapper.args.text_model)
    token_limit = int(wrapper.args.text_len)
    token_rows = tokenizer_preflight(tokenizer, selected, text_model, token_limit)

    texts = [row["text"] for row in selected]
    with torch.inference_mode():
        batch_first_raw = clap_model.encode_text(texts)
        batch_repeat_raw = clap_model.encode_text(texts)

    configured_dimension = int(getattr(wrapper.args, "d_proj", as_tensor(batch_first_raw).shape[1]))
    batch_first = validate_embedding_matrix(batch_first_raw, ACTIVE_COUNT, configured_dimension)
    batch_repeat = validate_embedding_matrix(batch_repeat_raw, ACTIVE_COUNT, configured_dimension)
    repeated_batch = difference_report(batch_first, batch_repeat)

    single_rows = []
    for index, query in enumerate(selected):
        with torch.inference_mode():
            single_raw = clap_model.encode_text([query["text"]])
        single = validate_embedding_matrix(single_raw, 1, configured_dimension)
        single_rows.append({
            "query_id": query["query_id"],
            **difference_report(batch_first[index:index + 1], single),
        })

    checkpoint = Path(wrapper.model_fp)
    require(checkpoint.is_file(), f"MSCLAP checkpoint not found: {checkpoint.name}")
    checkpoint_hash = sha256_file(checkpoint)
    embeddings = np.asarray(batch_first.cpu().numpy(), dtype="<f4", order="C")
    embedding_path = embedding_path if embedding_path.is_absolute() else root / embedding_path
    embedding_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(embedding_path, embeddings=embeddings, query_ids=np.asarray([q["query_id"] for q in selected]))

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

    result = {
        "schema_version": 1,
        "experiment": "NSUAI-36 calibration v1 Text Embedding",
        "result_status": (
            "PASS_WITH_BATCH_SINGLE_DIFFERENCE_RECORDED"
            if any(not row["exact_equal"] for row in single_rows)
            else "PASS"
        ),
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
            "query_set_version": document.get("query_set_version"),
            "active_set_version": document.get("active_set_version"),
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
            "The same-size batch repeat and batch-versus-single differences are diagnostics; no project tolerance is established.",
            "If batch and single outputs differ, downstream cosine work must use the recorded fixed-batch artifact consistently.",
        ] if any(not row["exact_equal"] for row in single_rows) else [],
        "model_runtime": {
            "model": "MSCLAP",
            "model_version": "2023",
            "embedding_generation_profile": TOOL_PROFILE,
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "package_version": importlib.metadata.version("msclap"),
            "checkpoint_file": checkpoint.name,
            "checkpoint_sha256": checkpoint_hash,
            "text_model": text_model,
            "token_limit": token_limit,
            "projection_dimension_config": configured_dimension,
            "tokenizer_name_or_path": str(getattr(tokenizer, "name_or_path", "unknown")),
            "tokenizer_vocab_size": int(len(tokenizer)),
            "eos_token_id": getattr(tokenizer, "eos_token_id", None),
            "python_version": platform.python_version(),
            "torch_version": importlib.metadata.version("torch"),
            "transformers_version": importlib.metadata.version("transformers"),
            "numpy_version": importlib.metadata.version("numpy"),
            "device": str(batch_first.device) if isinstance(batch_first_raw, torch.Tensor) else "cpu (non-Torch output)",
            "dtype": str(batch_first.dtype),
            "model_eval_mode": not bool(getattr(getattr(wrapper, "clap", None), "training", False)),
            "torch_num_threads": torch.get_num_threads(),
        },
        "tokenizer_preflight": token_rows,
        "embedding_output": {
            "shape": list(batch_first.shape),
            "dimension": int(batch_first.shape[1]),
            "dtype": str(batch_first.dtype),
            "device": str(batch_first.device) if isinstance(batch_first_raw, torch.Tensor) else "cpu (non-Torch output)",
            "all_finite": bool(torch.isfinite(batch_first).all()),
            "zero_vector_count": sum(row["zero_vector"] for row in vector_checks),
            "l2_norms": vector_checks,
            "normalization_observation": "The raw get_text_embeddings output is unnormalized; no normalization was applied in this run.",
            "repeat_batch": repeated_batch,
            "batch_vs_single": single_rows,
            "reproducibility_status": (
                "repeated_batch_exact; batch_vs_single_difference_observed_no_acceptance_tolerance"
                if repeated_batch["exact_equal"] and any(not row["exact_equal"] for row in single_rows)
                else "see repeated_batch and batch_vs_single measurements"
            ),
            "artifact": {
                "path": embedding_path.relative_to(root).as_posix() if embedding_path.is_relative_to(root) else str(embedding_path),
                "sha256": sha256_file(embedding_path),
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
