import copy
import json
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

from scripts.datasets.highlight_dataset import (
    DatasetError, load_manifest, process_track, run, sha256,
)


@pytest.fixture
def fixture(tmp_path):
    def build(rate=44100, duration=62):
        frames = rate * duration
        # 서로 다른 채널과 frame별 값으로 채널 유지 및 시작/끝 경계 오류를 검출한다.
        index = np.arange(frames, dtype=np.int32)
        pcm = np.column_stack(((index % 1009) / 1024, -(index % 997) / 1024)).astype('float32')
        sf.write(tmp_path / 'source.wav', pcm, rate, subtype='FLOAT')
        track = {
            'track_id': 'synthetic', 'title': 'Synthetic', 'artist': 'Test',
            'source': {'path': 'source.wav', 'sha256': sha256(tmp_path / 'source.wav'),
                       'decoded_frames': frames, 'sample_rate': rate, 'channels': 2},
            'highlight': {'path': 'out.wav', 'start_seconds': 2, 'duration_seconds': 60,
                          'start_frame': 2 * rate, 'end_frame_exclusive': 62 * rate,
                          'format_policy': {'container': 'WAV', 'subtype': 'FLOAT',
                                            'encoding': 'PCM_F', 'bits_per_sample': 32,
                                            'sample_rate': 'preserve_source', 'channels': 'preserve_source'}},
            'rights': {'verification_status': 'pending', 'source_url': None,
                       'license': None, 'license_url': None, 'attribution': None},
        }
        manifest = {'schema_version': 1, 'dataset_id': 'synthetic',
                    'path_base': 'repository_root', 'tracks': [track]}
        path = tmp_path / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        return track, manifest, path, pcm
    return build


@pytest.mark.parametrize('rate', [44100, 48000])
def test_exact_frames_stereo_pcm_and_reproducibility(fixture, tmp_path, rate):
    track, manifest, path, source = fixture(rate)
    load_manifest(path, tmp_path)
    result = process_track(track, tmp_path, 'prepare')
    pcm, actual_rate = sf.read(tmp_path / 'out.wav', dtype='float32', always_2d=True)
    assert actual_rate == rate
    assert pcm.shape == (60 * rate, 2)
    assert np.array_equal(pcm, source[2 * rate:62 * rate])
    assert np.array_equal(pcm[0], source[2 * rate])
    assert np.array_equal(pcm[-1], source[62 * rate - 1])
    assert result['output_duration_seconds'] == 60
    assert sf.info(tmp_path / 'out.wav').subtype == 'FLOAT'
    first_hash = sha256(tmp_path / 'out.wav')
    repeated = process_track(track, tmp_path, 'highlights', repeat=True)
    assert repeated['reproducible']
    assert repeated['repeated_output_sha256'] == first_hash
    assert sha256(tmp_path / 'out.wav') == first_hash
    # 메모리 비교뿐 아니라 별도 파일로 실제 재생성한 결과도 확인한다.
    track2 = copy.deepcopy(track)
    track2['highlight']['path'] = 'second.wav'
    process_track(track2, tmp_path, 'prepare')
    assert sha256(tmp_path / 'second.wav') == first_hash
    assert not run(manifest, tmp_path, 'source')['rights_cleared']


@pytest.mark.parametrize('case,reason', [
    ('hash', 'source_hash_mismatch'), ('missing', 'source_missing'),
    ('short', 'insufficient_duration'), ('exists', 'output_exists'),
])
def test_expected_failures(fixture, tmp_path, case, reason):
    track, _, _, _ = fixture(duration=61 if case == 'short' else 62)
    if case == 'hash':
        track['source']['sha256'] = '0' * 64
    elif case == 'missing':
        track['source']['path'] = 'missing.wav'
    elif case == 'exists':
        (tmp_path / 'out.wav').write_bytes(b'preserve me')
    with pytest.raises(DatasetError) as error:
        process_track(track, tmp_path, 'prepare')
    assert error.value.reason == reason
    if case == 'exists':
        assert (tmp_path / 'out.wav').read_bytes() == b'preserve me'
    else:
        assert not (tmp_path / 'out.wav').exists()


