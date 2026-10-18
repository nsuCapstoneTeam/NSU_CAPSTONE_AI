import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from scripts.matching import register_calibration_audio as registration


MANIFEST_PATH = registration.DEFAULT_MANIFEST


def _manifest():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    sample = next(
        row for row in manifest['samples']
        if row['sample_id'] == 'cal-incompetech-mandeville'
    )
    for field in (
        'source_local_path', 'source_sha256', 'source_file_size', 'decoded_duration',
        'decoded_frame_count', 'source_sample_rate', 'source_channels', 'source_codec',
        'prepared_local_path', 'segment_start_frame', 'segment_end_frame_exclusive',
        'prepared_sha256', 'prepared_duration',
    ):
        sample[field] = None
    sample.update({
        'acquisition_method': 'not_acquired', 'source_file_kind': 'unknown',
        'full_track_verified': None, 'full_track_evidence': None,
    })
    return manifest


def _write_audio(root, sample_id='cal-incompetech-mandeville', *, seconds=61, value=0.1):
    relative = f'data/calibration/audio/source/{sample_id}/fixture.wav'
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.full((seconds * 8000, 2), value, dtype=np.float32)
    sf.write(path, samples, 8000, subtype='FLOAT')
    return relative, path


def _register(root, relative, *, kind='full_track', verified=True, evidence='verified from full source file'):
    return registration.register_source_audio(
        manifest=_manifest(),
        sample_id='cal-incompetech-mandeville',
        source_file=relative,
        acquisition_method='official_direct_download',
        source_file_kind=kind,
        full_track_verified=verified,
        full_track_evidence=evidence,
        repository_root=root,
    )


def test_valid_full_track_registration_dry_run_returns_metadata_without_mutating_input(tmp_path):
    relative, _ = _write_audio(tmp_path)
    original = _manifest()

    candidate, metadata = _register(tmp_path, relative)

    assert candidate is not original
    assert metadata['source_local_path'] == relative
    assert metadata['source_file_size'] > 0
    assert metadata['decoded_frame_count'] == 61 * 8000
    assert metadata['decoded_duration'] == 61
    assert metadata['source_sample_rate'] == 8000
    assert metadata['source_channels'] == 2
    assert metadata['source_codec'] == 'WAV/FLOAT'
    assert original['samples'][0]['acquisition_method'] == 'not_acquired'


def test_cli_dry_run_does_not_write_manifest(tmp_path, monkeypatch, capsys):
    source_relative, _ = _write_audio(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(_manifest()), encoding='utf-8')
    original_bytes = manifest_path.read_bytes()
    monkeypatch.setattr(registration, 'REPOSITORY_ROOT', tmp_path)

    result = registration.main([
        '--manifest', str(manifest_path), '--sample-id', 'cal-incompetech-mandeville',
        '--source-file', source_relative, '--acquisition-method', 'official_direct_download',
        '--source-file-kind', 'full_track', '--full-track-verified',
        '--full-track-evidence', 'verified from full source file',
    ])

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output['mode'] == 'dry_run'
    assert output['manifest_updated'] is False
    assert manifest_path.read_bytes() == original_bytes


def test_verified_full_track_requires_nonblank_evidence(tmp_path):
    relative, _ = _write_audio(tmp_path)

    try:
        _register(tmp_path, relative, evidence='   ')
    except ValueError as error:
        assert 'full_track_evidence' in str(error)
    else:
        raise AssertionError('missing full-track evidence should fail')


def test_preview_cannot_be_registered_as_verified_full_track(tmp_path):
    relative, _ = _write_audio(tmp_path)

    try:
        _register(tmp_path, relative, kind='preview')
    except ValueError as error:
        assert 'source_file_kind=full_track' in str(error)
    else:
        raise AssertionError('preview must not be accepted as a verified full track')


def test_missing_source_file_fails(tmp_path):
    try:
        _register(tmp_path, 'data/calibration/audio/source/cal-incompetech-mandeville/missing.wav')
    except FileNotFoundError as error:
        assert 'does not exist' in str(error)
    else:
        raise AssertionError('missing audio must fail')


def test_invalid_audio_bytes_fail_decode(tmp_path):
    relative = 'data/calibration/audio/source/cal-incompetech-mandeville/broken.wav'
    path = tmp_path / Path(relative)
    path.parent.mkdir(parents=True)
    path.write_bytes(b'not an audio file')

    try:
        _register(tmp_path, relative)
    except ValueError as error:
        assert 'decode/metadata' in str(error)
    else:
        raise AssertionError('invalid audio must fail decoding')


