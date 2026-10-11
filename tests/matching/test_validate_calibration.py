import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.matching.validate_calibration import main


CALIBRATION_DIR = (
    Path(__file__).resolve().parents[2]
    / 'docs'
    / 'experiments'
    / 'audio-similarity-calibration'
)


def _load_json(name):
    return json.loads((CALIBRATION_DIR / name).read_text(encoding='utf-8'))


def _run_validator(tmp_path, capsys, *, manifest=None, event_queries=None):
    paths = {
        'manifest': tmp_path / 'manifest.json',
        'event-queries': tmp_path / 'event-queries.json',
    }
    paths['manifest'].write_text(json.dumps(manifest or _load_json('manifest.json')), encoding='utf-8')
    paths['event-queries'].write_text(
        json.dumps(event_queries or _load_json('event-queries.json')),
        encoding='utf-8',
    )
    result = main([
        '--manifest', str(paths['manifest']),
        '--event-queries', str(paths['event-queries']),
    ])
    return result, capsys.readouterr()


def test_current_manifest_and_event_queries_pass(capsys):
    assert main([]) == 0
    assert 'Calibration validation passed' in capsys.readouterr().out


def test_documented_module_invocation_runs_from_repository_root():
    repository_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-m', 'scripts.matching.validate_calibration'],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'schemas' in result.stdout
    assert 'track identities' in result.stdout


def test_missing_manifest_required_field_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest.pop('dataset_version')

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'dataset_version' in output.err


def test_event_query_schema_violation_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    event_queries['queries'][0]['unexpected_field'] = True

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'Additional properties are not allowed' in output.err


@pytest.mark.parametrize('identifier', ['sample_id', 'query_id'])
def test_duplicate_identifiers_fail(tmp_path, capsys, identifier):
    manifest = _load_json('manifest.json')
    event_queries = _load_json('event-queries.json')
    if identifier == 'sample_id':
        manifest['samples'][1]['sample_id'] = manifest['samples'][0]['sample_id']
    else:
        event_queries['queries'][1]['query_id'] = event_queries['queries'][0]['query_id']

    result, output = _run_validator(
        tmp_path,
        capsys,
        manifest=manifest,
        event_queries=event_queries,
    )

    assert result == 1
    assert f'Duplicate {identifier} values:' in output.err


