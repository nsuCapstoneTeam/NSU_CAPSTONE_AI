"""Calibration manifest의 sample_id 고유성을 검사하는 CLI."""

import argparse
import json
import re
import sys
from pathlib import Path


DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / 'docs'
    / 'experiments'
    / 'audio-similarity-calibration'
    / 'manifest.json'
)

_SHA256_RE = re.compile(r'^[a-f0-9]{64}$')
_SOURCE_AUDIO_ROOT = 'data/calibration/audio/source/'
_PREPARED_AUDIO_ROOT = 'data/calibration/audio/prepared/'
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _valid_repository_relative_audio_path(value, prefix):
    """Accept only a repository-relative POSIX path below the requested data directory."""
    if not isinstance(value, str) or not value.strip() or '\\' in value:
        return False
    if value.startswith('/') or re.match(r'^[A-Za-z]:', value):
        return False
    if not value.startswith(prefix):
        return False
    components = value.split('/')
    return all(component not in ('', '.', '..') for component in components)


def _resolves_within_repository(value, repository_root):
    root = Path(repository_root).resolve()
    candidate = root.joinpath(*value.split('/')).resolve(strict=False)
    return candidate.is_relative_to(root)


def acquisition_preparation_errors(manifest, repository_root=_REPOSITORY_ROOT):
    """Validate acquisition identity and the prerequisites for a prepared 60-second asset."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")

    errors = []
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        sample_id = sample.get('sample_id', f'samples[{index}]')

        source_path = sample.get('source_local_path')
        source_prefix = f'{_SOURCE_AUDIO_ROOT}{sample_id}/'
        if source_path is not None and not _valid_repository_relative_audio_path(source_path, source_prefix):
            errors.append(
                f'{sample_id}.source_local_path must be a repository-relative path below {source_prefix}'
            )
        elif source_path is not None:
            try:
                if not _resolves_within_repository(source_path, repository_root):
                    errors.append(f'{sample_id}.source_local_path resolves outside the repository root')
            except (OSError, RuntimeError, ValueError):
                errors.append(f'{sample_id}.source_local_path cannot be safely resolved')

        prepared_path = sample.get('prepared_local_path')
        expected_prepared_path = f'{_PREPARED_AUDIO_ROOT}{sample_id}.wav'
        if prepared_path is not None and prepared_path != expected_prepared_path:
            errors.append(
                f'{sample_id}.prepared_local_path must equal {expected_prepared_path}'
            )
        elif prepared_path is not None:
            try:
                if not _resolves_within_repository(prepared_path, repository_root):
                    errors.append(f'{sample_id}.prepared_local_path resolves outside the repository root')
            except (OSError, RuntimeError, ValueError):
                errors.append(f'{sample_id}.prepared_local_path cannot be safely resolved')

        method = sample.get('acquisition_method')
        kind = sample.get('source_file_kind')
        verified = sample.get('full_track_verified')
        evidence = sample.get('full_track_evidence')
        source_hash = sample.get('source_sha256')
        prepared_fields = (
            'prepared_local_path', 'prepared_sha256', 'prepared_duration',
            'segment_start_frame', 'segment_end_frame_exclusive',
        )
        prepared = any(sample.get(field) is not None for field in prepared_fields)

        if verified is True:
            if kind != 'full_track':
                errors.append(f'{sample_id}.full_track_verified=true requires source_file_kind=full_track')
            if not isinstance(evidence, str) or not evidence.strip():
                errors.append(f'{sample_id}.full_track_evidence must be non-blank when full_track_verified=true')

        if kind in ('preview', 'sample', 'unknown') and verified is True:
            errors.append(f'{sample_id} cannot verify {kind} as a full track')
        if kind in ('preview', 'sample', 'unknown') and prepared:
            errors.append(f'{sample_id} cannot be prepared when source_file_kind is {kind}')

        if method in ('not_acquired', 'pending'):
            pre_acquisition_fields = (
                'source_local_path', 'source_sha256', 'source_file_size', 'decoded_duration',
                'decoded_frame_count', 'source_sample_rate', 'source_channels', 'source_codec',
                'prepared_local_path', 'prepared_sha256', 'prepared_duration',
                'segment_start_frame', 'segment_end_frame_exclusive',
            )
            if any(sample.get(field) is not None for field in pre_acquisition_fields):
                errors.append(f'{sample_id} cannot record acquired/prepared metadata while {method}')
            if kind != 'unknown' or verified is not None or evidence is not None:
                errors.append(f'{sample_id} must leave full-track verification unknown while {method}')
            continue

        if method in ('official_direct_download', 'other_confirmed_method'):
            if not _valid_repository_relative_audio_path(source_path, source_prefix):
                errors.append(f'{sample_id}.source_local_path is required for an acquired source')
            if not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(source_hash):
                errors.append(f'{sample_id}.source_sha256 is required for an acquired source')
            size = sample.get('source_file_size')
            if type(size) is not int or size <= 0:
                errors.append(f'{sample_id}.source_file_size must be a positive integer for an acquired source')

        if verified is True:
            required_verified_fields = (
                'source_local_path', 'source_sha256', 'source_file_size', 'decoded_duration',
                'decoded_frame_count', 'source_sample_rate', 'source_channels',
            )
            missing = [field for field in required_verified_fields if sample.get(field) is None]
            if missing:
                errors.append(f'{sample_id} verified full-track state requires: {", ".join(missing)}')
            duration = sample.get('decoded_duration')
            if isinstance(duration, (int, float)) and duration < 60:
                errors.append(f'{sample_id} verified full-track decoded_duration must be at least 60 seconds')

        if prepared:
            required_source = (
                ('source_local_path', source_path),
                ('source_sha256', source_hash),
                ('source_file_size', sample.get('source_file_size')),
                ('decoded_duration', sample.get('decoded_duration')),
                ('decoded_frame_count', sample.get('decoded_frame_count')),
                ('source_sample_rate', sample.get('source_sample_rate')),
                ('source_channels', sample.get('source_channels')),
            )
            missing = [field for field, value in required_source if value is None]
            if missing:
                errors.append(f'{sample_id} prepared metadata requires source/decode fields: {", ".join(missing)}')
            if method not in ('official_direct_download', 'other_confirmed_method'):
                errors.append(f'{sample_id} prepared metadata requires a completed acquisition')
            if kind != 'full_track' or verified is not True or not isinstance(evidence, str) or not evidence.strip():
                errors.append(f'{sample_id} prepared metadata requires verified full-track evidence')
            duration = sample.get('decoded_duration')
            if isinstance(duration, (int, float)) and duration < 60:
                errors.append(f'{sample_id} decoded_duration must be at least 60 seconds before preparation')

    return errors


def duplicate_source_content_hashes(manifest):
    """Return repeated non-blank source hashes regardless of cohort status."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")

    seen = set()
    duplicates = set()
    for sample in manifest['samples']:
        digest = sample.get('source_sha256') if isinstance(sample, dict) else None
        if isinstance(digest, str) and digest.strip() and _SHA256_RE.fullmatch(digest):
            if digest in seen:
                duplicates.add(digest)
            seen.add(digest)
    return sorted(duplicates)


