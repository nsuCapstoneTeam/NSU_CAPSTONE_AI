"""명시적 opt-in과 live guard를 통과한 전용 DB에서만 실행한다."""

import os
import uuid

import pytest

from scripts.database import validate_audio_embedding_postgres as tool

pytestmark = pytest.mark.skipif(os.environ.get('RUN_AUDIO_POSTGRES_VALIDATION_TESTS') != '1',
                                reason='전용 validation DB 명시적 opt-in 필요')


@pytest.fixture
def connection():
    expected = os.environ.get('AUDIO_VALIDATION_EXPECTED_DATABASE', '')
    # identity 확인 전 migration/write는 불가능하다.
    probe, _ = tool.connect_validation(expected)
    probe.close()
    tool.apply_validated_migrations(expected)
    connection, _ = tool.connect_validation(expected)
    try:
        assert connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone()[0] == 0
        yield connection
    finally:
        connection.rollback()
        connection.close()
        fresh, _ = tool.connect_validation(expected)
        try:
            assert fresh.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone()[0] == 0
        finally:
            fresh.rollback()
            fresh.close()


def test_production_schema(connection):
    assert tool.schema_evidence(connection)['status'] == 'PASS'


def test_synthetic_meaning_tie_compatibility_and_conflict(connection):
    rows = tool.synthetic_checks(connection, tool.AudioEmbeddingRepository(), 'validation-'+uuid.uuid4().hex+'-')
    assert all(row['status'] == 'PASS' for row in rows)
    assert len([r for r in rows if r['case'].startswith('mismatch_')]) == 14


def test_repository_measurement_without_model_inference(connection):
    inputs = [({'track_id': str(i)}, tool.synthetic_result(values, str(i)))
              for i, values in enumerate(([1, 0, 0], [0, 1, 0], [-1, 0, 0]))]
    measured = tool.measure_transaction(connection, inputs, 'validation-'+uuid.uuid4().hex+'-')
    assert measured['status'] == 'PASS'
    assert len(measured['cosine_comparisons']) == 6
    assert all(r['exact_equal'] for r in measured['roundtrips'])