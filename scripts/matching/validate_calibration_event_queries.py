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


def event_query_raw_reference_errors(event_queries):
    """Validate reviewed annotations against their own raw service input."""
    if not isinstance(event_queries, dict) or not isinstance(event_queries.get('queries'), list):
        raise ValueError("event query inventory must contain a 'queries' array")

    errors = []
    for index, query in enumerate(event_queries['queries']):
        if not isinstance(query, dict) or query.get('selection_status') != 'active_v1':
            continue

        query_id = query.get('query_id', f'queries[{index}]')
        raw_input = query.get('raw_service_input')
        interpretation = query.get('structured_interpretation')
        if not isinstance(raw_input, dict) or not isinstance(interpretation, dict):
            continue  # JSON Schema reports structural errors.

        attributes = interpretation.get('attributes')
        if not isinstance(attributes, dict):
            continue  # JSON Schema reports structural errors.

        raw_sources = {
            key: value
            for key in ('event_type', 'event_description_ko', 'desired_genre')
            if isinstance((value := raw_input.get(key)), str) and value
        }

        for attribute, annotation in attributes.items():
            if not isinstance(annotation, dict):
                continue

            evidence = annotation.get('evidence')
            if not isinstance(evidence, list):
                continue  # JSON Schema reports structural errors.

            for evidence_index, excerpt in enumerate(evidence):
                location = (
                    f'query {query_id} structured_interpretation.attributes.'
                    f'{attribute}.evidence[{evidence_index}]'
                )
                if not isinstance(excerpt, str) or not excerpt.strip():
                    errors.append(f'{location} must be a non-empty Raw excerpt')
                    continue

                if attribute == 'desired_genre':
                    raw_genre = raw_input.get('desired_genre')
                    if not isinstance(raw_genre, str) or excerpt not in raw_genre:
                        errors.append(
                            f'{location} must be an exact substring of '
                            'raw_service_input.desired_genre'
                        )
                elif not any(excerpt in source for source in raw_sources.values()):
                    errors.append(
                        f'{location} must be an exact substring of this query\'s '
                        'raw_service_input.event_type, event_description_ko, or desired_genre'
                    )

        desired_genre = attributes.get('desired_genre')
        if not isinstance(desired_genre, dict):
            continue
        raw_genre = raw_input.get('desired_genre')
        state = desired_genre.get('state')
        value_ref = desired_genre.get('value_ref')
        location = f'query {query_id} structured_interpretation.attributes.desired_genre'

        if state == 'interpreted':
            if value_ref != '#/raw_service_input/desired_genre':
                errors.append(f'{location}.value_ref must point to raw_service_input.desired_genre')
            if not isinstance(raw_genre, str) or not raw_genre.strip():
                errors.append(
                    f'{location} cannot be interpreted when raw_service_input.desired_genre is null or empty'
                )
        elif state == 'not_requested' and raw_genre is not None:
            errors.append(
                f'{location} is not_requested but raw_service_input.desired_genre contains a request'
            )
        elif state == 'unable_to_interpret' and raw_genre is None:
            errors.append(
                f'{location} is unable_to_interpret but raw_service_input.desired_genre has no request'
            )

    return errors


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
