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
