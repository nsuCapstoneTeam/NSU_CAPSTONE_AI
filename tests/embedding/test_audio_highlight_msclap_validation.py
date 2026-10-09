"""실제 모델을 로드하지 않고 관측 도구의 비간섭·실패·증거 정책을 검사한다."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import torch

from app.embedding.audio_embedding import AudioEmbeddingGenerator, audio_file_sha256
from scripts.embedding import validate_audio_highlight_msclap as tool


class Model:
    def __init__(self, checkpoint):
        self.model_fp = str(checkpoint)
        self.calls = 0

    def get_audio_embeddings(self, paths, *, resample):
        assert resample is False and len(paths) == 8
        self.calls += 1
        return torch.arange(1, 41, dtype=torch.float32).reshape(8, 5)


def synthetic(root, rate):
    path = root / 'highlight.wav'
    time = np.arange(60 * rate, dtype=np.float32) / rate
    wave = np.sin(time * 100).astype(np.float32) * .25
    sf.write(path, np.column_stack([wave, wave * .5]), rate, subtype='FLOAT')
    checkpoint = root / 'datasets/cache/snapshots/test-revision/CLAP_weights_2023.pth'
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b'synthetic checkpoint, not loaded')
    row = {'track_id': 'fixture', 'title': '합성 입력', 'path': path.name,
           'sha256': audio_file_sha256(path), 'sample_rate': rate, 'channels': 2}
    return path, checkpoint, row


@pytest.mark.parametrize('rate', [44100, 48000])
def test_observation_does_not_change_production_result_and_uses_dynamic_dimension(tmp_path, rate):
    path, checkpoint, row = synthetic(tmp_path, rate)
    plain = AudioEmbeddingGenerator(Model(checkpoint)).generate(path)
    model = Model(checkpoint)
    observer = tool.ObservingModel(model)
    generator = AudioEmbeddingGenerator(observer)
    rng = torch.random.get_rng_state().clone()
    record, raw, vector = tool.observe(generator, observer, row, tmp_path)
    assert torch.equal(vector, plain.vector)
    assert torch.equal(rng, torch.random.get_rng_state())
    assert model.calls == 1 and raw.shape == (8, 5) and vector.shape == (1, 5)
    assert record['batch_shape'] == [8, 5] and record['representative_shape'] == [1, 5]
    assert record['metadata']['dimension'] == 5
    assert record['chunks'][0]['start_frame'] == 0
    assert record['chunks'][-1]['end_frame_exclusive'] == 56 * 44100
    assert all(c['frames'] == 308700 and c['channels'] == 1 for c in record['chunks'])
    assert all(c['reference_pcm_exact_equal'] for c in record['chunks'])
    assert all(c['normalized_norm'] == pytest.approx(1) for c in record['chunks'])
    assert record['final_norm'] == pytest.approx(1, abs=1e-6)
    assert set(record['checks'].values()) == {'PASS'}
    repeat, _, repeated = tool.observe(generator, observer, row, tmp_path)
    assert repeat['representative_sha256'] == record['representative_sha256']
    assert tool.differences(vector, repeated)['status'] == 'PASS'


def test_non_exact_reproducibility_is_review_required_without_allclose_threshold():
    first = torch.tensor([[1., 0.]])
    second = torch.tensor([[1., 1e-8]])
    diff = tool.differences(first, second)
    assert diff['status'] == 'REVIEW_REQUIRED'
    assert diff['exact_equal'] is False
    assert diff['max_absolute_difference'] > 0
    assert diff['rms_difference'] > 0 and diff['l2_difference'] > 0


def test_canonical_digest_ignores_contiguity_and_checks_values():
    first = torch.arange(6, dtype=torch.float32).reshape(2, 3)
    assert tool.digest(first) == tool.digest(first.T.contiguous().T)
    assert tool.digest(first) != tool.digest(first + 1)


def preflight_fixture(root, monkeypatch):
    tracks, lines = [], []
    for identity in sorted(tool.TRACK_IDS):
        source = root / (identity + '.mp3')
        output = root / (identity + '.wav')
        source.write_bytes(b'synthetic source ' + identity.encode())
        output.write_bytes(b'synthetic output ' + identity.encode())
        source_hash, output_hash = audio_file_sha256(source), audio_file_sha256(output)
        tracks.append({'track_id': identity, 'title': identity,
                       'highlight': {'path': output.name},
                       'source': {'path': source.name, 'sha256': source_hash,
                                  'sample_rate': 44100, 'channels': 2},
                       'rights': {'verification_status': 'verified'}})
        lines.append(f'| {identity} | `{source_hash}` | `{output_hash}` |')
    report = root / 'inspection-report.md'
    report.write_text('\n'.join(lines), encoding='utf-8')
    monkeypatch.setattr(tool.torchaudio, 'load', lambda path: (torch.ones(2, 60 * 44100), 44100))
    monkeypatch.setattr(tool.sf, 'info', lambda path: SimpleNamespace(format='WAV', subtype='FLOAT'))
    return {'dataset_id': 'adr0007-audio-highlight-phase-a-v1', 'tracks': tracks}, report


@pytest.mark.parametrize('kind', ['highlight_hash', 'source_hash', 'missing', 'identity', 'rights'])
def test_preflight_stops_all_inference_on_invalid_input(tmp_path, monkeypatch, kind):
    manifest, report = preflight_fixture(tmp_path, monkeypatch)
    assert len(tool.preflight(manifest, tmp_path, report)) == 6
    first = manifest['tracks'][0]
    if kind == 'highlight_hash':
        (tmp_path / first['highlight']['path']).write_bytes(b'changed')
    elif kind == 'source_hash':
        first['source']['sha256'] = '0' * 64
    elif kind == 'missing':
        (tmp_path / first['highlight']['path']).unlink()
    elif kind == 'identity':
        first['track_id'] = 'not-approved'
    else:
        first['rights']['verification_status'] = 'pending'
    with pytest.raises(tool.ValidationError):
        tool.preflight(manifest, tmp_path, report)


def test_offline_cache_missing_is_not_downloaded(tmp_path):
    with pytest.raises(FileNotFoundError):
        tool.cache_identity(tmp_path)


def test_report_never_overwrites_existing_evidence(tmp_path):
    path = tmp_path / 'report.json'
    tool.write_json(path, {'status': 'PASS'})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        tool.write_json(path, {'status': 'FAIL'})
    assert path.read_bytes() == before


@pytest.mark.parametrize(('status', 'returncode', 'accepted'), [
    ('PASS', 0, True), ('REVIEW_REQUIRED', 1, True), ('FAIL', 1, False),
])
def test_reload_review_evidence_is_kept_separate_from_technical_failure(tmp_path, status, returncode, accepted):
    path = tmp_path / 'reload.json'
    tool.write_json(path, {'status': status, 'error': '테스트 기술 실패'})
    if accepted:
        assert tool.read_reload_result(path, returncode)['status'] == status
    else:
        with pytest.raises(tool.ValidationError, match='기술 검증 실패'):
            tool.read_reload_result(path, returncode)


def test_lazy_loading_and_repeated_calls_keep_production_path(tmp_path, monkeypatch):
    _, checkpoint, row = synthetic(tmp_path, 44100)
    constructed = []
    def factory(*, version, use_cuda):
        assert version == '2023' and use_cuda is False
        model = Model(checkpoint)
        constructed.append(model)
        return model
    monkeypatch.setitem(sys.modules, 'msclap', SimpleNamespace(CLAP=factory))
    report = tmp_path / 'datasets/run.json'
    report.parent.mkdir(exist_ok=True)
    args = SimpleNamespace(repeat=2, report=report)
    cache = {'microsoft--msclap': {'revision': 'test-revision', 'files': {
        'CLAP_weights_2023.pth': {'sha256': audio_file_sha256(checkpoint)}}}}
    result = tool.run_process(args, tmp_path, [row], cache)
    assert len(constructed) == 1 and constructed[0].calls == 2
    assert len(result['runs']) == 2
    assert result['same_process_reproducibility'][0]['status'] == 'PASS'
    with np.load(report.with_suffix('.vectors.npz'), allow_pickle=False) as vectors:
        assert vectors['fixture_0_raw'].shape == (8, 5)
        assert np.array_equal(vectors['fixture_0_representative'], vectors['fixture_1_representative'])


def test_cli_invalid_manifest_returns_nonzero_without_model_load():
    command = [sys.executable, '-X', 'utf8', '-B', '-m', 'scripts.embedding.validate_audio_highlight_msclap',
               '--manifest', 'does-not-exist.json', '--report', 'outside-datasets.json']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 2
    assert 'datasets' in result.stderr


def test_programming_errors_are_not_hidden(monkeypatch):
    monkeypatch.setattr(tool, 'load_manifest', lambda *args: {})
    def broken(*args):
        raise TypeError('programming error')
    monkeypatch.setattr(tool, 'preflight', broken)
    with pytest.raises(TypeError, match='programming error'):
        tool.main(['--manifest', 'unused.json', '--report', 'datasets/programming-error-test.json'])
