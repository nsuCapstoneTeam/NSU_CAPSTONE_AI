"""MSCLAP Text Embedding generation for validated CLAP query text."""

from __future__ import annotations

import hashlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MODEL_VERSION = "2023"
GENERATION_VERSION = "msclap2023-text-query-v1"
GENERATION_PROFILE = "ClapModel.encode_text/msclap-default-v1"
CALIBRATION_CHECKPOINT_SHA256 = "2cef4016d47d00eb28d153d522f397222057f95000e9bad6b9583c631284a1e6"
CALIBRATION_MSCLAP_PACKAGE_VERSION = "1.3.3"


class TextEmbeddingError(ValueError):
    """Raised when a query or MSCLAP Text Embedding is invalid."""


@dataclass(frozen=True)
class TextEmbeddingResult:
    """A single unnormalized Text Embedding and its generation identity."""

    vector: Any
    metadata: dict[str, Any]


def _positive_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 1:
        raise TextEmbeddingError(f"{name} must be a positive integer")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_query_text(query_text: Any) -> str:
    if not isinstance(query_text, str):
        raise TextEmbeddingError("query_text must be a string")
    if not query_text.strip():
        raise TextEmbeddingError("query_text must not be empty or whitespace-only")
    return query_text


def _token_count_without_truncation(query_text: str, model: Any) -> tuple[int, int, str]:
    """Mirror MSCLAP 1.3.3 preprocessing and reject inputs the wrapper would truncate."""
    inner = getattr(model, "model", None)
    args = getattr(inner, "args", None)
    tokenizer = getattr(inner, "tokenizer", None)
    text_model = getattr(args, "text_model", None)
    token_limit = _positive_int(getattr(args, "text_len", None), "MSCLAP text_len")
    if not isinstance(text_model, str) or not text_model.strip():
        raise TextEmbeddingError("MSCLAP text model identity is unavailable")
    if tokenizer is None or not callable(getattr(tokenizer, "encode_plus", None)):
        raise TextEmbeddingError("MSCLAP tokenizer is unavailable")

    effective_text = query_text + " <|endoftext|>" if "gpt" in text_model else query_text
    try:
        encoded = tokenizer.encode_plus(
            text=effective_text,
            add_special_tokens=True,
            max_length=token_limit,
            padding="max_length",
            return_tensors="pt",
        )
        token_count = int(encoded["attention_mask"].reshape(-1).sum().item())
        padded_length = int(encoded["input_ids"].shape[-1])
    except Exception as exc:
        raise TextEmbeddingError("MSCLAP tokenizer preprocessing failed") from exc
    if token_count > token_limit or padded_length != token_limit:
        raise TextEmbeddingError("query_text exceeds the MSCLAP token limit; truncation is not allowed")
    return token_count, token_limit, text_model


def validate_text_embedding(
    value: Any,
    *,
    expected_count: int = 1,
    expected_dimension: int | None = None,
):
    """Validate a [batch, dimension] floating vector result without normalizing it."""
    import torch

    try:
        tensor = value.detach() if isinstance(value, torch.Tensor) else torch.as_tensor(value)
    except Exception as exc:
        raise TextEmbeddingError("MSCLAP returned a non-numeric embedding") from exc
    if tensor.ndim != 2 or tensor.shape[0] != expected_count or tensor.shape[1] < 1:
        raise TextEmbeddingError(f"invalid Text Embedding shape: {tuple(tensor.shape)}")
    if not tensor.is_floating_point():
        raise TextEmbeddingError("Text Embedding must use a floating-point dtype")
    if not bool(torch.isfinite(tensor).all()):
        raise TextEmbeddingError("Text Embedding contains NaN or infinity")
    norms = torch.linalg.vector_norm(tensor.to(dtype=torch.float64), dim=1)
    if not bool(torch.isfinite(norms).all()) or not bool(norms.gt(0).all()):
        raise TextEmbeddingError("Text Embedding contains a zero or invalid vector")
    if expected_dimension is not None and tensor.shape[1] != expected_dimension:
        raise TextEmbeddingError(
            f"Text Embedding dimension mismatch: expected {expected_dimension}, got {tensor.shape[1]}"
        )
    return tensor


