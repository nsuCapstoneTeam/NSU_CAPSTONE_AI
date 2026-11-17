"""명시적으로 지정한 실제 DB에서 제약과 트랜잭션을 검증하고 테스트 행을 정리한다."""

import os
import json
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
    assert repository.save(connection, music_id, 1, result()).created
    assert not repository.save(connection, music_id, 1, result()).created
    row = connection.execute('''SELECT dimension, vector_dims(embedding), metadata,
        1 - (embedding <=> %s::vector) FROM ai_embeddings.audio_embeddings WHERE music_id = %s''',
        (json.dumps([1] * TEXT_EMBEDDING_DIMENSION), music_id)).fetchone()
    assert row[0:2] == (TEXT_EMBEDDING_DIMENSION, TEXT_EMBEDDING_DIMENSION)
    assert row[2]['source_sha256'] == 'a' * 64
    assert row[3] == pytest.approx(1.0)


@pytest.mark.parametrize('change', ['hash', 'vector'])
def test_conflict_preserves_existing_row(connection, change):
    music_id = 'test-' + uuid.uuid4().hex
    repository = AudioEmbeddingRepository()
    repository.save(connection, music_id, 1, result())
    other = result(2.0 if change == 'vector' else 1.0)
    if change == 'hash':
        other.metadata['source_sha256'] = 'b' * 64
    with pytest.raises(EmbeddingConflict):
        repository.save(connection, music_id, 1, other)
    assert connection.execute('SELECT embedding::text FROM ai_embeddings.audio_embeddings WHERE music_id = %s',
                              (music_id,)).fetchone()[0] == json.dumps([1] * TEXT_EMBEDDING_DIMENSION, separators=(',', ':'))


def test_database_enforces_vector_dimension(connection):
    music_id = 'test-' + uuid.uuid4().hex
    AudioEmbeddingRepository().save(connection, music_id, 1, result())
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute('UPDATE ai_embeddings.audio_embeddings SET dimension = 3 WHERE music_id = %s', (music_id,))


def test_same_file_can_belong_to_different_music_ids(connection):
    repository = AudioEmbeddingRepository()
    assert repository.save(connection, 'test-' + uuid.uuid4().hex, 1, result()).created
    assert repository.save(connection, 'test-' + uuid.uuid4().hex, 1, result()).created


def test_save_is_rolled_back_when_transaction_fails():
    music_id = 'test-rollback-' + uuid.uuid4().hex
    with pytest.raises(RuntimeError, match='later failure'):
        with connect_database() as connection:
            AudioEmbeddingRepository().save(connection, music_id, 1, result())
            raise RuntimeError('later failure')
    with connect_database() as connection:
        assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings WHERE music_id = %s',
                                  (music_id,)).fetchone()[0] == 0


def test_concurrent_identical_requests_create_one_row():
    music_id = 'test-concurrent-' + uuid.uuid4().hex
    def save(_):
        with connect_database() as connection:
            return AudioEmbeddingRepository().save(connection, music_id, 1, result())
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            saved = list(pool.map(save, range(2)))
            assert sorted(row.created for row in saved) == [False, True]
            assert saved[0].id == saved[1].id
        with connect_database() as connection:
            assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings WHERE music_id = %s',
                                      (music_id,)).fetchone()[0] == 1
            assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_sources WHERE music_id = %s',
                                      (music_id,)).fetchone()[0] == 1
            assert connection.execute('''SELECT count(*) FROM ai_embeddings.audio_embeddings e
                LEFT JOIN ai_embeddings.audio_sources s
                  ON s.music_id = e.music_id AND s.audio_revision = e.audio_revision
                 AND s.source_sha256 = e.source_sha256
                WHERE e.music_id = %s AND s.music_id IS NULL''', (music_id,)).fetchone()[0] == 0
    finally:
        with connect_database() as connection:
            connection.execute('DELETE FROM ai_embeddings.audio_embeddings WHERE music_id = %s', (music_id,))
            connection.execute('DELETE FROM ai_embeddings.audio_sources WHERE music_id = %s', (music_id,))


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
    audio_repository.save(connection, 'test-text-match-' + suffix, 1, matching)
    audio_repository.save(connection, 'test-text-mismatch-' + suffix, 1, other_revision)

    found = TextEmbeddingRepository().search_audio(connection, text_result())
    returned_ids = {item['music_id'] for item in found['results']}
    assert 'test-text-match-' + suffix in returned_ids
    assert 'test-text-mismatch-' + suffix not in returned_ids



