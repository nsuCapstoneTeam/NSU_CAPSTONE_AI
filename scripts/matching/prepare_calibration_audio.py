"""Create and validate one centered, exact 60-second calibration WAV."""

import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

import numpy as np
import soundfile as sf

from scripts.datasets.highlight_dataset import DatasetError, decode, relative_path, sha256, wav_bytes
from scripts.matching import register_calibration_audio as registration
from scripts.matching.validate_calibration import CALIBRATION_DIR, _read_json, validate_calibration


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = CALIBRATION_DIR / 'manifest.json'
PREPARED_ROOT = 'data/calibration/audio/prepared/'
SOURCE_ROOT = 'data/calibration/audio/source/'
SEGMENT_RULE = 'offline_calibration_decoded_audio_center_exact_60_seconds'


def _validate_manifest(manifest, manifest_path):
    manifest_schema = _read_json(CALIBRATION_DIR / 'manifest.schema.json', 'manifest schema')
    event_queries = _read_json(CALIBRATION_DIR / 'event-queries.json', 'event queries')
    event_queries_schema = _read_json(
        CALIBRATION_DIR / 'event-queries.schema.json', 'event query schema'
    )
    errors = validate_calibration(
        manifest, manifest_schema, event_queries, event_queries_schema
    )
    if errors:
        raise ValueError(
            f'calibration manifest validation failed ({manifest_path}):\n- '
            + '\n- '.join(errors)
        )


def _sample_for_id(manifest, sample_id):
    matches = [sample for sample in manifest['samples'] if sample.get('sample_id') == sample_id]
    if len(matches) != 1:
        raise ValueError(f'{sample_id}: expected exactly one manifest sample, found {len(matches)}')
    return matches[0]


def _has_prepared_metadata(sample):
    return any(sample.get(field) is not None for field in (
        'prepared_local_path', 'prepared_sha256', 'prepared_duration',
        'segment_start_frame', 'segment_end_frame_exclusive',
    ))


def _resolve_source(sample, sample_id, repository_root):
    source_relative = sample.get('source_local_path')
    expected_prefix = f'{SOURCE_ROOT}{sample_id}/'
    if not isinstance(source_relative, str) or not source_relative.strip():
        raise ValueError(f'{sample_id}.source_local_path is missing or blank')
    if not source_relative.startswith(expected_prefix):
        raise ValueError(f'{sample_id}.source_local_path must be below {expected_prefix}')
    source_path = relative_path(repository_root, source_relative)
    sample_directory = (repository_root / expected_prefix.rstrip('/')).resolve()
    if not source_path.is_relative_to(sample_directory):
        raise ValueError(f'{sample_id}.source_local_path resolves outside its sample directory')
    if not source_path.is_file():
        raise FileNotFoundError(f'{sample_id} source file does not exist: {source_relative}')
    return source_relative, source_path


def _require_source_gate(sample, sample_id):
    required = (
        'source_sha256', 'source_file_size', 'decoded_duration', 'decoded_frame_count',
        'source_sample_rate', 'source_channels',
    )
    missing = [field for field in required if sample.get(field) is None]
    if missing:
        raise ValueError(f'{sample_id} is missing registered source metadata: {", ".join(missing)}')
    if sample.get('acquisition_method') not in registration.ACQUISITION_METHODS:
        raise ValueError(f'{sample_id} has no completed acquisition method')
    if sample.get('source_file_kind') != 'full_track':
        raise ValueError(f'{sample_id} preparation requires source_file_kind=full_track')
    if sample.get('full_track_verified') is not True:
        raise ValueError(f'{sample_id} preparation requires full_track_verified=true')
    evidence = sample.get('full_track_evidence')
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError(f'{sample_id} preparation requires non-blank full_track_evidence')
    if type(sample.get('decoded_frame_count')) is not int or sample['decoded_frame_count'] <= 0:
        raise ValueError(f'{sample_id}.decoded_frame_count must be a positive integer')
    if type(sample.get('source_sample_rate')) is not int or sample['source_sample_rate'] <= 0:
        raise ValueError(f'{sample_id}.source_sample_rate must be a positive integer')
    if type(sample.get('source_channels')) is not int or sample['source_channels'] <= 0:
        raise ValueError(f'{sample_id}.source_channels must be a positive integer')
    if type(sample.get('source_file_size')) is not int or sample['source_file_size'] <= 0:
        raise ValueError(f'{sample_id}.source_file_size must be a positive integer')
    if not isinstance(sample.get('source_sha256'), str) or not sample['source_sha256'].strip():
        raise ValueError(f'{sample_id}.source_sha256 must be non-blank')
    if sample['decoded_frame_count'] < 60 * sample['source_sample_rate']:
        raise ValueError(f'{sample_id} decoded source is shorter than 60 seconds')


