"""Run all JSON Schema and cross-record checks for the calibration dataset."""

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, SchemaError

from scripts.matching.validate_calibration_event_queries import duplicate_query_ids
from scripts.matching.validate_calibration_manifest import duplicate_sample_ids


CALIBRATION_DIR = (
    Path(__file__).resolve().parents[2]
    / 'docs'
    / 'experiments'
    / 'audio-similarity-calibration'
)


def _schema_errors(instance, schema, label):
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f'{label} schema is invalid: {exc.message}']

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for error in validator.iter_errors(instance):
        location = '/'.join(str(part) for part in error.absolute_path) or '<root>'
        errors.append(f'{label} {location}: {error.message}')
    return errors


def validate_calibration(manifest, manifest_schema, event_queries, event_queries_schema):
    """Return all schema and cross-record validation errors."""
    errors = []
    errors.extend(_schema_errors(manifest, manifest_schema, 'manifest'))
    errors.extend(_schema_errors(event_queries, event_queries_schema, 'event queries'))

    try:
        duplicates = duplicate_sample_ids(manifest)
        if duplicates:
            errors.append('Duplicate sample_id values: ' + ', '.join(duplicates))
    except ValueError as exc:
        errors.append(str(exc))

    try:
        duplicates = duplicate_query_ids(event_queries)
        if duplicates:
            errors.append('Duplicate query_id values: ' + ', '.join(duplicates))
    except ValueError as exc:
        errors.append(str(exc))

    return errors


def _read_json(path, label):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot read {label} from {path}: {exc}') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=CALIBRATION_DIR / 'manifest.json')
    parser.add_argument('--manifest-schema', type=Path, default=CALIBRATION_DIR / 'manifest.schema.json')
    parser.add_argument('--event-queries', type=Path, default=CALIBRATION_DIR / 'event-queries.json')
    parser.add_argument(
        '--event-queries-schema',
        type=Path,
        default=CALIBRATION_DIR / 'event-queries.schema.json',
    )
    args = parser.parse_args(argv)

    try:
        manifest = _read_json(args.manifest, 'manifest')
        manifest_schema = _read_json(args.manifest_schema, 'manifest schema')
        event_queries = _read_json(args.event_queries, 'event queries')
        event_queries_schema = _read_json(args.event_queries_schema, 'event query schema')
    except ValueError as exc:
        print(f'Calibration validation failed: {exc}', file=sys.stderr)
        return 1

    errors = validate_calibration(
        manifest,
        manifest_schema,
        event_queries,
        event_queries_schema,
    )
    if errors:
        print('Calibration validation failed:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1

    print(
        'Calibration validation passed: manifest schema and sample_id uniqueness; '
        'event query schema and query_id uniqueness.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