class TextEmbeddingGenerator:
    """Generate one MSCLAP 2023 Text Embedding from validated CLAP query text."""

    def __init__(self, model: Any | None = None, *, expected_dimension: int | None = None):
        if expected_dimension is not None:
            _positive_int(expected_dimension, "expected_dimension")
        self._model = model
        self.dimension = expected_dimension

    def _load_model(self):
        if self._model is None:
            from app.inference.clap_model import ClapModel

            self._model = ClapModel()
        return self._model

    def generate(self, query_text: str) -> TextEmbeddingResult:
        """Encode an already interpreted query using MSCLAP's official text path."""
        query_text = _validate_query_text(query_text)
        model = self._load_model()
        inner = getattr(model, "model", None)
        args = getattr(inner, "args", None)
        configured_dimension = _positive_int(getattr(args, "d_proj", None), "MSCLAP d_proj")
        if self.dimension is not None and configured_dimension != self.dimension:
            raise TextEmbeddingError(
                f"configured MSCLAP dimension mismatch: expected {self.dimension}, got {configured_dimension}"
            )

        token_count, token_limit, text_model = _token_count_without_truncation(query_text, model)
        clap_module = getattr(inner, "clap", None)
        training = getattr(clap_module, "training", None)
        if not isinstance(training, bool) or training:
            raise TextEmbeddingError("MSCLAP must be initialized in evaluation mode")

        try:
            import torch

            with torch.inference_mode():
                raw = model.encode_text([query_text])
            vector = validate_text_embedding(raw, expected_count=1, expected_dimension=configured_dimension)
        except TextEmbeddingError:
            raise
        except Exception as exc:
            raise TextEmbeddingError("MSCLAP Text Embedding generation failed") from exc

        checkpoint_value = getattr(inner, "model_fp", None)
        if not isinstance(checkpoint_value, (str, Path)) or not str(checkpoint_value).strip():
            raise TextEmbeddingError("MSCLAP checkpoint identity is unavailable")
        checkpoint = Path(checkpoint_value)
        if not checkpoint.is_file():
            raise TextEmbeddingError("MSCLAP checkpoint file is unavailable")
        checkpoint_sha256 = _sha256_file(checkpoint)
        if checkpoint_sha256 != CALIBRATION_CHECKPOINT_SHA256:
            raise TextEmbeddingError("MSCLAP checkpoint differs from the validated calibration checkpoint")

        package_versions = {}
        for package in ("msclap", "torch", "transformers", "numpy"):
            try:
                package_versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError as exc:
                raise TextEmbeddingError(f"required package metadata is unavailable: {package}") from exc
        if package_versions["msclap"] != CALIBRATION_MSCLAP_PACKAGE_VERSION:
            raise TextEmbeddingError("installed MSCLAP package differs from the validated calibration version")

        checkpoint_parts = checkpoint.parts
        revision = None
        if "snapshots" in checkpoint_parts:
            index = checkpoint_parts.index("snapshots") + 1
            if index < len(checkpoint_parts):
                revision = checkpoint_parts[index]
        self.dimension = configured_dimension
        metadata = {
            "model": "MSCLAP",
            "model_version": MODEL_VERSION,
            "checkpoint_file": checkpoint.name,
            "checkpoint_revision": revision,
            "checkpoint_sha256": checkpoint_sha256,
            "packages": package_versions,
            "device": str(vector.device),
            "shape": list(vector.shape),
            "dimension": configured_dimension,
            "dtype": str(vector.dtype),
            "generation_version": GENERATION_VERSION,
            "embedding_generation_profile": GENERATION_PROFILE,
            "query_text_sha256": hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
            "text_preprocessing": {
                "encoder_api": "CLAP.get_text_embeddings",
                "text_model": text_model,
                "token_count_including_model_end_marker_and_specials": token_count,
                "token_limit": token_limit,
                "truncation": "rejected",
                "normalization": "none; raw MSCLAP Text Embedding",
            },
        }
        return TextEmbeddingResult(vector=vector, metadata=metadata)