def test_duplicate_source_url_fails_even_when_logical_ids_differ(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    first, second = manifest['samples'][:2]
    second['sample_id'] = 'cal-distinct-sample-id'
    second['provider_track_id'] = 'distinct-provider-track-id'
    second['source_url'] = first['source_url']

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'Duplicate source_url values:' in output.err


def test_duplicate_provider_track_identity_fails_with_distinct_source_urls(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    first, second = manifest['samples'][:2]
    second['sample_id'] = 'cal-distinct-sample-id'
    second['provider'] = first['provider']
    second['provider_track_id'] = first['provider_track_id']

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'Duplicate (provider, provider_track_id) identities:' in output.err


def test_distinct_track_identities_pass(tmp_path, capsys):
    manifest = _load_json('manifest.json')

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 0, output.err


def test_missing_provider_track_id_falls_back_to_source_url(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['provider_track_id'] = None

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 0, output.err


def test_provider_track_id_can_repeat_across_different_providers(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    first, second = manifest['samples'][:2]
    second['provider'] = 'Separate Provider'
    second['provider_track_id'] = first['provider_track_id']

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 0, output.err


def test_incomplete_cohort_allows_duplicate_track_candidates(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['cohort_status'] = 'candidate_selection_incomplete'
    manifest['samples'].pop()
    manifest['samples'][1]['source_url'] = manifest['samples'][0]['source_url']
    manifest['samples'][1]['provider'] = manifest['samples'][0]['provider']
    manifest['samples'][1]['provider_track_id'] = manifest['samples'][0]['provider_track_id']

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 0, output.err


def test_active_query_not_reviewed_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['selection_status'] == 'active_v1')
    active['structured_interpretation']['review_status'] = 'not_reviewed'

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'reviewed_for_raw_support' in output.err


def test_duplicate_raw_scenario_fails_even_when_query_ids_differ(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    first, second = event_queries['queries'][:2]
    second['raw_service_input'] = json.loads(json.dumps(first['raw_service_input']))

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'Duplicate normalized raw_service_input records:' in output.err


@pytest.mark.parametrize(
    ('attribute', 'value_key'),
    [
        ('mood', 'value'),
        ('tempo', 'value'),
        ('desired_genre', 'value_ref'),
        ('instrument_preference', 'value'),
        ('vocal_preference', 'value'),
        ('acoustic_electronic', 'value'),
        ('dynamic_progression', 'value'),
        ('usage_context', 'value'),
        ('rhythmic_character', 'value'),
        ('activity_character', 'value'),
    ],
)
def test_interpreted_attribute_with_null_value_fails(
    tmp_path,
    capsys,
    attribute,
    value_key,
):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['selection_status'] == 'active_v1')
    annotation = active['structured_interpretation']['attributes'][attribute]
    annotation['state'] = 'interpreted'
    annotation[value_key] = None
    annotation['evidence'] = ['raw evidence']

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert attribute in output.err


def test_interpreted_attribute_with_empty_evidence_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['mood']['evidence'] = []

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'evidence' in output.err


@pytest.mark.parametrize(
    ('state', 'value', 'evidence'),
    [
        ('not_requested', None, []),
        ('unable_to_interpret', None, ['같이 즐길 수 있는']),
    ],
)
def test_uninterpreted_states_allow_null_value_with_expected_evidence(
    tmp_path,
    capsys,
    state,
    value,
    evidence,
):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['tempo'] = {
        'state': state,
        'value': value,
        'evidence': evidence,
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 0, output.err


def test_unable_to_interpret_requires_evidence(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['mood'] = {
        'state': 'unable_to_interpret',
        'value': None,
        'evidence': [],
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'minItems' in output.err or 'no evidence' in output.err


@pytest.mark.parametrize(
    ('attribute', 'value_key'),
    [
        ('mood', 'value'),
        ('tempo', 'value'),
        ('desired_genre', 'value_ref'),
        ('instrument_preference', 'value'),
        ('vocal_preference', 'value'),
        ('acoustic_electronic', 'value'),
        ('dynamic_progression', 'value'),
        ('usage_context', 'value'),
        ('rhythmic_character', 'value'),
        ('activity_character', 'value'),
    ],
)
def test_unable_to_interpret_empty_evidence_fails_for_every_attribute(
    tmp_path,
    capsys,
    attribute,
    value_key,
):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes'][attribute] = {
        'state': 'unable_to_interpret',
        value_key: None,
        'evidence': [],
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert attribute in output.err


def test_unable_to_interpret_with_valid_raw_evidence_passes(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['mood'] = {
        'state': 'unable_to_interpret',
        'value': None,
        'evidence': ['같이 즐길 수 있는'],
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 0, output.err


def test_complete_cohort_with_49_samples_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'].pop()

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert '50' in output.err


def test_complete_cohort_with_ineligible_sample_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['rights_status'] = 'excluded'

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'rights_status' in output.err


def test_complete_cohort_with_duration_below_60_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['source_catalog_duration'] = 59.9

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'source_catalog_duration' in output.err


def test_complete_cohort_with_null_catalog_duration_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['source_catalog_duration'] = None

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'source_catalog_duration' in output.err


def test_complete_cohort_with_restricted_commercial_use_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['commercial_use_status'] = 'restricted'

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'commercial_use_status' in output.err


def test_complete_cohort_with_decoded_duration_below_60_fails(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['decoded_duration'] = 59.9
    manifest['samples'][0]['acquisition_method'] = 'official_direct_download'

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'decoded_duration' in output.err


def test_acquired_complete_sample_requires_decoded_duration(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['acquisition_method'] = 'official_direct_download'

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 1
    assert 'decoded_duration' in output.err


def test_acquired_complete_sample_with_60_second_decode_passes(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['samples'][0]['acquisition_method'] = 'official_direct_download'
    manifest['samples'][0]['decoded_duration'] = 60

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 0, output.err


def test_incomplete_cohort_does_not_apply_complete_only_eligibility_rules(tmp_path, capsys):
    manifest = _load_json('manifest.json')
    manifest['cohort_status'] = 'candidate_selection_incomplete'
    manifest['samples'].pop()
    manifest['samples'][0]['rights_status'] = 'excluded'
    manifest['samples'][0]['commercial_use_status'] = 'restricted'
    manifest['samples'][0]['source_catalog_duration'] = None
    manifest['samples'][0]['decoded_duration'] = 0

    result, output = _run_validator(tmp_path, capsys, manifest=manifest)

    assert result == 0, output.err


def test_interpreted_evidence_must_be_an_exact_raw_excerpt(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['mood']['evidence'] = [
        'excerpt absent from current Raw'
    ]

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'exact substring' in output.err


def test_interpreted_evidence_rejects_empty_or_whitespace_excerpt(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['mood']['evidence'] = ['  ']

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'non-empty Raw excerpt' in output.err


def test_evidence_from_another_query_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    event_01 = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    event_02 = next(query for query in event_queries['queries'] if query['query_id'] == 'event-02')
    event_02['structured_interpretation']['attributes']['mood']['evidence'] = (
        event_01['structured_interpretation']['attributes']['mood']['evidence']
    )

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'exact substring' in output.err


def test_stale_historical_raw_evidence_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-02')
    active['structured_interpretation']['attributes']['mood']['evidence'] = [
        active['historical_raw_draft']['event_description_ko']
    ]

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'exact substring' in output.err


def test_desired_genre_reference_requires_non_null_raw_target(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['raw_service_input']['desired_genre'] = None

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'cannot be interpreted when raw_service_input.desired_genre is null' in output.err


def test_desired_genre_reference_must_use_expected_pointer(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['desired_genre']['value_ref'] = (
        '#/raw_service_input/event_description_ko'
    )

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'desired_genre' in output.err


def test_desired_genre_evidence_must_come_from_referenced_raw_field(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['desired_genre']['evidence'] = [
        active['raw_service_input']['event_description_ko'][:6]
    ]

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'raw_service_input.desired_genre' in output.err


def test_desired_genre_not_requested_requires_null_raw_value(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    active['structured_interpretation']['attributes']['desired_genre'] = {
        'state': 'not_requested',
        'value_ref': None,
        'evidence': [],
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'contains a request' in output.err


def test_desired_genre_not_requested_with_null_raw_value_passes(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 0, output.err


def test_reserve_and_replace_unreviewed_placeholders_pass(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    deferred = [
        query
        for query in event_queries['queries']
        if query['selection_status'] in {'reserve', 'replace_candidate'}
    ]

    assert len(deferred) == 4
    assert all(query['structured_interpretation']['review_status'] == 'not_reviewed' for query in deferred)
    assert all(
        annotation['state'] == 'not_requested'
        for query in deferred
        for annotation in query['structured_interpretation']['attributes'].values()
    )

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 0, output.err


def test_desired_genre_unable_to_interpret_without_raw_request_fails(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-07')
    active['structured_interpretation']['attributes']['desired_genre'] = {
        'state': 'unable_to_interpret',
        'value_ref': None,
        'evidence': [],
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'has no request' in output.err


def test_unable_to_interpret_evidence_must_reference_current_raw(tmp_path, capsys):
    event_queries = _load_json('event-queries.json')
    active = next(query for query in event_queries['queries'] if query['query_id'] == 'event-01')
    other_query = next(query for query in event_queries['queries'] if query['query_id'] == 'event-02')
    foreign_excerpt = other_query['raw_service_input']['event_description_ko']
    assert foreign_excerpt not in active['raw_service_input']['event_description_ko']
    active['structured_interpretation']['attributes']['mood'] = {
        'state': 'unable_to_interpret',
        'value': None,
        'evidence': [foreign_excerpt],
    }

    result, output = _run_validator(tmp_path, capsys, event_queries=event_queries)

    assert result == 1
    assert 'exact substring' in output.err
