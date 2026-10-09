"""DB에 연결하지 않고 guard·측정·CLI 동작을 검증한다."""

import json
import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
import torch

from scripts.database import validate_audio_embedding_postgres as tool


@pytest.fixture
def validation_env(monkeypatch):
    for key, value in {'DB_HOST': '127.0.0.1', 'DB_PORT': '55432',
                       'DB_NAME': 'audio_embedding_validation', 'DB_USER': 'audio_validation',
                       'DB_PASSWORD': 'unit-test-secret'}.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(('phases', 'pytest_exit_code', 'expected'), [
    ([('setup', 'passed'), ('call', 'passed'), ('teardown', 'passed')], 0,
     {'passed': 1, 'failed': 0, 'skipped': 0}),
    ([('setup', 'failed'), ('teardown', 'passed')], 1,
     {'passed': 0, 'failed': 1, 'skipped': 0}),
    ([('setup', 'passed'), ('call', 'passed'), ('teardown', 'failed')], 1,
     {'passed': 0, 'failed': 1, 'skipped': 0}),
    ([('setup', 'skipped'), ('teardown', 'passed')], 0,
     {'passed': 0, 'failed': 0, 'skipped': 1}),
    ([('setup', 'passed'), ('call', 'failed'), ('teardown', 'failed')], 1,
     {'passed': 0, 'failed': 1, 'skipped': 0}),
])
def test_integration_test_counts_aggregate_all_phases_once(phases, pytest_exit_code, expected):
    counts = tool.IntegrationTestCounts()
    for phase, outcome in phases:
        counts.pytest_runtest_logreport(MagicMock(nodeid='test_fixture_case', when=phase, outcome=outcome))

    result = counts.summarize(pytest_exit_code)

    assert result['counts'] == expected
    assert result['exit_code'] == pytest_exit_code
    assert result['suite_failure'] is False


def test_integration_test_counts_turn_nonzero_exit_without_test_failure_into_failed():
    result = tool.IntegrationTestCounts().summarize(2)

    assert result['counts'] == {'passed': 0, 'failed': 1, 'skipped': 0}
    assert result['suite_failure'] is True
    assert result['exit_code'] == 2


@pytest.mark.parametrize(('process_exit_code', 'summary_exit_code', 'summary_failed', 'expected_exit', 'expected_status'), [
    (0, 0, 0, 0, 'PASS'),
    (1, 1, 0, 1, 'FAIL'),
    (0, 0, 1, 1, 'FAIL'),
])
def test_guarded_runner_keeps_report_failure_and_process_exit_consistent(
        monkeypatch, process_exit_code, summary_exit_code, summary_failed, expected_exit, expected_status):
    monkeypatch.setattr(tool, 'connect_validation', lambda expected: (MagicMock(), {}))
    summary = {'counts': {'passed': 1, 'failed': summary_failed, 'skipped': 0},
               'pytest_exit_code': summary_exit_code, 'exit_code': summary_exit_code,
               'suite_failure': False}
    completed = subprocess.CompletedProcess(
        args=[], returncode=process_exit_code,
        stdout='VALIDATION_TEST_RESULT='+json.dumps(summary)+'\n', stderr='')
    monkeypatch.setattr(tool.subprocess, 'run', lambda *args, **kwargs: completed)

    result = tool.run_guarded_integration_tests('audio_embedding_validation')

    assert result['exit_code'] == expected_exit
    assert result['status'] == expected_status
    assert (result['counts']['failed'] >= 1) is (expected_status == 'FAIL')


