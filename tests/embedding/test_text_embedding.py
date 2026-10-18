from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import importlib.metadata
from pathlib import Path
import inspect
from types import SimpleNamespace

import pytest
import torch

from app.embedding import text_embedding
from app.embedding.text_embedding import TextEmbeddingError, TextEmbeddingGenerator


class FakeTokenizer:
    name_or_path = "gpt2"

    def encode_plus(self, *, text, max_length, **kwargs):
        count = max_length + 1 if "overflow" in text else 4
        return {
            "attention_mask": torch.tensor([[1] * count]),
            "input_ids": torch.zeros((1, max_length), dtype=torch.long),
        }


class FakeModel:
    def __init__(self, checkpoint, output=None, *, dimension=3, training=False):
        self.model = SimpleNamespace(
            args=SimpleNamespace(text_model="gpt2", text_len=77, d_proj=dimension),
            tokenizer=FakeTokenizer(),
            clap=SimpleNamespace(training=training),
            model_fp=str(checkpoint),
            text_encoder_identity={
                "model_id": text_embedding.TEXT_ENCODER_MODEL_ID,
                "revision": text_embedding.TEXT_ENCODER_REVISION,
                "config_sha256": text_embedding.TEXT_ENCODER_TOKENIZER_FILE_SHA256["config.json"],
                "model_file": text_embedding.TEXT_ENCODER_MODEL_FILE,
                "model_file_sha256": text_embedding.TEXT_ENCODER_MODEL_SHA256,
                "tokenizer_id": text_embedding.TEXT_ENCODER_MODEL_ID,
                "tokenizer_revision": text_embedding.TEXT_ENCODER_REVISION,
                "tokenizer_runtime_sha256": "9d827e1d30539b6604dd86bd5b9a242400ae5f4c307c3c97c296205ae9508aa8",
                "tokenizer_files_sha256": text_embedding.TEXT_ENCODER_TOKENIZER_FILE_SHA256.copy(),
            },
            msclap_implementation_identity={
                "package_version": text_embedding.CALIBRATION_MSCLAP_PACKAGE_VERSION,
                "source_file_count": text_embedding.CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
                "source_sha256": text_embedding.CALIBRATION_MSCLAP_SOURCE_SHA256,
                "config_file": "configs/config_2023.yml",
                "config_sha256": text_embedding.CALIBRATION_MSCLAP_CONFIG_SHA256,
            },
        )
        self.output = torch.tensor([[1.0, 2.0, 3.0]]) if output is None else output
        self.inputs = []

    def encode_text(self, texts):
        self.inputs.append(texts)
        return self.output


@pytest.fixture
def configured_model(tmp_path, monkeypatch):
    checkpoint = tmp_path / "CLAP_weights_2023.pth"
    checkpoint.write_bytes(b"validated checkpoint fixture")
    monkeypatch.setattr(
        text_embedding,
        "CALIBRATION_CHECKPOINT_SHA256",
        text_embedding._sha256_file(checkpoint),
    )
    monkeypatch.setattr(text_embedding.importlib.metadata, "version", lambda package: {
        "msclap": "1.3.3",
        "torch": "test-torch",
        "transformers": "test-transformers",
        "tokenizers": "test-tokenizers",
        "numpy": "test-numpy",
    }[package])
    monkeypatch.setattr(
        text_embedding,
        "_verify_msclap_implementation_identity",
        lambda: configured_msclap_identity(),
    )
    return FakeModel(checkpoint)


def configured_msclap_identity():
    return {
        "package_version": text_embedding.CALIBRATION_MSCLAP_PACKAGE_VERSION,
        "source_file_count": text_embedding.CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        "source_sha256": text_embedding.CALIBRATION_MSCLAP_SOURCE_SHA256,
        "config_file": "configs/config_2023.yml",
        "config_sha256": text_embedding.CALIBRATION_MSCLAP_CONFIG_SHA256,
    }


