import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.matching.validate_calibration_manifest import (
    acquisition_preparation_errors,
    duplicate_sample_ids,
    duplicate_source_content_hashes,
)


def test_duplicate_sample_ids_reports_only_repeated_ids():
    manifest = {
        'samples': [
            {'sample_id': 'cal-a'},
            {'sample_id': 'cal-b'},
            {'sample_id': 'cal-a'},
        ]
    }

    assert duplicate_sample_ids(manifest) == ['cal-a']


def test_duplicate_source_content_hashes_detect_reused_audio_bytes():
    digest = 'a' * 64
    manifest = {
        'cohort_status': 'candidate_selection_complete',
        'samples': [
            {'sample_id': 'cal-a', 'source_sha256': digest},
            {'sample_id': 'cal-b', 'source_sha256': digest},
            {'sample_id': 'cal-c', 'source_sha256': None},
        ],
    }

    assert duplicate_source_content_hashes(manifest) == [digest]


def test_duplicate_source_content_hashes_are_checked_for_incomplete_cohorts():
    digest = 'b' * 64
    manifest = {
        'cohort_status': 'candidate_selection_incomplete',
        'samples': [
            {'sample_id': 'cal-a', 'source_sha256': digest},
            {'sample_id': 'cal-b', 'source_sha256': digest},
        ],
    }

    assert duplicate_source_content_hashes(manifest) == [digest]


def test_distinct_source_hashes_in_incomplete_cohort_pass():
    manifest = {
        'cohort_status': 'candidate_selection_incomplete',
        'samples': [
            {'sample_id': 'cal-a', 'source_sha256': 'a' * 64},
            {'sample_id': 'cal-b', 'source_sha256': 'b' * 64},
        ],
    }

    assert duplicate_source_content_hashes(manifest) == []


def test_null_and_blank_source_hashes_are_ignored():
    manifest = {
        'cohort_status': 'candidate_selection_incomplete',
        'samples': [
            {'sample_id': 'cal-a', 'source_sha256': None},
            {'sample_id': 'cal-b', 'source_sha256': None},
            {'sample_id': 'cal-c', 'source_sha256': ''},
            {'sample_id': 'cal-d', 'source_sha256': '   '},
        ],
    }

    assert duplicate_source_content_hashes(manifest) == []


def test_current_not_acquired_manifest_has_no_duplicate_source_hashes():
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / 'docs' / 'experiments' / 'audio-similarity-calibration' / 'manifest.json'
    )
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

    assert len(manifest['samples']) == 50
    assert all(sample['acquisition_method'] == 'not_acquired' for sample in manifest['samples'])
    assert duplicate_source_content_hashes(manifest) == []


def test_semantic_validator_rejects_symlink_escape(tmp_path):
    repository_root = tmp_path / 'repo'
    outside = tmp_path / 'outside'
    outside.mkdir()
    sample_id = 'cal-a'
    source_root = repository_root / 'data' / 'calibration' / 'audio' / 'source'
    source_root.mkdir(parents=True)
    try:
        (source_root / sample_id).symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'filesystem does not permit directory symlinks: {exc}')

    errors = acquisition_preparation_errors({
        'samples': [{
            'sample_id': sample_id,
            'acquisition_method': 'official_direct_download',
            'source_local_path': f'data/calibration/audio/source/{sample_id}/track.mp3',
            'source_sha256': 'a' * 64,
            'source_file_size': 10,
            'source_file_kind': 'full_track',
            'full_track_verified': False,
            'full_track_evidence': None,
        }]
    }, repository_root=repository_root)
    assert any('resolves outside the repository root' in error for error in errors)


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
