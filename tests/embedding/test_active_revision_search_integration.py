"""ACTIVE 후보 pair가 revision/profile을 정확히 제한하는지 검증한다."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

pytest_plugins = ("test_audio_embedding_postgres_validation_integration",)

from app.core.database import connect_database
from app.embedding.audio_embedding import PREPROCESSING_VERSION
from app.repository.embedding_repository import (
    AudioEmbeddingRepository,
    CandidateCompatibilityStatus,
)
from test_embedding_database import result as audio_result, text_result


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
            "DELETE FROM ai_embeddings.audio_embeddings WHERE music_id = %s",
            (value,),
        )
        cleanup.execute(
            "DELETE FROM ai_embeddings.audio_sources WHERE music_id = %s",
            (value,),
        )


def save_revision(connection, music_id, revision, value, *, preprocessing_version=None):
    result = audio_result(value)
    result.metadata["preprocessing_version"] = (
        PREPROCESSING_VERSION if preprocessing_version is None else preprocessing_version
    )
    return AudioEmbeddingRepository().save(connection, music_id, revision, result)


def rank_requested_pair(music_id, revision):
    repository = AudioEmbeddingRepository()
    query = text_result()
    with connect_database() as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        checked = repository.check_candidate_compatibility(
            connection, [(music_id, revision)], query
        )[0]
        if checked.compatible_candidate is None:
            return checked.status, []
        ranked = repository.rank_candidates(
            connection, [checked.compatible_candidate], query
        )
    return checked.status, ranked


def test_revision_one_remains_searchable_while_revision_two_is_saved_and_committed(
    connection, music_id
):
    repository = AudioEmbeddingRepository()
    with connect_database() as writer:
        first = save_revision(writer, music_id, 1, 1.0)

    backend_active_pair = Mock(return_value=(music_id, 1))
    writer = connect_database()
    try:
        second = save_revision(writer, music_id, 2, -1.0)

        status, ranked = rank_requested_pair(*backend_active_pair())
        assert status == CandidateCompatibilityStatus.COMPATIBLE
        assert [(row.music_id, row.audio_revision) for row in ranked] == [(music_id, 1)]
        assert repository.get(
            writer, music_id, 1, first.generation_profile_sha256
        )["id"] == first.id

        writer.commit()
        status, ranked = rank_requested_pair(*backend_active_pair())
        assert status == CandidateCompatibilityStatus.COMPATIBLE
        assert [(row.music_id, row.audio_revision) for row in ranked] == [(music_id, 1)]
        assert repository.get(
            writer, music_id, 2, second.generation_profile_sha256
        )["id"] == second.id
    finally:
        writer.rollback()
        writer.close()


def test_mocked_backend_activation_switches_search_to_exact_revision_two(
    connection, music_id
):
    with connect_database() as writer:
        save_revision(writer, music_id, 1, 1.0)
        second = save_revision(writer, music_id, 2, -1.0)

    backend = Mock()
    backend.active_pair = (music_id, 1)
    status, ranked = rank_requested_pair(*backend.active_pair)
    assert status == CandidateCompatibilityStatus.COMPATIBLE
    assert [(row.music_id, row.audio_revision) for row in ranked] == [(music_id, 1)]

    backend.confirm_active_revision.return_value = (music_id, 2)
    backend.active_pair = backend.confirm_active_revision(music_id, 2)

    status, ranked = rank_requested_pair(*backend.active_pair)
    assert backend.confirm_active_revision.call_args.args == (music_id, 2)
    assert status == CandidateCompatibilityStatus.COMPATIBLE
    assert [(row.music_id, row.audio_revision) for row in ranked] == [(music_id, 2)]
    assert ranked[0].embedding_id == second.id


@pytest.mark.parametrize("failure", ["generation_rollback", "activation_failure"])
def test_generation_or_activation_failure_preserves_revision_one(
    connection, music_id, failure
):
    with connect_database() as writer:
        first = save_revision(writer, music_id, 1, 1.0)

    backend = Mock()
    backend.active_pair = (music_id, 1)
    if failure == "generation_rollback":
        writer = connect_database()
        try:
            save_revision(writer, music_id, 2, -1.0)
            writer.rollback()
        finally:
            writer.close()
    else:
        with connect_database() as writer:
            save_revision(writer, music_id, 2, -1.0)
        backend.confirm_active_revision.side_effect = RuntimeError(
            "backend activation failed"
        )
        with pytest.raises(RuntimeError, match="backend activation failed"):
            backend.confirm_active_revision(music_id, 2)

    status, ranked = rank_requested_pair(*backend.active_pair)
    assert status == CandidateCompatibilityStatus.COMPATIBLE
    assert [(row.music_id, row.audio_revision) for row in ranked] == [(music_id, 1)]
    with connect_database() as reader:
        exact = AudioEmbeddingRepository().get(
            reader, music_id, 1, first.generation_profile_sha256
        )
        assert exact["id"] == first.id
        if failure == "generation_rollback":
            assert AudioEmbeddingRepository().get(
                reader, music_id, 2, first.generation_profile_sha256
            ) is None


def test_concurrent_reads_use_exact_revision_and_profile_without_fallback(
    connection, music_id
):
    repository = AudioEmbeddingRepository()
    with connect_database() as writer:
        first = save_revision(writer, music_id, 1, 1.0)
        second = save_revision(writer, music_id, 2, -1.0)
        second_profile = save_revision(
            writer,
            music_id,
            2,
            -1.0,
            preprocessing_version=PREPROCESSING_VERSION + "-alternate",
        )
        incompatible = save_revision(
            writer,
            music_id,
            3,
            -1.0,
            preprocessing_version=PREPROCESSING_VERSION + "-unsupported",
        )

    identities = [
        (music_id, 1, first.generation_profile_sha256),
        (music_id, 2, second.generation_profile_sha256),
        (music_id, 2, second_profile.generation_profile_sha256),
    ]

    def read_exact(identity):
        with connect_database() as reader:
            row = repository.get(reader, *identity)
            return (row["id"], row["audio_revision"], row["generation_profile_sha256"])

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(read_exact, identities))

    assert results == [
        (first.id, 1, first.generation_profile_sha256),
        (second.id, 2, second.generation_profile_sha256),
        (second_profile.id, 2, second_profile.generation_profile_sha256),
    ]
    assert len({row[0] for row in results}) == 3

    with connect_database() as reader:
        missing = repository.get(
            reader, music_id, 4, first.generation_profile_sha256
        )
        exact_incompatible = repository.get(
            reader, music_id, 3, incompatible.generation_profile_sha256
        )
    assert missing is None
    assert exact_incompatible["id"] == incompatible.id
    status, ranked = rank_requested_pair(music_id, 3)
    assert status == CandidateCompatibilityStatus.INCOMPATIBLE_PROFILE
    assert ranked == []
    assert incompatible.audio_revision == 3
