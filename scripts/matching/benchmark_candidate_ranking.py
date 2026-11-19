"""격리 DB에서 production 후보 진단·ranking을 관찰하는 개발용 benchmark."""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import resource
import statistics
import sys
import threading
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import numpy as np
import psycopg
import torch
from psycopg import sql
from psycopg.types.json import Jsonb

from app.core.database import connect_database
from app.core.migrations import apply_migrations
from app.embedding import text_embedding as text
from app.embedding.audio_embedding import PREPROCESSING_VERSION
from app.repository.embedding_repository import (
    AudioEmbeddingRepository, CandidateCompatibilityStatus as Status,
    generation_profile_sha256, prepare_text_embedding,
)

DIMENSION = 1024
DEFAULT_COUNTS = (10, 50, 100, 500, 1000, 2000, 5000)
CSV_FIELDS = ('scenario', 'candidate_count', 'profile_count', 'concurrency', 'iteration',
              'connection_mode', 'phase', 'elapsed_ns', 'success', 'error_type')


def percentile(values, quantile):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(values):
    return {
        'count': len(values), 'mean_ns': statistics.mean(values) if values else None,
        'min_ns': min(values) if values else None, 'max_ns': max(values) if values else None,
        **{f'p{int(q * 100)}_ns': percentile(values, q) for q in (0.5, 0.95, 0.99)},
        'p99_exploratory': len(values) <= 100,
    }