@pytest.mark.parametrize('key,value', [
    ('DB_HOST', 'host.docker.internal'), ('DB_HOST', 'remote-production'),
    ('DB_PORT', '5432'), ('DB_NAME', 'capstone_db'), ('DB_USER', 'capstone'),
    ('DB_PASSWORD', ''), ('DB_PORT', 'invalid'),
])
def test_unsafe_environment_never_connects(validation_env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    connect = MagicMock()
    monkeypatch.setattr(tool, 'connect_database', connect)
    with pytest.raises(tool.SafetyBlocked):
        tool.connect_validation('audio_embedding_validation')
    connect.assert_not_called()


@pytest.mark.parametrize('name', ['capstone_db', 'production', 'audio_embedding_validation;drop', ''])
def test_expected_database_cannot_name_development_db(validation_env, name):
    with pytest.raises(tool.SafetyBlocked):
        tool.validation_settings(name)


def test_no_environment_defaults(monkeypatch):
    for key in ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(tool.SafetyBlocked, match='fallback'):
        tool.validation_settings('audio_embedding_validation')


@pytest.mark.parametrize('index,value', [(0, 'capstone_db'), (1, 'other'), (2, 'other'), (3, None)])
def test_live_identity_mismatch_closes_without_write(validation_env, monkeypatch, index, value):
    connection = MagicMock()
    row = ['audio_embedding_validation', 'audio_validation', 'audio_validation', tool.DATABASE_MARKER, 'PostgreSQL test']
    row[index] = value
    connection.execute.return_value.fetchone.return_value = tuple(row)
    monkeypatch.setattr(tool, 'connect_database', lambda: connection)
    with pytest.raises(tool.SafetyBlocked):
        tool.connect_validation('audio_embedding_validation')
    connection.close.assert_called_once()
    sqls = [call.args[0] for call in connection.execute.call_args_list]
    assert sqls[0] == 'SET TRANSACTION READ ONLY'
    assert all(sql.startswith(('SET TRANSACTION READ ONLY', 'SELECT ')) for sql in sqls)


def test_verified_identity_rolls_back_readonly_probe(validation_env):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        'audio_embedding_validation', 'audio_validation', 'audio_validation', tool.DATABASE_MARKER, 'PostgreSQL test')
    identity = tool.guard_connection(connection, 'audio_embedding_validation', 'audio_validation')
    assert identity['identity_verified']
    assert 'audio_validation' not in json.dumps(identity)
    connection.rollback.assert_called_once()


