from unittest.mock import MagicMock, Mock

import pytest
import torch

from app.embedding.audio_embedding import AudioEmbeddingError, AudioEmbeddingResult
from app.matching.database_audio_search import DatabaseAudioSearch
from app.repository.embedding_repository import AudioEmbeddingRepository


@pytest.mark.parametrize('top_k', [0, -1, 101, True, 1.5])
def test_invalid_limit_does_not_generate(top_k):
    generator = Mock()
    with pytest.raises(ValueError):
        DatabaseAudioSearch(generator=generator).search('query', top_k=top_k)
    generator.generate.assert_not_called()


def test_generation_failure_does_not_connect(monkeypatch):
    connect = Mock()
    monkeypatch.setattr('app.matching.database_audio_search.connect_database', connect)
    generator = Mock()
    generator.generate.side_effect = AudioEmbeddingError('audio_embedding_failed', 'query')
    with pytest.raises(AudioEmbeddingError):
        DatabaseAudioSearch(generator=generator).search('query')
    connect.assert_not_called()


@pytest.mark.parametrize('rows,status', [([], 'no_candidates'),
    ([{'music_id': 'music-1', 'cosine_similarity': 0.6427},
      {'music_id': 'music-2', 'cosine_similarity': -0.1}], 'ok')])
def test_readonly_search_and_provisional_scores(monkeypatch, rows, status):
    context = MagicMock()
    monkeypatch.setattr('app.matching.database_audio_search.connect_database', lambda: context)
    generator, repository = Mock(), Mock()
    generator.generate.return_value = AudioEmbeddingResult(torch.ones(1, 4),
        {'source_sha256': 'a' * 64, 'dimension': 4})
    repository.search.return_value = {'candidate_count': len(rows), 'results': rows}
    found = DatabaseAudioSearch(generator, repository).search('query')
    context.__enter__.return_value.execute.assert_called_once_with('SET TRANSACTION READ ONLY')
    generator.generate.assert_called_once_with('query')
    assert found['status'] == status
    assert found['candidate_count'] == len(rows)
    if rows:
        assert [row['rank'] for row in found['results']] == [1, 2]
        assert [row['audio_similarity_score'] for row in found['results']] == pytest.approx([64.27, 0])


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_database_score_is_rejected(value):
    query = AudioEmbeddingResult(torch.ones(1, 2), {
        'source_sha256': 'a' * 64, 'dimension': 2, 'shape': [1, 2],
        'model': 'MSCLAP', 'model_version': '2023', 'preprocessing_version': 'test',
        'packages': {}, 'preprocessing': {},
    })
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchall.return_value = [(1, 'music-1', value)]
    with pytest.raises(ValueError, match='invalid_database_cosine'):
        AudioEmbeddingRepository().search(connection, query)
