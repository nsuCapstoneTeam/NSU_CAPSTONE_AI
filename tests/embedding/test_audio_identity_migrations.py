"""개별 임시 DB에서 migration을 검증하며 기존 DB의 행은 사용하지 않는다."""

import os
import shutil
import uuid

import psycopg
from psycopg import sql
import pytest
import json

from app.core import migrations
from app.core.config import DatabaseSettings
from app.core.database import connect_database
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
from app.repository.embedding_repository import (
    AudioEmbeddingRepository,
    generation_profile_sha256,
)


pytestmark = pytest.mark.skipif(os.environ.get('RUN_IDENTITY_MIGRATION_TESTS') != '1',
                                reason='Explicit isolated migration database opt-in required')


@pytest.fixture
def migration_database(monkeypatch):
    settings = DatabaseSettings.from_environment()
    name = 'identity_migration_' + uuid.uuid4().hex
    # CREATE/DROP 대상은 이 fixture가 생성한 무작위 DB 하나뿐이다.
    with psycopg.connect(host=settings.host, port=settings.port, dbname=settings.name,
                         user=settings.user, password=settings.password, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            monkeypatch.setenv('DB_NAME', name)
            with connect_database() as connection:
                connection.execute('CREATE EXTENSION vector')
            yield name
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def test_fresh_migrations_rerun_and_identity_catalog(migration_database):
    expected = ['0001_audio_embeddings.sql', '0002_text_embeddings.sql',
                '0003_audio_embedding_identity.sql']
    assert migrations.apply_migrations() == expected
    assert migrations.apply_migrations() == []
    with connect_database() as connection:
        assert connection.execute('SELECT uuid_extract_version(uuidv7())').fetchone()[0] == 7
        columns = {row[0]: row[1:] for row in connection.execute("""SELECT column_name, udt_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='ai_embeddings' AND table_name='audio_embeddings'""").fetchall()}
        assert columns['id'][0:2] == ('uuid', 'NO')
        assert 'uuidv7()' in columns['id'][2]
        assert columns['audio_revision'] == ('int8', 'NO', None)
        assert columns['music_id'][0:2] == ('text', 'NO')
        assert columns['generation_profile_sha256'][0:2] == ('text', 'NO')
        from scripts.database.validate_audio_embedding_postgres import schema_evidence
        assert schema_evidence(connection)['status'] == 'PASS'
        constraints = [r[0] for r in connection.execute("""SELECT pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='ai_embeddings.audio_embeddings'::regclass""")]
        for fragment in ('PRIMARY KEY (id)', 'UNIQUE (music_id, audio_revision, generation_profile_sha256)',
                         'FOREIGN KEY (music_id, audio_revision, source_sha256)',
                         'vector_dims(embedding) = dimension', 'vector_norm(embedding)',
                         'audio_revision >= 1', 'uuid_extract_version(id)'):
            assert any(fragment in c for c in constraints)
        source_constraints = [r[0] for r in connection.execute("""SELECT pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='ai_embeddings.audio_sources'::regclass""")]
        assert any('PRIMARY KEY (music_id, audio_revision)' in c for c in source_constraints)
        assert any('UNIQUE (music_id, audio_revision, source_sha256)' in c for c in source_constraints)
        indexes = [r[0] for r in connection.execute("""SELECT indexdef FROM pg_indexes
            WHERE schemaname='ai_embeddings'""")]
        assert any('audio_embeddings_source_sha256_idx' in i for i in indexes)
        assert any('music_id, audio_revision, generation_profile_sha256' in i for i in indexes)
        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.transaction():
                connection.execute('INSERT INTO ai_embeddings.audio_sources VALUES (%s, 0, %s)',
                                   ('invalid-revision', 'a' * 64))
        with pytest.raises(psycopg.errors.NotNullViolation):
            with connection.transaction():
                connection.execute('INSERT INTO ai_embeddings.audio_sources VALUES (%s, NULL, %s)',
                                   ('missing-revision', 'a' * 64))


def test_existing_rows_require_mapping_and_leave_schema_unchanged(migration_database, monkeypatch, tmp_path):
    production_directory = migrations.MIGRATION_DIRECTORY
    for name in ('0001_audio_embeddings.sql', '0002_text_embeddings.sql'):
        shutil.copyfile(production_directory / name, tmp_path / name)
    monkeypatch.setattr(migrations, 'MIGRATION_DIRECTORY', tmp_path)
    migrations.apply_migrations()
    with connect_database() as connection:
        connection.execute("""INSERT INTO ai_embeddings.audio_embeddings
            (music_id, source_sha256, model, model_version, preprocessing_version,
             dimension, embedding, generation_profile, metadata)
            VALUES ('legacy-music', %s, 'fixture', '1', 'fixture', 2, '[1,0]', '{}', '{}')""", ('a' * 64,))
    monkeypatch.setattr(migrations, 'MIGRATION_DIRECTORY', production_directory)
    with pytest.raises(psycopg.Error, match='audio_revision_mapping_required'):
        migrations.apply_migrations()
    with connect_database() as connection:
        assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone()[0] == 1
        assert connection.execute("SELECT to_regclass('ai_embeddings.audio_sources')").fetchone()[0] is None
        assert connection.execute("""SELECT count(*) FROM information_schema.columns
            WHERE table_schema='ai_embeddings' AND table_name='audio_embeddings'
              AND column_name='audio_revision'""").fetchone()[0] == 0
        assert connection.execute('SELECT count(*) FROM ai_embeddings.schema_migrations').fetchone()[0] == 2


def test_checksum_change_is_rejected(migration_database, monkeypatch, tmp_path):
    migrations.apply_migrations()
    for source in migrations.MIGRATION_DIRECTORY.glob('*.sql'):
        shutil.copyfile(source, tmp_path / source.name)
    first = tmp_path / '0001_audio_embeddings.sql'
    first.write_text(first.read_text(encoding='utf-8') + '\n-- checksum fixture\n', encoding='utf-8')
    monkeypatch.setattr(migrations, 'MIGRATION_DIRECTORY', tmp_path)
    with pytest.raises(RuntimeError, match='migration_checksum_mismatch'):
        migrations.apply_migrations()


def test_failed_ddl_rolls_back_tables_and_history(migration_database, monkeypatch, tmp_path):
    for source in migrations.MIGRATION_DIRECTORY.glob('*.sql'):
        shutil.copyfile(source, tmp_path / source.name)
    (tmp_path / '0004_failure_fixture.sql').write_text('SELECT missing_fixture_function();', encoding='utf-8')
    monkeypatch.setattr(migrations, 'MIGRATION_DIRECTORY', tmp_path)
    with pytest.raises(psycopg.errors.UndefinedFunction):
        migrations.apply_migrations()
    with connect_database() as connection:
        assert connection.execute("SELECT to_regclass('ai_embeddings.audio_embeddings')").fetchone()[0] is None
        assert connection.execute("SELECT to_regclass('ai_embeddings.schema_migrations')").fetchone()[0] is None


def test_validation_helpers_roundtrip_new_identity_schema(migration_database):
    from scripts.database import validate_audio_embedding_postgres as tool
    migrations.apply_migrations()
    with connect_database() as connection:
        assert tool.schema_evidence(connection)['status'] == 'PASS'
        cases = tool.synthetic_checks(connection, tool.AudioEmbeddingRepository(), 'identity-helper-')
        assert all(case['status'] == 'PASS' for case in cases)
        connection.rollback()
        inputs = [({'track_id': str(i)}, tool.synthetic_result(values, str(i)))
                  for i, values in enumerate(([1, 0, 0], [0, 1, 0], [-1, 0, 0]))]
        measurement = tool.measure_transaction(connection, inputs, 'identity-measure-')
        assert measurement['status'] == 'PASS'
        assert len(measurement['cosine_comparisons']) == 6
        connection.rollback()


def test_candidate_compatibility_batch_uses_exact_pairs_and_profile_count(migration_database, monkeypatch):
    migrations.apply_migrations()
    implementation = {
        'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
    }
    text_profile = {
        'generation_version': GENERATION_VERSION,
        'embedding_generation_profile': GENERATION_PROFILE,
        'model': 'MSCLAP', 'model_version': MODEL_VERSION,
        'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
        'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
        'msclap_implementation': implementation,
        'text_encoder': {
            'model_id': TEXT_ENCODER_MODEL_ID, 'revision': TEXT_ENCODER_REVISION,
            'config_sha256': TEXT_ENCODER_TOKENIZER_FILE_SHA256['config.json'],
            'model_file': 'model.safetensors', 'model_file_sha256': TEXT_ENCODER_MODEL_SHA256,
            'tokenizer_id': TEXT_ENCODER_MODEL_ID, 'tokenizer_revision': TEXT_ENCODER_REVISION,
            'tokenizer_files_sha256': TEXT_ENCODER_TOKENIZER_FILE_SHA256,
            'tokenizer_runtime_sha256': '1' * 64,
        },
        'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION},
        'dimension': TEXT_EMBEDDING_DIMENSION, 'dtype': 'torch.float32',
        'text_preprocessing': {
            'encoder_api': 'CLAP.get_text_embeddings', 'text_model': TEXT_ENCODER_MODEL_ID,
            'text_model_revision': TEXT_ENCODER_REVISION, 'token_limit': 77,
            'truncation': 'rejected', 'normalization': 'none; raw MSCLAP Text Embedding',
        },
    }
    monkeypatch.setattr('app.repository.embedding_repository.prepare_text_embedding',
                        lambda _: (None, text_profile, None, None))

    def audio_profile(**changes):
        profile = {
            'model': 'MSCLAP', 'model_version': MODEL_VERSION,
            'checkpoint_revision': CALIBRATION_CHECKPOINT_REVISION,
            'checkpoint_sha256': CALIBRATION_CHECKPOINT_SHA256,
            'msclap_implementation': implementation,
            'packages': {'msclap': CALIBRATION_MSCLAP_PACKAGE_VERSION, 'torch': 'test'},
            'preprocessing_version': PREPROCESSING_VERSION,
            'preprocessing': {'analysis_duration_seconds': 56},
            'dimension': TEXT_EMBEDDING_DIMENSION, 'dtype': 'torch.float32',
            'device': 'cpu',
        }
        profile.update(changes)
        return profile

    music_ids = {key: 'compat-' + uuid.uuid4().hex for key in ('one', 'ambiguous', 'incompatible', 'source_only')}
    with connect_database() as connection:
        def insert_source(music_id, revision):
            connection.execute('''INSERT INTO ai_embeddings.audio_sources VALUES (%s, %s, %s)
                ON CONFLICT (music_id, audio_revision) DO NOTHING''',
                               (music_id, revision, 'a' * 64))

        def insert_embedding(music_id, revision, profile):
            insert_source(music_id, revision)
            connection.execute('''INSERT INTO ai_embeddings.audio_embeddings
                (music_id, audio_revision, source_sha256, model, model_version,
                 preprocessing_version, dimension, embedding, generation_profile,
                 generation_profile_sha256, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, '{}'::jsonb)''',
                (music_id, revision, 'a' * 64, profile['model'], profile['model_version'],
                 profile['preprocessing_version'], TEXT_EMBEDDING_DIMENSION,
                 json.dumps([1.0] + [0.0] * (TEXT_EMBEDDING_DIMENSION - 1)),
                 json.dumps(profile), generation_profile_sha256(profile)))

        insert_embedding(music_ids['one'], 1, audio_profile())
        insert_embedding(music_ids['ambiguous'], 3, audio_profile(device='cpu'))
        insert_embedding(music_ids['ambiguous'], 3, audio_profile(device='cuda'))
        insert_embedding(music_ids['incompatible'], 2, audio_profile(model='OTHER'))
        insert_source(music_ids['source_only'], 5)

        candidates = [
            (music_ids['one'], 1),
            (music_ids['ambiguous'], 3),
            (music_ids['incompatible'], 2),
            (music_ids['source_only'], 5),
            ('unknown-' + uuid.uuid4().hex, 1),
            (music_ids['one'], 2),
            (music_ids['one'], 1),
        ]
        results = AudioEmbeddingRepository().check_candidate_compatibility(
            connection, candidates, object())
        assert [result.status.value for result in results] == [
            'COMPATIBLE', 'AMBIGUOUS_PROFILE', 'INCOMPATIBLE_PROFILE',
            'MISSING_EMBEDDING', 'MISSING_SOURCE', 'MISSING_SOURCE', 'DUPLICATE',
        ]
        assert results[0].compatible_candidate.music_id == music_ids['one']
        assert results[0].compatible_candidate.audio_revision == 1
        assert results[0].compatible_candidate.embedding_id
        assert results[0].compatible_candidate.generation_profile_sha256
        connection.rollback()
