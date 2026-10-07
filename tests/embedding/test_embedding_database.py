"""명시적으로 지정한 실제 DB에서 제약과 트랜잭션을 검증하고 테스트 행을 정리한다."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
import torch

from app.core.database import connect_database
from app.embedding.audio_embedding import AudioEmbeddingResult
from app.repository.embedding_repository import AudioEmbeddingRepository, EmbeddingConflict


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
    return AudioEmbeddingResult(torch.full((1, 4), value), {
        'source_sha256': 'a' * 64, 'shape': [1, 4], 'dimension': 4,
        'model': 'MSCLAP', 'model_version': '2023', 'preprocessing_version': 'test-v1',
        'packages': {'torch': 'test'}, 'preprocessing': {
            'analysis_duration_seconds': 56, 'chunk_duration_seconds': 7,
            'chunk_count': 8, 'chunk_overlap_seconds': 0,
            'chunk_normalization': 'l2', 'aggregation': 'mean',
            'final_normalization': 'l2', 'channel_policy': 'arithmetic_mean_downmix_to_mono',
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