def synthetic_vectors(count, seed=320):
    rng = np.random.default_rng(seed)
    vectors = rng.standard_normal((count, DIMENSION), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    for index, cosine in enumerate((0.95, 0.5, 0.0, -0.5, -1.0, 0.75, 0.75)):
        if index < count:
            vectors[index] = 0
            vectors[index, 0] = cosine
            vectors[index, 1] = math.sqrt(1 - cosine * cosine)
    return vectors.astype(np.float32)


def implementation():
    return {
        'package_version': text.CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': text.CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': text.CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': text.CALIBRATION_MSCLAP_CONFIG_SHA256,
    }


def audio_profile(**changes):
    profile = {
        'model': 'MSCLAP', 'model_version': text.MODEL_VERSION,
        'checkpoint_revision': text.CALIBRATION_CHECKPOINT_REVISION,
        'checkpoint_sha256': text.CALIBRATION_CHECKPOINT_SHA256,
        'msclap_implementation': implementation(),
        'packages': {'msclap': text.CALIBRATION_MSCLAP_PACKAGE_VERSION,
                     'torch': torch.__version__},
        'preprocessing_version': PREPROCESSING_VERSION,
        'preprocessing': {
            'analysis_duration_seconds': 56, 'chunk_duration_seconds': 7,
            'chunk_count': 8, 'chunk_overlap_seconds': 0,
            'chunk_normalization': 'l2', 'aggregation': 'mean', 'final_normalization': 'l2',
            'channel_policy': 'arithmetic_mean_downmix_to_mono',
        },
        'dimension': DIMENSION, 'dtype': 'torch.float32', 'device': 'cpu',
    }
    profile.update(changes)
    return profile


def query_result():
    vector = torch.zeros((1, DIMENSION), dtype=torch.float32)
    vector[0, 0] = 1
    metadata = audio_profile()
    metadata.pop('preprocessing_version')
    metadata.pop('preprocessing')
    metadata.update({
        'query_text_sha256': hashlib.sha256(b'synthetic query; no model inference').hexdigest(),
        'shape': [1, DIMENSION], 'generation_version': text.GENERATION_VERSION,
        'embedding_generation_profile': text.GENERATION_PROFILE,
        'text_encoder': {
            'model_id': text.TEXT_ENCODER_MODEL_ID, 'revision': text.TEXT_ENCODER_REVISION,
            'config_sha256': text.TEXT_ENCODER_TOKENIZER_FILE_SHA256['config.json'],
            'model_file': 'model.safetensors', 'model_file_sha256': text.TEXT_ENCODER_MODEL_SHA256,
            'tokenizer_id': text.TEXT_ENCODER_MODEL_ID,
            'tokenizer_revision': text.TEXT_ENCODER_REVISION,
            'tokenizer_runtime_sha256': '1' * 64,
            'tokenizer_files_sha256': text.TEXT_ENCODER_TOKENIZER_FILE_SHA256.copy(),
        },
        'text_preprocessing': {
            'encoder_api': 'CLAP.get_text_embeddings', 'text_model': text.TEXT_ENCODER_MODEL_ID,
            'text_model_revision': text.TEXT_ENCODER_REVISION, 'token_limit': 77,
            'truncation': 'rejected', 'normalization': 'none; raw MSCLAP Text Embedding',
        },
        'synthetic': True,
    })
    return text.TextEmbeddingResult(vector, metadata)


def rss():
    status = Path('/proc/self/status').read_text()
    fields = {line.split(':')[0]: int(line.split()[1]) * 1024
              for line in status.splitlines() if line.startswith(('VmRSS:', 'VmHWM:'))}
    return {'rss_bytes': fields['VmRSS'], 'peak_rss_bytes': fields['VmHWM'],
            'resource_maxrss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}


class ObservedCursor:
    def __init__(self, cursor, observations):
        self.cursor = cursor
        self.observations = observations

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def execute(self, statement, parameters):
        started = time.perf_counter_ns()
        try:
            return self.cursor.execute(statement, parameters)
        finally:
            self.current = {
                'sql': statement, 'params': parameters, 'parameter_count': len(parameters),
                'sql_bytes': len(statement.encode('utf-8')),
                'execute_ns': time.perf_counter_ns() - started, 'fetch_ns': 0,
            }
            self.observations.append(self.current)

    def fetchall(self):
        started = time.perf_counter_ns()
        try:
            return self.cursor.fetchall()
        finally:
            self.current['fetch_ns'] += time.perf_counter_ns() - started


class ObservedConnection:
    def __init__(self, connection):
        self.connection = connection
        self.observations = []

    def cursor(self):
        return ObservedCursor(self.connection.cursor(), self.observations)


def run_request(connection, pairs, query):
    observed = ObservedConnection(connection)
    repository = AudioEmbeddingRepository()
    started = time.perf_counter_ns()
    diagnoses = repository.check_candidate_compatibility(observed, pairs, query)
    diagnosed = time.perf_counter_ns()
    identities = [d.compatible_candidate for d in diagnoses if d.status == Status.COMPATIBLE]
    valid = all(d.status == Status.COMPATIBLE for d in diagnoses)
    ranking = repository.rank_candidates(observed, identities, query) if valid else []
    ended = time.perf_counter_ns()
    selected = {(c.music_id,c.audio_revision,c.embedding_id,c.generation_profile_sha256) for c in identities}
    assert all((r.music_id,r.audio_revision,r.embedding_id,r.generation_profile_sha256) in selected for r in ranking)
    phases = {'compatibility': diagnosed - started, 'ranking': ended - diagnosed if valid else 0,
              'total': ended - started}
    unique = len(set(pairs))
    expected = [2 * unique] if unique else []
    if valid and identities:
        expected.append(4 * len(identities) + 2)
    assert [o['parameter_count'] for o in observed.observations] == expected
    for index, name in enumerate(('compatibility', 'ranking')):
        if index < len(observed.observations):
            observation = observed.observations[index]
            phases[name + '_execute'] = observation['execute_ns']
            phases[name + '_fetch'] = observation['fetch_ns']
            phases[name + '_python_remainder'] = (
                phases[name] - observation['execute_ns'] - observation['fetch_ns'])
    return diagnoses, ranking, phases, observed.observations


def assert_ranking(ranking, pairs, expected_ids=None):
    assert len(ranking) == min(len(set(pairs)), 100)
    assert [r.rank for r in ranking] == list(range(1, len(ranking) + 1))
    assert all((r.music_id, r.audio_revision) in set(pairs) for r in ranking)
    assert len({r.embedding_id for r in ranking}) == len(ranking)
    keys = [(-r.raw_cosine, r.music_id, r.audio_revision, r.embedding_id) for r in ranking]
    assert keys == sorted(keys)
    if expected_ids is not None:
        assert [r.music_id for r in ranking] == expected_ids


def insert_embeddings(connection, entries):
    """실험 준비용 COPY만 수행하며 검색 SQL은 repository가 전담한다."""
    entries = list(entries)
    sources = {(music, revision): hashlib.sha256(music.encode()).hexdigest()
               for music, revision, _, _ in entries}
    with connection.cursor() as cursor:
        for (music, revision), source in sources.items():
            cursor.execute('''INSERT INTO ai_embeddings.audio_sources VALUES (%s, %s, %s)
                              ON CONFLICT DO NOTHING''', (music, revision, source))
        with cursor.copy('''COPY ai_embeddings.audio_embeddings
            (music_id, audio_revision, source_sha256, model, model_version, preprocessing_version,
             dimension, embedding, generation_profile, generation_profile_sha256, metadata)
            FROM STDIN''') as copy:
            for music, revision, vector, profile in entries:
                copy.write_row((music, revision, sources[(music, revision)], profile['model'],
                                profile['model_version'], profile['preprocessing_version'],
                                len(vector), json.dumps(vector.tolist()), Jsonb(profile),
                                generation_profile_sha256(profile), Jsonb({'synthetic': True})))
    connection.commit()


@contextmanager
def isolated_database():
    admin_name = os.environ.get('DB_NAME')
    if admin_name != 'benchmark_admin':
        raise ValueError('전용 benchmark_admin DB를 가진 격리 컨테이너만 허용합니다')
    name = 'nsuai32_' + uuid.uuid4().hex
    with connect_database() as admin:
        admin.autocommit = True
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        os.environ['DB_NAME'] = name
        try:
            with connect_database() as connection:
                connection.execute('CREATE EXTENSION vector')
            yield name
        finally:
            os.environ['DB_NAME'] = admin_name
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s',
                          (name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def environment(connection):
    settings = ['max_connections', 'work_mem', 'shared_buffers', 'statement_timeout',
                'lock_timeout', 'effective_cache_size', 'max_parallel_workers_per_gather']
    return {
        'os': platform.platform(), 'python': sys.version, 'cpu_count': os.cpu_count(),
        'cpu_model': next((line.split(':', 1)[1].strip() for line in
                           Path('/proc/cpuinfo').read_text().splitlines()
                           if line.startswith('model name')), None),
        'meminfo': {line.split(':')[0]: line.split(':')[1].strip() for line in
                    Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))},
        'cgroup_memory_max': Path('/sys/fs/cgroup/memory.max').read_text().strip(),
        'cgroup_cpu_max': Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
        'psycopg': psycopg.__version__, 'libpq': psycopg.pq.version(),
        'torch': torch.__version__, 'numpy': np.__version__,
        'postgresql': connection.execute('SELECT version()').fetchone()[0],
        'pgvector': connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0],
        'database_settings': {setting: connection.execute('SELECT current_setting(%s)', (setting,)).fetchone()[0]
                              for setting in settings},
        'prepare_threshold': connection.prepare_threshold,
    }