def test_revision_profile_exact_lookup_and_uuid_reuse(connection):
    repository = AudioEmbeddingRepository()
    music_id = 'test-identity-' + uuid.uuid4().hex
    original = result()
    first = repository.save(connection, music_id, 1, original)
    reused = repository.save(connection, music_id, 1, original)
    assert uuid.UUID(first.id).version == 7
    assert reused.id == first.id and not reused.created
    second = repository.save(connection, music_id, 9, original)
    assert second.id != first.id
    other = result()
    other.metadata['preprocessing_version'] = 'test-v2'
    another_profile = repository.save(connection, music_id, 1, other)
    assert another_profile.id not in {first.id, second.id}
    for saved in (first, second, another_profile):
        found = repository.get(connection, music_id, saved.audio_revision, saved.generation_profile_sha256)
        assert found['id'] == saved.id
        assert found['source_sha256'] == 'a' * 64
    assert repository.get(connection, music_id, 2, first.generation_profile_sha256) is None
    before = repository.get(connection, music_id, 1, first.generation_profile_sha256)
    with pytest.raises(EmbeddingConflict):
        repository.save(connection, music_id, 1, result(2.0))
    assert repository.get(connection, music_id, 1, first.generation_profile_sha256) == before
    bad_source = result()
    bad_source.metadata.update(source_sha256='b' * 64, preprocessing_version='test-v3')
    with pytest.raises(EmbeddingConflict):
        repository.save(connection, music_id, 1, bad_source)
    assert repository.get(connection, music_id, 1, first.generation_profile_sha256) == before


def test_savepoint_rolls_back_source_when_embedding_insert_fails(connection):
    music_id = 'test-partial-' + uuid.uuid4().hex
    connection.execute('''CREATE FUNCTION pg_temp.reject_audio_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture_insert_failure'; END $$''')
    connection.execute('''CREATE TRIGGER fixture_reject_insert BEFORE INSERT ON ai_embeddings.audio_embeddings
        FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_audio_insert()''')
    with pytest.raises(psycopg.Error, match='fixture_insert_failure'):
        AudioEmbeddingRepository().save(connection, music_id, 1, result())
    assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_sources WHERE music_id=%s',
                              (music_id,)).fetchone()[0] == 0


def test_database_rejects_cross_profile_source_mismatch(connection):
    repository = AudioEmbeddingRepository()
    music_id = 'test-fk-' + uuid.uuid4().hex
    saved = repository.save(connection, music_id, 1, result())
    with connection.transaction():
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with connection.transaction():
                connection.execute('UPDATE ai_embeddings.audio_embeddings SET source_sha256=%s WHERE id=%s',
                                   ('b' * 64, saved.id))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            connection.execute('''INSERT INTO ai_embeddings.audio_sources VALUES (%s, 1, %s)''',
                               (music_id, 'b' * 64))


def test_concurrent_different_sources_preserve_one_identity():
    music_id = 'test-source-race-' + uuid.uuid4().hex
    def save(source):
        candidate = result()
        candidate.metadata['source_sha256'] = source * 64
        try:
            with connect_database() as connection:
                return AudioEmbeddingRepository().save(connection, music_id, 1, candidate).source_sha256
        except EmbeddingConflict:
            return 'conflict'
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save, ['a', 'b']))
        assert outcomes.count('conflict') == 1
        with connect_database() as connection:
            rows = connection.execute('SELECT source_sha256 FROM ai_embeddings.audio_sources WHERE music_id=%s',
                                      (music_id,)).fetchall()
            assert len(rows) == 1 and rows[0][0] in outcomes
            assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings WHERE music_id=%s',
                                      (music_id,)).fetchone()[0] == 1
            assert connection.execute('''SELECT count(*) FROM ai_embeddings.audio_embeddings e
                LEFT JOIN ai_embeddings.audio_sources s
                  ON s.music_id = e.music_id AND s.audio_revision = e.audio_revision
                 AND s.source_sha256 = e.source_sha256
                WHERE e.music_id = %s AND s.music_id IS NULL''', (music_id,)).fetchone()[0] == 0
    finally:
        with connect_database() as connection:
            connection.execute('DELETE FROM ai_embeddings.audio_embeddings WHERE music_id=%s', (music_id,))
            connection.execute('DELETE FROM ai_embeddings.audio_sources WHERE music_id=%s', (music_id,))
