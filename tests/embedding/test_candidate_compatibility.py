from unittest.mock import patch

import pytest

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
    TEXT_EMBEDDING_DIMENSION,
    TEXT_ENCODER_MODEL_ID,
    TEXT_ENCODER_MODEL_SHA256,
    TEXT_ENCODER_REVISION,
    TEXT_ENCODER_TOKENIZER_FILE_SHA256,
)
from app.repository import embedding_repository as repository_module
from app.repository.embedding_repository import (
    AudioEmbeddingRepository,
    CandidateCompatibilityStatus as Status,
    generation_profile_sha256,
)


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.cursor_instance = Cursor(rows)

    def cursor(self):
        return self.cursor_instance


def text_profile():
    implementation = {
        'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
    }
    return {
        'generation_version': GENERATION_VERSION,
        'embedding_generation_profile': GENERATION_PROFILE,
        'model': 'MSCLAP',
        'model_version': MODEL_VERSION,
        'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
        'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
        'msclap_implementation': implementation,
        'text_encoder': {
            'model_id': TEXT_ENCODER_MODEL_ID,
            'revision': TEXT_ENCODER_REVISION,
            'config_sha256': TEXT_ENCODER_TOKENIZER_FILE_SHA256['config.json'],
            'model_file': 'model.safetensors',
            'model_file_sha256': TEXT_ENCODER_MODEL_SHA256,
            'tokenizer_id': TEXT_ENCODER_MODEL_ID,
            'tokenizer_revision': TEXT_ENCODER_REVISION,
            'tokenizer_files_sha256': TEXT_ENCODER_TOKENIZER_FILE_SHA256,
            'tokenizer_runtime_sha256': '1' * 64,
        },
        'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
        'dimension': TEXT_EMBEDDING_DIMENSION,
        'dtype': 'torch.float32',
        'text_preprocessing': {
            'encoder_api': 'CLAP.get_text_embeddings',
            'text_model': TEXT_ENCODER_MODEL_ID,
            'text_model_revision': TEXT_ENCODER_REVISION,
            'token_limit': 77,
            'truncation': 'rejected',
            'normalization': 'none; raw MSCLAP Text Embedding',
        },
    }


def audio_profile(**changes):
    profile = {
        'model': 'MSCLAP',
        'model_version': MODEL_VERSION,
        'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
        'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
        'msclap_implementation': {
            'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
            'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
            'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
            'config_file': 'configs/config_2023.yml',
            'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
        },
        'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION, 'torch': 'test'},
        'preprocessing_version': PREPROCESSING_VERSION,
        'preprocessing': {'analysis_duration_seconds': 56},
        'dimension': TEXT_EMBEDDING_DIMENSION,
        'dtype': 'torch.float32',
        'device': 'cpu',
    }
    profile.update(changes)
    return profile


def row(music_id, revision, *, profile=None, dimension=TEXT_EMBEDDING_DIMENSION,
        source_exists=True, embedding_id='00000000-0000-7000-8000-000000000001'):
    profile = audio_profile() if profile is None else profile
    return (
        music_id, revision, source_exists,
        embedding_id if source_exists else None,
        generation_profile_sha256(profile) if profile is not None else None,
        dimension if source_exists else None,
        profile if source_exists else None,
    )


def run_check(monkeypatch, candidates, rows, profile=None):
    connection = Connection(rows)
    profile = text_profile() if profile is None else profile
    with patch.object(repository_module, 'prepare_text_embedding',
                      return_value=(None, profile, None, None)):
        result = AudioEmbeddingRepository().check_candidate_compatibility(
            connection, candidates, object())
    return result, connection


def test_batch_lookup_preserves_exact_pairs_revision_and_embedding_identity(monkeypatch):
    rows = [row('music-a', 2), row('music-a', 9, embedding_id='00000000-0000-7000-8000-000000000009')]
    results, connection = run_check(monkeypatch, [('music-a', 2), ('music-a', 9)], rows)
    assert [result.status for result in results] == [Status.COMPATIBLE, Status.COMPATIBLE]
    assert results[0].compatible_candidate.audio_revision == 2
    assert results[1].compatible_candidate.audio_revision == 9
    assert results[0].compatible_candidate.embedding_id.endswith('0001')
    assert results[0].compatible_candidate.generation_profile_sha256 == rows[0][4]
    assert len(connection.cursor_instance.calls) == 1
    sql, params = connection.cursor_instance.calls[0]
    assert 'audio_revision IN' not in sql
    assert 's.music_id = c.music_id AND s.audio_revision = c.audio_revision' in sql
    assert 'e.music_id = c.music_id AND e.audio_revision = c.audio_revision' in sql
    assert params == ('music-a', 2, 'music-a', 9)


def test_requested_pair_without_source_and_source_without_embedding(monkeypatch):
    results, _ = run_check(monkeypatch, [('missing', 1), ('source-only', 5)], [
        row('missing', 1, source_exists=False),
        ('source-only', 5, True, None, None, None, None),
    ])
    assert [result.status for result in results] == [Status.MISSING_SOURCE, Status.MISSING_EMBEDDING]