def samples_for(connection, pairs, query, repetitions, warmup, scenario, mode, profile_count=1):
    samples, last = [], None
    for iteration in range(-warmup, repetitions):
        connect_started = time.perf_counter_ns()
        owned = connect_database() if mode == 'included' else None
        current = owned if owned is not None else connection
        connection_ns = time.perf_counter_ns() - connect_started if owned else 0
        try:
            diagnoses, ranking, phases, observations = run_request(current, pairs, query)
            assert all(d.status == Status.COMPATIBLE for d in diagnoses)
            assert_ranking(ranking, pairs)
            commit_started=time.perf_counter_ns()
            current.commit()
            phases['commit']=time.perf_counter_ns()-commit_started
            close_started=time.perf_counter_ns()
            if owned is not None:
                owned.close()
            phases['close']=time.perf_counter_ns()-close_started if owned else 0
            phases['connection'] = connection_ns
            phases['total_including_connection'] = phases['total'] + connection_ns + phases['commit'] + phases['close']
            if iteration >= 0:
                samples.extend({'scenario': scenario, 'candidate_count': len(pairs),
                                'profile_count': profile_count, 'concurrency': 1,
                                'iteration': iteration, 'connection_mode': mode, 'phase': phase,
                                'elapsed_ns': elapsed, 'success': True, 'error_type': ''}
                               for phase, elapsed in phases.items())
            last = observations
        finally:
            if owned is not None:
                owned.close()
    return samples, last


def explain(connection, observations, directory, count):
    directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for phase, observation in zip(('compatibility', 'ranking'), observations):
        statement = 'EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON) ' + observation['sql']
        plan = connection.execute(statement, observation['params']).fetchone()[0]
        path = directory / f'{count}-{phase}.json'
        path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
        summaries.append({'candidate_count': count, 'phase': phase, 'file': str(path),
                          'planning_ms': plan[0]['Planning Time'],
                          'execution_ms': plan[0]['Execution Time']})
    connection.commit()
    return summaries


