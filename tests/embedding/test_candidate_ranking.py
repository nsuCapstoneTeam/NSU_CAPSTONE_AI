import os
from dataclasses import replace
from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest
import torch

from app.core import migrations
from app.core.database import connect_database
from app.embedding.audio_embedding import AudioEmbeddingResult, PREPROCESSING_VERSION
from app.embedding.text_embedding import TEXT_EMBEDDING_DIMENSION
from app.repository.embedding_repository import AudioEmbeddingRepository, CompatibleCandidate
from tests.embedding.test_audio_identity_migrations import migration_database
from tests.embedding.test_embedding_database import result as audio_result
from tests.embedding.test_text_embedding_storage import make_result


def vector(*values):
    tensor = torch.zeros((1, TEXT_EMBEDDING_DIMENSION), dtype=torch.float32)
    tensor[0, :len(values)] = torch.tensor(values)
    return tensor


def candidate(music_id='music', revision=1):
    return CompatibleCandidate(music_id, revision,
                               '00000000-0000-7000-8000-000000000001', 'a' * 64)


def fake_connection(rows=()):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value = Mock()
    cursor.fetchall.return_value = rows
    return connection, cursor


def test_exact_identity_batch_query_preserves_raw_scores_and_ranks():
    connection, cursor = fake_connection([
        ('music-a', 2, UUID(candidate().embedding_id), 'a' * 64, 0.83),
        ('music-b', 5, UUID(candidate().embedding_id), 'b' * 64, -0.03),
    ])
    inputs = [candidate('music-a', 2), candidate('music-b', 5)]
    results = AudioEmbeddingRepository().rank_candidates(connection, inputs, make_result())
    assert [row.rank for row in results] == [1, 2]
    assert [row.raw_cosine for row in results] == [0.83, -0.03]
    assert results[0].music_id == 'music-a'
    assert results[0].audio_revision == 2
    assert results[0].embedding_id == inputs[0].embedding_id
    assert results[0].generation_profile_sha256 == 'a' * 64
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args.args
    for fragment in ('eligible AS MATERIALIZED', 'e.id = r.id', 'e.music_id = r.music_id',
                     'e.audio_revision = r.audio_revision',
                     'e.generation_profile_sha256 = r.profile_sha', 'WHERE e.dimension = %s',
                     '1 - (embedding <=> %s::vector)', 'SELECT DISTINCT',
                     'ORDER BY raw_cosine DESC, music_id COLLATE "C", audio_revision, id',
                     'LIMIT 100'):
        assert fragment in sql
    assert params[:4] == (inputs[0].embedding_id, 'music-a', 2, 'a' * 64)
    assert params[-2] == TEXT_EMBEDDING_DIMENSION


def test_empty_candidates_do_not_validate_query_or_touch_database():
    connection = Mock()
    assert AudioEmbeddingRepository().rank_candidates(connection, [], object()) == []
    connection.cursor.assert_not_called()


@pytest.mark.parametrize('invalid_vector', [
    vector(0), vector(float('nan')), vector(float('inf')),
    torch.ones((1, TEXT_EMBEDDING_DIMENSION - 1)), torch.ones((2, TEXT_EMBEDDING_DIMENSION)),
])
def test_invalid_query_vector_is_rejected_before_database(invalid_vector):
    connection = Mock()
    with pytest.raises(ValueError):
        AudioEmbeddingRepository().rank_candidates(
            connection, [candidate()], make_result(vector=invalid_vector))
    connection.cursor.assert_not_called()


def test_invalid_query_dimension_is_rejected_before_database():
    connection = Mock()
    with pytest.raises(ValueError, match='invalid_embedding_dimension'):
        AudioEmbeddingRepository().rank_candidates(
            connection, [candidate()], make_result(dimension=512))
    connection.cursor.assert_not_called()


def test_database_failure_propagates():
    connection, cursor = fake_connection()
    cursor.execute.side_effect = RuntimeError('database unavailable')
    with pytest.raises(RuntimeError, match='database unavailable'):
        AudioEmbeddingRepository().rank_candidates(connection, [candidate()], make_result())


@pytest.fixture
def ranking_database(request):
    if os.environ.get('RUN_IDENTITY_MIGRATION_TESTS') != '1':
        pytest.skip('Explicit isolated migration database opt-in required')
    request.getfixturevalue('migration_database')
    assert migrations.apply_migrations() == [
        '0001_audio_embeddings.sql', '0002_text_embeddings.sql', '0003_audio_embedding_identity.sql',
        '0004_audio_processing_attempts.sql']
    with connect_database() as connection:
        yield connection
        connection.rollback()


def store(connection, music_id, values, *, revision=1, device='cpu'):
    metadata = audio_result().metadata.copy()
    metadata.update(preprocessing_version=PREPROCESSING_VERSION, device=device)
    saved = AudioEmbeddingRepository().save(
        connection, music_id, revision, AudioEmbeddingResult(vector(*values), metadata))
    return CompatibleCandidate(music_id, revision, saved.id, saved.generation_profile_sha256)


