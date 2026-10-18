from unittest.mock import Mock

import pytest
import torch

from app.embedding.storage import TextEmbeddingStorage
from app.embedding.audio_embedding import PREPROCESSING_VERSION
from app.embedding.text_embedding import (
    CALIBRATION_CHECKPOINT_REVISION,
    CALIBRATION_CHECKPOINT_SHA256,
    CALIBRATION_MSCLAP_CONFIG_SHA256,
    CALIBRATION_MSCLAP_PACKAGE_VERSION,
    CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
    CALIBRATION_MSCLAP_SOURCE_SHA256,
    GENERATION_PROFILE,
    GENERATION_VERSION,
    MODEL_VERSION,
    TextEmbeddingResult,
)
from app.repository.embedding_repository import (
    EmbeddingConflict,
    TextEmbeddingRepository,
    prepare_text_embedding,
    text_audio_profiles_compatible,
)


def make_result(vector=None, **changes):
    metadata = {
        'query_text_sha256': 'a' * 64, 'shape': [1, 4], 'dimension': 4,
        'model': 'MSCLAP', 'model_version': '2023',
        'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
        'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
        'msclap_implementation': {
            'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
            'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
            'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
            'config_file': 'configs/config_2023.yml',
            'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
        },
        'text_encoder': {
            'model_id': 'gpt2', 'revision': 'e' * 40, 'model_file_sha256': 'f' * 64,
            'tokenizer_id': 'gpt2', 'tokenizer_revision': 'e' * 40,
        },
        'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION, 'torch': 'test'},
        'generation_version': GENERATION_VERSION,
        'embedding_generation_profile': GENERATION_PROFILE,
        'text_preprocessing': {'encoder_api': 'encode_text', 'normalization': 'none'},
        'dtype': 'torch.float32', 'device': 'cpu',
    }
    metadata.update(changes)
    if vector is None:
        vector = torch.tensor([[1.0, 2.0, 3.0, 4.0]], dtype=torch.float32)
    return TextEmbeddingResult(vector, metadata)


class Cursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return next(self.responses)

    def fetchall(self):
        return next(self.responses)


class Connection:
    def __init__(self, responses):
        self.cursor_instance = Cursor(responses)

    def cursor(self):
        return self.cursor_instance


def test_text_vector_is_validated_and_profile_identity_is_stable():
    prepared = prepare_text_embedding(make_result())
    changed_input = prepare_text_embedding(make_result(query_text_sha256='f' * 64))
    changed_profile = prepare_text_embedding(make_result(generation_version='text-v3'))
    assert prepared[2] == changed_input[2]
    assert prepared[2] != changed_profile[2]
    assert prepared[3] == '[1.0, 2.0, 3.0, 4.0]'


@pytest.mark.parametrize('vector', [
    torch.tensor([[float('nan'), 1, 1, 1]]),
    torch.tensor([[float('inf'), 1, 1, 1]]),
    torch.zeros((1, 4)),
    torch.ones((1, 3)),
    torch.ones((1, 4), dtype=torch.int64),
])
def test_invalid_text_vectors_are_rejected(vector):
    with pytest.raises(ValueError):
        prepare_text_embedding(make_result(vector))


@pytest.mark.parametrize('metadata_change', [
    {'dimension': 3}, {'query_text_sha256': 'bad'}, {'generation_version': ''},
    {'embedding_generation_profile': ''}, {'checkpoint_sha256': ''},
    {'packages': {}}, {'text_preprocessing': None},
])
def test_missing_or_inconsistent_text_identity_is_rejected(metadata_change):
    with pytest.raises(ValueError):
        prepare_text_embedding(make_result(**metadata_change))


def test_same_text_and_profile_reuses_identical_row_and_rejects_vector_conflict():
    result = make_result()
    inserted = Connection([('created',)])
    reused = Connection([None, (True,)])
    conflict = Connection([None, (False,)])
    repository = TextEmbeddingRepository()
    assert repository.save(inserted, result).created
    assert not repository.save(reused, result).created
    with pytest.raises(EmbeddingConflict):
        repository.save(conflict, make_result(torch.tensor([[4., 3., 2., 1.]])))
    assert 'ON CONFLICT (query_text_sha256, generation_profile_sha256) DO NOTHING' in inserted.cursor_instance.calls[0][0]


def test_get_returns_stored_vector_dimension_and_profile_identity():
    row = ('[1,2,3,4]', 4, 'text-v2', 'f' * 64, {'dimension': 4}, {'dimension': 4})
    connection = Connection([row])
    stored = TextEmbeddingRepository().get(connection, 'a' * 64, 'f' * 64)
    assert stored['embedding'] == '[1,2,3,4]'
    assert stored['dimension'] == 4
    assert stored['generation_version'] == 'text-v2'
    assert stored['generation_profile_sha256'] == 'f' * 64


def test_profile_compatibility_uses_shared_model_checkpoint_package_and_dimension():
    implementation = {
        'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
    }
    text = {'model': 'MSCLAP', 'model_version': MODEL_VERSION,
            'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
            'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
            'msclap_implementation': implementation,
            'dimension': 4, 'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
            'generation_version': GENERATION_VERSION, 'embedding_generation_profile': GENERATION_PROFILE,
            'generation_profile_sha256': 'a' * 64}
    audio = {'model': 'MSCLAP', 'model_version': MODEL_VERSION,
             'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
             'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
             'msclap_implementation': implementation,
             'dimension': 4, 'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
             'preprocessing_version': PREPROCESSING_VERSION,
             'generation_version': 'audio-generation-v2',
             'embedding_generation_profile': 'audio-first56s-8x7s-v2',
             'generation_profile_sha256': 'b' * 64}
    assert text_audio_profiles_compatible(text, audio)