def test_generates_one_valid_raw_embedding_with_calibration_metadata(configured_model):
    result = TextEmbeddingGenerator(configured_model).generate("A calm outdoor family event")

    assert result.vector.shape == (1, 3)
    assert result.vector.dtype == torch.float32
    assert torch.isfinite(result.vector).all()
    assert result.vector.norm().item() == pytest.approx(torch.tensor([1.0, 2.0, 3.0]).norm().item())
    assert configured_model.inputs == [["A calm outdoor family event"]]
    metadata = result.metadata
    assert metadata["model"] == "MSCLAP"
    assert metadata["model_version"] == "2023"
    assert metadata["checkpoint_sha256"] == text_embedding.CALIBRATION_CHECKPOINT_SHA256
    assert metadata["msclap_implementation"]["source_sha256"] == text_embedding.CALIBRATION_MSCLAP_SOURCE_SHA256
    assert metadata["msclap_implementation"]["config_sha256"] == text_embedding.CALIBRATION_MSCLAP_CONFIG_SHA256
    assert metadata["packages"]["msclap"] == "1.3.3"
    assert metadata["dimension"] == 3
    assert metadata["generation_version"] == text_embedding.GENERATION_VERSION
    assert metadata["embedding_generation_profile"] == "ClapModel.encode_text/msclap-default-v1"
    assert metadata["text_encoder"]["revision"] == text_embedding.TEXT_ENCODER_REVISION
    assert metadata["text_encoder"]["tokenizer_revision"] == text_embedding.TEXT_ENCODER_REVISION
    assert metadata["text_encoder"]["model_file_sha256"] == text_embedding.TEXT_ENCODER_MODEL_SHA256
    assert metadata["packages"]["tokenizers"] == "test-tokenizers"
    assert metadata["text_preprocessing"]["normalization"] == "none; raw MSCLAP Text Embedding"
    assert metadata["text_preprocessing"]["token_count_including_model_end_marker_and_specials"] == 4
    assert "query_text" not in metadata


@pytest.mark.parametrize("query_text", [None, 7, [], {}])
def test_rejects_invalid_query_type(configured_model, query_text):
    with pytest.raises(TextEmbeddingError, match="query_text must be a string"):
        TextEmbeddingGenerator(configured_model).generate(query_text)


@pytest.mark.parametrize("query_text", ["", " \t\n"])
def test_rejects_empty_or_whitespace_query(configured_model, query_text):
    with pytest.raises(TextEmbeddingError, match="empty or whitespace-only"):
        TextEmbeddingGenerator(configured_model).generate(query_text)


@pytest.mark.parametrize(
    ("output", "dimension", "error"),
    [
        (torch.ones(3), 3, "invalid Text Embedding shape"),
        (torch.ones(2, 3), 3, "invalid Text Embedding shape"),
        (torch.ones(1, 4), 3, "dimension mismatch"),
        (torch.tensor([[1.0, float("nan"), 0.0]]), 3, "NaN or infinity"),
        (torch.tensor([[1.0, float("inf"), 0.0]]), 3, "NaN or infinity"),
        (torch.zeros(1, 3), 3, "zero or invalid vector"),
        (torch.ones(1, 3, dtype=torch.int64), 3, "floating-point dtype"),
    ],
)
def test_rejects_invalid_model_output(configured_model, output, dimension, error):
    configured_model.output = output
    with pytest.raises(TextEmbeddingError, match=error):
        TextEmbeddingGenerator(configured_model, expected_dimension=dimension).generate("a valid query")


def test_rejects_query_that_would_exceed_msclap_limit(configured_model):
    with pytest.raises(TextEmbeddingError, match="token limit"):
        TextEmbeddingGenerator(configured_model).generate("overflow")
    assert configured_model.inputs == []


def test_rejects_training_mode_and_dimension_configuration_mismatch(configured_model):
    configured_model.model.clap.training = True
    with pytest.raises(TextEmbeddingError, match="evaluation mode"):
        TextEmbeddingGenerator(configured_model).generate("a valid query")

    configured_model.model.clap.training = False
    with pytest.raises(TextEmbeddingError, match="configured MSCLAP dimension mismatch"):
        TextEmbeddingGenerator(configured_model, expected_dimension=4).generate("a valid query")


def test_rejects_checkpoint_or_msclap_package_that_differs_from_calibration(configured_model, monkeypatch):
    monkeypatch.setattr(text_embedding, "CALIBRATION_CHECKPOINT_SHA256", "0" * 64)
    with pytest.raises(TextEmbeddingError, match="checkpoint differs"):
        TextEmbeddingGenerator(configured_model)


def test_rejects_msclap_package_that_differs_from_calibration(configured_model, monkeypatch):
    monkeypatch.setattr(
        text_embedding.importlib.metadata,
        "version",
        lambda package: "different" if package == "msclap" else "test",
    )
    with pytest.raises(TextEmbeddingError, match="package differs"):
        TextEmbeddingGenerator(configured_model).generate("a valid query")