def test_postgres_cosine_matches_torch_and_preserves_exact_subset(ranking_database):
    connection = ranking_database
    repository = AudioEmbeddingRepository()
    query = make_result(vector=vector(1, 0, 0))
    candidates = [
        store(connection, 'a', (0.5, 0.5, 0), revision=2),
        store(connection, 'b', (0, 1, 0)),
        store(connection, 'c', (-1, 0, 0)),
    ]
    # 요청 밖 최고 cosine, 같은 음악의 다른 revision/profile도 검색하지 않는다.
    store(connection, 'outside', (1, 0, 0))
    store(connection, 'a', (1, 0, 0), revision=3)
    store(connection, 'a', (1, 0, 0), revision=2, device='cuda')
    results = repository.rank_candidates(connection, list(reversed(candidates)), query)
    assert [row.music_id for row in results] == ['a', 'b', 'c']
    assert [row.rank for row in results] == [1, 2, 3]
    expected = [torch.nn.functional.cosine_similarity(query.vector, vector(*values)).item()
                for values in ((0.5, 0.5, 0), (0, 1, 0), (-1, 0, 0))]
    assert [row.raw_cosine for row in results] == pytest.approx(expected, abs=1e-6, rel=0)
    assert [(r.music_id, r.audio_revision, r.embedding_id, r.generation_profile_sha256)
            for r in results] == [(c.music_id, c.audio_revision, c.embedding_id,
                                   c.generation_profile_sha256) for c in candidates]


@pytest.mark.parametrize('count', [1, 30, 100, 105])
def test_postgres_top100_and_deterministic_ties(ranking_database, count):
    connection = ranking_database
    candidates = [store(connection, f'music-{i:03}', (1, 0)) for i in range(count)]
    results = AudioEmbeddingRepository().rank_candidates(
        connection, list(reversed(candidates)), make_result(vector=vector(1, 0)))
    assert len(results) == min(count, 100)
    assert [row.music_id for row in results] == [f'music-{i:03}' for i in range(min(count, 100))]
    assert [row.rank for row in results] == list(range(1, min(count, 100) + 1))
    assert all(row.raw_cosine == pytest.approx(1) for row in results)


def test_postgres_duplicate_and_all_tie_breakers(ranking_database):
    connection = ranking_database
    identities = [store(connection, 'a', (1, 0), revision=2),
                  store(connection, 'a', (1, 0), revision=1),
                  store(connection, 'a', (1, 0), revision=1, device='cuda'),
                  store(connection, 'A', (1, 0))]
    query = make_result(vector=vector(1, 0))
    expected = sorted(identities, key=lambda c: (c.music_id, c.audio_revision, c.embedding_id))
    results = AudioEmbeddingRepository().rank_candidates(connection, identities + identities, query)
    assert [r.embedding_id for r in results] == [c.embedding_id for c in expected]
    assert AudioEmbeddingRepository().rank_candidates(connection, [], query) == []


def test_postgres_top100_selects_highest_cosines_before_limit(ranking_database):
    connection = ranking_database
    # 입력의 마지막 후보가 최고 cosine이고 앞의 다섯 후보가 하위 다섯 개다.
    candidates = [store(connection, f'music-{i:03}', (i + 1, 105 - i)) for i in range(105)]
    query = make_result(vector=vector(1, 0))
    results = AudioEmbeddingRepository().rank_candidates(connection, candidates, query)
    assert [r.music_id for r in results] == [f'music-{i:03}' for i in range(104, 4, -1)]
    assert len(results) == 100
    expected = [torch.nn.functional.cosine_similarity(query.vector, vector(i + 1, 105 - i)).item()
                for i in range(104, 4, -1)]
    assert [r.raw_cosine for r in results] == pytest.approx(expected, abs=1e-6, rel=0)


def test_postgres_stale_identity_and_dimension_do_not_fallback(ranking_database):
    connection = ranking_database
    identity = store(connection, 'music', (1, 0))
    inputs = [replace(identity, music_id='other'), replace(identity, audio_revision=2),
              replace(identity, generation_profile_sha256='f' * 64),
              replace(identity, embedding_id='00000000-0000-7000-8000-000000000001')]
    repository = AudioEmbeddingRepository()
    query = make_result(vector=vector(1, 0))
    assert repository.rank_candidates(connection, inputs, query) == []
    # DB가 허용하는 다른 차원 행은 최종 SQL 경계에서 cosine 연산 전에 제외한다.
    connection.execute('''UPDATE ai_embeddings.audio_embeddings
        SET embedding = '[1,0]'::vector, dimension = 2 WHERE id = %s::uuid''',
                       (identity.embedding_id,))
    assert repository.rank_candidates(connection, [identity], query) == []


def test_postgres_compatible_candidate_output_connects_to_ranking(ranking_database):
    connection = ranking_database
    identity = store(connection, 'music', (1, 0), revision=3)
    query = make_result(vector=vector(1, 0))
    repository = AudioEmbeddingRepository()
    diagnostic = repository.check_candidate_compatibility(connection, [('music', 3)], query)
    assert diagnostic[0].status.value == 'COMPATIBLE'
    results = repository.rank_candidates(connection, [diagnostic[0].compatible_candidate], query)
    assert results[0].embedding_id == identity.embedding_id
