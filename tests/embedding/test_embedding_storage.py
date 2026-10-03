from unittest.mock import Mock

import pytest
import torch

from app.embedding.audio_embedding import AudioEmbeddingError, AudioEmbeddingResult
from app.embedding.storage import AudioEmbeddingStorage
from app.repository.embedding_repository import prepare_embedding, validate_music_id


def make_result():
    return AudioEmbeddingResult(torch.ones(1, 4), {
        'source_sha256': 'a' * 64, 'shape': [1, 4], 'dimension': 4,
        'model': 'MSCLAP', 'model_version': '2023', 'preprocessing_version': 'test-v1',
        'packages': {'torch': 'test'}, 'preprocessing': {'base_seed': 43},
        'dtype': 'torch.float32', 'device': 'cpu', 'source_path': '/test/audio.mp3',
    })


@pytest.mark.parametrize('music_id', ['', ' ', ' id', 'id ', 'a' * 201, 1, None])
def test_invalid_music_id_rejected(music_id):
    with pytest.raises(ValueError):
        validate_music_id(music_id)


@pytest.mark.parametrize('key,value', [
    ('dimension', 3), ('dimension', True), ('shape', [4]),
    ('source_sha256', 'invalid'), ('model_version', ''), ('packages', None),
])
def test_inconsistent_metadata_rejected(key, value):
    result = make_result()
    result.metadata[key] = value
    with pytest.raises(ValueError):
        prepare_embedding(result)


def test_float32_conversion_cannot_store_zero_or_infinite_vector():
    result = make_result()
    for number in (1e-100, 1e100):
        vector = torch.full((1, 4), number, dtype=torch.float64)
        with pytest.raises(ValueError):
            prepare_embedding(AudioEmbeddingResult(vector, result.metadata))


def test_generation_failure_does_not_open_database(monkeypatch):
    connect = Mock()
    monkeypatch.setattr('app.embedding.storage.connect_database', connect)
    generator = Mock()
    generator.generate.side_effect = AudioEmbeddingError('audio_embedding_failed', 'file')
    with pytest.raises(AudioEmbeddingError):
        AudioEmbeddingStorage(generator=generator).store('music-1', 'file')
    connect.assert_not_called()


def test_database_context_receives_save_failure(monkeypatch):
    connect = Mock()
    monkeypatch.setattr('app.embedding.storage.connect_database', connect)
    generator = Mock()
    generator.generate.return_value = make_result()
    repository = Mock()
    repository.save.side_effect = RuntimeError('save failed')
    context = connect.return_value
    context.__enter__ = Mock(return_value=Mock())
    context.__exit__ = Mock(return_value=False)
    with pytest.raises(RuntimeError, match='save failed'):
        AudioEmbeddingStorage(generator, repository).store('music-1', 'file')
    assert context.__exit__.call_args.args[0] is RuntimeError