def duplicate_sample_ids(manifest):
    """Manifest 안에서 두 번 이상 등장하는 sample_id를 반환한다."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")

    seen = set()
    duplicates = set()
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        sample_id = sample.get('sample_id')
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f'samples[{index}].sample_id must be a non-empty string')
        if sample_id in seen:
            duplicates.add(sample_id)
        seen.add(sample_id)
    return sorted(duplicates)


def duplicate_source_urls(manifest):
    """Return duplicate track source URLs in a complete calibration cohort."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")
    if manifest.get('cohort_status') != 'candidate_selection_complete':
        return []

    seen = set()
    duplicates = set()
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        source_url = sample.get('source_url')
        if not isinstance(source_url, str) or not source_url:
            continue  # JSON Schema reports malformed URLs.
        if source_url in seen:
            duplicates.add(source_url)
        seen.add(source_url)
    return sorted(duplicates)


def duplicate_provider_track_identities(manifest):
    """Return duplicate (provider, provider_track_id) identities in a complete cohort."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")
    if manifest.get('cohort_status') != 'candidate_selection_complete':
        return []

    seen = set()
    duplicates = set()
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        provider = sample.get('provider')
        provider_track_id = sample.get('provider_track_id')
        if not isinstance(provider, str) or not provider or not isinstance(provider_track_id, str) or not provider_track_id:
            continue  # A missing provider ID falls back to source_url uniqueness.
        identity = (provider, provider_track_id)
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)
    return sorted(duplicates)


def artist_count_errors(manifest, max_per_artist=2):
    """Enforce the documented credited-artist cap for a complete cohort."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")
    if manifest.get('cohort_status') != 'candidate_selection_complete':
        return []

    counts = {}
    display_names = {}
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        artist = sample.get('artist')
        if not isinstance(artist, str) or not artist.strip():
            continue  # JSON Schema reports missing or blank artist values.
        normalized = ' '.join(artist.split()).casefold()
        counts[normalized] = counts.get(normalized, 0) + 1
        display_names.setdefault(normalized, ' '.join(artist.split()))

    return [
        f"artist '{display_names[artist]}' occurs {count} times; maximum is {max_per_artist}"
        for artist, count in sorted(counts.items())
        if count > max_per_artist
    ]