@pytest.mark.parametrize('case', ['json', 'fields', 'duration', 'boundary', 'traversal',
                                  'duplicate', 'policy', 'rights', 'type'])
def test_malformed_manifest(fixture, tmp_path, case):
    track, manifest, path, _ = fixture()
    if case == 'json':
        path.write_text('{', encoding='utf-8')
    else:
        if case == 'fields': del track['source']['sha256']
        elif case == 'duration': track['highlight']['duration_seconds'] = 59
        elif case == 'boundary': track['highlight']['end_frame_exclusive'] -= 1
        elif case == 'traversal': track['highlight']['path'] = '../out.wav'
        elif case == 'duplicate': manifest['tracks'].append(copy.deepcopy(track))
        elif case == 'policy': track['highlight']['format_policy']['subtype'] = 'PCM_16'
        elif case == 'rights': track['rights']['verification_status'] = 'verified'
        elif case == 'type': track['source']['sample_rate'] = True
        path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(DatasetError, match='malformed_manifest'):
        load_manifest(path, tmp_path)


def test_validation_detects_tampered_pcm(fixture, tmp_path):
    track, _, _, _ = fixture()
    process_track(track, tmp_path, 'prepare')
    pcm, rate = sf.read(tmp_path / 'out.wav', dtype='float32', always_2d=True)
    pcm[0, 0] += 0.01
    sf.write(tmp_path / 'out.wav', pcm, rate, subtype='FLOAT')
    with pytest.raises(DatasetError, match='output_pcm_mismatch'):
        process_track(track, tmp_path, 'highlights')


def cli(module, path, root, *args):
    return subprocess.run([sys.executable, '-B', '-m', f'scripts.datasets.{module}',
                           '--manifest', str(path), '--root', str(root), *args],
                          capture_output=True, text=True, encoding='utf-8')


def test_cli_exit_codes_readonly_and_report_protection(fixture, tmp_path):
    _, _, path, _ = fixture()
    source_hash = sha256(tmp_path / 'source.wav')
    validated = cli('validate_audio_highlights', path, tmp_path, '--check', 'source')
    assert validated.returncode == 0, validated.stderr
    assert not (tmp_path / 'out.wav').exists()
    prepared = cli('prepare_audio_highlights', path, tmp_path)
    assert prepared.returncode == 0, prepared.stderr
    out_hash = sha256(tmp_path / 'out.wav')
    repeated = cli('validate_audio_highlights', path, tmp_path, '--repeat')
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)['tracks'][0]['reproducible']
    blocked = cli('prepare_audio_highlights', path, tmp_path)
    assert blocked.returncode == 1
    assert 'output_exists' in blocked.stderr and 'out.wav' in blocked.stderr
    report = tmp_path / 'existing.json'
    report.write_text('preserve', encoding='utf-8')
    assert cli('prepare_audio_highlights', path, tmp_path, '--report', str(report)).returncode == 2
    assert report.read_text() == 'preserve'
    path.write_text('{}', encoding='utf-8')
    invalid = cli('validate_audio_highlights', path, tmp_path)
    assert invalid.returncode == 2 and 'malformed_manifest' in invalid.stderr
    assert sha256(tmp_path / 'source.wav') == source_hash
    assert sha256(tmp_path / 'out.wav') == out_hash


def test_cli_source_missing(fixture, tmp_path):
    track, manifest, path, _ = fixture()
    track['source']['path'] = 'missing.wav'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    failed = cli('validate_audio_highlights', path, tmp_path, '--check', 'source')
    assert failed.returncode == 1
    assert 'source_missing' in failed.stderr and 'missing.wav' in failed.stderr