def _inspect_registered_source(sample, sample_id, repository_root):
    source_relative, source_path = _resolve_source(sample, sample_id, repository_root)
    expected_hash = sample['source_sha256']
    expected_size = sample['source_file_size']
    if sha256(source_path) != expected_hash:
        raise ValueError(f'{sample_id} source SHA-256 differs from registered source_sha256')
    if source_path.stat().st_size != expected_size:
        raise ValueError(f'{sample_id} source file size differs from registered source_file_size')
    try:
        pcm, sample_rate = decode(source_path)
        info = sf.info(str(source_path))
    except (DatasetError, OSError, RuntimeError, sf.LibsndfileError) as exc:
        raise ValueError(f'{sample_id} source decode failed: {exc}') from exc

    frame_count, channels = pcm.shape
    actual = (frame_count, sample_rate, channels)
    expected = (
        sample['decoded_frame_count'], sample['source_sample_rate'], sample['source_channels']
    )
    container = (info.frames, info.samplerate, info.channels)
    if actual != expected:
        raise ValueError(f'{sample_id} decoded source metadata changed: {actual}, expected {expected}')
    if actual != container:
        raise ValueError(f'{sample_id} decoder/container metadata disagree: {actual} != {container}')
    if frame_count < 60 * sample_rate:
        raise ValueError(f'{sample_id} decoded source is shorter than 60 seconds')
    if sample.get('source_codec') is not None and sample['source_codec'] != f'{info.format}/{info.subtype}':
        raise ValueError(
            f'{sample_id} source codec/container identity differs from registered source_codec'
        )
    if sha256(source_path) != expected_hash or source_path.stat().st_size != expected_size:
        raise ValueError(f'{sample_id} source changed while it was being decoded')
    return source_relative, source_path, pcm, sample_rate


def _validate_prepared_wav(path, expected_pcm, sample_rate, sample_id):
    try:
        decoded, output_rate = decode(path)
        info = sf.info(str(path))
    except (DatasetError, OSError, RuntimeError, sf.LibsndfileError) as exc:
        raise ValueError(f'{sample_id} prepared WAV re-decode failed: {exc}') from exc
    expected_frames, expected_channels = expected_pcm.shape
    if info.format != 'WAV' or info.subtype != 'FLOAT':
        raise ValueError(f'{sample_id} prepared WAV must be WAV with IEEE float32 (FLOAT) subtype')
    if (len(decoded) != expected_frames or output_rate != sample_rate
            or decoded.shape[1] != expected_channels):
        raise ValueError(
            f'{sample_id} prepared WAV metadata mismatch: '
            f'{(len(decoded), output_rate, decoded.shape[1])}, '
            f'expected {(expected_frames, sample_rate, expected_channels)}'
        )
    if not np.isfinite(decoded).all():
        raise ValueError(f'{sample_id} prepared WAV contains non-finite PCM')
    if not np.array_equal(decoded, expected_pcm):
        raise ValueError(f'{sample_id} prepared WAV PCM differs from the centered source slice')
    if info.frames != expected_frames or info.samplerate != sample_rate or info.channels != expected_channels:
        raise ValueError(f'{sample_id} prepared WAV container metadata does not match decoded PCM')
    return sha256(path), path.stat().st_size


