"""실제 production generator의 Phase A 입력·중간 관측·재현성을 검증한다."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch
import torchaudio

from app.embedding.audio_embedding import (
    ANALYSIS_DURATION_SECONDS, CHUNK_COUNT, CHUNK_DURATION_SECONDS,
    PREPROCESSING_VERSION, TARGET_SAMPLE_RATE, AudioEmbeddingError,
    AudioEmbeddingGenerator, audio_file_sha256, validate_chunk_embeddings,
)
from scripts.datasets.highlight_dataset import DatasetError, load_manifest

SCHEMA_VERSION = 1
TOOL_VERSION = 'phase-a-production-generator-observation-v1'
TRACK_IDS = {'the-britons', 'dentaneosuchus-hunt', 'cretaceous-dawn',
             'that-zen-moment', 'boogie-party', 'all-this'}
FINAL_NORM_ABS_TOLERANCE = 1e-6  # 기존 generator unit test의 final norm 기준만 사용한다.
PROFILE_KEYS = ('model', 'model_version', 'checkpoint_revision', 'packages',
                'preprocessing_version', 'preprocessing', 'dimension', 'dtype', 'device')


class ValidationError(ValueError):
    """실험 검증 실패를 입력 파일과 함께 보고한다."""


def require(condition, reason):
    if not condition:
        raise ValidationError(reason)


def digest(tensor):
    """경로·컨테이너 metadata와 무관한 C-order little-endian float32 식별값."""
    values = tensor.detach().cpu().numpy().astype('<f4', copy=False)
    return hashlib.sha256(values.tobytes(order='C')).hexdigest()


def differences(first, second):
    require(first.shape == second.shape, '반복 출력 shape가 다릅니다')
    a, b = first.double(), second.double()
    delta = a - b
    exact = torch.equal(first, second)
    return {
        'exact_equal': exact, 'canonical_float32_digest_equal': digest(first) == digest(second),
        'max_absolute_difference': float(delta.abs().max()),
        'rms_difference': float(torch.sqrt((delta * delta).mean())),
        'l2_difference': float(torch.linalg.vector_norm(delta)),
        'cosine_difference': float(1 - torch.nn.functional.cosine_similarity(a, b).item()),
        'status': 'PASS' if exact and digest(first) == digest(second) else 'REVIEW_REQUIRED',
        'tolerance_policy': 'exact_only_no_project_approximate_reproducibility_threshold',
    }


def preflight(manifest, root, phase_a_report):
    """모델을 import/load하기 전에 여섯 입력 모두를 검증한다."""
    require(manifest['dataset_id'] == 'adr0007-audio-highlight-phase-a-v1', 'Phase A dataset_id 불일치')
    require(len(manifest['tracks']) == 6 and {t['track_id'] for t in manifest['tracks']} == TRACK_IDS,
            '승인된 Phase A 6곡만 허용합니다')
    historical = phase_a_report.read_text(encoding='utf-8')
    rows = []
    for track in manifest['tracks']:
        name = track['highlight']['path']
        path = root / name
        source = root / track['source']['path']
        require(path.is_file(), f'{name}: Highlight 파일 누락')
        require(source.is_file(), f'{source}: 원본 MP3 누락')
        expected = [re.findall(r'[a-f0-9]{64}', line) for line in historical.splitlines()
                    if line.startswith('| ' + track['title'] + ' |')]
        expected = [hashes for hashes in expected if len(hashes) == 2]
        require(len(expected) == 1, f'{name}: Phase A 기록의 SHA 행이 없거나 중복됩니다')
        source_hash, output_hash = expected[0]
        require(source_hash == track['source']['sha256'] == audio_file_sha256(source),
                f'{source}: source SHA-256 불일치')
        require(output_hash == audio_file_sha256(path), f'{name}: Highlight SHA-256 불일치')
        require(path.name == track['track_id'] + '.wav', f'{name}: fixture 파일명 불일치')
        wave, rate = torchaudio.load(str(path))
        require(wave.shape == (2, 60 * rate) and rate == track['source']['sample_rate'],
                f'{name}: decoded frame/rate/channel 불일치')
        require(track['source']['channels'] == 2 and bool(torch.isfinite(wave).all()),
                f'{name}: channel/finite 검사 실패')
        info = sf.info(str(path))
        require(info.format == 'WAV' and info.subtype == 'FLOAT', f'{name}: WAV/FLOAT 정책 불일치')
        require(track['rights']['verification_status'] == 'verified', f'{name}: 권리 상태 미확인')
        rows.append({'track_id': track['track_id'], 'title': track['title'], 'path': name,
                     'sha256': output_hash, 'original_mp3_path': track['source']['path'],
                     'original_mp3_sha256': source_hash, 'decoded_frames': wave.shape[1],
                     'duration_seconds': wave.shape[1] / rate, 'sample_rate': rate,
                     'channels': wave.shape[0], 'format': info.format, 'subtype': info.subtype,
                     'status': 'PASS'})
    return rows


def reference_analysis(path):
    """추론 입력을 바꾸지 않는 PCM 대조 기준만 계산한다."""
    wave, rate = torchaudio.load(str(path))
    wave = wave[:, :ANALYSIS_DURATION_SECONDS * rate].mean(dim=0, keepdim=True)
    if rate != TARGET_SAMPLE_RATE:
        wave = torchaudio.transforms.Resample(rate, TARGET_SAMPLE_RATE)(wave)
    return wave


class ObservingModel:
    """원래 모델을 그대로 호출하고 복제한 출력만 관측한다."""

    def __init__(self, model):
        self.model = model
        self.expected_pcm = None
        self.calls = []
        self.raw_vectors = None

    @property
    def model_fp(self):
        return self.model.model_fp

    def get_audio_embeddings(self, paths, *, resample):
        require(resample is False and len(paths) == CHUNK_COUNT, 'MSCLAP batch 입력 정책 불일치')
        chunk_rows = []
        frames = CHUNK_DURATION_SECONDS * TARGET_SAMPLE_RATE
        for index, path in enumerate(paths):
            pcm, rate = torchaudio.load(path)
            expected = self.expected_pcm[:, index * frames:(index + 1) * frames]
            info = sf.info(path)
            require(rate == TARGET_SAMPLE_RATE and pcm.shape == (1, frames), f'chunk {index}: shape/rate 불일치')
            require(bool(torch.isfinite(pcm).all()) and bool(torch.count_nonzero(pcm)),
                    f'chunk {index}: non-finite 또는 silent PCM')
            require(torch.equal(pcm, expected), f'chunk {index}: [0,56) mono/resample PCM 불일치')
            require(info.format == 'WAV' and info.subtype == 'FLOAT', f'chunk {index}: PCM_F 불일치')
            chunk_rows.append({'index': index, 'start_seconds': index * CHUNK_DURATION_SECONDS,
                               'end_seconds_exclusive': (index + 1) * CHUNK_DURATION_SECONDS,
                               'start_frame': index * frames, 'end_frame_exclusive': (index + 1) * frames,
                               'frames': frames, 'duration_seconds': CHUNK_DURATION_SECONDS,
                               'sample_rate': rate, 'channels': 1, 'pcm_sha256': digest(pcm),
                               'finite': True, 'nonzero': True, 'reference_pcm_exact_equal': True})
        self.calls.append({'chunks': chunk_rows, 'resample_argument': resample})
        # 이 반환값은 변환하거나 교체하지 않는다. generator가 원래 출력을 집계한다.
        result = self.model.get_audio_embeddings(paths, resample=resample)
        validate_chunk_embeddings(result)
        self.raw_vectors = result.detach().cpu().clone()
        return result


def observe(generator, observer, input_row, root):
    observer.expected_pcm = reference_analysis(root / input_row['path'])
    observer.calls.clear()
    start = time.perf_counter()
    result = generator.generate(root / input_row['path'], expected_sha256=input_row['sha256'])
    return inspect_result(result, observer, input_row, root, time.perf_counter() - start)


def inspect_result(result, observer, input_row, root, elapsed):
    require(len(observer.calls) == 1, '곡별 MSCLAP batch 호출 수가 1이 아닙니다')
    raw = observer.raw_vectors
    norms = torch.linalg.vector_norm(raw.double(), dim=1, keepdim=True)
    normalized = raw.double() / norms
    normalized_norms = torch.linalg.vector_norm(normalized, dim=1)
    mean = normalized.mean(dim=0, keepdim=True)
    mean_norm = torch.linalg.vector_norm(mean, dim=1, keepdim=True)
    require(bool(torch.isfinite(normalized).all()) and bool(torch.isfinite(mean_norm).all())
            and float(mean_norm) > 0, '정규화/평균 검사 실패')
    expected = (mean / mean_norm).float()
    require(torch.equal(result.vector, expected), 'production aggregation과 관측 출력 재계산 불일치')
    final_norm = float(result.vector.norm())
    require(abs(final_norm - 1) <= FINAL_NORM_ABS_TOLERANCE, '기존 final norm abs=1e-6 기준 실패')
    metadata = result.metadata.copy()
    require(metadata['source_sha256'] == input_row['sha256']
            and metadata['source_duration_seconds'] == 60
            and metadata['source_sample_rate'] == input_row['sample_rate']
            and metadata['source_channels'] == input_row['channels'], 'input metadata 불일치')
    expected_preprocessing = {
        'resample': True, 'target_sample_rate': TARGET_SAMPLE_RATE,
        'channel_policy': 'arithmetic_mean_downmix_to_mono',
        'analysis_duration_seconds': ANALYSIS_DURATION_SECONDS,
        'chunk_duration_seconds': CHUNK_DURATION_SECONDS, 'chunk_count': CHUNK_COUNT,
        'chunk_overlap_seconds': 0, 'chunk_normalization': 'l2', 'aggregation': 'mean',
        'final_normalization': 'l2', 'chunk_input': 'temporary_pcm_float32_wav',
    }
    require(metadata['preprocessing_version'] == PREPROCESSING_VERSION
            and metadata['preprocessing'] == expected_preprocessing, 'generation policy/profile 불일치')
    require(metadata['model'] == 'MSCLAP' and metadata['model_version'] == '2023'
            and metadata['device'] == 'cpu' and metadata['dtype'] == 'torch.float32'
            and metadata['shape'] == list(result.vector.shape)
            and metadata['dimension'] == raw.shape[1], 'model/shape metadata 불일치')
    require(audio_file_sha256(root / input_row['path']) == input_row['sha256'], '추론 후 input SHA 변경')
    metadata['source_path'] = input_row['path']
    checkpoint = Path(metadata['checkpoint_path'])
    if checkpoint.is_relative_to(root):
        metadata['checkpoint_path'] = checkpoint.relative_to(root).as_posix()
    chunks = observer.calls[0]['chunks']
    for index, row in enumerate(chunks):
        row.update(raw_embedding_shape=[raw.shape[1]], raw_norm=float(norms[index]),
                   normalized_norm=float(normalized_norms[index]), embedding_finite=True,
                   embedding_nonzero=True, raw_vector_sha256=digest(raw[index]), status='PASS')
    checks = {key: 'PASS' for key in ('input_integrity', 'first56_pcm', 'arithmetic_mean_mono',
              'resampling_and_chunk_boundaries', 'batch_count_and_shape', 'chunk_finite_nonzero',
              'chunk_l2', 'mean_pooling_final_l2', 'generation_metadata_profile')}
    record = {'track_id': input_row['track_id'], 'chunks': chunks, 'batch_calls': len(observer.calls),
              'batch_shape': list(raw.shape), 'batch_dtype': str(raw.dtype),
              'resample_argument': False, 'mean_norm': float(mean_norm),
              'representative_shape': list(result.vector.shape), 'final_norm': final_norm,
              'final_norm_abs_tolerance': FINAL_NORM_ABS_TOLERANCE,
              'representative_finite': bool(torch.isfinite(result.vector).all()),
              'representative_nonzero': bool(torch.count_nonzero(result.vector)),
              'representative_sha256': digest(result.vector), 'aggregation_exact_equal': True,
              'metadata': metadata, 'generation_profile': {k: metadata[k] for k in PROFILE_KEYS},
              'normalization_observation': 'derived_from_observed_raw_vectors_and_verified_against_production_output',
              'checks': checks, 'elapsed_seconds': elapsed}
    return record, raw, result.vector.detach().cpu().clone()


def cache_identity(cache):
    hub = cache / 'hub'
    result = {}
    required = {'microsoft--msclap': ['CLAP_weights_2023.pth'],
                'gpt2': ['config.json', 'model.safetensors', 'tokenizer.json',
                         'tokenizer_config.json', 'vocab.json', 'merges.txt']}
    for name, files in required.items():
        model = hub / ('models--' + name)
        revision = (model / 'refs/main').read_text(encoding='utf-8').strip()
        snapshot = model / 'snapshots' / revision
        require(all((snapshot / f).is_file() for f in files), f'{name}: offline cache 누락')
        result[name] = {'revision': revision, 'files': {
            f: {'sha256': audio_file_sha256(snapshot / f), 'bytes': (snapshot / f).stat().st_size}
            for f in files}}
    return result


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def read_reload_result(path, returncode):
    require(path.is_file(), '별도 process가 결과 evidence를 기록하지 않았습니다')
    child = json.loads(path.read_text(encoding='utf-8'))
    # exact 불일치의 종료 코드 1은 기술 실패와 구분하여 차이 측정을 계속한다.
    require(returncode in (0, 1) and child['status'] in ('PASS', 'REVIEW_REQUIRED'),
            '별도 process 기술 검증 실패: ' + child.get('error', str(returncode)))
    return child


def run_process(args, root, inputs, cache):
    # factory를 관측 wrapper로 감싸지만 production의 lazy load와 RNG 복원 경로를 유지한다.
    from msclap import CLAP
    holder = {}

    def factory(*a, **kw):
        holder['observer'] = ObservingModel(CLAP(*a, **kw))
        holder['observer'].expected_pcm = holder['expected_pcm']
        return holder['observer']

    generator = AudioEmbeddingGenerator()
    runs, vectors, same_process = [], {}, []
    with patch('msclap.CLAP', side_effect=factory):
        for input_row in inputs:
            for repetition in range(args.repeat):
                if 'observer' not in holder:
                    holder['expected_pcm'] = reference_analysis(root / input_row['path'])
                    start = time.perf_counter()
                    result = generator.generate(root / input_row['path'], expected_sha256=input_row['sha256'])
                    record, raw, representative = inspect_result(
                        result, holder['observer'], input_row, root, time.perf_counter() - start)
                else:
                    record, raw, representative = observe(generator, holder['observer'], input_row, root)
                require(record['metadata']['checkpoint_revision'] == cache['microsoft--msclap']['revision'],
                        '실제 로드 checkpoint revision 불일치')
                checkpoint = root / record['metadata']['checkpoint_path']
                require(audio_file_sha256(checkpoint) == cache['microsoft--msclap']['files']['CLAP_weights_2023.pth']['sha256'],
                        '실제 로드 checkpoint hash 불일치')
                key = input_row['track_id'] + '_' + str(repetition)
                vectors[key + '_raw'] = raw.numpy()
                vectors[key + '_representative'] = representative.numpy()
                record['repetition'] = repetition
                runs.append(record)
                if repetition:
                    baseline = torch.from_numpy(vectors[input_row['track_id'] + '_0_representative'])
                    comparison = differences(baseline, representative)
                    comparison.update(track_id=input_row['track_id'], repetition=repetition,
                                      chunk_raw_exact_equal=bool(np.array_equal(vectors[input_row['track_id'] + '_0_raw'], raw.numpy())))
                    if not comparison['chunk_raw_exact_equal']:
                        comparison['status'] = 'REVIEW_REQUIRED'
                    same_process.append(comparison)
                print(f"{input_row['title']} 반복 {repetition + 1}: {record['batch_shape']} → {record['representative_shape']} PASS", flush=True)
    vector_path = args.report.with_suffix('.vectors.npz')
    with vector_path.open('xb') as stream:
        np.savez(stream, **vectors)
    return {'runs': runs, 'same_process_reproducibility': same_process,
            'local_vector_evidence': {'path': vector_path.relative_to(root).as_posix(),
                                      'sha256': audio_file_sha256(vector_path), 'git_tracked': False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--phase-a-report', type=Path, default=Path('docs/experiments/audio-highlight-phase-a/inspection-report.md'))
    parser.add_argument('--cache', type=Path, default=Path('datasets/fma/huggingface'))
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    args.report = args.report.resolve()
    if not args.report.is_relative_to(root / 'datasets'):
        parser.error('report는 Git 제외 datasets 아래에 저장해야 합니다')
    child_report = args.report.with_name(args.report.stem + '-reload.json')
    reserved = [args.report, args.report.with_suffix('.vectors.npz')]
    if not args.worker:
        reserved += [child_report, child_report.with_suffix('.vectors.npz')]
    if args.repeat < 2 or any(p.exists() for p in reserved):
        parser.error('repeat는 최소 2이며 report/vector 경로는 새 경로여야 합니다')
    evidence = {'schema_version': SCHEMA_VERSION, 'tool_version': TOOL_VERSION,
                'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'repository_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                'tool_sha256': audio_file_sha256(Path(__file__)),
                'generator_sha256': audio_file_sha256(root / 'app/embedding/audio_embedding.py'),
                'status': 'FAIL', 'unresolved': []}
    try:
        manifest = load_manifest(args.manifest, root)
        inputs = preflight(manifest, root, args.phase_a_report)
        evidence.update(inputs=inputs, phase_a_manifest={'dataset_id': manifest['dataset_id'],
                        'path': args.manifest.as_posix(), 'sha256': audio_file_sha256(args.manifest),
                        'inspection_report_sha256': audio_file_sha256(args.phase_a_report)},
                        rights_cleared=True, rights_scope='phase_a_local_msclap_technical_validation')
        os.environ['HF_HOME'] = str(args.cache.resolve())
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        cache = cache_identity(args.cache)
        evidence['cache'] = cache
        evidence['environment'] = {
            'python': platform.python_version(), 'platform': platform.platform(),
            'python_executable': sys.executable, 'device': 'cpu', 'cuda_available': torch.cuda.is_available(),
            'packages': {n: importlib.metadata.version(n) for n in
                         ('msclap', 'torch', 'torchaudio', 'numpy', 'soundfile', 'transformers')},
            'libsndfile': sf.__libsndfile_version__, 'available_audio_backends': torchaudio.list_audio_backends(),
            'backend_selection': 'production_default_dispatcher',
            'torch_cpu_threads': torch.get_num_threads(), 'torch_interop_threads': torch.get_num_interop_threads(),
            'hf_home': args.cache.as_posix(), 'offline': True,
            'execution_environment_role': 'one_time_local_validation_not_official_long_term_environment',
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        evidence.update(run_process(args, root, inputs, cache))
        if not args.worker:
            command = [sys.executable, '-X', 'utf8', '-B', '-m', 'scripts.embedding.validate_audio_highlight_msclap',
                       '--manifest', str(args.manifest), '--phase-a-report', str(args.phase_a_report),
                       '--cache', str(args.cache), '--repeat', str(args.repeat), '--report', str(child_report), '--worker']
            completed = subprocess.run(command, cwd=root, check=False)
            child = read_reload_result(child_report, completed.returncode)
            evidence['reloaded_process'] = child
            require(child['cache'] == cache and child['phase_a_manifest'] == evidence['phase_a_manifest']
                    and child['environment'] == evidence['environment'], '별도 process 실행 identity 불일치')
            cross = []
            with np.load(args.report.with_suffix('.vectors.npz'), allow_pickle=False) as first, \
                    np.load(child_report.with_suffix('.vectors.npz'), allow_pickle=False) as second:
                for track in inputs:
                    for repetition in range(args.repeat):
                        key = track['track_id'] + '_' + str(repetition)
                        comparison = differences(torch.from_numpy(first[track['track_id'] + '_0_representative']),
                                                 torch.from_numpy(second[key + '_representative']))
                        comparison.update(track_id=track['track_id'], repetition=repetition,
                                          chunk_raw_exact_equal=bool(np.array_equal(first[track['track_id'] + '_0_raw'], second[key + '_raw'])))
                        if not comparison['chunk_raw_exact_equal']:
                            comparison['status'] = 'REVIEW_REQUIRED'
                        cross.append(comparison)
            evidence['cross_process_reproducibility'] = cross
        comparisons = evidence['same_process_reproducibility'] + evidence.get('cross_process_reproducibility', [])
        evidence['status'] = 'PASS' if all(c['status'] == 'PASS' for c in comparisons) else 'REVIEW_REQUIRED'
        if evidence['status'] != 'PASS':
            evidence['unresolved'].append('실제 MSCLAP 재현성 허용 오차 정책 미정. exact 불일치로 별도 검토가 필요합니다.')
        for row in inputs:
            require(audio_file_sha256(root / row['path']) == row['sha256'], '최종 입력 SHA 변경')
            require(audio_file_sha256(root / row['original_mp3_path']) == row['original_mp3_sha256'],
                    '최종 원본 MP3 SHA 변경')
        evidence['input_sha_after_execution_unchanged'] = True
        evidence['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(args.report, evidence)
        print(f"검증 결과: {evidence['status']} — {args.report}", flush=True)
        return 0 if evidence['status'] == 'PASS' else 1
    except (AudioEmbeddingError, DatasetError, ValidationError, OSError, subprocess.CalledProcessError) as error:
        evidence['error'] = str(error)
        if error.__cause__ is not None:
            evidence['cause'] = str(error.__cause__)
        write_json(args.report, evidence)
        print(f'검증 실패: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