def test_checkpoint_hash_is_computed_once_at_generator_initialization(configured_model, monkeypatch):
    original_hash = text_embedding._sha256_file
    calls = []

    def counted_hash(path):
        calls.append(Path(path))
        return original_hash(path)

    monkeypatch.setattr(text_embedding, "_sha256_file", counted_hash)
    generator = TextEmbeddingGenerator(configured_model)
    assert len(calls) == 1

    first = generator.generate("first valid query")
    second = generator.generate("second valid query")
    assert len(calls) == 1
    assert first.metadata["checkpoint_sha256"] == second.metadata["checkpoint_sha256"]
    assert first.metadata["checkpoint_sha256"] == generator._checkpoint_sha256


def test_msclap_source_identity_is_verified_once_at_initialization(configured_model, monkeypatch):
    calls = []
    monkeypatch.setattr(
        text_embedding,
        "_verify_msclap_implementation_identity",
        lambda: calls.append("verified") or configured_msclap_identity(),
    )
    generator = TextEmbeddingGenerator(configured_model)
    generator.generate("first valid query")
    generator.generate("second valid query")
    assert calls == ["verified"]


@pytest.mark.parametrize("field,value", [
    ("revision", "0" * 40),
    ("tokenizer_revision", "0" * 40),
    ("tokenizer_id", "other-model"),
    ("tokenizer_files_sha256", {"config.json": "0" * 64}),
])
def test_rejects_unpinned_or_mismatched_text_resources(configured_model, field, value):
    configured_model.model.text_encoder_identity[field] = value
    with pytest.raises(TextEmbeddingError, match="identity differs"):
        TextEmbeddingGenerator(configured_model)


def test_rejects_missing_text_resource_identity(configured_model):
    del configured_model.model.text_encoder_identity
    with pytest.raises(TextEmbeddingError, match="identity is unavailable"):
        TextEmbeddingGenerator(configured_model)


def test_pinned_huggingface_loader_forces_revision_and_local_only(tmp_path):
    class Loader:
        called = None

        @classmethod
        def from_pretrained(cls, repository_id, **kwargs):
            cls.called = (repository_id, kwargs)
            return "loaded"

    assert text_embedding._pinned_from_pretrained(Loader, "gpt2", tmp_path) == "loaded"
    repository_id, kwargs = Loader.called
    assert repository_id == "gpt2"
    assert kwargs["revision"] == text_embedding.TEXT_ENCODER_REVISION
    assert kwargs["local_files_only"] is True
    assert kwargs["cache_dir"] == str(tmp_path)


def test_pinned_huggingface_loader_rejects_different_revision(tmp_path):
    class Loader:
        @classmethod
        def from_pretrained(cls, repository_id, **kwargs):
            raise AssertionError("loader should not run")

    with pytest.raises(TextEmbeddingError, match="different GPT-2 revision"):
        text_embedding._pinned_from_pretrained(
            Loader, "gpt2", tmp_path, revision="0" * 40
        )


def test_clap_model_keeps_public_constructor_and_supports_model_instance_injection():
    from app.inference.clap_model import ClapModel

    assert list(inspect.signature(ClapModel.__init__).parameters) == ["self"]
    sentinel = object()
    assert ClapModel.from_model_instance(sentinel).model is sentinel


def test_instance_scoped_loaders_do_not_share_state_between_threads(tmp_path):
    class Loader:
        def __init__(self, identity):
            self.identity = identity
            self.calls = []

        def from_pretrained(self, repository_id, **kwargs):
            self.calls.append((repository_id, kwargs))
            return self.identity

    first_loader = Loader("first")
    second_loader = Loader("second")
    first = text_embedding._PinnedHuggingFaceLoader(first_loader, tmp_path / "first")
    second = text_embedding._PinnedHuggingFaceLoader(second_loader, tmp_path / "second")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda loader: loader.from_pretrained("gpt2"), [first, second]))

    assert results == ["first", "second"]
    assert first_loader.calls[0][1]["cache_dir"] == str(tmp_path / "first")
    assert second_loader.calls[0][1]["cache_dir"] == str(tmp_path / "second")
    assert all(call[1]["revision"] == text_embedding.TEXT_ENCODER_REVISION for call in (
        first_loader.calls[0], second_loader.calls[0]
    ))


