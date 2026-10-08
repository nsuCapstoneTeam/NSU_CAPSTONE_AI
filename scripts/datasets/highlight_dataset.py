"""Prepare and inspect the ADR-0007 Phase A fixture without model or DB access."""

import hashlib
import importlib.metadata
import io
import json
import platform
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
import torchaudio


class DatasetError(ValueError):
    def __init__(self, reason, path, detail):
        self.reason = reason
        self.path = str(path)
        self.detail = detail
        super().__init__(f'{path}: {reason}: {detail}')


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def environment():
    return {
        'python': platform.python_version(), 'platform': platform.platform(),
        'packages': {name: importlib.metadata.version(name)
                     for name in ('torch', 'torchaudio', 'soundfile')},
        'libsndfile': sf.__libsndfile_version__, 'backend': 'soundfile',
        'extraction_version': 'full-decode-frame-slice-float32-wav-v1',
    }


def relative_path(root, value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('path must be a repository-relative POSIX path')
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('path must stay inside repository root')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('resolved path leaves repository root')
    return resolved


def load_manifest(path, root):
    try:
        manifest = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
            raise ValueError('schema_version must be 1')
        if manifest.get('path_base') != 'repository_root':
            raise ValueError('path_base must be repository_root')
        if not isinstance(manifest.get('dataset_id'), str) or not manifest['dataset_id']:
            raise ValueError('dataset_id is required')
        tracks = manifest.get('tracks')
        if not isinstance(tracks, list) or not tracks:
            raise ValueError('tracks must be a nonempty list')
        ids, sources, outputs = set(), set(), set()
        for track in tracks:
            if not isinstance(track, dict):
                raise ValueError('each track must be an object')
            for key in ('track_id', 'title', 'artist'):
                if not isinstance(track[key], str) or not track[key]:
                    raise ValueError(f'{key} must be nonempty text')
            if track['track_id'] in ids:
                raise ValueError('duplicate track_id')
            ids.add(track['track_id'])
            source, highlight, rights = track['source'], track['highlight'], track['rights']
            if not all(isinstance(value, dict) for value in (source, highlight, rights)):
                raise ValueError('source, highlight and rights must be objects')
            source_path = relative_path(root, source['path'])
            output_path = relative_path(root, highlight['path'])
            if source_path in sources or output_path in outputs:
                raise ValueError('duplicate source or output path')
            sources.add(source_path)
            outputs.add(output_path)
            if output_path.suffix.lower() != '.wav':
                raise ValueError('output must be WAV')
            if not isinstance(source['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', source['sha256']):
                raise ValueError('source sha256 must be lowercase hex')
            for key in ('decoded_frames', 'sample_rate', 'channels'):
                if type(source[key]) is not int or source[key] <= 0:
                    raise ValueError(f'source {key} must be a positive integer')
            for key in ('start_seconds', 'duration_seconds', 'start_frame', 'end_frame_exclusive'):
                if type(highlight[key]) is not int or highlight[key] < 0:
                    raise ValueError(f'highlight {key} must be a nonnegative integer')
            if highlight['duration_seconds'] != 60:
                raise ValueError('highlight duration must be exactly 60 seconds')
            rate = source['sample_rate']
            if (highlight['start_frame'] != highlight['start_seconds'] * rate
                    or highlight['end_frame_exclusive'] != highlight['start_frame'] + 60 * rate):
                raise ValueError('inconsistent highlight frame boundaries')
            expected_policy = {'container': 'WAV', 'subtype': 'FLOAT', 'encoding': 'PCM_F',
                               'bits_per_sample': 32, 'sample_rate': 'preserve_source',
                               'channels': 'preserve_source'}
            if highlight['format_policy'] != expected_policy:
                raise ValueError('unsupported output format policy')
            if rights['verification_status'] not in ('pending', 'verified'):
                raise ValueError('rights verification_status must be pending or verified')
            for key in ('source_url', 'license', 'license_url', 'attribution'):
                if rights[key] is not None and not isinstance(rights[key], str):
                    raise ValueError(f'rights {key} must be text or null')
            if rights['verification_status'] == 'verified' and not all(rights[k] for k in
                    ('source_url', 'license', 'license_url', 'attribution')):
                raise ValueError('verified rights require source, license and attribution')
        if sources & outputs:
            raise ValueError('output cannot overwrite a source')
        return manifest
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        raise DatasetError('malformed_manifest', path, str(error)) from error


def decode(path):
    if not path.is_file():
        raise DatasetError('audio_missing', path, 'file does not exist')
    try:
        wave, rate = torchaudio.load(str(path), backend='soundfile')
    except (OSError, RuntimeError, sf.LibsndfileError) as error:
        raise DatasetError('decode_failed', path, str(error)) from error
    pcm = wave.numpy().T.copy()
    if pcm.ndim != 2 or not pcm.size or rate <= 0 or not np.isfinite(pcm).all():
        raise DatasetError('invalid_pcm', path, 'expected nonempty finite audio')
    return pcm, rate


def inspect_source(track, root):
    source, highlight = track['source'], track['highlight']
    path = relative_path(root, source['path'])
    if not path.is_file():
        raise DatasetError('source_missing', path, 'source file does not exist')
    digest = sha256(path)
    if digest != source['sha256']:
        raise DatasetError('source_hash_mismatch', path, 'source SHA-256 differs from manifest')
    pcm, rate = decode(path)
    actual = (len(pcm), rate, pcm.shape[1])
    expected = (source['decoded_frames'], source['sample_rate'], source['channels'])
    if actual != expected:
        raise DatasetError('source_metadata_mismatch', path, f'frames/rate/channels {actual}, expected {expected}')
    if highlight['end_frame_exclusive'] > len(pcm):
        raise DatasetError('insufficient_duration', path, 'selected interval exceeds decoded audio')
    if sha256(path) != digest:
        raise DatasetError('source_changed', path, 'source changed during decode')
    info = sf.info(str(path))
    result = {'source_sha256': digest, 'source_file_size_bytes': path.stat().st_size,
              'source_decoded_frames': len(pcm), 'source_duration_seconds': len(pcm) / rate,
              'source_sample_rate': rate, 'source_channels': pcm.shape[1],
              'source_format': info.format, 'source_subtype': info.subtype,
              'source_info_frames': info.frames, 'source_finite': True}
    return pcm, rate, result


def selected_pcm(track, pcm):
    h = track['highlight']
    return pcm[h['start_frame']:h['end_frame_exclusive']].copy()


def wav_bytes(pcm, rate):
    """Encode deterministic little-endian IEEE float32 RIFF/WAV bytes."""
    channels = pcm.shape[1]
    data = pcm.astype('<f4', copy=False).tobytes(order='C')
    fmt = struct.pack('<HHIIHH', 3, channels, rate, rate * channels * 4, channels * 4, 32)
    # libsndfile의 기본 FLOAT writer는 PEAK chunk에 시각을 넣으므로 해시가 달라진다.
    # 표준 fmt/fact/data만 기록해 PCM과 파일 바이트의 재현성을 함께 보장한다.
    body = (b'WAVEfmt ' + struct.pack('<I', len(fmt)) + fmt
            + b'fact' + struct.pack('<II', 4, len(pcm))
            + b'data' + struct.pack('<I', len(data)) + data)
    return b'RIFF' + struct.pack('<I', len(body)) + body


def validate_output(track, root, expected, rate, repeat=False):
    path = relative_path(root, track['highlight']['path'])
    pcm, output_rate = decode(path)
    info = sf.info(str(path))
    if info.format != 'WAV' or info.subtype != 'FLOAT':
        raise DatasetError('output_format_mismatch', path, 'expected WAV / PCM_F / float32')
    if output_rate != rate or pcm.shape != expected.shape or len(pcm) != 60 * rate:
        raise DatasetError('output_metadata_mismatch', path, 'duration/frame/rate/channel mismatch')
    if not np.array_equal(pcm, expected):
        raise DatasetError('output_pcm_mismatch', path, 'PCM differs from decoded source interval')
    digest = sha256(path)
    result = {'output_sha256': digest, 'output_file_size_bytes': path.stat().st_size,
              'output_frames': len(pcm), 'output_duration_seconds': len(pcm) / rate,
              'output_sample_rate': rate, 'output_channels': pcm.shape[1],
              'output_format': info.format, 'output_subtype': info.subtype,
              'output_finite': True, 'pcm_identical': True}
    if repeat:
        # 원본을 다시 decode해 기존 출력을 덮어쓰지 않고 PCM과 WAV 바이트 재현성을 확인한다.
        repeated_source, repeated_rate, _ = inspect_source(track, root)
        repeated = selected_pcm(track, repeated_source)
        payload = wav_bytes(repeated, repeated_rate)
        repeated_pcm, repeated_output_rate = sf.read(io.BytesIO(payload), dtype='float32', always_2d=True)
        repeated_hash = hashlib.sha256(payload).hexdigest()
        if (repeated_hash != digest or repeated_output_rate != rate
                or not np.array_equal(repeated_pcm, pcm)):
            raise DatasetError('reproducibility_failed', path, 'repeated decode and WAV generation differ')
        result.update(reproducible=True, repeated_output_sha256=repeated_hash)
    if sha256(path) != digest:
        raise DatasetError('output_changed', path, 'output changed during validation')
    return result


def process_track(track, root, mode, repeat=False):
    path = relative_path(root, track['highlight']['path'])
    if mode == 'prepare' and path.exists():
        raise DatasetError('output_exists', path, 'refusing to overwrite existing output')
    pcm, rate, result = inspect_source(track, root)
    if mode != 'source':
        selected = selected_pcm(track, pcm)
        if mode == 'prepare':
            path.parent.mkdir(parents=True, exist_ok=True)
            # 사전 확인 이후 만들어진 파일도 보호하도록 배타적으로 생성한다.
            with path.open('xb') as stream:
                stream.write(wav_bytes(selected, rate))
        result.update(validate_output(track, root, selected, rate, repeat=repeat))
    if sha256(relative_path(root, track['source']['path'])) != track['source']['sha256']:
        raise DatasetError('source_changed', track['source']['path'], 'source changed during processing')
    return result


def run(manifest, root, mode, repeat=False):
    results = []
    for track in manifest['tracks']:
        row = {'track_id': track['track_id'], 'title': track['title'],
               'source_path': track['source']['path'], 'output_path': track['highlight']['path'],
               'rights_verification_status': track['rights']['verification_status']}
        try:
            row.update(process_track(track, root, mode, repeat))
            row['technical_status'] = 'passed'
        except DatasetError as error:
            row.update(technical_status='failed', reason=error.reason,
                       failed_path=error.path, detail=error.detail)
        except OSError as error:
            row.update(technical_status='failed', reason='file_io_failed',
                       failed_path=str(error.filename or track['source']['path']), detail=str(error))
        results.append(row)
    return {'dataset_id': manifest['dataset_id'], 'mode': mode,
            'executed_at_utc': datetime.now(timezone.utc).isoformat(), 'environment': environment(),
            'technical_passed': all(r['technical_status'] == 'passed' for r in results),
            'rights_cleared': all(r['rights_verification_status'] == 'verified' for r in results),
            'tracks': results}
