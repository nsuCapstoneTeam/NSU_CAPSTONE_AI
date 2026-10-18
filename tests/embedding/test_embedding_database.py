"""명시적으로 지정한 실제 DB에서 제약과 트랜잭션을 검증하고 테스트 행을 정리한다."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
import torch

from app.core.database import connect_database
from app.embedding.audio_embedding import (
    PREPROCESSING_VERSION, AudioEmbeddingResult,
    CALIBRATION_CHECKPOINT_REVISION, CALIBRATION_CHECKPOINT_SHA256,
)
from app.embedding.text_embedding import (
    CALIBRATION_MSCLAP_CONFIG_SHA256, CALIBRATION_MSCLAP_PACKAGE_VERSION,
    CALIBRATION_MSCLAP_SOURCE_FILE_COUNT, CALIBRATION_MSCLAP_SOURCE_SHA256,
    GENERATION_PROFILE, GENERATION_VERSION, TEXT_EMBEDDING_DIMENSION,
    TEXT_ENCODER_MODEL_ID, TEXT_ENCODER_MODEL_SHA256, TEXT_ENCODER_REVISION,
    TEXT_ENCODER_TOKENIZER_FILE_SHA256, TextEmbeddingResult,
)
from app.repository.embedding_repository import (
    AudioEmbeddingRepository, EmbeddingConflict, TextEmbeddingRepository,
)


pytestmark = pytest.mark.skipif(os.environ.get('RUN_EMBEDDING_DB_TESTS') != '1',
                                reason='Explicit database integration opt-in required')


@pytest.fixture
def connection():
    with connect_database() as connection:
        try:
            yield connection
        finally:
            # 기존 데이터에 손대지 않고 각 테스트의 행을 트랜잭션 단위로 취소한다.
            connection.rollback()


def result(value=1.0):
    return AudioEmbeddingResult(torch.full((1, TEXT_EMBEDDING_DIMENSION), value), {
        'source_sha256': 'a' * 64, 'shape': [1, TEXT_EMBEDDING_DIMENSION], 'dimension': TEXT_EMBEDDING_DIMENSION,
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
        'packages': {'msclap': '1.3.3', 'torch': 'test'}, 'preprocessing': {
            'analysis_duration_seconds': 56, 'chunk_duration_seconds': 7,
            'chunk_count': 8, 'chunk_overlap_seconds': 0,
            'chunk_normalization': 'l2', 'aggregation': 'mean',
            'final_normalization': 'l2', 'channel_policy': 'arithmetic_mean_downmix_to_mono',
        },
        'dtype': 'torch.float32', 'device': 'cpu',
    })


def text_result(value=1.0, *, generation_version=GENERATION_VERSION):
    return TextEmbeddingResult(torch.full((1, TEXT_EMBEDDING_DIMENSION), value), {
        'query_text_sha256': 'b' * 64, 'shape': [1, TEXT_EMBEDDING_DIMENSION], 'dimension': TEXT_EMBEDDING_DIMENSION,
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
            'model_id': TEXT_ENCODER_MODEL_ID, 'revision': TEXT_ENCODER_REVISION,
            'config_sha256': TEXT_ENCODER_TOKENIZER_FILE_SHA256['config.json'],
            'model_file': 'model.safetensors', 'model_file_sha256': TEXT_ENCODER_MODEL_SHA256,
            'tokenizer_id': TEXT_ENCODER_MODEL_ID, 'tokenizer_revision': TEXT_ENCODER_REVISION,
            'tokenizer_runtime_sha256': '1' * 64,
            'tokenizer_files_sha256': TEXT_ENCODER_TOKENIZER_FILE_SHA256.copy(),
        },
        'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION, 'torch': 'test'},
        'generation_version': generation_version,
        'embedding_generation_profile': GENERATION_PROFILE,
        'text_preprocessing': {
            'encoder_api': 'CLAP.get_text_embeddings', 'text_model': TEXT_ENCODER_MODEL_ID,
            'text_model_revision': TEXT_ENCODER_REVISION, 'token_limit': 77,
            'truncation': 'rejected', 'normalization': 'none; raw MSCLAP Text Embedding',
            'token_count_including_model_end_marker_and_specials': 4,
        },
        'dtype': 'torch.float32', 'device': 'cpu',
    })


def test_roundtrip_and_duplicate_reuse(connection):
    music_id = 'test-' + uuid.uuid4().hex
    repository = AudioEmbeddingRepository()
    assert repository.save(connection, music_id, result()).created
    assert not repository.save(connection, music_id, result()).created
    row = connection.execute('''SELECT dimension, vector_dims(embedding), metadata,
        1 - (embedding <=> %s::vector) FROM ai_embeddings.audio_embeddings WHERE music_id = %s''',
        ('[1,1,1,1]', music_id)).fetchone()
    assert row[0:2] == (4, 4)
    assert row[2]['source_sha256'] == 'a' * 64
    assert row[3] == pytest.approx(1.0)


@pytest.mark.parametrize('change', ['hash', 'vector', 'profile'])
def test_conflict_preserves_existing_row(connection, change):
    music_id = 'test-' + uuid.uuid4().hex
    repository = AudioEmbeddingRepository()
    repository.save(connection, music_id, result())
    other = result(2.0 if change == 'vector' else 1.0)
    if change == 'hash':
        other.metadata['source_sha256'] = 'b' * 64
    if change == 'profile':
        other.metadata['preprocessing_version'] = 'test-v2'
    with pytest.raises(EmbeddingConflict):
        repository.save(connection, music_id, other)
    assert connection.execute('SELECT embedding::text FROM ai_embeddings.audio_embeddings WHERE music_id = %s',
                              (music_id,)).fetchone()[0] == '[1,1,1,1]'


def test_database_enforces_vector_dimension(connection):
    music_id = 'test-' + uuid.uuid4().hex
    AudioEmbeddingRepository().save(connection, music_id, result())
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute('UPDATE ai_embeddings.audio_embeddings SET dimension = 3 WHERE music_id = %s', (music_id,))


def test_same_file_can_belong_to_different_music_ids(connection):
    repository = AudioEmbeddingRepository()
    assert repository.save(connection, 'test-' + uuid.uuid4().hex, result()).created
    assert repository.save(connection, 'test-' + uuid.uuid4().hex, result()).created


def test_save_is_rolled_back_when_transaction_fails():
    music_id = 'test-rollback-' + uuid.uuid4().hex
    with pytest.raises(RuntimeError, match='later failure'):
        with connect_database() as connection:
            AudioEmbeddingRepository().save(connection, music_id, result())
            raise RuntimeError('later failure')
    with connect_database() as connection:
        assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings WHERE music_id = %s',
                                  (music_id,)).fetchone()[0] == 0


def test_concurrent_identical_requests_create_one_row():
    music_id = 'test-concurrent-' + uuid.uuid4().hex
    def save(_):
        with connect_database() as connection:
            return AudioEmbeddingRepository().save(connection, music_id, result()).created
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(save, range(2))) == [False, True]
        with connect_database() as connection:
            assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings WHERE music_id = %s',
                                      (music_id,)).fetchone()[0] == 1
    finally:
        with connect_database() as connection:
            connection.execute('DELETE FROM ai_embeddings.audio_embeddings WHERE music_id = %s', (music_id,))


def test_text_embedding_roundtrip_reuse_profile_separation_and_conflict(connection):
    repository = TextEmbeddingRepository()
    first = text_result()
    saved = repository.save(connection, first)
    assert saved.created
    assert not repository.save(connection, first).created
    row = repository.get(connection, saved.query_text_sha256, saved.generation_profile_sha256)
    assert row['dimension'] == TEXT_EMBEDDING_DIMENSION
    assert row['generation_version'] == GENERATION_VERSION
    assert row['metadata']['query_text_sha256'] == 'b' * 64

    other_profile = text_result(generation_version='text-test-v2')
    assert repository.save(connection, other_profile).created
    with pytest.raises(EmbeddingConflict):
        repository.save(connection, text_result(value=2.0))


def test_text_query_search_excludes_incompatible_audio_profiles(connection):
    suffix = uuid.uuid4().hex
    audio_repository = AudioEmbeddingRepository()
    matching = result()
    matching.metadata['checkpoint_revision'] = CALIBRATION_CHECKPOINT_REVISION
    matching.metadata['checkpoint_sha256'] = CALIBRATION_CHECKPOINT_SHA256
    matching.metadata['preprocessing_version'] = PREPROCESSING_VERSION
    other_revision = result()
    other_revision.metadata.update({
        'source_sha256': '9' * 64, 'checkpoint_revision': '9' * 40,
        'checkpoint_sha256': '9' * 64,
        'preprocessing_version': PREPROCESSING_VERSION,
    })
    audio_repository.save(connection, 'test-text-match-' + suffix, matching)
    audio_repository.save(connection, 'test-text-mismatch-' + suffix, other_revision)

    found = TextEmbeddingRepository().search_audio(connection, text_result())
    returned_ids = {item['music_id'] for item in found['results']}
    assert 'test-text-match-' + suffix in returned_ids
    assert 'test-text-mismatch-' + suffix not in returned_ids