def test_production_text_loader_does_not_patch_global_huggingface_classes():
    source = Path(text_embedding.__file__).read_text(encoding="utf-8")
    assert "patch.object" not in source
    assert "unittest.mock" not in source


def _source_identity_for_test(package_root):
    files = sorted(
        path for path in package_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".yml", ".yaml"}
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(hashlib.sha256(path.read_bytes()).hexdigest()))
        digest.update(b"\n")
    return files, digest.hexdigest()


def test_installed_msclap_source_identity_matches_calibration(monkeypatch):
    wrapper = importlib.import_module("msclap.CLAPWrapper")
    calls = []
    original_hash = text_embedding._sha256_file

    def counted_hash(path):
        calls.append(path)
        return original_hash(path)

    monkeypatch.setattr(text_embedding, "_sha256_file", counted_hash)
    identity = text_embedding._verify_msclap_implementation_identity(
        Path(wrapper.__file__).resolve().parent
    )
    assert identity["package_version"] == "1.3.3"
    assert identity["source_file_count"] == 13
    assert identity["source_sha256"] == "e867cdbb71f7bcee529afb92a096578faab46c69feb35d8192d4f220de56c181"
    assert identity["config_sha256"] == "41fbc893997f75fe144d93bf2ec44d5ca27fe61beb8870dd815a53c064cb030f"
    assert len(calls) == 13


def test_rejects_modified_msclap_source_even_when_package_version_matches(tmp_path, monkeypatch):
    root = tmp_path / "msclap"
    (root / "configs").mkdir(parents=True)
    (root / "configs" / "config_2023.yml").write_text("validated-config", encoding="utf-8")
    for index in range(12):
        (root / f"module{index}.py").write_text(f"source-{index}", encoding="utf-8")
    files, source_sha = _source_identity_for_test(root)
    config_sha = hashlib.sha256((root / "configs" / "config_2023.yml").read_bytes()).hexdigest()
    monkeypatch.setattr(text_embedding.importlib.metadata, "version", lambda _: "1.3.3")
    monkeypatch.setattr(text_embedding, "CALIBRATION_MSCLAP_SOURCE_FILE_COUNT", len(files))
    monkeypatch.setattr(text_embedding, "CALIBRATION_MSCLAP_SOURCE_SHA256", source_sha)
    monkeypatch.setattr(text_embedding, "CALIBRATION_MSCLAP_CONFIG_SHA256", config_sha)
    text_embedding._verify_msclap_implementation_identity(root)

    (root / "module0.py").write_text("modified-source", encoding="utf-8")
    with pytest.raises(TextEmbeddingError, match="implementation source differs"):
        text_embedding._verify_msclap_implementation_identity(root)


def test_rejects_missing_calibration_msclap_config_file(tmp_path, monkeypatch):
    root = tmp_path / "msclap"
    root.mkdir()
    for index in range(13):
        (root / f"module{index}.py").write_text(f"source-{index}", encoding="utf-8")
    files, source_sha = _source_identity_for_test(root)
    monkeypatch.setattr(text_embedding.importlib.metadata, "version", lambda _: "1.3.3")
    monkeypatch.setattr(text_embedding, "CALIBRATION_MSCLAP_SOURCE_FILE_COUNT", len(files))
    monkeypatch.setattr(text_embedding, "CALIBRATION_MSCLAP_SOURCE_SHA256", source_sha)
    with pytest.raises(TextEmbeddingError, match="configuration is missing"):
        text_embedding._verify_msclap_implementation_identity(root)


def test_rejects_missing_msclap_source_file(tmp_path, monkeypatch):
    root = tmp_path / "msclap"
    (root / "configs").mkdir(parents=True)
    (root / "configs" / "config_2023.yml").write_text("config", encoding="utf-8")
    for index in range(11):
        (root / f"module{index}.py").write_text(f"source-{index}", encoding="utf-8")
    monkeypatch.setattr(text_embedding.importlib.metadata, "version", lambda _: "1.3.3")
    with pytest.raises(TextEmbeddingError, match="source/config file set differs"):
        text_embedding._verify_msclap_implementation_identity(root)


def test_default_constructor_rejects_msclap_version_mismatch(monkeypatch):
    monkeypatch.setattr(text_embedding.importlib.metadata, "version", lambda _: "1.2.0")
    with pytest.raises(TextEmbeddingError, match="package differs"):
        TextEmbeddingGenerator()