@pytest.mark.parametrize(('field', 'text_value', 'audio_value'), [
    ('model', 'MSCLAP', 'other-model'),
    ('model_version', '2023', '2024'),
    ('checkpoint_revision', 'rev-a', 'rev-b'),
    ('checkpoint_sha256', CALIBRATION_CHECKPOINT_SHA256, '9' * 64),
    ('dimension', 4, 5),
    ('packages', {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION}, {'msclap': '1.4.0'}),
])
def test_profile_compatibility_rejects_different_shared_embedding_space(field, text_value, audio_value):
    implementation = {
        'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
    }
    text = {'model': 'MSCLAP', 'model_version': MODEL_VERSION,
            'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
            'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
            'msclap_implementation': implementation,
            'dimension': 4, 'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
            'generation_version': GENERATION_VERSION, 'embedding_generation_profile': GENERATION_PROFILE}
    audio = {'model': 'MSCLAP', 'model_version': MODEL_VERSION,
             'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
             'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
             'msclap_implementation': implementation,
             'dimension': 4, 'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
             'preprocessing_version': PREPROCESSING_VERSION}
    text[field] = text_value
    audio[field] = audio_value
    assert not text_audio_profiles_compatible(text, audio)


@pytest.mark.parametrize('missing_field', ['checkpoint_sha256', 'msclap_implementation'])
def test_missing_audio_joint_space_identity_is_incompatible(missing_field):
    text = prepare_text_embedding(make_result())[1]
    audio = {
        'model': text['model'], 'model_version': text['model_version'],
        'checkpoint_revision': text['checkpoint_revision'],
        'checkpoint_sha256': text['checkpoint_sha256'],
        'msclap_implementation': text['msclap_implementation'],
        'dimension': text['dimension'], 'packages': text['packages'],
        'preprocessing_version': PREPROCESSING_VERSION,
    }
    audio.pop(missing_field)
    assert not text_audio_profiles_compatible(text, audio)


def test_different_msclap_implementation_identity_is_incompatible():
    text = prepare_text_embedding(make_result())[1]
    audio = {
        'model': text['model'], 'model_version': text['model_version'],
        'checkpoint_revision': text['checkpoint_revision'],
        'checkpoint_sha256': text['checkpoint_sha256'],
        'msclap_implementation': {**text['msclap_implementation'], 'config_sha256': '9' * 64},
        'dimension': text['dimension'], 'packages': text['packages'],
        'preprocessing_version': PREPROCESSING_VERSION,
    }
    assert not text_audio_profiles_compatible(text, audio)


def test_profile_compatibility_rejects_unsupported_modality_profiles():
    implementation = {
        'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
    }
    text = {'model': 'MSCLAP', 'model_version': MODEL_VERSION,
            'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
            'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
            'msclap_implementation': implementation,
            'dimension': 4, 'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
            'generation_version': GENERATION_VERSION, 'embedding_generation_profile': GENERATION_PROFILE}
    audio = {'model': 'MSCLAP', 'model_version': MODEL_VERSION,
             'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
             'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
             'msclap_implementation': implementation,
             'dimension': 4, 'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
             'preprocessing_version': PREPROCESSING_VERSION}
    assert text_audio_profiles_compatible(text, audio)
    assert not text_audio_profiles_compatible(text, {**audio, 'preprocessing_version': 'unsupported-audio-v99'})
    assert not text_audio_profiles_compatible(text, {**text, 'generation_version': 'unsupported-text-v99'})
    assert not text_audio_profiles_compatible(text, {**text, 'embedding_generation_profile': 'unsupported-text-profile'})


def test_text_search_filters_audio_by_shared_profile_identity():
    connection = Connection([[(1, 'music-1', 0.75)]])
    found = TextEmbeddingRepository().search_audio(connection, make_result())
    sql, params = connection.cursor_instance.calls[0]
    assert found == {'candidate_count': 1, 'results': [{'music_id': 'music-1', 'cosine_similarity': 0.75}]}
    assert "generation_profile->>'checkpoint_revision' = %s" in sql
    assert "generation_profile->>'checkpoint_sha256' = %s" in sql
    assert "generation_profile->'msclap_implementation' = %s" in sql
    assert params[0:6] == (
        4, 'MSCLAP', MODEL_VERSION, CALIBRATION_CHECKPOINT_REVISION,
        CALIBRATION_CHECKPOINT_SHA256, CALIBRATION_MSCLAP_PACKAGE_VERSION,
    )
    assert params[7] == PREPROCESSING_VERSION


def test_unsupported_text_generation_profile_cannot_search_audio():
    connection = Connection([])
    result = make_result(generation_version='unvalidated-text-v99')
    with pytest.raises(ValueError, match='not_audio_search_compatible'):
        TextEmbeddingRepository().search_audio(connection, result)
    assert connection.cursor_instance.calls == []


def test_storage_generates_before_opening_transaction_and_returns_saved_identity(monkeypatch):
    connect = Mock()
    monkeypatch.setattr('app.embedding.storage.connect_database', connect)
    generator = Mock()
    generator.generate.return_value = make_result()
    repository = Mock()
    repository.save.return_value = 'saved'
    context = connect.return_value
    context.__enter__ = Mock(return_value=Mock())
    context.__exit__ = Mock(return_value=False)
    assert TextEmbeddingStorage(generator, repository).store('event query') == 'saved'
    generator.generate.assert_called_once_with('event query')
    repository.save.assert_called_once()
