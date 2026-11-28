"""Synthetic 생성기와 독립 PostgreSQL 세션으로 소유권·rollback·재사용을 검증한다."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Barrier
from unittest.mock import Mock

import pytest

from app.core.database import connect_database
from app.core.migrations import apply_migrations
from app.embedding.audio_embedding import AudioEmbeddingError, audio_file_sha256
from app.embedding.storage import AudioEmbeddingStorage
from app.repository.audio_processing_repository import (
    AttemptNoLongerProcessing, AudioProcessingRepository, ProcessingInProgress,
)
from app.repository.embedding_repository import AudioEmbeddingRepository, EmbeddingConflict, prepare_embedding
from test_active_revision_search_integration import assert_request_returns, save_revision
from test_audio_identity_migrations import migration_database
from test_embedding_storage import make_result


pytestmark = pytest.mark.skipif(os.environ.get('RUN_IDENTITY_MIGRATION_TESTS') != '1',
                                reason='Explicit isolated migration database opt-in required')


@pytest.fixture
def attempts(migration_database):
    apply_migrations()
    return AudioProcessingRepository()


def claim(repo, result, revision=1, *, stale_before=None):
    metadata, profile, _ = prepare_embedding(result)
    with connect_database() as conn:
        return repo.acquire(conn, 'music', revision, metadata['source_sha256'], profile, stale_before=stale_before)


def state(attempt):
    with connect_database() as conn:
        return conn.execute('''SELECT state, started_at, finished_at, failure_kind, failure_reason, stale_cutoff
            FROM ai_embeddings.audio_processing_attempts WHERE attempt_id = %s''', (attempt.id,)).fetchone()


def read_embedding(attempt):
    with connect_database() as conn:
        return AudioEmbeddingRepository().get(conn, 'music', attempt.audio_revision, attempt.profile_sha256)


def test_simultaneous_claim_has_one_owner(attempts):
    result = make_result()
    profile = prepare_embedding(result)[1]
    gate = Barrier(2, timeout=20)

    def request():
        with connect_database() as conn:
            gate.wait()
            try:
                return attempts.acquire(conn, 'music', 1, result.metadata['source_sha256'], profile)
            except ProcessingInProgress:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = [future.result() for future in [pool.submit(request), pool.submit(request)]]
    assert (a is None) != (b is None)
    assert state(a or b)[0] == 'processing'


def test_stale_cutoff_boundary_including_no_policy(attempts):
    result = make_result()
    first = claim(attempts, result)
    started = state(first)[1]
    with pytest.raises(ValueError, match='stale_before_must_not_be_in_the_future'):
        claim(attempts, result, stale_before=started + timedelta(days=1))
    for cutoff in (None, started - timedelta(microseconds=1)):
        with pytest.raises(ProcessingInProgress):
            claim(attempts, result, stale_before=cutoff)
    assert state(first) == ('processing', started, None, None, None, None)
    second = claim(attempts, result, stale_before=started)
    failed = state(first)
    assert failed[0] == 'failed' and failed[2] >= started
    assert failed[3:] == ('transient', 'stale_takeover', started)
    assert second.id != first.id and state(second)[0] == 'processing'


@pytest.mark.parametrize('b_ready', [False, True])
@pytest.mark.parametrize('late_success', [False, True])
def test_old_worker_cannot_finish_after_takeover(attempts, b_ready, late_success):
    old_result, new_result = make_result(), make_result()
    new_result.vector.neg_()
    with connect_database() as conn:
        active = save_revision(conn, 'music', 1, 1.0)
    first = claim(attempts, old_result, revision=2)
    gate = Barrier(2, timeout=20)

    def deliver_late_result():
        with connect_database() as conn:
            gate.wait()
            with pytest.raises(AttemptNoLongerProcessing):
                if late_success:
                    attempts.complete(conn, first, old_result)
                else:
                    attempts.fail(conn, first, 'transient', 'audio_generation_failed')

    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(deliver_late_result)
        try:
            second = claim(attempts, new_result, revision=2, stale_before=state(first)[1])
            if b_ready:
                with connect_database() as conn:
                    attempts.complete(conn, second, new_result)
            before = state(second), read_embedding(second)
            gate.wait()
            late.result()
        finally:
            gate.abort()
    assert_request_returns(('music', 1), active)
    assert (state(second), read_embedding(second)) == before
    if not b_ready:
        assert before[1] is None
        with connect_database() as conn:
            attempts.complete(conn, second, new_result)
    assert state(second)[0] == 'ready'
    assert read_embedding(second)['embedding'] == '[-1,-1,-1,-1]'
    assert state(first)[4] == 'stale_takeover'


@pytest.mark.parametrize('terminal', ['ready', 'failed'])
def test_current_attempt_cannot_transition_twice(attempts, terminal):
    result = make_result()
    first = claim(attempts, result)
    with connect_database() as conn:
        if terminal == 'ready':
            attempts.complete(conn, first, result)
        else:
            attempts.fail(conn, first, 'input', 'invalid_input')
    original = state(first), read_embedding(first)
    with connect_database() as conn:
        with pytest.raises(AttemptNoLongerProcessing):
            attempts.complete(conn, first, result)
        with pytest.raises(AttemptNoLongerProcessing):
            attempts.fail(conn, first, 'transient', 'audio_storage_failed')
    assert (state(first), read_embedding(first)) == original


def test_revision_source_and_profiles_remain_independent(attempts):
    result = make_result()
    one = claim(attempts, result)
    result.metadata['device'] = 'other'
    two = claim(attempts, result)
    result.metadata['source_sha256'] = 'b' * 64
    with pytest.raises(EmbeddingConflict, match='different_source'):
        claim(attempts, result)
    three = claim(attempts, result, revision=2)
    assert len({one.id, two.id, three.id}) == 3
    assert all(state(a)[0] == 'processing' for a in (one, two, three))


def test_profile_mismatch_undoes_vector_and_state_even_if_caller_commits(attempts):
    result = make_result()
    first = claim(attempts, result)
    result.metadata['device'] = 'different'
    with connect_database() as conn:
        with pytest.raises(EmbeddingConflict, match='audio_generation_profile_changed'):
            attempts.complete(conn, first, result)
        assert conn.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone() == (0,)
    assert state(first)[0] == 'processing' and read_embedding(first) is None


@pytest.mark.parametrize('historical', [True, False])
def test_retry_reuses_committed_exact_result_without_inference(attempts, tmp_path, historical):
    path = tmp_path / 'mock.wav'
    path.write_bytes(b'audio')
    result = make_result()
    result.metadata['source_sha256'] = audio_file_sha256(path)
    generator = Mock()
    generator.generation_profile.return_value = prepare_embedding(result)[1]
    generator.generate.return_value = result
    store = AudioEmbeddingStorage(generator)
    if historical:
        with connect_database() as conn:
            saved = attempts.embeddings.save(conn, 'music', 1, result)
    else:
        saved = store.store('music', path, audio_revision=1)
        generator.generate.assert_called_once_with(path, expected_sha256=result.metadata['source_sha256'])
    generator.generate.reset_mock()
    retry = store.store('music', path, audio_revision=1)
    assert retry.id == saved.id and not retry.created
    generator.generate.assert_not_called()

    def change_during_preflight(audio_path):
        audio_path.write_bytes(b'changed during profile verification')
        return prepare_embedding(result)[1]

    generator.generation_profile.side_effect = change_during_preflight
    with pytest.raises(AudioEmbeddingError, match='audio_source_changed'):
        store.store('music', path, audio_revision=1)
    generator.generate.assert_not_called()


def test_store_avoids_duplicate_inference_and_records_failure(attempts, tmp_path):
    path = tmp_path / 'mock.wav'
    path.write_bytes(b'audio')
    result = make_result()
    result.metadata['source_sha256'] = audio_file_sha256(path)
    generator = Mock()
    generator.generation_profile.return_value = prepare_embedding(result)[1]
    store = AudioEmbeddingStorage(generator)
    gate = Barrier(2, timeout=20)

    def generate(audio_path, *, expected_sha256):
        gate.wait()
        gate.wait()
        assert audio_file_sha256(audio_path) != expected_sha256
        raise AudioEmbeddingError('audio_source_changed', audio_path)

    generator.generate.side_effect = generate
    with ThreadPoolExecutor(max_workers=1) as pool:
        active = pool.submit(store.store, 'music', path, audio_revision=1)
        try:
            gate.wait()
            with pytest.raises(ProcessingInProgress):
                store.store('music', path, audio_revision=1)
            path.write_bytes(b'changed while generating')
            gate.wait()
            with pytest.raises(AudioEmbeddingError, match='audio_source_changed'):
                active.result()
        finally:
            gate.abort()
    generator.generate.assert_called_once()
    with connect_database() as conn:
        assert conn.execute('''SELECT state, failure_kind, failure_reason FROM
            ai_embeddings.audio_processing_attempts''').fetchone() == ('failed', 'transient', 'audio_source_changed')
        assert conn.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone() == (0,)


def test_unknown_completion_commit_preserves_ready_and_retry(attempts, tmp_path, monkeypatch):
    path = tmp_path / 'audio'
    path.write_bytes(b'audio')
    result = make_result()
    result.metadata['source_sha256'] = audio_file_sha256(path)
    generator = Mock()
    generator.generation_profile.return_value = prepare_embedding(result)[1]
    generator.generate.return_value = result
    calls = 0

    @contextmanager
    def disconnect_after_commit():
        nonlocal calls
        calls += 1
        with connect_database() as conn:
            yield conn
        if calls == 2:
            raise TimeoutError('commit acknowledgement lost')

    monkeypatch.setattr('app.embedding.storage.connect_database', disconnect_after_commit)
    store = AudioEmbeddingStorage(generator)
    with pytest.raises(TimeoutError, match='commit acknowledgement lost'):
        store.store('music', path, audio_revision=1)
    retry = store.store('music', path, audio_revision=1)
    assert not retry.created
    generator.generate.assert_called_once()
    with connect_database() as conn:
        assert conn.execute('SELECT state, failure_reason FROM ai_embeddings.audio_processing_attempts').fetchall() == [
            ('ready', None)]


def test_failed_save_rolls_back_and_marks_only_current_attempt(attempts, tmp_path, monkeypatch):
    path = tmp_path / 'audio'
    path.write_bytes(b'audio')
    result = make_result()
    result.metadata['source_sha256'] = audio_file_sha256(path)
    generator = Mock()
    generator.generation_profile.return_value = prepare_embedding(result)[1]
    generator.generate.return_value = result
    store = AudioEmbeddingStorage(generator)
    original = store.attempts.embeddings.save

    def fail_after_insert(*args):
        original(*args)
        raise RuntimeError('injected storage failure')

    monkeypatch.setattr(store.attempts.embeddings, 'save', fail_after_insert)
    with pytest.raises(RuntimeError, match='injected storage failure'):
        store.store('music', path, audio_revision=1)
    with connect_database() as conn:
        assert conn.execute('SELECT count(*) FROM ai_embeddings.audio_embeddings').fetchone() == (0,)
        assert conn.execute('SELECT state, failure_reason FROM ai_embeddings.audio_processing_attempts').fetchall() == [
            ('failed', 'audio_storage_failed')]
    monkeypatch.setattr(store.attempts.embeddings, 'save', original)
    assert store.store('music', path, audio_revision=1).created
