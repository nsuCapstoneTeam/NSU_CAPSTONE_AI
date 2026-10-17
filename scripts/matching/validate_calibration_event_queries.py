"""Calibration Event query inventory의 query_id 고유성을 검사하는 CLI."""

import argparse
import sys
from pathlib import Path

from scripts.matching.strict_json import parse_json_bytes


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


def duplicate_raw_service_inputs(event_queries):
    """Return exact normalized Raw input tuples shared by multiple query records."""
    if not isinstance(event_queries, dict) or not isinstance(event_queries.get('queries'), list):
        raise ValueError("event query inventory must contain a 'queries' array")

    seen = {}
    duplicates = set()
    for index, query in enumerate(event_queries['queries']):
        if not isinstance(query, dict):
            raise ValueError(f'queries[{index}] must be an object')
        raw_input = query.get('raw_service_input')
        if not isinstance(raw_input, dict):
            continue  # JSON Schema reports structural errors.

        values = []
        malformed = False
        for field in ('event_type', 'event_description_ko', 'desired_genre'):
            value = raw_input.get(field)
            if isinstance(value, str):
                value = ' '.join(value.split()).casefold()
            elif value is not None:
                malformed = True
                break
            values.append(value)
        if malformed:
            continue  # JSON Schema reports malformed Raw input fields.
        identity = tuple(values)
        query_id = query.get('query_id')
        if not isinstance(query_id, str) or not query_id:
            query_id = f'queries[{index}]'
        if identity in seen:
            duplicates.add((seen[identity], query_id))
        else:
            seen[identity] = query_id
    return sorted(duplicates)


def _has_nonblank_value(value):
    """Return whether an interpreted value contains usable non-blank text."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(
            isinstance(item, str) and item.strip()
            for item in value
        )
    return False


def event_query_raw_reference_errors(event_queries):
    """Validate annotation evidence against its query's current Raw input."""
    if not isinstance(event_queries, dict) or not isinstance(event_queries.get('queries'), list):
        raise ValueError("event query inventory must contain a 'queries' array")

    errors = []
    for index, query in enumerate(event_queries['queries']):
        if not isinstance(query, dict):
            continue

        is_active = query.get('selection_status') == 'active_v1'
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

            state = annotation.get('state')
            value_key = 'value_ref' if attribute == 'desired_genre' else 'value'
            value = annotation.get(value_key)
            evidence = annotation.get('evidence')
            if not isinstance(evidence, list):
                continue  # JSON Schema reports structural errors.

            location = f'query {query_id} structured_interpretation.attributes.{attribute}'
            if state == 'interpreted':
                if attribute == 'desired_genre':
                    if not _has_nonblank_value(value):
                        errors.append(f'{location} is interpreted but has no value_ref')
                elif not _has_nonblank_value(value):
                    errors.append(f'{location} is interpreted but has no non-blank value')
                if not evidence:
                    errors.append(f'{location} is interpreted but has no evidence')
            elif state == 'not_requested':
                if value is not None:
                    errors.append(f'{location} is not_requested but has a value')
                if evidence:
                    errors.append(f'{location} is not_requested but has evidence')
            elif state == 'unable_to_interpret':
                if value is not None:
                    errors.append(f'{location} is unable_to_interpret but has a value')
                if not evidence:
                    errors.append(f'{location} is unable_to_interpret but has no evidence')

            for evidence_index, excerpt in enumerate(evidence):
                evidence_location = (
                    f'query {query_id} structured_interpretation.attributes.'
                    f'{attribute}.evidence[{evidence_index}]'
                )
                if not isinstance(excerpt, str) or not excerpt.strip():
                    errors.append(f'{evidence_location} must be a non-empty Raw excerpt')
                    continue

                if attribute == 'desired_genre':
                    raw_genre = raw_input.get('desired_genre')
                    if not isinstance(raw_genre, str) or excerpt not in raw_genre:
                        errors.append(
                            f'{evidence_location} must be an exact substring of '
                            'raw_service_input.desired_genre'
                        )
                elif not any(excerpt in source for source in raw_sources.values()):
                    errors.append(
                        f'{evidence_location} must be an exact substring of this query\'s '
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
        elif not is_active:
            continue
        elif state == 'not_requested' and raw_genre is not None:
            errors.append(
                f'{location} is not_requested but raw_service_input.desired_genre contains a request'
            )
        elif state == 'unable_to_interpret' and (
            not isinstance(raw_genre, str) or not raw_genre.strip()
        ):
            errors.append(
                f'{location} is unable_to_interpret but raw_service_input.desired_genre has no request'
            )

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event_queries', nargs='?', type=Path, default=DEFAULT_EVENT_QUERIES)
    args = parser.parse_args(argv)

    try:
        payload = parse_json_bytes(
            args.event_queries.read_bytes(), 'event query inventory', args.event_queries
        )
        duplicates = duplicate_query_ids(payload)
    except (OSError, ValueError) as exc:
        print(f'Invalid calibration Event query inventory: {exc}', file=sys.stderr)
        return 1

    if duplicates:
        print('Duplicate query_id values: ' + ', '.join(duplicates), file=sys.stderr)
        return 1

    print(f'Unique query_id check passed: {len(payload["queries"])} queries.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
