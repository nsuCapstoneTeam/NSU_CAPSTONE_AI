import random
from unittest.mock import Mock

import pytest
import torch

from app.embedding.audio_embedding import AudioEmbeddingError, AudioEmbeddingGenerator, audio_file_sha256


@pytest.fixture
def audio_path(tmp_path):
    path = tmp_path / 'reference.mp3'
    path.write_bytes(b'synthetic audio input for mocked model')
    return path


@pytest.fixture(autouse=True)
def package_metadata(monkeypatch):
    monkeypatch.setattr('app.embedding.audio_embedding.importlib.metadata.version', lambda name: 'test')


def test_same_bytes_reproduce_vector_and_restore_random_states(audio_path, tmp_path):
    def encode(paths, *, resample):
        assert resample is True
        assert len(paths) == 1
        return torch.rand(1, 4) + random.random()
    model = Mock()
    model.model_fp = '/cache/snapshots/revision123/CLAP_weights_2023.pth'
    model.get_audio_embeddings.side_effect = encode
    generator = AudioEmbeddingGenerator(model)
    python_state, torch_state = random.getstate(), torch.random.get_rng_state().clone()
    first = generator.generate(audio_path)
    copy = tmp_path / 'renamed.mp3'
    copy.write_bytes(audio_path.read_bytes())
    second = generator.generate(copy)
    assert torch.equal(first.vector, second.vector)
    assert first.metadata['source_sha256'] == second.metadata['source_sha256']
    assert first.metadata['dimension'] == 4
    assert first.metadata['checkpoint_revision'] == 'revision123'
    assert first.metadata['preprocessing']['crop_seed'] == 43 + int(audio_file_sha256(audio_path)[:8], 16)
    assert random.getstate() == python_state
    assert torch.equal(torch.random.get_rng_state(), torch_state)


@pytest.mark.parametrize('value, reason', [
    (torch.ones(2, 4), 'invalid_embedding_shape'),
    (torch.zeros(1, 4), 'zero_embedding'),
    (torch.tensor([[float('nan')]]), 'non_finite_or_non_float_embedding'),
    (torch.tensor([[float('inf')]]), 'non_finite_or_non_float_embedding'),
])
def test_invalid_model_output_rejected(audio_path, value, reason):
    model = Mock(model_fp='checkpoint')
    model.get_audio_embeddings.return_value = value
    with pytest.raises(AudioEmbeddingError) as caught:
        AudioEmbeddingGenerator(model).generate(audio_path)
    assert caught.value.reason == reason


def test_dimension_changes_are_rejected(audio_path):
    model = Mock(model_fp='checkpoint')
    model.get_audio_embeddings.side_effect = [torch.ones(1, 4), torch.ones(1, 3)]
    generator = AudioEmbeddingGenerator(model)
    generator.generate(audio_path)
    with pytest.raises(AudioEmbeddingError, match='embedding_dimension_mismatch'):
        generator.generate(audio_path)


def test_model_failure_restores_states_and_preserves_cause(audio_path):
    def fail(*args, **kwargs):
        random.random(); torch.rand(1)
        raise RuntimeError('decoder failed')
    model = Mock()
    model.get_audio_embeddings.side_effect = fail
    python_state, torch_state = random.getstate(), torch.random.get_rng_state().clone()
    with pytest.raises(AudioEmbeddingError, match='audio_embedding_failed') as caught:
        AudioEmbeddingGenerator(model).generate(audio_path)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert random.getstate() == python_state
    assert torch.equal(torch.random.get_rng_state(), torch_state)


def test_missing_empty_or_changed_input_never_calls_model(tmp_path, audio_path):
    model = Mock()
    generator = AudioEmbeddingGenerator(model)
    with pytest.raises(AudioEmbeddingError, match='audio_file_missing'):
        generator.generate(tmp_path / 'missing.mp3')
    empty = tmp_path / 'empty.mp3'; empty.touch()
    with pytest.raises(AudioEmbeddingError, match='audio_file_empty'):
        generator.generate(empty)
    with pytest.raises(AudioEmbeddingError, match='audio_source_changed'):
        generator.generate(audio_path, expected_sha256='0' * 64)
    model.get_audio_embeddings.assert_not_called()


def test_input_changed_during_generation_rejected(audio_path):
    def encode(*args, **kwargs):
        audio_path.write_bytes(b'changed')
        return torch.ones(1, 4)
    model = Mock(model_fp='checkpoint')
    model.get_audio_embeddings.side_effect = encode
    with pytest.raises(AudioEmbeddingError, match='audio_source_changed'):
        AudioEmbeddingGenerator(model).generate(audio_path)
