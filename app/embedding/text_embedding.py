"""MSCLAP Text Embedding generation for validated CLAP query text."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MODEL_VERSION = "2023"
GENERATION_VERSION = "msclap2023-text-query-v2-gpt2-607a30d783df"
GENERATION_PROFILE = "ClapModel.encode_text/msclap-default-v1"
CALIBRATION_CHECKPOINT_SHA256 = "2cef4016d47d00eb28d153d522f397222057f95000e9bad6b9583c631284a1e6"
CALIBRATION_MSCLAP_PACKAGE_VERSION = "1.3.3"
CALIBRATION_MSCLAP_SOURCE_FILE_COUNT = 13
CALIBRATION_MSCLAP_SOURCE_SHA256 = "e867cdbb71f7bcee529afb92a096578faab46c69feb35d8192d4f220de56c181"
CALIBRATION_MSCLAP_CONFIG_SHA256 = "41fbc893997f75fe144d93bf2ec44d5ca27fe61beb8870dd815a53c064cb030f"
CALIBRATION_CHECKPOINT_REVISION = "c47d441165daa21986ead0850660917636a81775"
TEXT_ENCODER_MODEL_ID = "gpt2"
TEXT_ENCODER_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
TEXT_ENCODER_MODEL_FILE = "model.safetensors"
TEXT_ENCODER_MODEL_SHA256 = "248dfc3911869ec493c76e65bf2fcf7f615828b0254c12b473182f0f81d3a707"
TEXT_ENCODER_TOKENIZER_FILE_SHA256 = {
    "tokenizer.json": "8414cab924d8b9b33013f0d221c5862f365ee9be39c5c2bfae8a5a9e970478a6",
    "vocab.json": "196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783",
    "merges.txt": "1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5",
    "tokenizer_config.json": "5e04eb606e3a1583530a42e36c2a6b6615c86f34fe77e44d9ddeb43ff940931f",
    "config.json": "0daed7749b4f02b8f76240d5444551d7b08712dab4d0adb8239c56ba823bb7b4",
}


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


def _verify_msclap_implementation_identity(package_root: Path | None = None) -> dict[str, Any]:
    """Verify the exact calibration-recorded MSCLAP source/config set once at load."""
    try:
        package_version = importlib.metadata.version("msclap")
        if package_version != CALIBRATION_MSCLAP_PACKAGE_VERSION:
            raise TextEmbeddingError("installed MSCLAP package differs from the validated calibration version")
        if package_root is None:
            wrapper = importlib.import_module("msclap.CLAPWrapper")
            wrapper_path = getattr(wrapper, "__file__", None)
            if not isinstance(wrapper_path, str) or not wrapper_path:
                raise TextEmbeddingError("MSCLAP package source path is unavailable")
            package_root = Path(wrapper_path).resolve().parent
        else:
            package_root = Path(package_root).resolve()

        if not package_root.is_dir():
            raise TextEmbeddingError("MSCLAP package source directory is unavailable")
        source_files = sorted(
            path for path in package_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".py", ".yml", ".yaml"}
        )
        if len(source_files) != CALIBRATION_MSCLAP_SOURCE_FILE_COUNT:
            raise TextEmbeddingError("MSCLAP source/config file set differs from calibration")
        digest = hashlib.sha256()
        source_hashes = {}
        for path in source_files:
            relative = path.relative_to(package_root).as_posix()
            file_sha256 = _sha256_file(path)
            source_hashes[relative] = file_sha256
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(bytes.fromhex(file_sha256))
            digest.update(b"\n")
        config_relative = Path("configs") / f"config_{MODEL_VERSION}.yml"
        config_sha256 = source_hashes.get(config_relative.as_posix())
        if config_sha256 is None:
            raise TextEmbeddingError("calibration-pinned MSCLAP configuration is missing")
        if config_sha256 != CALIBRATION_MSCLAP_CONFIG_SHA256:
            raise TextEmbeddingError("MSCLAP configuration differs from the validated calibration identity")
        source_sha256 = digest.hexdigest()
        if source_sha256 != CALIBRATION_MSCLAP_SOURCE_SHA256:
            raise TextEmbeddingError("MSCLAP implementation source differs from the validated calibration identity")
        return {
            "package_version": package_version,
            "source_file_count": len(source_files),
            "source_sha256": source_sha256,
            "config_file": config_relative.as_posix(),
            "config_sha256": config_sha256,
        }
    except TextEmbeddingError:
        raise
    except Exception as exc:
        raise TextEmbeddingError("MSCLAP source/config identity could not be verified") from exc


def _huggingface_cache_paths() -> tuple[Path, Path]:
    """Return the cache roots used by the installed HF libraries without network access."""
    for name in (
        "HF_HOME", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE",
        "PYTORCH_TRANSFORMERS_CACHE", "PYTORCH_PRETRAINED_BERT_CACHE", "XDG_CACHE_HOME",
    ):
        value = os.environ.get(name)
        if value:
            os.environ[name] = os.path.expandvars(os.path.expanduser(value))

    try:
        transformers_override = os.environ.get("TRANSFORMERS_CACHE")
        transformers_hub = sys.modules.get("transformers.utils.hub")
        if transformers_override and transformers_hub is not None:
            transformers_hub.TRANSFORMERS_CACHE = transformers_override
        from huggingface_hub.constants import HF_HUB_CACHE
        from transformers.utils import hub as transformers_hub
        hub_cache = Path(HF_HUB_CACHE).expanduser()
        transformers_cache = Path(transformers_hub.TRANSFORMERS_CACHE).expanduser()
    except Exception as exc:
        raise TextEmbeddingError("Hugging Face cache locations are unavailable") from exc
    return hub_cache, transformers_cache


def _snapshot_path(cache_root: Path, repository_id: str) -> Path:
    return cache_root / f"models--{repository_id.replace('/', '--')}" / "snapshots" / TEXT_ENCODER_REVISION


def _verified_text_encoder_snapshot() -> tuple[Path, Path, dict[str, str]]:
    """Verify calibration-pinned GPT-2 files in local cache; never fetch resources."""
    hub_cache, transformers_cache = _huggingface_cache_paths()
    model_snapshot = _snapshot_path(transformers_cache, TEXT_ENCODER_MODEL_ID)
    try:
        if not model_snapshot.is_dir():
            raise TextEmbeddingError("pinned GPT-2 snapshot is unavailable in the local cache")
        file_hashes = dict(TEXT_ENCODER_TOKENIZER_FILE_SHA256)
        file_hashes[TEXT_ENCODER_MODEL_FILE] = TEXT_ENCODER_MODEL_SHA256
        for filename, expected_hash in file_hashes.items():
            path = model_snapshot / filename
            if not path.is_file() or _sha256_file(path) != expected_hash:
                raise TextEmbeddingError(f"pinned GPT-2 artifact is missing or mismatched: {filename}")

        checkpoint_snapshot = (
            hub_cache / "models--microsoft--msclap" / "snapshots" / CALIBRATION_CHECKPOINT_REVISION
        )
        checkpoint = checkpoint_snapshot / "CLAP_weights_2023.pth"
        if not checkpoint.is_file():
            raise TextEmbeddingError("calibration-pinned MSCLAP checkpoint is unavailable in the local cache")
        checkpoint_hash = _sha256_file(checkpoint)
        if checkpoint_hash != CALIBRATION_CHECKPOINT_SHA256:
            raise TextEmbeddingError("MSCLAP checkpoint differs from the validated calibration checkpoint")
    except TextEmbeddingError:
        raise
    except OSError as exc:
        raise TextEmbeddingError("could not verify pinned local model resources") from exc

    return model_snapshot, checkpoint.resolve(), {**file_hashes, "checkpoint_sha256": checkpoint_hash}


def _pinned_from_pretrained(loader: Any, repository_id: str, cache_dir: Path, *args: Any, **kwargs: Any):
    """Call an MSCLAP-owned HF loader with the calibration snapshot explicitly pinned."""
    if repository_id != TEXT_ENCODER_MODEL_ID:
        raise TextEmbeddingError("MSCLAP requested an unexpected text encoder resource")
    requested_revision = kwargs.pop("revision", TEXT_ENCODER_REVISION)
    if requested_revision != TEXT_ENCODER_REVISION:
        raise TextEmbeddingError("MSCLAP requested a different GPT-2 revision")
    kwargs.update(revision=TEXT_ENCODER_REVISION, cache_dir=str(cache_dir), local_files_only=True)
    try:
        return loader.from_pretrained(repository_id, *args, **kwargs)
    except TextEmbeddingError:
        raise
    except Exception as exc:
        raise TextEmbeddingError("pinned GPT-2 resources could not be loaded from local cache") from exc


class _PinnedHuggingFaceLoader:
    """Instance-scoped HF loader carrying one cache root and pinned revision."""

    def __init__(self, loader: Any, cache_dir: Path):
        self._loader = loader
        self._cache_dir = cache_dir

    def from_pretrained(self, repository_id: str, *args: Any, **kwargs: Any):
        return _pinned_from_pretrained(
            self._loader, repository_id, self._cache_dir, *args, **kwargs
        )


def _validate_loaded_text_resources(model: Any, expected_files: dict[str, str]) -> dict[str, Any]:
    inner = getattr(model, "model", None)
    args = getattr(inner, "args", None)
    if getattr(args, "text_model", None) != TEXT_ENCODER_MODEL_ID:
        raise TextEmbeddingError("MSCLAP text model identity does not match the pinned GPT-2 model")

    clap = getattr(inner, "clap", None)
    caption_encoder = getattr(clap, "caption_encoder", None)
    base = getattr(caption_encoder, "base", None)
    config = getattr(base, "config", None)
    tokenizer = getattr(inner, "tokenizer", None)
    if config is None or tokenizer is None:
        raise TextEmbeddingError("loaded GPT-2 model or tokenizer identity is unavailable")
    model_revision = getattr(config, "_commit_hash", None)
    model_id = getattr(config, "_name_or_path", None)
    tokenizer_id = getattr(tokenizer, "name_or_path", None)
    if model_revision != TEXT_ENCODER_REVISION:
        raise TextEmbeddingError("loaded GPT-2 model revision differs from calibration")
    if model_id != TEXT_ENCODER_MODEL_ID or tokenizer_id != TEXT_ENCODER_MODEL_ID:
        raise TextEmbeddingError("loaded GPT-2 model/tokenizer identity mismatch")
    backend = getattr(tokenizer, "backend_tokenizer", None)
    if backend is None:
        raise TextEmbeddingError("loaded GPT-2 tokenizer backend identity is unavailable")
    try:
        runtime_tokenizer_hash = hashlib.sha256(backend.to_str().encode("utf-8")).hexdigest()
    except Exception as exc:
        raise TextEmbeddingError("loaded GPT-2 tokenizer identity could not be verified") from exc
    identity = {
        "model_id": model_id,
        "revision": model_revision,
        "config_sha256": expected_files["config.json"],
        "model_file": TEXT_ENCODER_MODEL_FILE,
        "model_file_sha256": expected_files[TEXT_ENCODER_MODEL_FILE],
        "tokenizer_id": tokenizer_id,
        "tokenizer_revision": TEXT_ENCODER_REVISION,
        "tokenizer_runtime_sha256": runtime_tokenizer_hash,
        "tokenizer_files_sha256": {
            name: expected_files[name] for name in TEXT_ENCODER_TOKENIZER_FILE_SHA256
        },
    }
    inner.text_encoder_identity = identity
    return identity


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
        self._msclap_implementation_identity = _verify_msclap_implementation_identity()
        self._model = (
            model
            if model is not None
            else self._load_pinned_model(self._msclap_implementation_identity)
        )
        self.dimension = expected_dimension
        self._checkpoint_path, self._checkpoint_sha256 = self._initialize_checkpoint_identity(self._model)
        self._initialize_msclap_implementation_identity(self._model)
        self._text_encoder_identity = self._initialize_text_encoder_identity(self._model)

    @staticmethod
    def _initialize_checkpoint_identity(model: Any) -> tuple[Path, str]:
        inner = getattr(model, "model", None)
        checkpoint_value = getattr(inner, "model_fp", None)
        if not isinstance(checkpoint_value, (str, Path)) or not str(checkpoint_value).strip():
            raise TextEmbeddingError("MSCLAP checkpoint identity is unavailable")
        checkpoint = Path(checkpoint_value)
        if not checkpoint.is_file():
            raise TextEmbeddingError("MSCLAP checkpoint file is unavailable")
        checkpoint_sha256 = getattr(inner, "verified_checkpoint_sha256", None)
        if checkpoint_sha256 is None:
            checkpoint_sha256 = _sha256_file(checkpoint)
        if checkpoint_sha256 != CALIBRATION_CHECKPOINT_SHA256:
            raise TextEmbeddingError("MSCLAP checkpoint differs from the validated calibration checkpoint")
        return checkpoint.resolve(), checkpoint_sha256

    @staticmethod
    def _initialize_text_encoder_identity(model: Any) -> dict[str, Any]:
        inner = getattr(model, "model", None)
        identity = getattr(inner, "text_encoder_identity", None)
        if not isinstance(identity, dict):
            raise TextEmbeddingError("pinned GPT-2 text encoder identity is unavailable")
        if (
            identity.get("model_id") != TEXT_ENCODER_MODEL_ID
            or identity.get("revision") != TEXT_ENCODER_REVISION
            or identity.get("config_sha256") != TEXT_ENCODER_TOKENIZER_FILE_SHA256["config.json"]
            or identity.get("tokenizer_id") != TEXT_ENCODER_MODEL_ID
            or identity.get("tokenizer_revision") != TEXT_ENCODER_REVISION
            or identity.get("model_file_sha256") != TEXT_ENCODER_MODEL_SHA256
            or identity.get("tokenizer_files_sha256") != TEXT_ENCODER_TOKENIZER_FILE_SHA256
            or not isinstance(identity.get("tokenizer_runtime_sha256"), str)
            or len(identity["tokenizer_runtime_sha256"]) != 64
        ):
            raise TextEmbeddingError("loaded GPT-2 model/tokenizer identity differs from calibration")
        return identity.copy()

    @staticmethod
    def _initialize_msclap_implementation_identity(model: Any) -> dict[str, Any]:
        inner = getattr(model, "model", None)
        identity = getattr(inner, "msclap_implementation_identity", None)
        if (
            not isinstance(identity, dict)
            or identity.get("package_version") != CALIBRATION_MSCLAP_PACKAGE_VERSION
            or identity.get("source_file_count") != CALIBRATION_MSCLAP_SOURCE_FILE_COUNT
            or identity.get("source_sha256") != CALIBRATION_MSCLAP_SOURCE_SHA256
            or identity.get("config_file") != f"configs/config_{MODEL_VERSION}.yml"
            or identity.get("config_sha256") != CALIBRATION_MSCLAP_CONFIG_SHA256
        ):
            raise TextEmbeddingError("MSCLAP implementation identity is missing or differs from calibration")
        return identity.copy()

    @staticmethod
    def _load_pinned_model(implementation_identity: dict[str, Any]):
        model_snapshot, checkpoint_path, expected_files = _verified_text_encoder_snapshot()
        try:
            from transformers import AutoModel, AutoTokenizer
            from msclap import CLAP
            from app.inference.clap_model import ClapModel

            model_loader = _PinnedHuggingFaceLoader(AutoModel, model_snapshot.parents[2])
            tokenizer_loader = _PinnedHuggingFaceLoader(AutoTokenizer, model_snapshot.parents[2])

            class PinnedMSCLAP(CLAP):
                """Text-only MSCLAP initialization with instance-scoped HF loaders."""

                def __init__(self, *, model_fp, model_loader, tokenizer_loader):
                    self._text_model_loader = model_loader
                    self._tokenizer_loader = tokenizer_loader
                    super().__init__(model_fp=model_fp, version=MODEL_VERSION, use_cuda=False)

                def load_clap(self):
                    import math
                    import torch

                    core = importlib.import_module("msclap.models.clap")
                    args = self.read_config_as_args(self.config_as_str, is_config_str=True)
                    if "gpt" not in args.text_model:
                        raise TextEmbeddingError("MSCLAP config no longer selects the pinned GPT-2 encoder")
                    self.token_keys = ["input_ids", "attention_mask"]

                    clap = core.CLAP.__new__(core.CLAP)
                    torch.nn.Module.__init__(clap)
                    clap.audio_encoder = core.AudioEncoder(
                        args.audioenc_name,
                        args.out_emb,
                        args.d_proj,
                        args.sampling_rate,
                        args.window_size,
                        args.hop_size,
                        args.mel_bins,
                        args.fmin,
                        args.fmax,
                        args.num_classes,
                    )
                    base_model = self._text_model_loader.from_pretrained(args.text_model)
                    tokenizer = self._tokenizer_loader.from_pretrained(args.text_model)
                    tokenizer.add_special_tokens({"pad_token": "!"})

                    class PinnedTextEncoder(core.TextEncoder):
                        def __init__(self):
                            torch.nn.Module.__init__(self)
                            self.text_model = args.text_model
                            self.base = base_model
                            self.projection = core.Projection(
                                args.transformer_embed_dim, args.d_proj
                            )

                    clap.caption_encoder = PinnedTextEncoder()
                    clap.logit_scale = torch.nn.Parameter(torch.ones([]) * math.log(1 / 0.07))
                    state = torch.load(self.model_fp, map_location=torch.device("cpu"))["model"]
                    clap.load_state_dict(state, strict=False)
                    clap.eval()
                    if self.use_cuda and torch.cuda.is_available():
                        clap = clap.cuda()
                    return clap, tokenizer, args

            pinned_model = PinnedMSCLAP(
                model_fp=str(checkpoint_path),
                model_loader=model_loader,
                tokenizer_loader=tokenizer_loader,
            )
            pinned_model.verified_checkpoint_sha256 = expected_files["checkpoint_sha256"]
            pinned_model.msclap_implementation_identity = implementation_identity
            model = ClapModel.from_model_instance(pinned_model)
            _validate_loaded_text_resources(model, expected_files)
            return model
        except TextEmbeddingError:
            raise
        except Exception as exc:
            raise TextEmbeddingError("pinned MSCLAP text encoder could not be initialized offline") from exc

    def generate(self, query_text: str) -> TextEmbeddingResult:
        """Encode an already interpreted query using MSCLAP's official text path."""
        query_text = _validate_query_text(query_text)
        model = self._model
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

        package_versions = {}
        for package in ("msclap", "torch", "transformers", "tokenizers", "numpy"):
            try:
                package_versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError as exc:
                raise TextEmbeddingError(f"required package metadata is unavailable: {package}") from exc
        if package_versions["msclap"] != CALIBRATION_MSCLAP_PACKAGE_VERSION:
            raise TextEmbeddingError("installed MSCLAP package differs from the validated calibration version")

        self.dimension = configured_dimension
        implementation_identity = self._msclap_implementation_identity
        metadata = {
            "model": "MSCLAP",
            "model_version": MODEL_VERSION,
            "checkpoint_file": self._checkpoint_path.name,
            "checkpoint_revision": CALIBRATION_CHECKPOINT_REVISION,
            "checkpoint_sha256": self._checkpoint_sha256,
            "msclap_implementation": implementation_identity,
            "text_encoder": self._text_encoder_identity,
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
                "text_model_revision": TEXT_ENCODER_REVISION,
                "token_count_including_model_end_marker_and_specials": token_count,
                "token_limit": token_limit,
                "truncation": "rejected",
                "normalization": "none; raw MSCLAP Text Embedding",
            },
        }
        return TextEmbeddingResult(vector=vector, metadata=metadata)
