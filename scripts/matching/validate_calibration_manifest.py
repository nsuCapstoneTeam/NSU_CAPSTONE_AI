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