def test_production_migration_reuses_guarded_connection(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(tool, 'connect_validation', lambda expected: (connection, {}))
    original = tool.migrations.connect_database
    def apply():
        assert tool.migrations.connect_database() is connection
        return ['0001_audio_embeddings.sql']
    monkeypatch.setattr(tool.migrations, 'apply_migrations', apply)
    assert tool.apply_validated_migrations('audio_embedding_validation') == ['0001_audio_embeddings.sql']
    assert tool.migrations.connect_database is original


@pytest.mark.parametrize(('migration_error', 'reason_code', 'migration_name'), [
    ('vector_extension_missing', 'vector_extension_missing', None),
    ('unknown_applied_migration', 'unknown_applied_migration', None),
    ('migration_checksum_mismatch: 0001_audio_embeddings.sql',
     'migration_checksum_mismatch', '0001_audio_embeddings.sql'),
])
def test_expected_migration_runtime_errors_are_structured_and_sanitized(
        monkeypatch, migration_error, reason_code, migration_name):
    monkeypatch.setattr(tool, 'connect_validation', lambda expected: (MagicMock(), {}))

    def fail_migration():
        raise RuntimeError(migration_error)

    monkeypatch.setattr(tool.migrations, 'apply_migrations', fail_migration)
    with pytest.raises(tool.MigrationFailure) as raised:
        tool.apply_validated_migrations('audio_embedding_validation')
    report = raised.value.to_report()
    assert report['stage'] == 'migration'
    assert report['reason_code'] == reason_code
    assert report.get('migration_name') == migration_name
    assert migration_error not in report['message']


def test_unrecognized_migration_runtime_error_is_not_hidden(monkeypatch):
    monkeypatch.setattr(tool, 'connect_validation', lambda expected: (MagicMock(), {}))
    monkeypatch.setattr(tool.migrations, 'apply_migrations',
                        lambda: (_ for _ in ()).throw(RuntimeError('unexpected defect')))
    with pytest.raises(RuntimeError, match='unexpected defect'):
        tool.apply_validated_migrations('audio_embedding_validation')


def test_cli_writes_structured_migration_failure_without_credentials(
        tmp_path, validation_env, monkeypatch, capsys):
    monkeypatch.setattr(tool, 'ROOT', tmp_path)
    monkeypatch.setattr(tool, 'audio_file_sha256', lambda path: 'a' * 64)
    monkeypatch.setattr(tool, 'environment_evidence', lambda: {})
    monkeypatch.setattr(tool, 'input_evidence', lambda: ([], {}))
    monkeypatch.setattr(tool, 'validation_settings', lambda expected: object())
    monkeypatch.setattr(
        tool, 'execute_validation',
        lambda *args, **kwargs: (_ for _ in ()).throw(tool.MigrationFailure(
            'unknown_applied_migration',
            'DB migration 이력에 현재 repository에서 찾을 수 없는 migration이 있습니다')))
    report_path = tmp_path/'docs/experiments/audio-embedding-postgres-validation/failure.json'

    assert tool.main([
        '--expected-database', 'audio_embedding_validation',
        '--report', str(report_path),
    ]) == 1

    report = json.loads(report_path.read_text(encoding='utf-8'))
    output = capsys.readouterr().out
    assert report['status'] == 'FAIL'
    assert report['failure'] == {
        'stage': 'migration',
        'reason_code': 'unknown_applied_migration',
        'message': 'DB migration 이력에 현재 repository에서 찾을 수 없는 migration이 있습니다',
    }
    assert 'unit-test-secret' not in output
    assert 'unit-test-secret' not in report_path.read_text(encoding='utf-8')


def test_nonzero_roundtrip_difference_requires_review():
    before = torch.tensor([[1.0, 0.5]])
    after = torch.tensor([[1.0, 0.5000001]])
    row = tool.roundtrip_metrics(before, after)
    assert row['status'] == 'REVIEW_REQUIRED'
    assert row['max_absolute_difference'] > 0 and row['rms_difference'] > 0 and row['l2_difference'] > 0
    assert row['before_digest'] != row['after_digest']


def test_exact_roundtrip_and_dimension_are_measured():
    vector = torch.tensor([[1.0, 0.0, 0.0, 0.0, 0.0]])
    row = tool.roundtrip_metrics(vector, vector.clone())
    assert row['status'] == 'PASS' and row['dimension'] == 5
    assert row['max_absolute_difference'] == row['rms_difference'] == row['l2_difference'] == 0


@pytest.mark.parametrize('vector', [torch.zeros(1, 2), torch.tensor([[float('nan'), 1.0]]), torch.ones(8, 2)])
def test_invalid_roundtrip_vector_rejected(vector):
    with pytest.raises(ValueError):
        tool.roundtrip_metrics(torch.ones(1, 2), vector)


def test_cosine_difference_within_approved_absolute_tolerance_passes():
    row = tool.cosine_record(0.8, 0.8, 0.20000001, 0.79999999, 0.79999999)
    assert row['status'] == 'PASS' and row['absolute_difference'] > 0
    assert row['numerical_parity_tolerance'] == {'absolute': 1e-6, 'relative': 0.0}


def test_cosine_difference_above_approved_absolute_tolerance_requires_review():
    row = tool.cosine_record(0.8, 0.8, 0.2, 0.8000011, 0.8000011)
    assert row['status'] == 'REVIEW_REQUIRED' and row['absolute_difference'] > 1e-6


def test_cosine_tolerance_is_absolute_only():
    # 차이가 tolerance를 넘으면 값의 크기와 무관하게 통과시키지 않는다.
    row = tool.cosine_record(0.8, 0.8, 0.2, 0.8000011, 0.8000011)
    assert row['status'] == 'REVIEW_REQUIRED'


@pytest.mark.parametrize('similarity,distance', [(1.0, 0.0), (0.0, 1.0), (-1.0, 2.0)])
def test_exact_cosine_meaning(similarity, distance):
    assert tool.cosine_record(similarity, similarity, distance, 1-distance, similarity)['status'] == 'PASS'


def test_ranking_uses_raw_cosine_and_byte_order_without_epsilon():
    scores = {'2': 0.5, '10': 0.5, 'A': 0.50000000001}
    row = tool.compare_rankings(list(scores), scores, ['A', '10', '2'])
    assert row['match'] and row['python_ranking'] == ['A', '10', '2']
    assert row['adjacent_candidate_gaps'][0]['python_gap'] > 0


def test_ranking_mismatch_records_gap():
    row = tool.compare_rankings(['a', 'b'], {'a': 0.8, 'b': 0.7}, ['b', 'a'])
    assert row['status'] == 'FAIL' and not row['match'] and row['adjacent_candidate_gaps']


def test_fail_dominates_review_status():
    assert tool.aggregate_status([{'status': 'PASS'}, {'status': 'REVIEW_REQUIRED'}]) == 'REVIEW_REQUIRED'
    assert tool.aggregate_status([{'status': 'FAIL'}, {'status': 'REVIEW_REQUIRED'}]) == 'FAIL'


def test_blocked_cli_does_not_migrate_or_infer(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, 'ROOT', tmp_path)
    monkeypatch.setattr(tool, 'audio_file_sha256', lambda path: 'a'*64)
    monkeypatch.setattr(tool, 'environment_evidence', lambda: {})
    monkeypatch.setattr(tool, 'input_evidence', lambda: ([], {}))
    for key in ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']:
        monkeypatch.delenv(key, raising=False)
    execute = MagicMock()
    monkeypatch.setattr(tool, 'execute_validation', execute)
    report = tmp_path/'datasets/blocked.json'
    assert tool.main(['--expected-database', 'audio_embedding_validation', '--report', str(report)]) == 4
    execute.assert_not_called()
    data = json.loads(report.read_text(encoding='utf-8'))
    assert data['status'] == 'BLOCKED' and data['execution']['db_validation'] == 'NOT_EXECUTED'


def test_cli_invalid_expected_db_nonzero_and_secret_not_printed(tmp_path):
    report = tool.ROOT/'datasets/audio-embedding-postgres-validation/results/unit-invalid-cli.json'
    # parser의 출력 경로 검사에서 실제 DB·입력 접근 전에 종료한다.
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m',
        'scripts.database.validate_audio_embedding_postgres', '--expected-database', 'capstone_db',
        '--report', str(tmp_path/'outside.json')], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 2
    assert 'unit-test-secret' not in result.stdout+result.stderr
    assert not report.exists()