@pytest.mark.parametrize(('kind', 'seconds'), [
    ('preview', 30), ('sample', 10), ('unknown', 20),
])
def test_short_preview_sample_and_unknown_sources_can_be_registered(tmp_path, kind, seconds):
    relative, _ = _write_audio(tmp_path, seconds=seconds)

    candidate, metadata = _register(
        tmp_path, relative, kind=kind, verified=False, evidence=None,
    )

    assert metadata['decoded_duration'] == seconds
    sample = candidate['samples'][0]
    assert sample['source_file_kind'] == kind
    assert sample['full_track_verified'] is False
    assert sample['full_track_evidence'] is None


def test_short_full_track_can_be_registered_only_as_unverified_metadata(tmp_path):
    relative, _ = _write_audio(tmp_path, seconds=59)

    candidate, metadata = _register(
        tmp_path, relative, kind='full_track', verified=False, evidence=None,
    )

    assert metadata['decoded_duration'] == 59
    assert candidate['samples'][0]['full_track_verified'] is False


def test_short_full_track_cannot_be_registered_as_verified(tmp_path):
    relative, _ = _write_audio(tmp_path, seconds=59)

    try:
        _register(tmp_path, relative, kind='full_track', verified=True)
    except ValueError as error:
        assert 'full_track_verified cannot be true' in str(error)
    else:
        raise AssertionError('short full-track source must not be verified')


def test_absolute_or_outside_repository_source_path_fails(tmp_path):
    relative, path = _write_audio(tmp_path)
    for source_path in (str(path), '../outside.wav'):
        try:
            _register(tmp_path, source_path)
        except ValueError as error:
            assert 'repository-relative' in str(error) or 'below' in str(error)
        else:
            raise AssertionError('non repository-relative source path must fail')


def test_non_finite_decoded_pcm_fails(tmp_path):
    relative = f'data/calibration/audio/source/cal-incompetech-mandeville/nonfinite.wav'
    path = tmp_path / Path(relative)
    path.parent.mkdir(parents=True)
    sf.write(path, np.full((61 * 8000, 1), np.nan, dtype=np.float32), 8000, subtype='FLOAT')

    try:
        _register(tmp_path, relative)
    except ValueError as error:
        assert 'decode/metadata' in str(error)
    else:
        raise AssertionError('non-finite decoded PCM must fail')


def test_decoder_and_container_metadata_must_match(tmp_path, monkeypatch):
    relative, path = _write_audio(tmp_path)
    monkeypatch.setattr(
        registration, 'decode',
        lambda _path: (np.zeros((61 * 8000, 2), dtype=np.float32), 16000),
    )

    try:
        _register(tmp_path, relative)
    except ValueError as error:
        assert 'metadata disagree' in str(error)
    else:
        raise AssertionError('decoder/container metadata mismatch must fail')


def test_mp3_frame_count_estimate_allows_two_layer_iii_frames():
    info = SimpleNamespace(frames=9_572_313, samplerate=44_100, channels=2, format='MP3')

    registration.validate_decoded_container_metadata(
        9_570_816, 44_100, 2, info, 'source audio'
    )


def test_mp3_frame_count_estimate_rejects_discrepancy_over_two_frames():
    info = SimpleNamespace(frames=9_570_816 + 2305, samplerate=44_100, channels=2, format='MP3')

    with pytest.raises(ValueError, match='metadata disagree'):
        registration.validate_decoded_container_metadata(
            9_570_816, 44_100, 2, info, 'source audio'
        )


def test_mp3_vbr_estimate_requires_decoded_duration_to_match_catalog():
    decoded_frames = 9_570_816
    info = SimpleNamespace(
        frames=decoded_frames + 700_000, samplerate=44_100, channels=2, format='MP3'
    )

    registration.validate_decoded_container_metadata(
        decoded_frames, 44_100, 2, info, 'source audio', catalog_duration=217
    )
    with pytest.raises(ValueError, match='metadata disagree'):
        registration.validate_decoded_container_metadata(
            decoded_frames, 44_100, 2, info, 'source audio', catalog_duration=240
        )


def test_pcm_wav_frame_count_mismatch_remains_exact():
    info = SimpleNamespace(frames=61 * 8000 + 1, samplerate=8000, channels=2, format='WAV')

    with pytest.raises(ValueError, match='metadata disagree'):
        registration.validate_decoded_container_metadata(
            61 * 8000, 8000, 2, info, 'source audio'
        )


