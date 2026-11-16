from unittest.mock import Mock

import pytest
import torch

from app.embedding.audio_embedding import (
    AudioEmbeddingError, AudioEmbeddingResult,
    CALIBRATION_CHECKPOINT_REVISION, CALIBRATION_CHECKPOINT_SHA256,
)
from app.embedding.text_embedding import (
    CALIBRATION_MSCLAP_CONFIG_SHA256, CALIBRATION_MSCLAP_PACKAGE_VERSION,
    CALIBRATION_MSCLAP_SOURCE_FILE_COUNT, CALIBRATION_MSCLAP_SOURCE_SHA256,
)
from app.embedding.storage import AudioEmbeddingStorage
from app.repository.embedding_repository import prepare_embedding, validate_music_id


def make_result():
    return AudioEmbeddingResult(torch.ones(1, 4), {
        'source_sha256': 'a' * 64, 'shape': [1, 4], 'dimension': 4,
        'model': 'MSCLAP', 'model_version': '2023', 'preprocessing_version': 'test-v1',
        'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
        'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
        'msclap_implementation': {
            'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
            'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
            'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
            'config_file': 'configs/config_2023.yml',
            'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
        },
        'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION, 'torch': 'test'}, 'preprocessing': {
            'analysis_duration_seconds': 56, 'chunk_duration_seconds': 7,
            'chunk_count': 8, 'chunk_overlap_seconds': 0,
            'chunk_normalization': 'l2', 'aggregation': 'mean',
            'final_normalization': 'l2', 'channel_policy': 'arithmetic_mean_downmix_to_mono',
        },
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


def test_source_facts_do_not_change_shared_generation_profile():
    first = make_result()
    second = make_result()
    second.metadata.update({
        'source_sha256': 'b' * 64,
        'source_duration_seconds': 60,
        'source_sample_rate': 48_000,
        'source_channels': 2,
        'source_path': '/another/location/audio.wav',
    })

    first_profile = prepare_embedding(first)[1]
    second_profile = prepare_embedding(second)[1]

    assert first_profile == second_profile
    assert 'source_sha256' not in first_profile
    assert 'source_duration_seconds' not in first_profile
    assert 'source_sample_rate' not in first_profile
    assert 'source_channels' not in first_profile


def test_generation_failure_does_not_open_database(monkeypatch):
    connect = Mock()
    monkeypatch.setattr('app.embedding.storage.connect_database', connect)
    generator = Mock()
    generator.generate.side_effect = AudioEmbeddingError('audio_embedding_failed', 'file')
    with pytest.raises(AudioEmbeddingError):
        AudioEmbeddingStorage(generator=generator).store('music-1', 'file', audio_revision=1)
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
        AudioEmbeddingStorage(generator, repository).store('music-1', 'file', audio_revision=1)
    assert context.__exit__.call_args.args[0] is RuntimeError


@pytest.mark.parametrize('revision', [None, True, False, 1.0, '1', 0, -1, 9223372036854775808])
def test_invalid_revision_is_rejected_before_inference(revision):
    generator = Mock()
    with pytest.raises(ValueError):
        AudioEmbeddingStorage(generator=generator).store('music-1', 'file', audio_revision=revision)
    generator.generate.assert_not_called()


def test_missing_revision_is_rejected():
    with pytest.raises(TypeError):
        AudioEmbeddingStorage(generator=Mock()).store('music-1', 'file')


def test_revision_bigint_boundaries_and_profile_hash():
    import hashlib
    import json
    from app.repository.embedding_repository import validate_audio_revision, generation_profile_sha256
    for revision in (1, 9223372036854775807):
        validate_audio_revision(revision)
    profile = prepare_embedding(make_result())[1]
    expected = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode('utf-8')).hexdigest()
    assert generation_profile_sha256(profile) == expected
    assert generation_profile_sha256(dict(reversed(list(profile.items())))) == expected
    assert 'device' in profile
    with pytest.raises(ValueError):
        generation_profile_sha256({'invalid': float('nan')})


def test_storage_passes_revision_and_saved_identity(monkeypatch):
    from unittest.mock import MagicMock
    context = MagicMock()
    monkeypatch.setattr('app.embedding.storage.connect_database', lambda: context)
    generator, repository = Mock(), Mock()
    result = make_result()
    generator.generate.return_value = result
    saved = AudioEmbeddingStorage(generator, repository).store('music-1', 'file', audio_revision=7)
    assert saved is repository.save.return_value
    repository.save.assert_called_once_with(context.__enter__.return_value, 'music-1', 7, result)


def test_store_cli_requires_revision_before_creating_storage(monkeypatch):
    from scripts.embedding import store_audio_embedding as cli
    constructor = Mock()
    monkeypatch.setattr(cli, 'AudioEmbeddingStorage', constructor)
    monkeypatch.setattr('sys.argv', ['store-audio', '--music-id', 'music-1', '--audio', 'file'])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    constructor.assert_not_called()


def test_store_cli_returns_persisted_identity(monkeypatch, capsys):
    import json
    from app.repository.embedding_repository import EmbeddingSaveResult
    from scripts.embedding import store_audio_embedding as cli
    storage = Mock()
    storage.store.return_value = EmbeddingSaveResult('stored-uuid', 'music-1', 7, 'a' * 64, False, 'b' * 64, 4)
    monkeypatch.setattr(cli, 'AudioEmbeddingStorage', lambda: storage)
    monkeypatch.setattr('sys.argv', ['store-audio', '--music-id', 'music-1', '--audio', 'file', '--audio-revision', '7'])
    assert cli.main() == 0
    storage.store.assert_called_once_with('music-1', 'file', audio_revision=7)
    output = json.loads(capsys.readouterr().out)
    assert output['id'] == 'stored-uuid' and output['created'] is False
    assert output['audio_revision'] == 7 and output['generation_profile_sha256'] == 'a' * 64