def _write_temp_manifest(manifest_path, manifest):
    descriptor, name = tempfile.mkstemp(
        prefix=f'.{manifest_path.name}.', suffix='.tmp', dir=manifest_path.parent
    )
    temporary_path = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=4, separators=(',', ':  '))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        loaded = json.loads(temporary_path.read_text(encoding='utf-8'))
        _validate_manifest(loaded, manifest_path)
        return temporary_path
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _write_temp_audio(payload, directory):
    descriptor, name = tempfile.mkstemp(prefix='.calibration-audio-', suffix='.wav.tmp', dir=directory)
    temporary_path = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return temporary_path
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _publish_pair(
    temp_audio, output_path, temp_manifest, manifest_path, expected_sha256,
    prepared_relative, sample_id,
):
    audio_published = False
    manifest_published = False
    original_manifest = manifest_path.read_bytes()
    try:
        # Hard-link publication is atomic and fails rather than replacing an existing prepared file.
        os.link(temp_audio, output_path)
        audio_published = True
        temp_audio.unlink()
        os.replace(temp_manifest, manifest_path)
        manifest_published = True
        if sha256(output_path) != expected_sha256:
            raise ValueError(f'{sample_id} published prepared SHA-256 mismatch')
        published_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        published_sample = _sample_for_id(published_manifest, sample_id)
        if (published_sample.get('prepared_local_path') != prepared_relative
                or published_sample.get('prepared_sha256') != expected_sha256):
            raise ValueError(f'{sample_id} published manifest does not identify the prepared WAV')
    except BaseException as exc:
        rollback_errors = []
        manifest_rollback_succeeded = not manifest_published
        if manifest_published:
            try:
                descriptor, name = tempfile.mkstemp(
                    prefix=f'.{manifest_path.name}.rollback-', suffix='.tmp', dir=manifest_path.parent
                )
                rollback_manifest = Path(name)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(original_manifest)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(rollback_manifest, manifest_path)
                manifest_rollback_succeeded = True
            except OSError as rollback_error:
                rollback_errors.append(f'manifest rollback failed: {rollback_error}')
            finally:
                if 'rollback_manifest' in locals():
                    rollback_manifest.unlink(missing_ok=True)
        if audio_published and manifest_rollback_succeeded:
            try:
                output_path.unlink()
            except OSError as rollback_error:
                rollback_errors.append(f'prepared WAV rollback failed: {rollback_error}')
        if rollback_errors:
            raise RuntimeError(
                f'{sample_id} transactional publish failed ({exc}); '
                + '; '.join(rollback_errors)
            ) from exc
        raise
    finally:
        temp_audio.unlink(missing_ok=True)
        temp_manifest.unlink(missing_ok=True)


