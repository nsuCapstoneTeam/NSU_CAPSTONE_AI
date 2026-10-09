"""전용 DB에서 production 대표 벡터 저장·검색을 관측하는 검증 CLI."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import psycopg
import torch

from app.core import migrations
from app.core.config import DatabaseSettings
from app.core.database import connect_database
from app.embedding.audio_embedding import (
    AudioEmbeddingError, AudioEmbeddingGenerator, AudioEmbeddingResult,
    PREPROCESSING_VERSION, audio_file_sha256, validate_audio_embedding,
)
from app.matching.audio_search import audio_cosine_similarities
from app.repository.embedding_repository import (
    AudioEmbeddingRepository, EmbeddingConflict, prepare_embedding,
)
from scripts.datasets.highlight_dataset import DatasetError, load_manifest
from scripts.embedding.validate_audio_highlight_msclap import (
    ValidationError, cache_identity, digest, preflight,
)

SCHEMA_VERSION = 1
TOOL_VERSION = 'production-audio-postgres-validation-v2'
COSINE_ABS_TOLERANCE = 1e-6
COSINE_REL_TOLERANCE = 0.0
DATABASE_MARKER = 'nsu-capstone-ai:audio-embedding-postgres-validation:v1'
ROOT = Path(__file__).resolve().parents[2]


class SafetyBlocked(ValueError):
    """의도적으로 준비한 validation DB 이외의 실행을 차단한다."""


class CheckFailed(ValueError):
    """수치 허용 오차와 무관한 명확한 검증 조건 위반."""


class MigrationFailure(ValueError):
    """예상된 production migration 거부를 안전한 구조화 오류로 전달한다."""

    def __init__(self, reason_code, message, migration_name=None):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.migration_name = migration_name

    def to_report(self):
        failure = {
            'stage': 'migration',
            'reason_code': self.reason_code,
            'message': self.message,
        }
        if self.migration_name is not None:
            failure['migration_name'] = self.migration_name
        return failure


def require(condition, reason):
    if not condition:
        raise CheckFailed(reason)


def validation_settings(expected_database):
    # production 기본값을 상속하면 capstone_db에 연결할 수 있으므로 모두 명시해야 한다.
    if not re.fullmatch(r'audio_embedding_validation(?:_[a-z0-9]+)?', expected_database):
        raise SafetyBlocked('전용 DB 이름은 audio_embedding_validation 또는 그 suffix 형식이어야 합니다')
    required = ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')
    if any(not os.environ.get(key) for key in required):
        raise SafetyBlocked('전용 validation DB의 DB_HOST/PORT/NAME/USER/PASSWORD를 모두 명시해야 합니다; 개발 DB fallback 없음')
    try:
        settings = DatabaseSettings.from_environment()
    except (KeyError, ValueError):
        raise SafetyBlocked('전용 DB 환경 설정이 올바르지 않습니다') from None
    if (settings.name != expected_database or settings.host not in ('127.0.0.1', 'localhost')
            or settings.port == 5432 or not settings.user.startswith('audio_validation')):
        raise SafetyBlocked('전용 loopback host·별도 port·audio_validation 사용자·expected DB 조건 불일치')
    return settings


def guard_connection(connection, expected_database, expected_user):
    # identity 확인 중에는 DB transaction 자체도 읽기 전용이다.
    connection.execute('SET TRANSACTION READ ONLY')
    row = connection.execute('''SELECT current_database(), current_user,
        pg_get_userbyid(datdba), shobj_description(oid, 'pg_database'), version()
        FROM pg_database WHERE datname = current_database()''').fetchone()
    if row is None or row[:3] != (expected_database, expected_user, expected_user) or row[3] != DATABASE_MARKER:
        raise SafetyBlocked('실제 DB identity/owner/전용 validation marker 불일치; write·migration 금지')
    connection.rollback()
    return {'database': row[0], 'ownership_marker': row[3], 'postgresql_version': row[4],
            'identity_verified': True, 'guard_transaction_read_only': True}


def connect_validation(expected_database):
    settings = validation_settings(expected_database)
    connection = connect_database()
    try:
        identity = guard_connection(connection, expected_database, settings.user)
    except (SafetyBlocked, psycopg.Error):
        connection.close()
        raise
    return connection, identity


def apply_validated_migrations(expected_database):
    def guarded_factory():
        return connect_validation(expected_database)[0]
    # production SQL·checksum 처리를 재사용하고 추가 연결도 매번 guard를 통과시킨다.
    with patch.object(migrations, 'connect_database', guarded_factory):
        try:
            return migrations.apply_migrations()
        except RuntimeError as error:
            message = str(error)
            if message == 'vector_extension_missing':
                raise MigrationFailure(
                    'vector_extension_missing',
                    '전용 validation DB에 pgvector extension이 없어 migration을 적용하지 못했습니다',
                ) from None
            if message == 'unknown_applied_migration':
                raise MigrationFailure(
                    'unknown_applied_migration',
                    'DB migration 이력에 현재 repository에서 찾을 수 없는 migration이 있습니다',
                ) from None
            mismatch = re.fullmatch(r'migration_checksum_mismatch: ([A-Za-z0-9_.-]+)', message)
            if mismatch:
                raise MigrationFailure(
                    'migration_checksum_mismatch',
                    '이미 적용된 migration의 checksum이 현재 파일과 다릅니다',
                    migration_name=mismatch.group(1),
                ) from None
            # 새롭거나 예상하지 못한 RuntimeError는 프로그래밍 오류일 수 있으므로 노출해 조사한다.
            raise


def schema_evidence(connection):
    extension = connection.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    require(extension is not None, 'pgvector extension이 활성화되지 않았습니다')
    history = dict(connection.execute('SELECT name, sha256 FROM ai_embeddings.schema_migrations').fetchall())
    expected = {p.name: hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
                for p in migrations.MIGRATION_DIRECTORY.glob('*.sql')}
    require(history == expected, 'production migration checksum/history 불일치')
    columns = dict(connection.execute("""SELECT column_name, udt_name FROM information_schema.columns
        WHERE table_schema='ai_embeddings' AND table_name='audio_embeddings'""").fetchall())
    require(columns == {'music_id': 'text', 'source_sha256': 'text', 'model': 'text',
        'model_version': 'text', 'preprocessing_version': 'text', 'dimension': 'int4',
        'embedding': 'vector', 'generation_profile': 'jsonb', 'metadata': 'jsonb',
        'created_at': 'timestamptz'}, 'production table column 구조 불일치')
    constraints = [r[0] for r in connection.execute("""SELECT pg_get_constraintdef(oid)
        FROM pg_constraint WHERE conrelid='ai_embeddings.audio_embeddings'::regclass ORDER BY conname""").fetchall()]
    require(any('vector_dims(embedding) = dimension' in c for c in constraints), 'dimension constraint 누락')
    require(any('vector_norm(embedding)' in c for c in constraints), 'nonzero constraint 누락')
    return {'pgvector_version': extension[0], 'migration_history': history,
            'columns': columns, 'constraints': constraints, 'status': 'PASS'}


def roundtrip_metrics(before, after):
    validate_audio_embedding(before)
    validate_audio_embedding(after, expected_dimension=before.shape[1])
    delta = before.double() - after.double()
    exact = torch.equal(before, after)
    return {'dimension': before.shape[1], 'shape': list(after.shape),
            'finite': bool(torch.isfinite(after).all()), 'nonzero': bool(torch.count_nonzero(after)),
            'before_norm': float(before.double().norm()), 'after_norm': float(after.double().norm()),
            'exact_equal': exact, 'before_digest': digest(before), 'after_digest': digest(after),
            'max_absolute_difference': float(delta.abs().max()),
            'rms_difference': float(delta.square().mean().sqrt()), 'l2_difference': float(delta.norm()),
            'status': 'PASS' if exact and digest(before) == digest(after) else 'REVIEW_REQUIRED'}


def read_vector(connection, music_id):
    row = connection.execute('SELECT embedding::text, dimension FROM ai_embeddings.audio_embeddings WHERE music_id=%s',
                             (music_id,)).fetchone()
    require(row is not None, '저장한 representative row 누락')
    vector = torch.tensor([json.loads(row[0])], dtype=torch.float32)
    validate_audio_embedding(vector, expected_dimension=row[1])
    return vector


def cosine_record(python_before, python_after, distance, sql_similarity, returned):
    require(all(math.isfinite(x) for x in (python_before, python_after, distance, sql_similarity, returned)),
            'cosine 측정값에 non-finite 포함')
    difference = python_before - sql_similarity
    absolute_difference = abs(difference)
    allowed_absolute_difference = (COSINE_ABS_TOLERANCE
                                   + COSINE_REL_TOLERANCE * abs(sql_similarity))
    within_tolerance = absolute_difference <= allowed_absolute_difference
    return {'python_before_storage': python_before, 'python_roundtrip': python_after,
            'postgresql_raw_cosine_distance': distance, 'sql_cosine_similarity': sql_similarity,
            'repository_cosine_similarity': returned, 'signed_difference': difference,
            'absolute_difference': absolute_difference, 'storage_cosine_difference': python_before-python_after,
            'repository_sql_difference': returned-sql_similarity,
            'allowed_absolute_difference': allowed_absolute_difference,
            'numerical_parity_tolerance': {'absolute': COSINE_ABS_TOLERANCE, 'relative': COSINE_REL_TOLERANCE},
            'status': 'PASS' if within_tolerance and python_before == python_after and returned == sql_similarity
                      else 'REVIEW_REQUIRED'}


def compare_rankings(ids, python_scores, db_ids):
    expected = sorted(ids, key=lambda key: (-python_scores[key], key.encode('utf-8')))
    gaps = [{'first': a, 'second': b, 'python_gap': python_scores[a]-python_scores[b]}
            for a, b in zip(expected, expected[1:])]
    return {'python_ranking': expected, 'postgresql_ranking': db_ids, 'adjacent_candidate_gaps': gaps,
            'match': expected == db_ids, 'status': 'PASS' if expected == db_ids else 'FAIL'}


def aggregate_status(records):
    statuses = [r['status'] for r in records]
    if 'FAIL' in statuses:
        return 'FAIL'
    return 'REVIEW_REQUIRED' if 'REVIEW_REQUIRED' in statuses else 'PASS'


def synthetic_result(values, label, profile='synthetic-v1'):
    vector = torch.tensor([values], dtype=torch.float32)
    return AudioEmbeddingResult(vector, {'shape': list(vector.shape), 'dimension': vector.shape[1],
        'source_sha256': hashlib.sha256(label.encode()).hexdigest(), 'model': 'synthetic-cosine-fixture',
        'model_version': '1', 'preprocessing_version': profile, 'checkpoint_revision': 'synthetic',
        'packages': {'fixture': '1'}, 'preprocessing': {'channel_policy': 'mono', 'target_sample_rate': 44100,
        'chunk_count': 8, 'chunk_normalization': 'l2', 'aggregation': 'mean', 'final_normalization': 'l2'},
        'dtype': 'torch.float32', 'device': 'cpu'})


def synthetic_checks(connection, repository, prefix):
    # SAVEPOINT로 보조 fixture 범위를 구분하고 마지막에 음악 행을 포함해 전체 rollback한다.
    evidence = []
    with connection.transaction():
        fixture_profile = 'synthetic-cosine-' + hashlib.sha256(prefix.encode()).hexdigest()[:12]
        query = synthetic_result([1, 0, 0], 'query', fixture_profile)
        ids = []
        for name, values, similarity in [('same', [1, 0, 0], 1.0), ('orthogonal', [0, 1, 0], 0.0),
                                          ('opposite', [-1, 0, 0], -1.0)]:
            music_id = prefix + name
            repository.save(connection, music_id, synthetic_result(values, name, fixture_profile))
            distance = connection.execute('SELECT embedding <=> %s::vector FROM ai_embeddings.audio_embeddings WHERE music_id=%s',
                (prepare_embedding(query)[2], music_id)).fetchone()[0]
            ids.append(music_id)
            evidence.append({'case': name, 'distance': distance, 'similarity': 1-distance,
                             'status': 'PASS' if distance == 1-similarity else 'FAIL'})
        found = repository.search(connection, query, top_k=100)
        require(found['candidate_count'] == 3 and [r['music_id'] for r in found['results']] == ids,
                'synthetic cosine ranking 실패')
    connection.execute('SAVEPOINT tie_fixture')
    try:
        query = synthetic_result([1, 0, 0], 'tie-query', 'tie-v1')
        candidate = synthetic_result([1, 0, 0], 'tie-candidate', 'tie-v1')
        groups = []
        for group, order in [('first', ['z', '2', '10', 'A']), ('second', ['A', '10', '2', 'z'])]:
            connection.execute('SAVEPOINT insertion_order')
            for suffix in order:
                repository.save(connection, prefix+'tie-'+suffix, candidate)
            found = repository.search(connection, query, top_k=100)
            actual = [r['music_id'] for r in found['results']]
            expected = sorted([prefix+'tie-'+s for s in order], key=lambda x: x.encode('utf-8'))
            groups.append({'insertion_order': order, 'ranking': actual, 'status': 'PASS' if actual == expected else 'FAIL'})
            connection.execute('ROLLBACK TO SAVEPOINT insertion_order')
            connection.execute('RELEASE SAVEPOINT insertion_order')
        evidence.append({'case': 'tie_C_collation', 'groups': groups, 'status': aggregate_status(groups)})
    finally:
        connection.execute('ROLLBACK TO SAVEPOINT tie_fixture')
        connection.execute('RELEASE SAVEPOINT tie_fixture')
    query = synthetic_result([1, 0, 0], 'compat-query', 'compat-v1')
    control = synthetic_result([1, 0, 0], 'compat-control', 'compat-v1')
    changes = [('dimension', None), ('model', 'model'), ('model_version', 'model_version'),
               ('checkpoint_revision', 'checkpoint_revision'), ('package', 'packages'),
               ('preprocessing_version', 'preprocessing_version'), ('dtype', 'dtype'), ('device', 'device')]
    changes += [(key, 'preprocessing') for key in ['channel_policy', 'target_sample_rate', 'chunk_count',
                                                'chunk_normalization', 'aggregation', 'final_normalization']]
    for name, field in changes:
        connection.execute('SAVEPOINT mismatch_fixture')
        try:
            candidate = copy.deepcopy(control)
            if name == 'dimension':
                candidate.metadata.update(dimension=4, shape=[1, 4])
                candidate = AudioEmbeddingResult(torch.ones(1, 4), candidate.metadata)
            elif field == 'packages':
                candidate.metadata[field]['fixture'] = 'different'
            elif field == 'preprocessing':
                candidate.metadata[field][name] = 'different'
            else:
                candidate.metadata[field] = 'different'
            repository.save(connection, prefix+'control', control)
            repository.save(connection, prefix+'mismatch', candidate)
            found = repository.search(connection, query, top_k=100)
            ok = found == {'candidate_count': 1, 'results': [{'music_id': prefix+'control', 'cosine_similarity': 1.0}]}
            evidence.append({'case': 'mismatch_'+name, 'query_sha': query.metadata['source_sha256'],
                'candidate_sha': candidate.metadata['source_sha256'], 'control_retained': ok,
                'mismatch_excluded': ok, 'status': 'PASS' if ok else 'FAIL'})
        finally:
            connection.execute('ROLLBACK TO SAVEPOINT mismatch_fixture')
            connection.execute('RELEASE SAVEPOINT mismatch_fixture')
    original = synthetic_result([1, 0, 0], 'duplicate', 'duplicate-v1')
    music_id = prefix+'duplicate'
    require(repository.save(connection, music_id, original).created, '최초 저장 실패')
    reused = not repository.save(connection, music_id, original).created
    for field in ['source_sha256', 'preprocessing_version', 'vector']:
        changed = copy.deepcopy(original)
        if field == 'vector':
            changed = AudioEmbeddingResult(torch.tensor([[0.0, 1.0, 0.0]]), changed.metadata)
        else:
            changed.metadata[field] = 'b'*64 if field == 'source_sha256' else 'different'
        conflict = False
        try:
            repository.save(connection, music_id, changed)
        except EmbeddingConflict:
            conflict = True
        preserved = torch.equal(read_vector(connection, music_id), original.vector)
        evidence.append({'case': 'conflict_'+field, 'conflict': conflict, 'original_preserved': preserved,
                         'status': 'PASS' if conflict and preserved and reused else 'FAIL'})
    evidence.append({'case': 'duplicate_reuse', 'created_false': reused, 'status': 'PASS' if reused else 'FAIL'})
    return evidence


def measure_transaction(connection, embeddings, prefix):
    repository = AudioEmbeddingRepository()
    ids = [prefix+row['track_id'] for row, _ in embeddings]
    reread, roundtrips, pairs, rankings = {}, [], [], []
    for (row, result), music_id in zip(embeddings, ids):
        require(repository.save(connection, music_id, result).created, 'validation row ID가 이미 존재합니다')
        reread[music_id] = read_vector(connection, music_id)
        roundtrips.append(dict(roundtrip_metrics(result.vector, reread[music_id]), music_id=music_id))
    for (input_row, query), query_id in zip(embeddings, ids):
        candidates = [(music_id, result) for (_, result), music_id in zip(embeddings, ids)
                      if result.metadata['source_sha256'] != query.metadata['source_sha256']]
        candidate_ids = [key for key, _ in candidates]
        before = audio_cosine_similarities(query.vector, torch.cat([r.vector for _, r in candidates])).tolist()
        after = audio_cosine_similarities(reread[query_id], torch.cat([reread[key] for key, _ in candidates])).tolist()
        found = repository.search(connection, query, top_k=100)
        require(found['candidate_count'] == len(candidate_ids), 'eligible candidate count 불일치')
        scores = {r['music_id']: r['cosine_similarity'] for r in found['results']}
        ranking = compare_rankings(candidate_ids, dict(zip(candidate_ids, before)), [r['music_id'] for r in found['results']])
        ranking['query_id'] = query_id
        ranking['top_k_checks'] = []
        for k in (1, 2, 5):
            limited = repository.search(connection, query, top_k=k)
            ok = limited['results'] == found['results'][:k] and limited['candidate_count'] == len(candidate_ids)
            ranking['top_k_checks'].append({'top_k': k, 'status': 'PASS' if ok else 'FAIL'})
        for key, a, b in zip(candidate_ids, before, after):
            distance, similarity = connection.execute('''SELECT embedding <=> %s::vector,
                1 - (embedding <=> %s::vector) FROM ai_embeddings.audio_embeddings WHERE music_id=%s''',
                (prepare_embedding(query)[2], prepare_embedding(query)[2], key)).fetchone()
            pairs.append(dict(cosine_record(a, b, distance, similarity, scores[key]), query_id=query_id, candidate_id=key))
        ranking['scores'] = [{'music_id': key, 'python': a, 'postgresql': scores[key],
                              'difference': a-scores[key]} for key, a in zip(candidate_ids, before)]
        ranking['status'] = aggregate_status([ranking]+ranking['top_k_checks'])
        rankings.append(ranking)
    fixtures = synthetic_checks(connection, repository, prefix+'fixture-')
    return {'roundtrips': roundtrips, 'cosine_comparisons': pairs, 'rankings': rankings,
            'synthetic_checks': fixtures, 'status': aggregate_status(roundtrips+pairs+rankings+fixtures)}


def input_evidence(root=ROOT):
    path = root/'docs/experiments/audio-highlight-phase-a/manifest.json'
    manifest = load_manifest(path, root=root)
    old_path = root/'docs/experiments/audio-highlight-msclap-validation/validation-result.json'
    old = json.loads(old_path.read_text(encoding='utf-8'))
    require(audio_file_sha256(path) == old['phase_a_manifest']['sha256'], 'Phase A manifest identity 불일치')
    rows = preflight(manifest, root, root/'docs/experiments/audio-highlight-phase-a/inspection-report.md')
    require(rows == old['inputs'], '입력 identity가 기존 MSCLAP evidence와 다릅니다')
    return rows, {'path': str(path.relative_to(root)), 'sha256': audio_file_sha256(path),
                  'dataset_id': manifest['dataset_id'], 'prior_msclap_evidence_sha256': audio_file_sha256(old_path)}


def docker_availability():
    try:
        result = subprocess.run(['docker', 'version', '--format', '{{.Server.Version}}'],
                                capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {'available': False, 'reason': 'Docker CLI 누락 또는 Engine 응답 timeout'}
    return {'available': result.returncode == 0, 'server_version': result.stdout.strip() or None,
            'reason': None if result.returncode == 0 else 'Docker Engine 연결 불가',
            'provisioning_performed': False, 'development_db_fallback': False}


class IntegrationTestCounts:
    """pytest의 setup/call/teardown 결과를 테스트당 한 번 집계한다."""

    def __init__(self):
        self.outcomes = {}

    def pytest_runtest_logreport(self, report):
        self.outcomes.setdefault(report.nodeid, []).append((report.when, report.outcome))

    def summarize(self, pytest_exit_code):
        counts = dict(passed=0, failed=0, skipped=0)
        for reports in self.outcomes.values():
            outcomes = {outcome for _, outcome in reports}
            if 'failed' in outcomes:
                counts['failed'] += 1
            elif 'skipped' in outcomes:
                counts['skipped'] += 1
            elif ('call', 'passed') in reports:
                counts['passed'] += 1

        suite_failure = pytest_exit_code != 0 and counts['failed'] == 0
        if suite_failure:
            # pytest collection/session failure도 report의 failed count에 드러낸다.
            counts['failed'] = 1
        effective_exit_code = pytest_exit_code if pytest_exit_code != 0 else int(counts['failed'] > 0)
        return {'counts': counts, 'pytest_exit_code': int(pytest_exit_code),
                'exit_code': effective_exit_code, 'suite_failure': suite_failure}


def run_guarded_integration_tests(expected_database):
    # 기존 테스트도 접속 factory를 guard로 감싼 별도 process에서만 실행한다.
    probe, _ = connect_validation(expected_database)
    probe.close()
    code = '''import sys
from app.core import database
from scripts.database import validate_audio_embedding_postgres as tool
import pytest, json
expected = sys.argv[1]
database.connect_database = lambda: tool.connect_validation(expected)[0]
counts = tool.IntegrationTestCounts()
exit_code = pytest.main(['tests/embedding/test_embedding_database.py',
'tests/matching/test_database_audio_search_integration.py',
 'tests/embedding/test_audio_embedding_postgres_validation_integration.py',
 '-q', '-p', 'no:cacheprovider'], plugins=[counts])
summary = counts.summarize(exit_code)
print('VALIDATION_TEST_RESULT='+json.dumps(summary))
raise SystemExit(summary['exit_code'])
'''
    environment = dict(os.environ, RUN_EMBEDDING_DB_TESTS='1', RUN_AUDIO_POSTGRES_VALIDATION_TESTS='1',
                       AUDIO_VALIDATION_EXPECTED_DATABASE=expected_database)
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code, expected_database],
                            cwd=ROOT, env=environment, capture_output=True, text=True, encoding='utf-8')
    # 예외 원문은 DB credentials를 포함할 수 있으므로 child 출력은 자동 publication하지 않는다.
    summaries = [line.removeprefix('VALIDATION_TEST_RESULT=') for line in result.stdout.splitlines()
                 if line.startswith('VALIDATION_TEST_RESULT=')]
    count_collection_error = not summaries
    summary = json.loads(summaries[-1]) if summaries else None
    counts = summary['counts'] if summary else dict(passed=0, failed=1, skipped=0)
    pytest_exit_code = summary['pytest_exit_code'] if summary else result.returncode
    effective_exit_code = summary['exit_code'] if summary else (result.returncode or 1)
    if result.returncode != effective_exit_code:
        if counts['failed'] == 0:
            counts['failed'] = 1
        effective_exit_code = result.returncode or 1
    if counts['failed'] > 0 and effective_exit_code == 0:
        effective_exit_code = 1
    if effective_exit_code != 0 and counts['failed'] == 0:
        counts['failed'] = 1
    return {'counts': counts, 'pytest_exit_code': pytest_exit_code,
            'exit_code': effective_exit_code, 'suite_failure': summary['suite_failure'] if summary else True,
            'count_collection_error': count_collection_error,
            'status': 'PASS' if effective_exit_code == 0 and counts['failed'] == 0 else 'FAIL',
            'tests': ['test_embedding_database.py', 'test_database_audio_search_integration.py',
                      'test_audio_embedding_postgres_validation_integration.py']}


def environment_evidence():
    import soundfile
    import torchaudio
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'libsndfile': soundfile.__libsndfile_version__, 'available_audio_backends': torchaudio.list_audio_backends(),
            'cpu_threads': torch.get_num_threads(), 'packages': {k: importlib.metadata.version(k) for k in ('psycopg', 'torch', 'torchaudio',
                'msclap', 'numpy', 'soundfile', 'transformers')}, 'device': 'cpu'}


def _error_message(error):
    if isinstance(error, psycopg.Error):
        return 'DB 실행 실패; 민감한 원본 오류는 출력하지 않음'
    return str(error)


def _rollback_and_close(connection, report):
    errors = []
    for action in (connection.rollback, connection.close):
        try:
            action()
        except Exception as error:
            errors.append(error)
    if errors:
        if len(errors) > 1:
            report.setdefault('rollback', {}).setdefault('cleanup_errors', []).extend(
                _error_message(error) for error in errors[1:])
        raise errors[0]


def _rollback_and_verify(connection, expected_database, report):
    execution = report['execution']
    execution['current_stage'] = 'rollback_verification'
    execution['rollback_verification'] = 'STARTED'
    report['rollback'] = {'status': 'STARTED'}
    fresh = None
    try:
        _rollback_and_close(connection, report)
        fresh, identity = connect_validation(expected_database)
        count = fresh.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone()[0]
        require(count == 0, 'rollback 후 validation row가 남았습니다')
        report['rollback'] = {'fresh_connection': True, 'remaining_validation_rows': count,
                              'identity': identity, 'status': 'PASS'}
        _rollback_and_close(fresh, report)
        fresh = None
    except Exception as error:
        # 오류를 삼키지 않는다. 상태를 기록한 뒤 호출부로 그대로 전달한다.
        message = _error_message(error)
        report['rollback'] = {**report.get('rollback', {}), 'status': 'FAIL', 'reason': message}
        execution['rollback_verification'] = 'FAILED'
        execution.setdefault('rollback_failure', {'stage': 'rollback_verification',
                                                   'reason_code': 'rollback_or_cleanup_failed',
                                                   'message': message})
        execution.setdefault('failed_stage', 'rollback_verification')
        raise
    finally:
        if fresh is not None:
            try:
                _rollback_and_close(fresh, report)
            except Exception as cleanup_error:
                # 이미 활성화된 측정/검증 오류를 유지하고 cleanup 오류도 별도로 기록한다.
                if sys.exc_info()[0] is not None:
                    report.setdefault('rollback', {}).setdefault('cleanup_errors', []).append(
                        _error_message(cleanup_error))
                else:
                    raise
    execution['rollback_verification'] = 'PASS'


def execute_validation(expected_database, inputs, report, *, run_tests=False):
    # migration·모델 로드 전에 실제 접속 identity를 확인한다.
    connection, identity = connect_validation(expected_database)
    execution = report.setdefault('execution', {})
    execution['db_validation'] = 'STARTED'
    execution['current_stage'] = 'database_preflight'
    report['isolation'] = dict(identity, existing_database_connection_attempted=False,
                               basis='explicit loopback/dedicated port/user/name + live identity/owner/marker guard')
    try:
        extension = connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        if extension is None:
            raise SafetyBlocked('전용 DB에 pgvector extension을 먼저 활성화해야 합니다')
        existing = connection.execute("SELECT to_regclass('ai_embeddings.audio_embeddings')").fetchone()[0]
        if existing:
            count = connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone()[0]
            if count:
                raise SafetyBlocked('전용 validation table이 비어 있지 않습니다; 기존 행을 변경하지 않습니다')
    finally:
        connection.rollback()
        connection.close()
    execution['current_stage'] = 'migration'
    report['migration_applied'] = apply_validated_migrations(expected_database)
    if run_tests:
        execution['current_stage'] = 'integration_tests'
        report['integration_tests'] = run_guarded_integration_tests(expected_database)
        require(report['integration_tests']['status'] == 'PASS', '전용 DB integration tests 실패')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HOME=str(ROOT/'datasets/fma/huggingface'))
    execution['current_stage'] = 'model_cache_preflight'
    report['cache'] = cache_identity(ROOT/'datasets/fma/huggingface')
    execution['current_stage'] = 'msclap_generation'
    execution['new_msclap_generation'] = 'STARTED'
    generator = AudioEmbeddingGenerator()
    embeddings = []
    report['generation'] = []
    for row in inputs:
        result = generator.generate(ROOT/row['path'], expected_sha256=row['sha256'])
        require(result.metadata['preprocessing_version'] == PREPROCESSING_VERSION, 'generation version 불일치')
        norm = float(result.vector.norm())
        require(abs(norm-1) <= 1e-6, 'final norm이 기존 abs=1e-6 기준을 벗어났습니다')
        profile = prepare_embedding(result)[1]
        checkpoint = Path(result.metadata.get('checkpoint_path', ''))
        require(checkpoint.is_file(), '실제 모델 checkpoint 파일 확인 실패')
        checkpoint_sha = audio_file_sha256(checkpoint)
        require(checkpoint_sha == report['cache']['microsoft--msclap']['files']['CLAP_weights_2023.pth']['sha256'],
                '실제 모델 checkpoint와 확인한 offline cache identity 불일치')
        require(result.metadata['checkpoint_revision'] == report['cache']['microsoft--msclap']['revision'],
                '실제 모델 checkpoint revision 불일치')
        report['generation'].append({'track_id': row['track_id'], 'dimension': result.vector.shape[1],
            'shape': list(result.vector.shape), 'finite': bool(torch.isfinite(result.vector).all()),
            'nonzero': bool(torch.count_nonzero(result.vector)), 'norm': norm, 'digest': digest(result.vector),
            'checkpoint_sha256': checkpoint_sha, 'generation_version': result.metadata['preprocessing_version'], 'generation_profile': profile,
            'status': 'PASS'})
        embeddings.append((row, result))
    require(all(r['generation_profile'] == report['generation'][0]['generation_profile'] for r in report['generation']),
            '6곡 generation profile 불일치')
    execution['new_msclap_generation'] = 'EXECUTED'
    prefix = 'validation-'+uuid.uuid4().hex+'-'
    execution['current_stage'] = 'database_measurements_connection'
    connection, identity = connect_validation(expected_database)
    execution['current_stage'] = 'schema_evidence'
    try:
        report['schema'] = schema_evidence(connection)
        execution['current_stage'] = 'database_measurements'
        require(connection.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone()[0] == 0,
                '시작 시 validation table이 비어 있지 않습니다')
        report['measurements'] = measure_transaction(connection, embeddings, prefix)
    except Exception as error:
        # finally에서 rollback을 수행해도 최초 원인과 stage를 보존한다.
        failed_stage = execution['current_stage']
        execution['failed_stage'] = failed_stage
        execution['primary_failure'] = {'stage': failed_stage,
            'reason_code': 'database_operation_failed' if isinstance(error, psycopg.Error) else 'validation_check_failed',
            'message': _error_message(error)}
        raise
    finally:
        failed_stage = execution.get('failed_stage')
        _rollback_and_verify(connection, expected_database, report)
        if failed_stage:
            execution['current_stage'] = failed_stage
    execution['current_stage'] = 'input_integrity_verification'
    report['input_sha_after_execution_unchanged'] = all(audio_file_sha256(ROOT/r['path']) == r['sha256']
                                                     and audio_file_sha256(ROOT/r['original_mp3_path']) == r['original_mp3_sha256'] for r in inputs)
    require(report['input_sha_after_execution_unchanged'], '입력 Audio SHA가 실행 중 변경됐습니다')
    execution['current_stage'] = 'complete'
    return aggregate_status([report['measurements'], report['rollback']])


def _execution_has_started(report):
    execution = report.get('execution', {})
    return any(execution.get(key) in ('STARTED', 'EXECUTED', 'FAILED')
               for key in ('db_validation', 'new_msclap_generation'))


def _record_failure(report, *, status, stage, reason_code, message, details=None):
    execution = report.setdefault('execution', {})
    primary = execution.get('primary_failure')
    rollback_failed = execution.get('rollback_verification') == 'FAILED'
    failure_stage = primary['stage'] if primary else stage
    failure_message = primary['message'] if primary else message
    if primary and rollback_failed:
        failure_message = f"{failure_message}; rollback verification도 실패했습니다"
    report['status'] = status
    report['reason'] = failure_message
    failure = {'stage': failure_stage,
               'reason_code': primary['reason_code'] if primary else reason_code,
               'message': failure_message}
    if details:
        failure.update(details)
    if primary:
        failure['primary_failure'] = primary
    if rollback_failed:
        failure['rollback_failure'] = execution.get('rollback_failure')
    report['failure'] = failure
    execution.setdefault('failed_stage', failure_stage)
    for key in ('db_validation', 'new_msclap_generation'):
        if execution.get(key) == 'STARTED':
            execution[key] = 'FAILED'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--run-integration-tests', action='store_true', help='guarded child process에서 기존/신규 DB tests 실행')
    parser.add_argument('--report', type=Path, required=True, help='새 JSON 경로; 기존 결과 덮어쓰기 금지')
    args = parser.parse_args(argv)
    output = args.report.resolve()
    if output.exists() or not (output.is_relative_to(ROOT/'datasets') or output.is_relative_to(ROOT/'docs/experiments/audio-embedding-postgres-validation')):
        parser.error('report는 지정 experiment 또는 ignored datasets 아래의 새 경로여야 합니다')
    report = {'schema_version': SCHEMA_VERSION, 'tool_version': TOOL_VERSION,
        'repository_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'tool_sha256': audio_file_sha256(__file__), 'generator_sha256': audio_file_sha256(ROOT/'app/embedding/audio_embedding.py'),
        'repository_sha256': audio_file_sha256(ROOT/'app/repository/embedding_repository.py'),
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'environment': environment_evidence(),
        'numerical_parity_policy': {'absolute_tolerance': COSINE_ABS_TOLERANCE,
            'relative_tolerance': COSINE_REL_TOLERANCE,
            'scope': 'Python cosine similarity versus PostgreSQL 1 - cosine_distance cosine similarity',
            'ranking_is_independent': True,
            'ranking_rule': 'candidate ID full order must match exactly; no epsilon/tolerance',
            'not_a_calibration_threshold': True},
        'docker': docker_availability(),
        'isolation': {'status': 'NOT_EXECUTED', 'expected_database': args.expected_database},
        'existing_db_protection': {'development_db_fallback': False, 'production_defaults_used': False,
            'existing_db_contents_audited': False, 'scope': '전용 DB만 허용; 기존 DB 내용 비교는 수행하지 않음'},
        'status': 'BLOCKED', 'limitations': ['전체 vector는 tracked evidence에 저장하지 않음',
            'cosine numerical tolerance는 Python/PostgreSQL parity 비교에만 적용; ranking 및 calibration 기준이 아님',
            'revision lifecycle·ACTIVE 후보 정책·검색 품질·calibration은 검증 대상 아님'],
        'unresolved': [], 'execution': {'db_validation': 'NOT_EXECUTED', 'new_msclap_generation': 'NOT_EXECUTED',
                                        'current_stage': 'preflight'}}
    try:
        inputs, manifest = input_evidence()
        report.update(inputs=inputs, phase_a_manifest=manifest)
        validation_settings(args.expected_database)
        report['status'] = execute_validation(args.expected_database, inputs, report, run_tests=args.run_integration_tests)
        report['execution']['db_validation'] = 'EXECUTED'
        report['execution']['new_msclap_generation'] = 'EXECUTED'
        report['execution']['current_stage'] = None
    except SafetyBlocked as error:
        if _execution_has_started(report):
            _record_failure(report, status='FAIL', stage=report['execution'].get('current_stage') or 'database_validation',
                            reason_code='validation_precondition_failed_after_start', message=str(error))
        else:
            _record_failure(report, status='BLOCKED', stage='preflight',
                            reason_code='validation_database_preflight_blocked', message=str(error))
            report['isolation']['status'] = 'BLOCKED'
            report['unresolved'].append('안전한 전용 validation PostgreSQL provision 필요')
    except MigrationFailure as error:
        _record_failure(report, status='FAIL', stage='migration', reason_code=error.reason_code,
                        message=error.message, details=error.to_report())
    except psycopg.OperationalError:
        if _execution_has_started(report):
            _record_failure(report, status='FAIL', stage=report['execution'].get('current_stage') or 'database_validation',
                            reason_code='database_connection_lost_during_validation',
                            message='validation DB 연결이 검증 실행 중 끊겼습니다; 민감한 원본 오류는 출력하지 않음')
        else:
            _record_failure(report, status='BLOCKED', stage='preflight',
                            reason_code='validation_database_unavailable_before_start',
                            message='전용 validation DB 접속 불가; 개발 DB fallback 없음')
            report['isolation']['status'] = 'BLOCKED'
            report['unresolved'].append('안전한 전용 validation PostgreSQL provision 필요')
    except (CheckFailed, ValidationError, DatasetError, AudioEmbeddingError, OSError, psycopg.Error) as error:
        stage = report['execution'].get('current_stage') or 'preflight'
        message = error.reason if isinstance(error, AudioEmbeddingError) else (
            'DB 실행 실패; 민감한 원본 오류는 출력하지 않음' if isinstance(error, psycopg.Error) else str(error))
        _record_failure(report, status='FAIL', stage=stage,
                        reason_code='database_operation_failed' if isinstance(error, psycopg.Error) else 'validation_check_failed',
                        message=message)
    report['failed_count'] = (report.get('integration_tests', {}).get('counts', {}).get('failed', 0)
                              if report['status'] == 'FAIL' else 0)
    if report['status'] == 'FAIL' and report['failed_count'] == 0:
        report['failed_count'] = 1
    report['exit_code'] = {'PASS': 0, 'FAIL': 1, 'REVIEW_REQUIRED': 3, 'BLOCKED': 4}[report['status']]
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as target:
        json.dump(report, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write('\n')
    print(json.dumps({'status': report['status'], 'reason': report.get('reason'),
                      'failed_count': report['failed_count'], 'exit_code': report['exit_code'],
                      'report': str(output.relative_to(ROOT))}, ensure_ascii=False))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
