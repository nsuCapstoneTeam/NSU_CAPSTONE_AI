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
    return FakeModel(checkpoint)


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
    assert metadata["packages"]["msclap"] == "1.3.3"
    assert metadata["dimension"] == 3
    assert metadata["generation_version"] == text_embedding.GENERATION_VERSION
    assert metadata["embedding_generation_profile"] == "ClapModel.encode_text/msclap-default-v1"
    assert metadata["text_encoder"]["revision"] == text_embedding.TEXT_ENCODER_REVISION
    assert metadata["text_encoder"]["tokenizer_revision"] == text_embedding.TEXT_ENCODER_REVISION
    assert metadata["text_encoder"]["model_file_sha256"] == text_embedding.TEXT_ENCODER_MODEL_SHA256
    assert metadata["packages"]["tokenizers"] == "test-tokenizers"
    assert metadata["text_preprocessing"]["normalization"] == "none; raw MSCLAP Text Embedding"
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

    from pathlib import Path

    monkeypatch.setattr(text_embedding, "_sha256_file", counted_hash)
    generator = TextEmbeddingGenerator(configured_model)
    assert len(calls) == 1

    first = generator.generate("first valid query")
    second = generator.generate("second valid query")
    assert len(calls) == 1
    assert first.metadata["checkpoint_sha256"] == second.metadata["checkpoint_sha256"]
    assert first.metadata["checkpoint_sha256"] == generator._checkpoint_sha256


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
