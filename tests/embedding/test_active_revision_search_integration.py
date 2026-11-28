"""Backend가 요청한 ACTIVE revision의 저장 및 검색 경계를 실제 DB에서 검증한다."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest

from app.core.database import connect_database
from app.embedding.audio_embedding import PREPROCESSING_VERSION, AudioEmbeddingError
from app.embedding.audio_embedding import audio_file_sha256
from app.repository.embedding_repository import prepare_embedding
from app.embedding.storage import AudioEmbeddingStorage
from app.repository.embedding_repository import (
    AudioEmbeddingRepository,
    CandidateCompatibilityStatus as Status,
    EmbeddingConflict,
)
from test_embedding_database import result as audio_result, text_result


pytest_plugins = ("test_audio_embedding_postgres_validation_integration",)
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AUDIO_POSTGRES_VALIDATION_TESTS") != "1",
    reason="전용 PostgreSQL validation DB 명시적 opt-in 필요",
)


@pytest.fixture
def music_id(connection):
    value = "active-revision-" + uuid.uuid4().hex
    yield value
    with connect_database() as cleanup:
        cleanup.execute(
            "DELETE FROM ai_embeddings.audio_embeddings WHERE music_id = %s", (value,)
        )
        cleanup.execute(
            "DELETE FROM ai_embeddings.audio_processing_attempts WHERE music_id = %s", (value,)
        )
        cleanup.execute(
            "DELETE FROM ai_embeddings.audio_sources WHERE music_id = %s", (value,)
        )
    assert connection.execute(
        """SELECT EXISTS (SELECT FROM ai_embeddings.audio_embeddings WHERE music_id = %s),
                  EXISTS (SELECT FROM ai_embeddings.audio_sources WHERE music_id = %s)""",
        (value, value),
    ).fetchone() == (False, False)


def save_revision(writer, music_id, revision, value, profile=PREPROCESSING_VERSION):
    result = audio_result(value)
    result.metadata["preprocessing_version"] = profile
    return AudioEmbeddingRepository().save(writer, music_id, revision, result)


@pytest.fixture
def first(music_id):
    with connect_database() as writer:
        return save_revision(writer, music_id, 1, 1.0)


def read_exact(saved):
    with connect_database() as reader:
        return AudioEmbeddingRepository().get(
            reader, saved.music_id, saved.audio_revision, saved.generation_profile_sha256
        )


def rank_requested_pair(pair):
    repository = AudioEmbeddingRepository()
    query = text_result()
    with connect_database() as reader:
        reader.execute("SET TRANSACTION READ ONLY")
        checked, = repository.check_candidate_compatibility(reader, [pair], query)
        candidates = [checked.compatible_candidate] if checked.compatible_candidate else []
        return checked.status, repository.rank_candidates(reader, candidates, query)


def assert_ranked_row(ranked, saved):
    row, = ranked
    assert (row.music_id, row.audio_revision, row.embedding_id, row.generation_profile_sha256) == (
        saved.music_id, saved.audio_revision, saved.id, saved.generation_profile_sha256
    )


def assert_request_returns(pair, saved):
    status, ranked = rank_requested_pair(pair)
    assert status == Status.COMPATIBLE
    assert_ranked_row(ranked, saved)


def test_uncommitted_revision_is_invisible_and_commit_preserves_active_request(music_id, first):
    active_pair = (music_id, 1)
    with connect_database() as writer:
        second = save_revision(writer, music_id, 2, -1.0)
        assert read_exact(second) is None
        assert rank_requested_pair((music_id, 2)) == (Status.MISSING_SOURCE, [])
        assert_request_returns(active_pair, first)

    assert read_exact(second)["id"] == second.id
    assert_request_returns(active_pair, first)


def test_inflight_search_keeps_revision_one_across_backend_activation(music_id, first):
    with connect_database() as writer:
        second = save_revision(writer, music_id, 2, -1.0)
        save_revision(writer, music_id, 2, -1.0, PREPROCESSING_VERSION + "-other")

    backend = Mock()
    backend.active_pair.return_value = (music_id, 1)
    phase = Barrier(2, timeout=30)

    def finish_inflight_search():
        repository = AudioEmbeddingRepository()
        query = text_result()
        with connect_database() as reader:
            reader.execute("SET TRANSACTION READ ONLY")
            checked, = repository.check_candidate_compatibility(reader, [backend.active_pair()], query)
            assert checked.status == Status.COMPATIBLE
            phase.wait()  # r1의 정확한 검색 identity를 확보했다.
            phase.wait()  # 새 ACTIVE 요청의 r2 검색이 끝났다.
            return repository.rank_candidates(reader, [checked.compatible_candidate], query)

    with ThreadPoolExecutor(max_workers=1) as pool:
        inflight = pool.submit(finish_inflight_search)
        try:
            phase.wait()
            backend.active_pair.return_value = (music_id, 2)
            assert_request_returns(backend.active_pair(), second)
            phase.wait()
            assert_ranked_row(inflight.result(), first)
        finally:
            phase.abort()


@pytest.mark.parametrize("failure", ["generation", "storage_rollback"])
def test_generation_and_storage_failures_preserve_active_row_and_vector(music_id, first, failure, tmp_path):
    active_pair = (music_id, 1)
    original = read_exact(first)
    if failure == "generation":
        generator = Mock()

        path = tmp_path / 'r2.wav'
        path.write_bytes(b'generation fixture')
        generator.generation_profile.return_value = prepare_embedding(audio_result(-1.0))[1]

        def fail_generation(audio_path, *, expected_sha256):
            assert expected_sha256 == audio_file_sha256(path)
            assert_request_returns(active_pair, first)
            raise AudioEmbeddingError("generation failed", audio_path)

        generator.generate.side_effect = fail_generation
        with pytest.raises(AudioEmbeddingError, match="generation failed"):
            AudioEmbeddingStorage(generator=generator).store(music_id, path, audio_revision=2)
    else:
        with pytest.raises(EmbeddingConflict):
            with connect_database() as writer:
                save_revision(writer, music_id, 2, -1.0)
                save_revision(writer, music_id, 2, 1.0)
        assert writer.closed

    expected = Status.MISSING_EMBEDDING if failure == 'generation' else Status.MISSING_SOURCE
    assert rank_requested_pair((music_id, 2)) == (expected, [])
    assert read_exact(first) == original
    assert_request_returns(active_pair, first)


@pytest.mark.parametrize("failure", ["activation", "notification"])
def test_backend_failure_preserves_committed_revisions(music_id, first, failure):
    original = read_exact(first)
    with connect_database() as writer:
        second = save_revision(writer, music_id, 2, -1.0)

    backend = Mock()
    backend.active_pair = (music_id, 1)
    if failure == "activation":
        backend.commit_active.side_effect = RuntimeError("activation failed")
        with pytest.raises(RuntimeError, match="activation failed"):
            backend.active_pair = backend.commit_active(music_id, 2)
        assert_request_returns(backend.active_pair, first)
    else:
        backend.commit_active.return_value = (music_id, 2)
        backend.active_pair = backend.commit_active(music_id, 2)
        backend.notify_ai.side_effect = TimeoutError("notification failed")
        with pytest.raises(TimeoutError, match="notification failed"):
            backend.notify_ai(backend.active_pair)
        assert_request_returns(backend.active_pair, second)

    assert read_exact(first) == original
    assert_request_returns((music_id, 1), first)
    assert read_exact(second)["id"] == second.id


def test_concurrent_reads_use_exact_revision_and_profile_without_fallback(music_id, first):
    with connect_database() as writer:
        second = save_revision(writer, music_id, 2, -1.0)
        alternate = save_revision(writer, music_id, 2, -1.0, PREPROCESSING_VERSION + "-alternate")
        incompatible = save_revision(writer, music_id, 3, -1.0, PREPROCESSING_VERSION + "-unsupported")

    identities = [first, second, alternate]
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(read_exact, identities))
    assert [(row["id"], row["audio_revision"], row["generation_profile_sha256"]) for row in rows] == [
        (saved.id, saved.audio_revision, saved.generation_profile_sha256) for saved in identities
    ]
    assert len({row["id"] for row in rows}) == 3

    with connect_database() as reader:
        assert AudioEmbeddingRepository().get(
            reader, music_id, 1, alternate.generation_profile_sha256
        ) is None
    assert rank_requested_pair((music_id, 4)) == (Status.MISSING_SOURCE, [])
    assert read_exact(incompatible)["id"] == incompatible.id
    assert rank_requested_pair((music_id, 3)) == (Status.INCOMPATIBLE_PROFILE, [])