def memory_measurement(connection, count, query):
    tracemalloc.start()
    snapshots = [{'phase': 'baseline', **rss()}]
    pairs = [(f'music-{i:05}', 1) for i in range(count)]
    snapshots.append({'phase': 'candidate_created', **rss()})
    observed = ObservedConnection(connection)
    repository = AudioEmbeddingRepository()
    snapshots.append({'phase': 'before_compatibility', **rss()})
    diagnoses = repository.check_candidate_compatibility(observed, pairs, query)
    snapshots.append({'phase': 'after_compatibility', **rss()})
    identities = [d.compatible_candidate for d in diagnoses]
    snapshots.append({'phase': 'before_ranking', **rss()})
    results = repository.rank_candidates(observed, identities, query)
    snapshots.append({'phase': 'after_ranking', **rss()})
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert_ranking(results, pairs)
    connection.commit()
    return {'candidate_count': count, 'snapshots': snapshots,
            'python_allocation_current_bytes': current, 'python_allocation_peak_bytes': peak}


def invalid_correctness(connection, query):
    repository = AudioEmbeddingRepository()
    vectors = synthetic_vectors(10)
    cases = {}
    # 실험 행은 마지막에 rollback하여 기본 dataset에 남기지 않는다.
    with connection.transaction(force_rollback=True):
        profile = audio_profile()
        source = 'a' * 64
        for music in ('source-only', 'bad-model', 'bad-dimension', 'ambiguous'):
            connection.execute('INSERT INTO ai_embeddings.audio_sources VALUES (%s, 1, %s)', (music, source))
        def add(music, vector, profile):
            connection.execute('''INSERT INTO ai_embeddings.audio_embeddings
                (music_id,audio_revision,source_sha256,model,model_version,preprocessing_version,
                 dimension,embedding,generation_profile,generation_profile_sha256,metadata)
                VALUES (%s,1,%s,%s,%s,%s,%s,%s::vector,%s,%s,%s)''',
                (music,hashlib.sha256(music.encode()).hexdigest() if music=='music-00000' else source,profile['model'],profile['model_version'],profile['preprocessing_version'],
                 len(vector),json.dumps(vector.tolist()),Jsonb(profile),
                 generation_profile_sha256(profile),Jsonb({'synthetic':True})))
        add('bad-model',vectors[0],audio_profile(model='incompatible'))
        add('bad-dimension',np.array([1,0],dtype=np.float32),audio_profile(dimension=2))
        add('ambiguous',vectors[0],profile)
        add('ambiguous',vectors[0],audio_profile(device='cuda'))
        for music, expected in [('unknown',Status.MISSING_SOURCE),('source-only',Status.MISSING_EMBEDDING),
                                ('bad-model',Status.INCOMPATIBLE_PROFILE),
                                ('bad-dimension',Status.INVALID_DIMENSION),('ambiguous',Status.AMBIGUOUS_PROFILE)]:
            diagnoses, ranked, _, observations = run_request(connection,[(music,1)],query)
            assert diagnoses[0].status == expected and ranked == [] and len(observations) == 1
            cases[expected.value] = {'diagnosis':True,'ranking_not_called':True}
        diagnoses, ranked, _, observations = run_request(connection,[('music-00000',1)] * 2,query)
        assert diagnoses[1].status == Status.DUPLICATE and not ranked and len(observations) == 1
        cases['DUPLICATE'] = {'diagnosis':True,'ranking_not_called':True}
        missing = repository.check_candidate_compatibility(connection,[('music-00000',999)],query)
        assert missing[0].status == Status.MISSING_SOURCE
        cases['missing_revision_no_fallback'] = True
        original=repository.check_candidate_compatibility(connection,[('music-00000',1)],query)[0].compatible_candidate
        add('music-00000',np.eye(1,DIMENSION,dtype=np.float32)[0],audio_profile(model='other-profile'))
        _,ranked,_,_=run_request(connection,[('music-00000',1)],query)
        assert ranked[0].embedding_id==original.embedding_id
        duplicate=repository.rank_candidates(connection,[original,original],query)
        assert len(duplicate)==1 and duplicate[0].embedding_id==original.embedding_id
        assert repository.rank_candidates(connection,[],query)==[]
        cases['other_profile_excluded']=True
        cases['duplicate_ranking_not_multiplied']=True
    connection.rollback()
    return cases