def prepare_sample(manifest, sample_id, repository_root=REPOSITORY_ROOT):
    """Build a validated deterministic prepared WAV and updated manifest in memory."""
    root = Path(repository_root).resolve()
    _validate_manifest(manifest, DEFAULT_MANIFEST)
    candidate = deepcopy(manifest)
    sample = _sample_for_id(candidate, sample_id)
    _require_source_gate(sample, sample_id)
    if _has_prepared_metadata(sample):
        raise ValueError(f'{sample_id} already has prepared metadata; refusing to replace it')

    source_relative, source_path, source_pcm, sample_rate = _inspect_registered_source(
        sample, sample_id, root
    )
    frame_count = len(source_pcm)
    target_frames = 60 * sample_rate
    remaining_frames = frame_count - target_frames
    start_frame = remaining_frames // 2
    end_frame_exclusive = start_frame + target_frames
    if end_frame_exclusive - start_frame != target_frames or end_frame_exclusive > frame_count:
        raise ValueError(f'{sample_id} centered frame range is invalid')
    prepared_pcm = source_pcm[start_frame:end_frame_exclusive].copy()
    if prepared_pcm.shape != (target_frames, sample['source_channels']):
        raise ValueError(f'{sample_id} centered source slice has unexpected shape {prepared_pcm.shape}')
    payload = wav_bytes(prepared_pcm, sample_rate)
    prepared_relative = f'{PREPARED_ROOT}{sample_id}.wav'
    prepared_path = relative_path(root, prepared_relative)
    if not prepared_path.is_relative_to((root / PREPARED_ROOT.rstrip('/')).resolve()):
        raise ValueError(f'{sample_id} prepared path escapes the repository prepared directory')
    if prepared_path.exists():
        raise FileExistsError(f'{sample_id} prepared output already exists: {prepared_relative}')

    with tempfile.TemporaryDirectory(prefix='calibration-audio-prepare-') as temporary_directory:
        validation_audio = _write_temp_audio(payload, Path(temporary_directory))
        prepared_sha, prepared_size = _validate_prepared_wav(
            validation_audio, prepared_pcm, sample_rate, sample_id
        )

    sample.update({
        'segment_rule': SEGMENT_RULE,
        'segment_start_frame': start_frame,
        'segment_end_frame_exclusive': end_frame_exclusive,
        'prepared_local_path': prepared_relative,
        'prepared_sha256': prepared_sha,
        'prepared_duration': 60,
    })
    _validate_manifest(candidate, DEFAULT_MANIFEST)
    return candidate, {
        'sample_id': sample_id,
        'source_local_path': source_relative,
        'source_sha256': sample['source_sha256'],
        'segment_rule': SEGMENT_RULE,
        'segment_start_frame': start_frame,
        'segment_end_frame_exclusive': end_frame_exclusive,
        'frame_count': target_frames,
        'sample_rate': sample_rate,
        'channels': sample['source_channels'],
        'prepared_local_path': prepared_relative,
        'prepared_sha256': prepared_sha,
        'prepared_file_size': prepared_size,
        'prepared_duration': 60,
        'prepared_subtype': 'FLOAT',
    }, payload, prepared_pcm


def _write_prepared_pair(manifest_path, candidate, result, payload, expected_pcm, repository_root):
    root = Path(repository_root).resolve()
    output_path = relative_path(root, result['prepared_local_path'])
    if output_path.exists():
        raise FileExistsError(f'refusing to overwrite existing prepared output: {output_path}')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_audio = _write_temp_audio(payload, output_path.parent)
    temp_manifest = None
    try:
        actual_sha, actual_size = _validate_prepared_wav(
            temp_audio,
            expected_pcm,
            result['sample_rate'],
            result['sample_id'],
        )
        if actual_sha != result['prepared_sha256'] or actual_size != result['prepared_file_size']:
            raise ValueError('temporary prepared WAV identity changed before publication')
        temp_manifest = _write_temp_manifest(manifest_path, candidate)
        _publish_pair(
            temp_audio,
            output_path,
            temp_manifest,
            manifest_path,
            result['prepared_sha256'],
            result['prepared_local_path'],
            result['sample_id'],
        )
    finally:
        temp_audio.unlink(missing_ok=True)
        if temp_manifest is not None:
            temp_manifest.unlink(missing_ok=True)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--sample-id', required=True)
    parser.add_argument('--write', action='store_true',
                        help='atomically publish the prepared WAV and manifest update')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        manifest = _read_json(args.manifest, 'manifest')
        candidate, result, payload, expected_pcm = prepare_sample(
            manifest, args.sample_id, repository_root=REPOSITORY_ROOT
        )
        result['mode'] = 'write' if args.write else 'dry_run'
        if args.write:
            _write_prepared_pair(
                args.manifest, candidate, result, payload, expected_pcm, REPOSITORY_ROOT
            )
            result['manifest_updated'] = True
            result['prepared_file_published'] = True
        else:
            result['manifest_updated'] = False
            result['prepared_file_published'] = False
            result['message'] = 'Validation passed; rerun with --write to publish both outputs.'
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'Calibration audio preparation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
