import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from scripts.matching import prepare_calibration_audio as preparation
from scripts.matching import register_calibration_audio as registration


SAMPLE_ID = 'cal-incompetech-mandeville'


def _manifest():
    return json.loads(registration.DEFAULT_MANIFEST.read_text(encoding='utf-8'))


def _write_source(
    root, *, sample_id=SAMPLE_ID, frames=61 * 8000, sample_rate=8000, channels=2, seed=0,
):
    relative = f'data/calibration/audio/source/{sample_id}/fixture.wav'
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = (np.arange(frames * channels, dtype=np.float32) + seed).reshape(frames, channels)
    values = (values % 1000) / 1000.0
    sf.write(path, values, sample_rate, subtype='FLOAT')
    return relative, path, values


def _registered(root, *, frames=61 * 8000, sample_rate=8000, channels=2):
    relative, path, values = _write_source(
        root, frames=frames, sample_rate=sample_rate, channels=channels
    )
    manifest, metadata = registration.register_source_audio(
        _manifest(), SAMPLE_ID, relative, 'official_direct_download', 'full_track', True,
        'full source file verified from provider download', repository_root=root,
    )
    return manifest, metadata, path, values


def _prepare(manifest, root):
    return preparation.prepare_sample(manifest, SAMPLE_ID, repository_root=root)


def test_exactly_60_seconds_uses_full_range_and_preserves_stereo_rate(tmp_path):
    manifest, _, _, source_pcm = _registered(tmp_path, frames=60 * 8000)

    candidate, result, payload, expected_pcm = _prepare(manifest, tmp_path)

    sample = candidate['samples'][0]
    assert result['segment_start_frame'] == 0
    assert result['segment_end_frame_exclusive'] == 60 * 8000
    assert result['frame_count'] == 60 * 8000
    assert result['sample_rate'] == 8000
    assert result['channels'] == 2
    assert np.array_equal(expected_pcm, source_pcm)
    assert result['prepared_duration'] == 60
    assert sample['segment_rule'] == preparation.SEGMENT_RULE
    assert sf.info(__import__('io').BytesIO(payload)).subtype == 'FLOAT'


def test_long_source_uses_centered_slice_and_odd_leftover_frame_rule(tmp_path):
    sample_rate = 8001
    target = 60 * sample_rate
    source_frames = target + 5
    manifest, _, _, source_pcm = _registered(
        tmp_path, frames=source_frames, sample_rate=sample_rate, channels=2
    )

    candidate, result, _, prepared_pcm = _prepare(manifest, tmp_path)

    start = 2  # floor(5 / 2); the extra leftover frame remains at the end.
    end = start + target
    assert result['segment_start_frame'] == start
    assert result['segment_end_frame_exclusive'] == end
    assert source_frames - end == 3
    assert np.array_equal(prepared_pcm, source_pcm[start:end])
    assert candidate['samples'][0]['source_sample_rate'] == sample_rate
    assert result['channels'] == 2


def test_prepared_wav_is_deterministic_for_same_source(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)

    first = _prepare(manifest, tmp_path)[1]
    second = _prepare(manifest, tmp_path)[1]

    assert first['prepared_sha256'] == second['prepared_sha256']