def complete_cohort_license_evidence_errors(manifest):
    """Require reviewable license and attribution evidence for a complete cohort."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")
    if manifest.get('cohort_status') != 'candidate_selection_complete':
        return []

    errors = []
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        sample_id = sample.get('sample_id', f'samples[{index}]')
        for field in ('license_name', 'license_url'):
            value = sample.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f'{sample_id}.{field} must be non-blank for candidate_selection_complete'
                )

        attribution_required = sample.get('attribution_required')
        if not isinstance(attribution_required, bool):
            errors.append(
                f'{sample_id}.attribution_required must be explicitly true or false '
                'for candidate_selection_complete'
            )
        elif attribution_required:
            attribution = sample.get('attribution')
            if not isinstance(attribution, str) or not attribution.strip():
                errors.append(
                    f'{sample_id}.attribution must be non-blank when attribution_required is true'
                )
    return errors


def decoded_audio_consistency_errors(manifest):
    """Check exact decoder metadata and centered prepared-frame arithmetic."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get('samples'), list):
        raise ValueError("manifest must contain a 'samples' array")

    errors = []
    for index, sample in enumerate(manifest['samples']):
        if not isinstance(sample, dict):
            raise ValueError(f'samples[{index}] must be an object')
        sample_id = sample.get('sample_id', f'samples[{index}]')
        decoded_duration = sample.get('decoded_duration')
        decoded_frames = sample.get('decoded_frame_count')
        sample_rate = sample.get('source_sample_rate')

        if decoded_duration is not None:
            if (type(decoded_frames) is not int or decoded_frames <= 0
                    or type(sample_rate) is not int or sample_rate <= 0):
                # JSON Schema reports missing or wrongly typed decode metadata.
                continue
            if decoded_duration != decoded_frames / sample_rate:
                errors.append(
                    f'{sample_id}.decoded_duration must equal '
                    'decoded_frame_count / source_sample_rate'
                )

        prepared_fields = (
            'prepared_local_path',
            'prepared_sha256',
            'prepared_duration',
            'segment_start_frame',
            'segment_end_frame_exclusive',
        )
        if not any(sample.get(field) is not None for field in prepared_fields):
            continue

        start = sample.get('segment_start_frame')
        end = sample.get('segment_end_frame_exclusive')
        if (type(start) is not int or type(end) is not int
                or type(decoded_frames) is not int or decoded_frames <= 0
                or type(sample_rate) is not int or sample_rate <= 0):
            # Schema reports incomplete, null, or wrongly typed prepared metadata.
            continue

        expected_span = 60 * sample_rate
        if start < 0:
            errors.append(f'{sample_id}.segment_start_frame must be non-negative')
        if end <= start:
            errors.append(
                f'{sample_id}.segment_end_frame_exclusive must be greater than segment_start_frame'
            )
            continue
        if end - start != expected_span:
            errors.append(
                f'{sample_id} prepared frame span must equal 60 * source_sample_rate'
            )
        if end > decoded_frames:
            errors.append(
                f'{sample_id}.segment_end_frame_exclusive exceeds decoded_frame_count'
            )
        expected_start = (decoded_frames - expected_span) // 2
        if decoded_frames < expected_span:
            errors.append(f'{sample_id} decoded audio is shorter than 60 seconds')
        elif start != expected_start or end != expected_start + expected_span:
            errors.append(
                f'{sample_id} segment frame range is not the centered exact 60-second extraction'
            )
        if sample.get('prepared_duration') != 60:
            errors.append(f'{sample_id}.prepared_duration must equal 60 seconds')

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', nargs='?', type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        duplicates = duplicate_sample_ids(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f'Invalid calibration manifest: {exc}', file=sys.stderr)
        return 1

    if duplicates:
        print('Duplicate sample_id values: ' + ', '.join(duplicates), file=sys.stderr)
        return 1

    print(f'Unique sample_id check passed: {len(payload["samples"])} samples.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
