"""임시 벡터로 DB 순위·후보 필터를 검증하고 테스트 트랜잭션을 롤백한다."""

import os
import uuid

import pytest
import torch

from app.core.database import connect_database
from app.embedding.audio_embedding import AudioEmbeddingResult
from app.matching.audio_search import audio_cosine_similarities
from app.repository.embedding_repository import AudioEmbeddingRepository


pytestmark = pytest.mark.skipif(os.environ.get('RUN_EMBEDDING_DB_TESTS') != '1',
                                reason='Explicit database integration opt-in required')


@pytest.fixture
def connection():
    with connect_database() as connection:
        try:
            yield connection
        finally:
            connection.rollback()


@pytest.fixture
def make_result():
    version = 'search-test-' + uuid.uuid4().hex
    def make(values, file_hash='a' * 64, profile_change=None):
        vector = torch.tensor([values], dtype=torch.float32)
        return AudioEmbeddingResult(vector, {
            'source_sha256': file_hash, 'shape': list(vector.shape), 'dimension': vector.shape[1],
            'model': 'MSCLAP', 'model_version': '2023', 'preprocessing_version': version,
            'packages': {'torch': 'test'}, 'preprocessing': {
                'analysis_duration_seconds': 56, 'chunk_duration_seconds': 7,
                'chunk_count': 8, 'aggregation': 'mean', 'channel_policy': 'mono',
                'profile_change': profile_change,
            },
            'dtype': 'torch.float32', 'device': 'cpu',
        })
    return make


def test_database_rank_matches_torch_and_returns_top_five(connection, make_result):
    query = make_result([1, 0, 0], file_hash='b' * 64)
    values = [[1, 0, 0], [0, 1, 0], [0.8, 0.6, 0], [-1, 0, 0], [0.5, 0.5, 0], [1, 0, 0]]
    prefix = 'test-' + uuid.uuid4().hex + '-'
    repository = AudioEmbeddingRepository()
    for index, vector in enumerate(values):
        repository.save(connection, prefix + str(index), make_result(vector))
    cosines = audio_cosine_similarities(query.vector, torch.tensor(values)).tolist()
    expected = sorted(range(len(values)), key=lambda index: (-cosines[index], prefix + str(index)))[:5]
    found = repository.search(connection, query)
    assert found['candidate_count'] == 6
    assert [row['music_id'] for row in found['results']] == [prefix + str(index) for index in expected]
    assert [row['cosine_similarity'] for row in found['results']] == pytest.approx([cosines[i] for i in expected], abs=1e-6)
    assert len(repository.search(connection, query, top_k=2)['results']) == 2


@pytest.mark.parametrize('mismatch', ['dimension', 'model_version', 'generation_profile', 'package', 'revision'])
def test_incompatible_embedding_excluded_before_distance(connection, make_result, mismatch):
    query = make_result([1, 0, 0], file_hash='b' * 64)
    candidate = make_result([1, 0, 0, 0] if mismatch == 'dimension' else [1, 0, 0])
    if mismatch == 'model_version':
        candidate.metadata['model_version'] = 'other'
    if mismatch == 'generation_profile':
        candidate.metadata['preprocessing']['profile_change'] = 'different'
    if mismatch == 'package':
        candidate.metadata['packages']['torch'] = 'other'
    if mismatch == 'revision':
        candidate.metadata['checkpoint_revision'] = 'other'
    AudioEmbeddingRepository().save(connection, 'test-' + uuid.uuid4().hex, candidate)
    assert AudioEmbeddingRepository().search(connection, query) == {'candidate_count': 0, 'results': []}


def test_all_identical_file_copies_are_excluded(connection, make_result):
    query = make_result([1, 0, 0])
    repository = AudioEmbeddingRepository()
    for _ in range(2):
        repository.save(connection, 'test-' + uuid.uuid4().hex, make_result([1, 0, 0]))
    assert repository.search(connection, query) == {'candidate_count': 0, 'results': []}


def test_fewer_than_five_candidates_are_returned_without_padding(connection, make_result):
    query = make_result([1, 0, 0], file_hash='b' * 64)
    music_id = 'test-' + uuid.uuid4().hex
    repository = AudioEmbeddingRepository()
    repository.save(connection, music_id, make_result([0, 1, 0]))
    found = repository.search(connection, query)
    assert found == {'candidate_count': 1, 'results': [{'music_id': music_id, 'cosine_similarity': 0.0}]}
