import json
import subprocess
import sys

from scripts.matching.validate_calibration_event_queries import duplicate_query_ids


def test_duplicate_query_ids_reports_only_repeated_ids():
    event_queries = {
        'queries': [
            {'query_id': 'event-01'},
            {'query_id': 'event-02'},
            {'query_id': 'event-01'},
        ]
    }

    assert duplicate_query_ids(event_queries) == ['event-01']


def test_unique_query_ids_pass_cli_with_twenty_queries(tmp_path):
    path = tmp_path / 'event-queries.json'
    path.write_text(
        json.dumps({'queries': [{'query_id': f'event-{index:02}'} for index in range(1, 21)]}),
        encoding='utf-8',
    )

    result = subprocess.run(
        [sys.executable, 'scripts/matching/validate_calibration_event_queries.py', str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert 'Unique query_id check passed: 20 queries.' in result.stdout


def test_duplicate_query_id_fails_cli_even_with_twenty_queries(tmp_path):
    path = tmp_path / 'event-queries.json'
    queries = [{'query_id': f'event-{index:02}'} for index in range(1, 21)]
    queries[-1]['query_id'] = queries[0]['query_id']
    path.write_text(json.dumps({'queries': queries}), encoding='utf-8')

    result = subprocess.run(
        [sys.executable, 'scripts/matching/validate_calibration_event_queries.py', str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert 'Duplicate query_id values: event-01' in result.stderr
