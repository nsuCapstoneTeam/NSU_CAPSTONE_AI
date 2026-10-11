"""Calibration Event query inventory의 query_id 고유성을 검사하는 CLI."""

import argparse
import json
import sys
from pathlib import Path


DEFAULT_EVENT_QUERIES = (
    Path(__file__).resolve().parents[2]
    / 'docs'
    / 'experiments'
    / 'audio-similarity-calibration'
    / 'event-queries.json'
)


def duplicate_query_ids(event_queries):
    """Event query inventory에서 두 번 이상 등장하는 query_id를 반환한다."""
    if not isinstance(event_queries, dict) or not isinstance(event_queries.get('queries'), list):
        raise ValueError("event query inventory must contain a 'queries' array")

    seen = set()
    duplicates = set()
    for index, query in enumerate(event_queries['queries']):
        if not isinstance(query, dict):
            raise ValueError(f'queries[{index}] must be an object')
        query_id = query.get('query_id')
        if not isinstance(query_id, str) or not query_id:
            raise ValueError(f'queries[{index}].query_id must be a non-empty string')
        if query_id in seen:
            duplicates.add(query_id)
        seen.add(query_id)
    return sorted(duplicates)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event_queries', nargs='?', type=Path, default=DEFAULT_EVENT_QUERIES)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.event_queries.read_text(encoding='utf-8-sig'))
        duplicates = duplicate_query_ids(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f'Invalid calibration Event query inventory: {exc}', file=sys.stderr)
        return 1

    if duplicates:
        print('Duplicate query_id values: ' + ', '.join(duplicates), file=sys.stderr)
        return 1

    print(f'Unique query_id check passed: {len(payload["queries"])} queries.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