def test_no_candidates_returns_empty_without_database_round_trip(monkeypatch):
    results, connection = run_check(monkeypatch, [], [])
    assert results == []
    assert connection.cursor_instance.calls == []


@pytest.mark.parametrize(('change', 'expected'), [
    ({'model': 'OTHER'}, Status.INCOMPATIBLE_PROFILE),
    ({'model_version': 'other'}, Status.INCOMPATIBLE_PROFILE),
    ({'checkpoint_revision': '0' * 40}, Status.INCOMPATIBLE_PROFILE),
    ({'checkpoint_sha256': '0' * 64}, Status.INCOMPATIBLE_PROFILE),
    ({'msclap_implementation': {}}, Status.INCOMPATIBLE_PROFILE),
    ({'packages': {'msclap': 'unsupported'}}, Status.INCOMPATIBLE_PROFILE),
    ({'preprocessing_version': 'unsupported'}, Status.INCOMPATIBLE_PROFILE),
    ({'dimension': TEXT_EMBEDDING_DIMENSION - 1}, Status.INVALID_DIMENSION),
])
def test_profile_mismatch_is_classified(monkeypatch, change, expected):
    profile = audio_profile(**change)
    dimension = profile.get('dimension', TEXT_EMBEDDING_DIMENSION)
    results, _ = run_check(monkeypatch, [('music', 1)], [
        row('music', 1, profile=profile, dimension=dimension)])
    assert results[0].status == expected


def test_device_only_difference_remains_compatible_and_profile_hash_is_preserved(monkeypatch):
    profile = audio_profile(device='cuda')
    result_value, _ = run_check(monkeypatch, [('music', 1)], [
        row('music', 1, profile=profile)])
    checked = result_value[0]
    assert checked.status == Status.COMPATIBLE
    assert checked.compatible_candidate.generation_profile_sha256 == generation_profile_sha256(profile)


def test_profile_hash_mismatch_is_not_selected(monkeypatch):
    profile = audio_profile()
    stored = list(row('music', 1, profile=profile))
    stored[4] = '0' * 64
    results, _ = run_check(monkeypatch, [('music', 1)], [tuple(stored)])
    assert results[0].status == Status.INCOMPATIBLE_PROFILE


def test_zero_one_and_multiple_compatible_profiles(monkeypatch):
    incompatible = audio_profile(model='OTHER')
    results, _ = run_check(monkeypatch, [('music', 1)], [
        row('music', 1, profile=incompatible)])
    assert results[0].status == Status.INCOMPATIBLE_PROFILE

    profile = audio_profile()
    results, _ = run_check(monkeypatch, [('music', 1)], [row('music', 1, profile=profile)])
    assert results[0].status == Status.COMPATIBLE
    assert results[0].compatible_candidate is not None

    other_profile = audio_profile(device='cuda')
    results, _ = run_check(monkeypatch, [('music', 1)], [
        row('music', 1, profile=profile),
        row('music', 1, profile=other_profile, embedding_id='00000000-0000-7000-8000-000000000002'),
    ])
    assert results[0].status == Status.AMBIGUOUS_PROFILE
    assert results[0].compatible_candidate is None


def test_duplicate_is_reported_without_deduplicating_diagnostic(monkeypatch):
    results, connection = run_check(monkeypatch, [('music', 1), ('music', 1)], [row('music', 1)])
    assert [result.status for result in results] == [Status.COMPATIBLE, Status.DUPLICATE]
    assert [result.ordinal for result in results] == [0, 1]
    assert len(connection.cursor_instance.calls) == 1
    assert connection.cursor_instance.calls[0][1] == ('music', 1)


@pytest.mark.parametrize('revision', [None, True, False, 0, -1, 1.5, '1', 9223372036854775808])
def test_invalid_revision_is_rejected_before_database_query(monkeypatch, revision):
    connection = Connection([])
    with patch.object(repository_module, 'prepare_text_embedding',
                      return_value=(None, text_profile(), None, None)):
        with pytest.raises(ValueError):
            AudioEmbeddingRepository().check_candidate_compatibility(
                connection, [('music', revision)], object())
    assert connection.cursor_instance.calls == []


def test_invalid_candidate_shape_and_music_id_are_rejected(monkeypatch):
    for candidates in [[('music', 1, 'extra')], [(None, 1)]]:
        connection = Connection([])
        with patch.object(repository_module, 'prepare_text_embedding',
                          return_value=(None, text_profile(), None, None)):
            with pytest.raises(ValueError):
                AudioEmbeddingRepository().check_candidate_compatibility(connection, candidates, object())
        assert connection.cursor_instance.calls == []


def test_database_failure_is_propagated(monkeypatch):
    class FailingCursor(Cursor):
        def execute(self, sql, params):
            raise RuntimeError('database unavailable')

    class FailingConnection(Connection):
        def cursor(self):
            return FailingCursor([])

    connection = FailingConnection([])
    with patch.object(repository_module, 'prepare_text_embedding',
                      return_value=(None, text_profile(), None, None)):
        with pytest.raises(RuntimeError, match='database unavailable'):
            AudioEmbeddingRepository().check_candidate_compatibility(
                connection, [('music', 1)], object())