def concurrency_measurement(pairs, query, concurrency, requests_per_worker=10):
    samples, raw, waits = [], [], []
    stopped=threading.Event()
    monitor_errors=[]
    def monitor():
        try:
            with connect_database() as connection:
                connection.autocommit=True
                while not stopped.is_set():
                    rows=connection.execute("""SELECT wait_event_type,wait_event,count(*)
                        FROM pg_stat_activity WHERE datname=current_database()
                        AND application_name='nsuai32-benchmark'
                        GROUP BY wait_event_type,wait_event""").fetchall()
                    waits.append({'elapsed_ns':time.perf_counter_ns()-started,
                                  'events':[{'type':r[0],'event':r[1],'sessions':r[2]} for r in rows]})
                    stopped.wait(0.025)
        except Exception as error:
            monitor_errors.append(type(error).__name__)
    def worker(worker_id):
        before=time.perf_counter_ns()
        with connect_database() as connection:
            connection_ns=time.perf_counter_ns()-before
            connection.execute("SELECT set_config('application_name','nsuai32-benchmark',false)")
            connection.commit()
            output=[]
            for iteration in range(requests_per_worker):
                diagnoses,ranked,phases,_=run_request(connection,pairs,query)
                connection.commit()
                assert all(d.status==Status.COMPATIBLE for d in diagnoses)
                assert_ranking(ranked,pairs)
                output.append((worker_id*requests_per_worker+iteration,phases['total'],
                               tuple(r.embedding_id for r in ranked),connection_ns))
            return output
    with connect_database() as observer:
        observer.autocommit=True
        before=observer.execute('SELECT deadlocks FROM pg_stat_database WHERE datname=current_database()').fetchone()[0]
        started=time.perf_counter_ns()
        thread=threading.Thread(target=monitor,daemon=True)
        thread.start()
        try:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                for output in executor.map(worker,range(concurrency)):
                    samples.extend(output)
            elapsed=time.perf_counter_ns()-started
        finally:
            stopped.set()
            thread.join()
        after=observer.execute('SELECT deadlocks FROM pg_stat_database WHERE datname=current_database()').fetchone()[0]
    assert len({row[2] for row in samples})==1
    connection_times=[]
    for iteration,elapsed_ns,_,connection_ns in samples:
        raw.append({'scenario':'concurrency','candidate_count':len(pairs),'profile_count':1,
                    'concurrency':concurrency,'iteration':iteration,'connection_mode':'reuse',
                    'phase':'total','elapsed_ns':elapsed_ns,'success':True,'error_type':''})
        if iteration%requests_per_worker==0:
            connection_times.append(connection_ns)
            raw.append({**raw[-1],'phase':'connection','elapsed_ns':connection_ns})
    return {
        'concurrency':concurrency,'candidate_count':len(pairs),'profile_count':1,
        'successful_requests':len(samples),'failed_requests':0,'timeout_count':0,
        'throughput_per_second':len(samples)*1e9/elapsed,
        'latency':summarize([row[1] for row in samples]),
        'connection_time':summarize(connection_times),'process_memory':rss(),
        'observed_lock_wait_samples':sum(any(e['type']=='Lock' for e in s['events']) for s in waits),
        'wait_sampling':waits,'wait_monitor_errors':monitor_errors,'deadlock_counter_delta':after-before,
        'correctness':True,'mode':'independent connection per worker, reused within worker',
        'limitations':'25ms sampling 사이의 짧은 wait는 미관측 가능. throughput은 접속/commit/검사 비용도 포함한다.',
    },raw


