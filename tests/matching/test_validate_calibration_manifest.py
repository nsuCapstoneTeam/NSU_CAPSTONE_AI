import json
import subprocess
import sys

from scripts.matching.validate_calibration_manifest import duplicate_sample_ids


def test_duplicate_sample_ids_reports_only_repeated_ids():
    manifest = {
        'samples': [
            {'sample_id': 'cal-a'},
            {'sample_id': 'cal-b'},
            {'sample_id': 'cal-a'},
        ]
    }

    assert duplicate_sample_ids(manifest) == ['cal-a']


def test_unique_sample_ids_pass_cli(tmp_path):
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps({'samples': [{'sample_id': f'cal-{index}'} for index in range(50)]}),
        encoding='utf-8',
    )

    result = subprocess.run(
        [sys.executable, 'scripts/matching/validate_calibration_manifest.py', str(manifest_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert 'Unique sample_id check passed: 50 samples.' in result.stdout


def test_duplicate_sample_ids_fail_cli(tmp_path):
    manifest_path = tmp_path / 'manifest.json'
    samples = [{'sample_id': f'cal-{index}'} for index in range(50)]
    samples[-1]['sample_id'] = samples[0]['sample_id']
    manifest_path.write_text(
        json.dumps({'samples': samples}),
        encoding='utf-8',
    )

    result = subprocess.run(
        [sys.executable, 'scripts/matching/validate_calibration_manifest.py', str(manifest_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert 'Duplicate sample_id values: cal-0' in result.stderr
