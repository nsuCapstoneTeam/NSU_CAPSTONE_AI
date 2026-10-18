"""Validate and optionally register one local calibration cohort source audio file."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

import soundfile as sf

from scripts.datasets.highlight_dataset import (
    DatasetError, audio_info, decode, relative_path, sha256,
)
from scripts.matching.validate_calibration import (
    CALIBRATION_DIR,
    _read_json,
    _parse_json_bytes,
    validate_calibration,
)
from scripts.matching.calibration_manifest_io import exclusive_manifest_update


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = CALIBRATION_DIR / 'manifest.json'
DEFAULT_SOURCE_ROOT = 'data/calibration/audio/source/'
ACQUISITION_METHODS = ('official_direct_download', 'other_confirmed_method')
SOURCE_FILE_KINDS = ('full_track', 'preview', 'sample', 'unknown')
_MP3_LAYER_III_MAX_FRAME_SAMPLES = 1152
_MP3_METADATA_FRAME_TOLERANCE = 2 * _MP3_LAYER_III_MAX_FRAME_SAMPLES


def validate_decoded_container_metadata(
    frames, sample_rate, channels, info, context, catalog_duration=None
):
    """Check decoder metadata against container metadata without trusting MP3 estimates."""
    if sample_rate != info.samplerate or channels != info.channels:
        raise ValueError(
            f'{context} decoder and container metadata disagree: '
            f'decoded={(frames, sample_rate, channels)}, '
            f'container={(info.frames, info.samplerate, info.channels)}'
        )
    frame_difference = abs(frames - info.frames)
    if frames == info.frames:
        return
    # libsndfile's MP3 frame count is a duration estimate; MPEG Layer III emits
    # at most 1152 PCM samples per MPEG-1 frame. Permit only a two-frame bound.
    if info.format == 'MP3':
        if frame_difference <= _MP3_METADATA_FRAME_TOLERANCE:
            return
        # VBR MP3 frame counts from libsndfile can be bitrate-based estimates.
        # For larger estimates, accept only when decoded duration independently
        # agrees with the already-vetted provider catalog duration (rounded sec).
        if (isinstance(catalog_duration, (int, float))
                and abs(frames / sample_rate - catalog_duration) <= 1.0):
            return
    raise ValueError(
        f'{context} decoder and container metadata disagree: '
        f'decoded={(frames, sample_rate, channels)}, '
        f'container={(info.frames, info.samplerate, info.channels)}'
    )


def _validate_payload(manifest, manifest_path):
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
            f'updated manifest failed calibration validation ({manifest_path}):\n- '
            + '\n- '.join(errors)
        )


def _sample_for_id(manifest, sample_id):
    matches = [sample for sample in manifest['samples'] if sample.get('sample_id') == sample_id]
    if len(matches) != 1:
        raise ValueError(f'{sample_id}: expected exactly one manifest sample, found {len(matches)}')
    return matches[0]


def inspect_source_audio(
    source_file, sample_id, repository_root=REPOSITORY_ROOT, catalog_duration=None
):
    """Decode an in-repository source file and return its stable identity metadata."""
    root = Path(repository_root).resolve()
    if not isinstance(source_file, str) or not source_file.strip():
        raise ValueError('source_file must be a non-blank repository-relative path')
    prefix = f'{DEFAULT_SOURCE_ROOT}{sample_id}/'
    if not source_file.startswith(prefix):
        raise ValueError(f'source_file must be below {prefix}')
    path = relative_path(root, source_file)
    expected_sample_directory = (root / prefix.rstrip('/')).resolve()
    if not path.is_relative_to(expected_sample_directory):
        raise ValueError(f'source file resolves outside its sample directory: {source_file}')
    if not path.is_file():
        raise FileNotFoundError(f'source audio file does not exist: {source_file}')

    digest_before = sha256(path)
    size_before = path.stat().st_size
    try:
        pcm, sample_rate = decode(path)
        info = audio_info(path)
    except (DatasetError, OSError, RuntimeError, sf.LibsndfileError) as exc:
        raise ValueError(f'source audio decode/metadata inspection failed: {exc}') from exc

    frames, channels = pcm.shape
    if frames <= 0 or channels <= 0 or sample_rate <= 0:
        raise ValueError('decoded frame count, sample rate and channels must be positive')
    validate_decoded_container_metadata(
        frames, sample_rate, channels, info, 'source audio', catalog_duration
    )
    digest_after = sha256(path)
    size_after = path.stat().st_size
    if digest_before != digest_after or size_before != size_after:
        raise ValueError('source file changed while it was being inspected')

    return {
        'source_local_path': source_file,
        'source_sha256': digest_after,
        'source_file_size': size_after,
        'decoded_duration': frames / sample_rate,
        'decoded_frame_count': frames,
        'source_sample_rate': sample_rate,
        'source_channels': channels,
        'source_codec': f'{info.format}/{info.subtype}',
    }


def register_source_audio(
    manifest,
    sample_id,
    source_file,
    acquisition_method,
    source_file_kind,
    full_track_verified,
    full_track_evidence,
    repository_root=REPOSITORY_ROOT,
):
    """Return a validated copy of the manifest with one newly inspected source registered."""
    if acquisition_method not in ACQUISITION_METHODS:
        raise ValueError(f'acquisition_method must be one of {ACQUISITION_METHODS}')
    if source_file_kind not in SOURCE_FILE_KINDS:
        raise ValueError(f'source_file_kind must be one of {SOURCE_FILE_KINDS}')
    if full_track_verified is True:
        if source_file_kind != 'full_track':
            raise ValueError('full_track_verified requires source_file_kind=full_track')
        if not isinstance(full_track_evidence, str) or not full_track_evidence.strip():
            raise ValueError('full_track_verified requires non-blank full_track_evidence')

    candidate = deepcopy(manifest)
    sample = _sample_for_id(candidate, sample_id)
    if sample.get('acquisition_method') not in ('not_acquired', 'pending'):
        raise ValueError(f'{sample_id}: source is already registered; refusing to replace it')

    metadata = inspect_source_audio(
        source_file, sample_id, repository_root,
        catalog_duration=sample.get('source_catalog_duration'),
    )
    if full_track_verified is True and metadata['decoded_duration'] < 60:
        raise ValueError(
            'full_track_verified cannot be true when decoded audio is shorter than 60 seconds'
        )
    other_samples = [row for row in candidate['samples'] if row is not sample]
    matching_hash = [
        row.get('sample_id') for row in other_samples
        if row.get('source_sha256') == metadata['source_sha256']
        and metadata['source_sha256'] is not None
    ]
    if matching_hash:
        raise ValueError(
            f'duplicate source content SHA-256 already registered for: {", ".join(matching_hash)}'
        )

    sample.update(metadata)
    sample.update({
        'acquisition_method': acquisition_method,
        'source_file_kind': source_file_kind,
        'full_track_verified': full_track_verified,
        'full_track_evidence': full_track_evidence,
    })
    _validate_payload(candidate, DEFAULT_MANIFEST)
    return candidate, metadata


def _atomic_write_manifest(manifest_path, manifest, expected_manifest_sha256):
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f'.{manifest_path.name}.', suffix='.tmp', dir=manifest_path.parent
        )
        temporary_path = Path(name)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=4, separators=(',', ':  '))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        reloaded = _parse_json_bytes(
            temporary_path.read_bytes(), 'temporary manifest', temporary_path
        )
        _validate_payload(reloaded, manifest_path)
        with exclusive_manifest_update(manifest_path, expected_manifest_sha256):
            os.replace(temporary_path, manifest_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--sample-id', required=True)
    parser.add_argument('--source-file', required=True,
                        help='repository-relative path below data/calibration/audio/source/<sample_id>/')
    parser.add_argument('--acquisition-method', required=True, choices=ACQUISITION_METHODS)
    parser.add_argument('--source-file-kind', required=True, choices=SOURCE_FILE_KINDS)
    verification = parser.add_mutually_exclusive_group()
    verification.add_argument('--full-track-verified', action='store_true', dest='full_track_verified')
    verification.add_argument('--full-track-unverified', action='store_false', dest='full_track_verified')
    parser.set_defaults(full_track_verified=None)
    parser.add_argument('--full-track-evidence')
    parser.add_argument('--write', action='store_true',
                        help='atomically update the manifest after all validation succeeds')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        manifest_bytes = args.manifest.read_bytes()
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        manifest = _parse_json_bytes(manifest_bytes, 'manifest', args.manifest)
        candidate, metadata = register_source_audio(
            manifest=manifest,
            sample_id=args.sample_id,
            source_file=args.source_file,
            acquisition_method=args.acquisition_method,
            source_file_kind=args.source_file_kind,
            full_track_verified=args.full_track_verified,
            full_track_evidence=args.full_track_evidence,
            repository_root=REPOSITORY_ROOT,
        )
        result = {
            'mode': 'write' if args.write else 'dry_run',
            'sample_id': args.sample_id,
            'metadata': metadata,
        }
        if args.write:
            _atomic_write_manifest(args.manifest, candidate, manifest_sha256)
            result['manifest_updated'] = True
        else:
            result['manifest_updated'] = False
            result['message'] = 'Validation passed; rerun with --write to update the manifest.'
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Calibration audio registration failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