def test_duplicate_source_sha_is_rejected(tmp_path):
    relative, path = _write_audio(tmp_path)
    manifest = _manifest()
    digest = registration.sha256(path)
    manifest['samples'][1]['source_sha256'] = digest

    try:
        registration.register_source_audio(
            manifest, 'cal-incompetech-mandeville', relative,
            'official_direct_download', 'full_track', True,
            'verified from full source file', repository_root=tmp_path,
        )
    except ValueError as error:
        assert 'duplicate source content' in str(error)
    else:
        raise AssertionError('duplicate source content must fail')


def test_duplicate_provider_source_identity_is_rejected(tmp_path):
    relative, _ = _write_audio(tmp_path)
    manifest = _manifest()
    manifest['samples'][1]['provider'] = manifest['samples'][0]['provider']
    manifest['samples'][1]['provider_track_id'] = manifest['samples'][0]['provider_track_id']

    try:
        registration.register_source_audio(
            manifest, 'cal-incompetech-mandeville', relative,
            'official_direct_download', 'full_track', True,
            'verified from full source file', repository_root=tmp_path,
        )
    except ValueError as error:
        assert 'Duplicate (provider, provider_track_id)' in str(error)
    else:
        raise AssertionError('duplicate provider/source identity must fail')


def test_write_mode_updates_only_after_validated_atomic_manifest_write(tmp_path, monkeypatch, capsys):
    source_relative, _ = _write_audio(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(_manifest()), encoding='utf-8')
    monkeypatch.setattr(registration, 'REPOSITORY_ROOT', tmp_path)

    result = registration.main([
        '--manifest', str(manifest_path), '--sample-id', 'cal-incompetech-mandeville',
        '--source-file', source_relative, '--acquisition-method', 'official_direct_download',
        '--source-file-kind', 'full_track', '--full-track-verified',
        '--full-track-evidence', 'verified from full source file', '--write',
    ])

    assert result == 0
    assert json.loads(capsys.readouterr().out)['manifest_updated'] is True
    updated = json.loads(manifest_path.read_text(encoding='utf-8'))
    sample = updated['samples'][0]
    assert sample['source_local_path'] == source_relative
    assert sample['decoded_frame_count'] == 61 * 8000
    assert sample['full_track_verified'] is True


def test_failed_write_validation_preserves_original_manifest_bytes(tmp_path, monkeypatch):
    source_relative, _ = _write_audio(tmp_path, seconds=59)
    manifest_path = tmp_path / 'manifest.json'
    original_bytes = json.dumps(_manifest()).encode('utf-8')
    manifest_path.write_bytes(original_bytes)
    monkeypatch.setattr(registration, 'REPOSITORY_ROOT', tmp_path)

    result = registration.main([
        '--manifest', str(manifest_path), '--sample-id', 'cal-incompetech-mandeville',
        '--source-file', source_relative, '--acquisition-method', 'official_direct_download',
        '--source-file-kind', 'full_track', '--full-track-verified',
        '--full-track-evidence', 'verified from full source file', '--write',
    ])

    assert result == 1
    assert manifest_path.read_bytes() == original_bytes


def test_stale_registration_write_preserves_concurrent_manifest_change(tmp_path, monkeypatch, capsys):
    source_relative, _ = _write_audio(tmp_path)
    manifest_path = tmp_path / 'manifest.json'
    original = json.dumps(_manifest()).encode('utf-8')
    manifest_path.write_bytes(original)
    external = json.dumps({**_manifest(), 'external_writer_marker': 'preserve'}).encode('utf-8')
    monkeypatch.setattr(registration, 'REPOSITORY_ROOT', tmp_path)
    real_write = registration._atomic_write_manifest

    def concurrent_change_then_write(path, candidate, expected_digest):
        Path(path).write_bytes(external)
        return real_write(path, candidate, expected_digest)

    monkeypatch.setattr(registration, '_atomic_write_manifest', concurrent_change_then_write)
    result = registration.main([
        '--manifest', str(manifest_path), '--sample-id', 'cal-incompetech-mandeville',
        '--source-file', source_relative, '--acquisition-method', 'official_direct_download',
        '--source-file-kind', 'full_track', '--full-track-verified',
        '--full-track-evidence', 'verified from full source file', '--write',
    ])

    assert result == 1
    assert 'manifest changed since this operation started' in capsys.readouterr().err
    assert manifest_path.read_bytes() == external