def test_programming_error_not_hidden(tmp_path, validation_env, monkeypatch):
    monkeypatch.setattr(tool, 'ROOT', tmp_path)
    monkeypatch.setattr(tool, 'audio_file_sha256', lambda path: 'a'*64)
    monkeypatch.setattr(tool, 'environment_evidence', lambda: {})
    monkeypatch.setattr(tool, 'input_evidence', lambda: ([], {}))
    def broken(*args, **kwargs):
        raise TypeError('programming defect')
    monkeypatch.setattr(tool, 'execute_validation', broken)
    with pytest.raises(TypeError, match='programming defect'):
        tool.main(['--expected-database', 'audio_embedding_validation', '--report', str(tmp_path/'datasets/x.json')])

def test_live_mismatch_blocks_migration_and_generator(validation_env, monkeypatch):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = ('capstone_db', 'capstone', 'capstone', None, 'server')
    monkeypatch.setattr(tool, 'connect_database', lambda: connection)
    migration, generator = MagicMock(), MagicMock()
    monkeypatch.setattr(tool, 'apply_validated_migrations', migration)
    monkeypatch.setattr(tool, 'AudioEmbeddingGenerator', generator)
    with pytest.raises(tool.SafetyBlocked):
        tool.execute_validation('audio_embedding_validation', [], {})
    migration.assert_not_called()
    generator.assert_not_called()


def test_measurement_failure_still_verifies_fresh_connection_rollback(monkeypatch):
    probe, work, fresh = MagicMock(), MagicMock(), MagicMock()
    probe.execute.return_value.fetchone.side_effect = [('0.8.6',), (None,)]
    work.execute.return_value.fetchone.return_value = (0,)
    fresh.execute.return_value.fetchone.return_value = (0,)
    connections = iter([probe, work, fresh])
    monkeypatch.setattr(tool, 'connect_validation', lambda expected: (next(connections), {'identity_verified': True}))
    monkeypatch.setattr(tool, 'apply_validated_migrations', lambda expected: [])
    monkeypatch.setattr(tool, 'cache_identity', lambda path: {'microsoft--msclap': {'revision': 'synthetic', 'files': {'CLAP_weights_2023.pth': {'sha256': 'c'*64}}}})
    monkeypatch.setattr(tool, 'audio_file_sha256', lambda path: 'c'*64)
    monkeypatch.setattr(tool, 'schema_evidence', lambda conn: {})
    result = tool.synthetic_result([1, 0, 0], 'rollback', tool.PREPROCESSING_VERSION)
    result.metadata['checkpoint_path'] = __file__
    generator = MagicMock()
    generator.generate.return_value = result
    monkeypatch.setattr(tool, 'AudioEmbeddingGenerator', lambda: generator)
    def failed(*args):
        raise tool.CheckFailed('measurement failure')
    monkeypatch.setattr(tool, 'measure_transaction', failed)
    report = {'execution': {}}
    with pytest.raises(tool.CheckFailed, match='measurement failure'):
        tool.execute_validation('audio_embedding_validation', [{'track_id': 'x', 'path': 'unused', 'sha256': 'a'*64}], report)
    work.rollback.assert_called_once()
    work.close.assert_called_once()
    assert report['rollback']['fresh_connection'] and report['rollback']['remaining_validation_rows'] == 0
    fresh.close.assert_called_once()