def test_dry_run_creates_no_prepared_file_and_preserves_manifest(tmp_path, monkeypatch, capsys):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    original = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(original)
    monkeypatch.setattr(preparation, 'REPOSITORY_ROOT', tmp_path)

    exit_code = preparation.main(['--manifest', str(manifest_path), '--sample-id', SAMPLE_ID])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output['mode'] == 'dry_run'
    assert output['manifest_updated'] is False
    assert output['prepared_file_published'] is False
    assert manifest_path.read_bytes() == original
    assert not (tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav').exists()


def test_write_publishes_valid_wav_and_manifest_with_provenance(tmp_path, monkeypatch, capsys):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(preparation, 'REPOSITORY_ROOT', tmp_path)

    exit_code = preparation.main([
        '--manifest', str(manifest_path), '--sample-id', SAMPLE_ID, '--write',
    ])

    assert exit_code == 0, capsys.readouterr().err
    result = json.loads(capsys.readouterr().out)
    updated = json.loads(manifest_path.read_text(encoding='utf-8'))
    sample = updated['samples'][0]
    prepared = tmp_path / sample['prepared_local_path']
    decoded, rate = preparation.decode(prepared)
    info = sf.info(str(prepared))
    assert result['prepared_file_published'] is True
    assert sample['segment_start_frame'] == (61 * 8000 - 60 * 8000) // 2
    assert sample['segment_end_frame_exclusive'] - sample['segment_start_frame'] == 60 * 8000
    assert sample['prepared_duration'] == 60
    assert sample['prepared_sha256'] == preparation.sha256(prepared)
    assert len(decoded) == 60 * 8000 and rate == 8000 and decoded.shape[1] == 2
    assert info.format == 'WAV' and info.subtype == 'FLOAT'


def test_short_source_rejected_before_any_prepared_output(tmp_path):
    manifest, _, source_path, _ = _registered(tmp_path)
    short_pcm = np.full((59 * 8000, 2), 0.125, dtype=np.float32)
    sf.write(source_path, short_pcm, 8000, subtype='FLOAT')
    sample = manifest['samples'][0]
    sample.update({
        'source_sha256': registration.sha256(source_path),
        'source_file_size': source_path.stat().st_size,
        'decoded_duration': 59,
        'decoded_frame_count': 59 * 8000,
    })

    try:
        _prepare(manifest, tmp_path)
    except ValueError as error:
        assert '60 seconds' in str(error) or 'minimum of 60' in str(error)
    else:
        raise AssertionError('source shorter than 60 seconds must fail')
    assert not (tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav').exists()


def test_registered_source_sha_and_size_are_rechecked(tmp_path):
    manifest, _, source_path, _ = _registered(tmp_path)
    source_path.write_bytes(source_path.read_bytes() + b'changed')

    try:
        _prepare(manifest, tmp_path)
    except ValueError as error:
        assert 'SHA-256' in str(error)
    else:
        raise AssertionError('changed source must fail identity check')

    manifest, _, _, _ = _registered(tmp_path / 'size-case')
    manifest['samples'][0]['source_file_size'] += 1
    try:
        _prepare(manifest, tmp_path / 'size-case')
    except ValueError as error:
        assert 'file size' in str(error)
    else:
        raise AssertionError('registered file size mismatch must fail')


def test_registered_sample_rate_and_channel_identity_are_rechecked(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)
    manifest['samples'][0]['source_sample_rate'] = 4000
    manifest['samples'][0]['decoded_duration'] = manifest['samples'][0]['decoded_frame_count'] / 4000
    try:
        _prepare(manifest, tmp_path)
    except ValueError as error:
        assert 'metadata changed' in str(error)
    else:
        raise AssertionError('sample rate mismatch must fail')

    manifest, _, _, _ = _registered(tmp_path / 'channel-case')
    manifest['samples'][0]['source_channels'] = 1
    try:
        _prepare(manifest, tmp_path / 'channel-case')
    except ValueError as error:
        assert 'metadata changed' in str(error)
    else:
        raise AssertionError('channel mismatch must fail')


@pytest.mark.parametrize('source_kind', ['preview', 'sample', 'unknown'])
def test_preview_sample_or_unknown_source_cannot_be_prepared(tmp_path, source_kind):
    manifest, _, _, _ = _registered(tmp_path)
    manifest['samples'][0]['source_file_kind'] = source_kind
    manifest['samples'][0]['full_track_verified'] = False
    try:
        _prepare(manifest, tmp_path)
    except ValueError as error:
        assert 'source_file_kind=full_track' in str(error) or 'validation failed' in str(error)
    else:
        raise AssertionError('preview must not be prepared')

    manifest, _, _, _ = _registered(tmp_path / 'unverified')
    manifest['samples'][0]['full_track_verified'] = False
    try:
        _prepare(manifest, tmp_path / 'unverified')
    except ValueError as error:
        assert 'full_track_verified=true' in str(error)
    else:
        raise AssertionError('unverified full track must not be prepared')


@pytest.mark.parametrize(('source_kind', 'seconds'), [
    ('preview', 30), ('sample', 10), ('unknown', 20),
])
def test_short_preview_sample_or_unknown_register_but_cannot_be_prepared(
    tmp_path, source_kind, seconds,
):
    relative, _, _ = _write_source(tmp_path, frames=seconds * 8000)
    manifest, _ = registration.register_source_audio(
        _manifest(), SAMPLE_ID, relative, 'official_direct_download',
        source_kind, False, None, repository_root=tmp_path,
    )

    assert manifest['samples'][0]['decoded_duration'] == seconds
    with pytest.raises(ValueError, match='cannot be prepared|full_track'):
        _prepare(manifest, tmp_path)


def test_missing_full_track_evidence_fails(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)
    manifest['samples'][0]['full_track_evidence'] = None
    try:
        _prepare(manifest, tmp_path)
    except ValueError as error:
        assert 'validation failed' in str(error) or 'evidence' in str(error)
    else:
        raise AssertionError('missing full-track evidence must fail')


@pytest.mark.parametrize(('cohort_status', 'field', 'value', 'error_text'), [
    ('candidate_selection_incomplete', 'commercial_use_status', 'restricted', 'commercial_use_status'),
    ('candidate_selection_incomplete', 'rights_status', 'excluded', 'rights_status'),
    ('candidate_selection_incomplete', 'license_name', '   ', 'license_name'),
    ('candidate_selection_incomplete', 'license_url', '', 'license_url'),
    ('candidate_selection_complete', 'commercial_use_status', 'restricted', 'commercial_use_status'),
])
def test_preparation_rights_gate_applies_regardless_of_cohort_status(
    tmp_path, cohort_status, field, value, error_text,
):
    manifest, _, _, _ = _registered(tmp_path)
    manifest['cohort_status'] = cohort_status
    manifest['samples'][0][field] = value

    with pytest.raises(ValueError, match=error_text):
        _prepare(manifest, tmp_path)


def test_valid_sample_rights_remain_preparable_in_incomplete_cohort(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)
    manifest['cohort_status'] = 'candidate_selection_incomplete'

    candidate, result, _, _ = _prepare(manifest, tmp_path)

    assert candidate['cohort_status'] == 'candidate_selection_incomplete'
    assert result['sample_id'] == SAMPLE_ID


def test_existing_prepared_output_is_never_overwritten(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)
    output = tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav'
    output.parent.mkdir(parents=True)
    output.write_bytes(b'keep-existing')

    try:
        _prepare(manifest, tmp_path)
    except FileExistsError as error:
        assert 'already exists' in str(error)
    else:
        raise AssertionError('existing prepared output must block preparation')
    assert output.read_bytes() == b'keep-existing'


def test_prepared_path_traversal_is_rejected_by_path_resolution(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)
    manifest['samples'][0]['prepared_local_path'] = 'data/calibration/audio/prepared/../escape.wav'
    manifest['samples'][0]['prepared_sha256'] = 'a' * 64
    manifest['samples'][0]['prepared_duration'] = 60
    manifest['samples'][0]['segment_start_frame'] = 4000
    manifest['samples'][0]['segment_end_frame_exclusive'] = 484000
    try:
        _prepare(manifest, tmp_path)
    except ValueError as error:
        assert 'validation failed' in str(error)
    else:
        raise AssertionError('invalid prepared path must fail validation')


def test_failed_temp_wav_validation_preserves_manifest_and_output(tmp_path, monkeypatch):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    original = json.dumps(manifest).encode()
    manifest_path.write_bytes(original)
    monkeypatch.setattr(preparation, 'REPOSITORY_ROOT', tmp_path)
    monkeypatch.setattr(
        preparation, '_validate_prepared_wav',
        lambda *_args: (_ for _ in ()).throw(ValueError('injected re-decode failure')),
    )

    exit_code = preparation.main([
        '--manifest', str(manifest_path), '--sample-id', SAMPLE_ID, '--write',
    ])

    assert exit_code == 1
    assert manifest_path.read_bytes() == original
    assert not (tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav').exists()


def test_manifest_replace_failure_rolls_back_prepared_audio(tmp_path, monkeypatch, capsys):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    original = json.dumps(manifest).encode()
    manifest_path.write_bytes(original)
    monkeypatch.setattr(preparation, 'REPOSITORY_ROOT', tmp_path)
    original_replace = preparation.os.replace

    def fail_manifest_replace(source, destination):
        if Path(destination) == manifest_path:
            original_replace(source, destination)
            raise OSError('injected manifest replace failure')
        return original_replace(source, destination)

    monkeypatch.setattr(preparation.os, 'replace', fail_manifest_replace)
    exit_code = preparation.main([
        '--manifest', str(manifest_path), '--sample-id', SAMPLE_ID, '--write',
    ])

    assert exit_code == 1
    assert 'injected manifest replace failure' in capsys.readouterr().err
    assert manifest_path.read_bytes() == original
    assert not (tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav').exists()


def test_external_manifest_change_before_publish_is_preserved_without_orphan(
    tmp_path, monkeypatch, capsys,
):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    original = json.dumps(manifest).encode()
    manifest_path.write_bytes(original)
    external = json.dumps({**manifest, 'external_writer_marker': 'kept'}).encode()
    monkeypatch.setattr(preparation, 'REPOSITORY_ROOT', tmp_path)
    real_write_temp_manifest = preparation._write_temp_manifest

    def mutate_before_publish(path, candidate):
        temporary = real_write_temp_manifest(path, candidate)
        manifest_path.write_bytes(external)
        return temporary

    monkeypatch.setattr(preparation, '_write_temp_manifest', mutate_before_publish)
    code = preparation.main(['--manifest', str(manifest_path), '--sample-id', SAMPLE_ID, '--write'])

    assert code == 1
    assert 'manifest changed since this operation started' in capsys.readouterr().err
    assert manifest_path.read_bytes() == external
    assert not (tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav').exists()


def test_two_different_sample_writers_from_same_snapshot_prevent_lost_update(tmp_path):
    manifest = _manifest()
    second_id = 'cal-incompetech-lasting-hope'
    for seed, sample_id in enumerate((SAMPLE_ID, second_id), start=1):
        relative, _, _ = _write_source(tmp_path, sample_id=sample_id, seed=seed)
        manifest, _ = registration.register_source_audio(
            manifest, sample_id, relative, 'official_direct_download', 'full_track', True,
            'verified from full source file', repository_root=tmp_path,
        )
    manifest_path = tmp_path / 'manifest.json'
    initial = json.dumps(manifest).encode()
    manifest_path.write_bytes(initial)
    expected_digest = __import__('hashlib').sha256(initial).hexdigest()
    first_candidate, first_result, first_payload, first_pcm = preparation.prepare_sample(
        manifest, SAMPLE_ID, repository_root=tmp_path
    )
    second_candidate, second_result, second_payload, second_pcm = preparation.prepare_sample(
        manifest, second_id, repository_root=tmp_path
    )

    preparation._write_prepared_pair(
        manifest_path, first_candidate, first_result, first_payload, first_pcm, tmp_path,
        expected_digest,
    )
    with pytest.raises(ValueError, match='manifest changed since this operation started'):
        preparation._write_prepared_pair(
            manifest_path, second_candidate, second_result, second_payload, second_pcm, tmp_path,
            expected_digest,
        )

    current = json.loads(manifest_path.read_text(encoding='utf-8'))
    current_by_id = {item['sample_id']: item for item in current['samples']}
    assert current_by_id[SAMPLE_ID]['prepared_sha256'] == first_result['prepared_sha256']
    assert current_by_id[second_id]['prepared_local_path'] is None
    assert (tmp_path / first_result['prepared_local_path']).is_file()
    assert not (tmp_path / second_result['prepared_local_path']).exists()


def test_same_sample_second_writer_cannot_publish_from_stale_snapshot(tmp_path):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    initial = json.dumps(manifest).encode()
    manifest_path.write_bytes(initial)
    expected_digest = __import__('hashlib').sha256(initial).hexdigest()
    candidate, result, payload, pcm = preparation.prepare_sample(
        manifest, SAMPLE_ID, repository_root=tmp_path
    )

    preparation._write_prepared_pair(
        manifest_path, candidate, result, payload, pcm, tmp_path, expected_digest,
    )
    with pytest.raises(FileExistsError):
        preparation._write_prepared_pair(
            manifest_path, candidate, result, payload, pcm, tmp_path, expected_digest,
        )
    assert json.loads(manifest_path.read_text(encoding='utf-8'))['samples'][0]['prepared_sha256'] == result['prepared_sha256']


def test_rollback_does_not_overwrite_external_manifest_change(tmp_path, monkeypatch, capsys):
    manifest, _, _, _ = _registered(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    original = json.dumps(manifest).encode()
    manifest_path.write_bytes(original)
    external = json.dumps({**manifest, 'external_writer_marker': 'preserve'}).encode()
    monkeypatch.setattr(preparation, 'REPOSITORY_ROOT', tmp_path)
    real_sha256 = preparation.sha256

    def mutate_then_fail_hash(path):
        if Path(path) == tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav':
            manifest_path.write_bytes(external)
            return '0' * 64
        return real_sha256(path)

    monkeypatch.setattr(preparation, 'sha256', mutate_then_fail_hash)
    code = preparation.main(['--manifest', str(manifest_path), '--sample-id', SAMPLE_ID, '--write'])

    assert code == 1
    assert manifest_path.read_bytes() == external
    assert not (tmp_path / f'data/calibration/audio/prepared/{SAMPLE_ID}.wav').exists()

