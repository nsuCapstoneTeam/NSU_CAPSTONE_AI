"""Calibration manifest의 sample_id 고유성을 검사하는 CLI."""

import argparse
import json
import sys
from pathlib import Path


DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / 'docs'
    / 'experiments'
    / 'audio-similarity-calibration'
    / 'manifest.json'
)


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