def write_results(output, result, samples):
    output.mkdir(parents=True,exist_ok=True)
    (output/'benchmark-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    with (output/'latency-samples.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(samples)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repository-commit',required=True)
    parser.add_argument('--counts',type=int,nargs='+',default=DEFAULT_COUNTS)
    parser.add_argument('--iterations',type=int,default=30)
    parser.add_argument('--warmup',type=int,default=5)
    parser.add_argument('--include-10000',action='store_true')
    args=parser.parse_args(argv)
    if args.iterations<1 or args.warmup<0 or any(n<1 or n>10000 for n in args.counts):
        parser.error('invalid scenario size')
    if args.include_10000 and 5000 not in args.counts:
        parser.error('10000 exploration requires an earlier 5000 scenario')
    torch.set_num_threads(1)
    result={
        'metadata':{'synthetic':True,'model_inference':False,'http_orchestration':False,
                    'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'source_state':'uncommitted benchmark source over repository_commit'},
        'repository_commit':args.repository_commit,
        'dataset':{'seed':320,'dimension':DIMENSION,'dtype':'float32','l2_normalized_audio':True},
        'scenarios':[],'latency':[],'memory':[],'concurrency':[],'correctness':{},
        'errors':[],'limitations':[
            '운영 SLA/입력 최대치 미확정; 측정 완료와 운영 성능 합격은 다르다.',
            'Text inference, HTTP latency, 모델 inference concurrency, 음악 품질 평가 미포함.',
            'Python remainder는 validation/serialization/object 생성 등을 포함하며 순수 profile 처리 시간이 아니다.',
            'p99는 표본 수에 민감하며 100회 이하는 탐색값이다.',
            '현재 RSS sampling은 순간 native allocation을 모두 포착하지 않는다.',
            '검증 이후 identity 소실의 운영 처리는 NSUAI-48/49 후속 범위다.',
        ],
        'parameter_boundary':{'postgresql':65535,'compatibility_unique_pairs':32767,
                              'ranking_identities':16383,'operational_limit':None},
    }
    samples=[]
    try:
        with isolated_database() as name:
            result['database']={'isolated_name':name}
            result['database']['migrations']=apply_migrations()
            assert apply_migrations()==[]
            with connect_database() as connection:
                result['environment']=environment(connection)
                result['database']['constraints']=[list(row) for row in connection.execute(
                    """SELECT conrelid::regclass::text,pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE connamespace='ai_embeddings'::regnamespace ORDER BY conrelid,conname""")]
                result['database']['indexes']=[row[0] for row in connection.execute(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname='ai_embeddings' ORDER BY indexname")]
                assert connection.execute('SELECT uuid_extract_version(uuidv7())').fetchone()[0]==7
                counts=list(args.counts)
                if args.include_10000:
                    counts.append(10000)
                maximum=max(counts)
                vectors=synthetic_vectors(maximum)
                profile=audio_profile()
                insert_embeddings(connection,((f'music-{i:05}',1,vector,profile) for i,vector in enumerate(vectors)))
                insert_embeddings(connection,[
                    ('outside-best',1,np.eye(1,DIMENSION,dtype=np.float32)[0],profile),
                    ('music-00000',2,np.eye(1,DIMENSION,dtype=np.float32)[0],profile),
                ])
                connection.execute('ANALYZE ai_embeddings.audio_sources')
                connection.execute('ANALYZE ai_embeddings.audio_embeddings')
                connection.commit()
                query=query_result()
                prepare_text_embedding(query)
                for count in counts:
                    if count==10000:
                        plans=[json.loads(path.read_text()) for path in (args.output/'explain').glob('5000-*.json')]
                        def spilled(node):
                            if isinstance(node,dict):
                                return node.get('Temp Written Blocks',0)>0 or any(spilled(v) for v in node.values())
                            return isinstance(node,list) and any(spilled(v) for v in node)
                        spill=any(spilled(plan) for plan in plans)
                        current=int(Path('/sys/fs/cgroup/memory.current').read_text())
                        limit=int(Path('/sys/fs/cgroup/memory.max').read_text())
                        safe=bool(plans) and not spill and current<limit*0.75
                        result['scale_10000_gate']={'prior_5000_errors':0,'prior_5000_plans':len(plans),
                            'temp_spill_detected':spill,'cgroup_current_bytes':current,
                            'cgroup_limit_bytes':limit,'executed':safe,
                            'note':'resource safety guard, not an operating SLA'}
                        if not safe:
                            break
                    pairs=[(f'music-{i:05}',1) for i in range(count)]
                    repetitions=args.iterations if count<=2000 else 10
                    # 대형 규모는 소수 smoke를 수행한 뒤 일반 측정으로 진행한다.
                    if count>=5000:
                        samples_for(connection,pairs,query,3,0,'safety-smoke','reuse')
                    for mode in ('reuse','included'):
                        batch,observations=samples_for(connection,pairs,query,repetitions,args.warmup,'scale',mode)
                        samples.extend(batch)
                        phases={phase:summarize([s['elapsed_ns'] for s in batch if s['phase']==phase])
                                for phase in sorted({s['phase'] for s in batch})}
                        result['latency'].append({'candidate_count':count,'profile_count':1,'mode':mode,
                                                  'iterations':repetitions,'warmup':args.warmup,
                                                  'phases':phases,'errors':0,'rss_after_repetitions':rss()})
                        result['scenarios'].append({'candidate_count':count,'mode':mode,
                            'parameters':[o['parameter_count'] for o in observations],
                            'sql_bytes':[o['sql_bytes'] for o in observations]})
                    _,ranked,_,observations=run_request(connection,pairs,query)
                    reference=torch.nn.functional.cosine_similarity(query.vector,
                        torch.from_numpy(vectors[:count]),dim=1).tolist()
                    expected=sorted(range(count),key=lambda i:(-reference[i],f'music-{i:05}'))[:100]
                    assert_ranking(ranked,pairs,[f'music-{i:05}' for i in expected])
                    for row in ranked:
                        index=int(row.music_id.split('-')[1])
                        assert abs(row.raw_cosine-reference[index])<=1e-6
                    if count in (100,1000,5000,10000):
                        result.setdefault('explain',[]).extend(explain(connection,observations,args.output/'explain',count))
                    result['memory'].append(memory_measurement(connection,count,query))
                    print(f'scale {count} complete',flush=True)
                    write_results(args.output,result,samples)
                result['correctness']['invalid_cases']=invalid_correctness(connection,query)
                result['correctness']['cosine_abs_tolerance']=1e-6
                result['correctness']['exact_subset_top100_ties_no_fallback']=True
                # profile 수는 후보 수와 분리하여 1,3,5를 비교한다.
                pairs=[(f'music-{i:05}',1) for i in range(min(1000,maximum))]
                for concurrent in (1,2,5,10):
                    concurrent_result,raw_concurrent=concurrency_measurement(pairs,query,concurrent)
                    result['concurrency'].append(concurrent_result)
                    samples.extend(raw_concurrent)
                    print(f'concurrency {concurrent} complete',flush=True)
                profile_candidates=min(1000,maximum)
                for extra in (2,4):
                    entries=[]
                    existing=0 if extra==2 else 2
                    for i in range(profile_candidates):
                        for j in range(existing,extra):
                            entries.append((f'music-{i:05}',1,vectors[i],
                                            audio_profile(model=f'incompatible-{j}')))
                    insert_embeddings(connection,entries)
                    pairs=[(f'music-{i:05}',1) for i in range(profile_candidates)]
                    batch,_=samples_for(connection,pairs,query,30,5,'profile-load','reuse',extra+1)
                    samples.extend(batch)
                    result.setdefault('profile_load',[]).append({
                        'candidate_count':profile_candidates,'profile_count':extra+1,
                        'phases':{phase:summarize([s['elapsed_ns'] for s in batch if s['phase']==phase])
                                  for phase in sorted({s['phase'] for s in batch})}})
                result['concurrency_20']={'executed':False,'reason':'CPU quota 2개 환경에서 10단계까지 측정; 20은 운영 동시성 확정이 아니므로 확대하지 않음'}
                result['correctness']['orphan_embeddings']=connection.execute('''SELECT count(*)
                    FROM ai_embeddings.audio_embeddings e LEFT JOIN ai_embeddings.audio_sources s
                    ON (s.music_id,s.audio_revision,s.source_sha256)=(e.music_id,e.audio_revision,e.source_sha256)
                    WHERE s.music_id IS NULL''').fetchone()[0]
                result['correctness']['sources_without_embedding']=connection.execute('''SELECT count(*)
                    FROM ai_embeddings.audio_sources s LEFT JOIN ai_embeddings.audio_embeddings e
                    ON (s.music_id,s.audio_revision)=(e.music_id,e.audio_revision)
                    WHERE e.id IS NULL''').fetchone()[0]
                assert result['correctness']['orphan_embeddings']==0
                assert result['correctness']['sources_without_embedding']==0
                result['memory_after_repetitions']=rss()
                result['dataset']['row_counts']=connection.execute('''SELECT
                    (SELECT count(*) FROM ai_embeddings.audio_sources),
                    (SELECT count(*) FROM ai_embeddings.audio_embeddings)''').fetchone()
                result['dataset']['profile']=profile
                result['completed']=True
        with connect_database() as admin:
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(name,)).fetchone()[0]==0
        result['database']['cleanup_verified']=True
    except Exception as error:
        result['errors'].append({'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        write_results(args.output,result,samples)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
