import csv
import json
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from scripts.matching import benchmark_candidate_ranking as benchmark


def test_dataset_is_deterministic_finite_normalized_with_exact_ties():
    first = benchmark.synthetic_vectors(20)
    assert first.shape == (20, 1024)
    assert first.dtype == np.float32
    assert np.array_equal(first, benchmark.synthetic_vectors(20))
    assert np.isfinite(first).all()
    assert np.linalg.norm(first, axis=1) == pytest.approx(np.ones(20), abs=1e-6)
    assert first[4, 0] == -1
    assert np.array_equal(first[5], first[6])


def test_percentiles_use_linear_interpolation_and_report_small_sample_limit():
    assert benchmark.percentile([40, 10, 30, 20], 0.5) == 25
    assert benchmark.percentile([10, 20], 0.95) == pytest.approx(19.5)
    assert benchmark.percentile([], 0.5) is None
    assert benchmark.summarize([10, 20])['p99_exploratory']
    assert benchmark.summarize([])['count'] == 0


def test_query_metadata_passes_actual_production_validation():
    metadata, profile, _, vector = benchmark.prepare_text_embedding(benchmark.query_result())
    assert metadata['synthetic'] is True
    assert len(json.loads(vector)) == 1024
    from app.repository.embedding_repository import text_audio_profiles_compatible
    assert text_audio_profiles_compatible(profile, benchmark.audio_profile())


@pytest.mark.parametrize('status', list(benchmark.Status)[1:])
def test_invalid_diagnostic_never_invokes_ranking(monkeypatch, status):
    repository = Mock()
    repository.check_candidate_compatibility.return_value = [
        SimpleNamespace(status=status, compatible_candidate=None)]
    def diagnose(connection, pairs, query):
        connection.observations.append({'parameter_count': 2, 'execute_ns': 1, 'fetch_ns': 1})
        return repository.check_candidate_compatibility.return_value
    repository.check_candidate_compatibility.side_effect = diagnose
    monkeypatch.setattr(benchmark, 'AudioEmbeddingRepository', lambda: repository)
    diagnoses, ranking, _, observations = benchmark.run_request(Mock(), [('music', 1)], object())
    assert diagnoses[0].status == status
    assert ranking == []
    assert len(observations) == 1
    repository.rank_candidates.assert_not_called()


def test_empty_input_uses_no_query(monkeypatch):
    repository = Mock()
    repository.check_candidate_compatibility.return_value = []
    repository.rank_candidates.return_value = []
    monkeypatch.setattr(benchmark, 'AudioEmbeddingRepository', lambda: repository)
    _, ranking, _, observations = benchmark.run_request(Mock(), [], object())
    assert ranking == []
    assert observations == []


def test_json_and_csv_preserve_raw_ns_and_no_extra_columns(tmp_path):
    sample = dict(zip(benchmark.CSV_FIELDS,
        ['scale',10,1,1,0,'reuse','total',123,True,'']))
    benchmark.write_results(tmp_path, {'synthetic':True}, [sample])
    assert json.loads((tmp_path/'benchmark-result.json').read_text()) == {'synthetic':True}
    with (tmp_path/'latency-samples.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]['elapsed_ns'] == '123'


def test_isolated_database_refuses_unapproved_target(monkeypatch):
    monkeypatch.setenv('DB_NAME', 'shared_database')
    with pytest.raises(ValueError, match='benchmark_admin'):
        with benchmark.isolated_database():
            pytest.fail('must not enter')


def test_cleanup_restores_environment_and_drops_only_created_name(monkeypatch):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    monkeypatch.setenv('DB_NAME','benchmark_admin')
    monkeypatch.setattr(benchmark,'connect_database',lambda:connection)
    with pytest.raises(RuntimeError, match='probe'):
        with benchmark.isolated_database() as name:
            assert name.startswith('nsuai32_')
            raise RuntimeError('probe')
    import os
    assert os.environ['DB_NAME'] == 'benchmark_admin'
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert any('DROP DATABASE' in statement and name in statement for statement in statements)
    assert not any('DROP DATABASE' in statement and 'benchmark_admin' in statement for statement in statements)
