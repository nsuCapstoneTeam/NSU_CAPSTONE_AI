import json
from pathlib import Path

import pytest

from scripts.matching.validate_calibration import main


CALIBRATION_DIR = (
    Path(__file__).resolve().parents[2]
    / 'docs'
    / 'experiments'
    / 'audio-similarity-calibration'
)


def _load_json(name):
    return json.loads((CALIBRATION_DIR / name).read_text(encoding='utf-8'))


def _run_validator(tmp_path, capsys, *, manifest=None, event_queries=None):
    paths = {
        'manifest': tmp_path / 'manifest.json',
        'event-queries': tmp_path / 'event-queries.json',
    }
    paths['manifest'].write_text(json.dumps(manifest or _load_json('manifest.json')), encoding='utf-8')
    paths['event-queries'].write_text(
        json.dumps(event_queries or _load_json('event-queries.json')),
        encoding='utf-8',
    )
    result = main([
        '--manifest', str(paths['manifest']),
        '--event-queries', str(paths['event-queries']),
    ])
    return result, capsys.readouterr()


def test_current_manifest_and_event_queries_pass(capsys):
    assert main([]) == 0
    assert 'Calibration validation passed' in capsys.readouterr().out


def test_missing_manifest_required_field_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest.pop('dataset_version')

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'dataset_version' in output.err


def test_event_query_schema_violation_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    event_queries['queries'][0]['unexpected_field'] = True

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'Additional properties are not allowed' in output.err


@pytest.mark.parametrize('identifier', ['sample_id', 'query_id'])
def test_duplicate_identifiers_fail(tmp_path, capsys, identifier):
    manifest = _load_json('manifest.json')
    event_queries = _load_json('event-queries.json')
    if identifier == 'sample_id':
        manifest['samples'][1]['sample_id'] = manifest['samples'][0]['sample_id']
    else:
        event_queries['queries'][1]['query_id'] = event_queries['queries'][0]['query_id']

    result, output = _run_validator(
        tmp_path,
        capsys,
        manifest=manifest,
        event_queries=event_queries,
    )

    assert result == 1
    assert f'Duplicate {identifier} values:' in output.err


def test_active_query_not_reviewed_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['selection_status'] == 'active_v1')
    active['structured_interpretation']['review_status'] = 'not_reviewed'

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'reviewed_for_raw_support' in output.err


def test_complete_cohort_with_49_samples_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'].pop()

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert '50' in output.err


def test_complete_cohort_with_ineligible_sample_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['rights_status'] = 'excluded'

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'rights_status' in output.err


def test_complete_cohort_with_duration_below_60_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['source_catalog_duration'] = 59.9

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'source_catalog_duration' in output.err
