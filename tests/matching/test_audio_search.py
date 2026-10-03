import json

import pytest
import torch

from app.matching.audio_search import audio_cosine_similarities, rank_audio_candidates
from scripts.matching.search_audio import load_candidates


def test_rank_uses_raw_cosine_even_when_display_scores_tie():
    candidates = [{'track_id': i, 'audio_path': str(i)} for i in [3, 2, 1]]
    results = rank_audio_candidates(candidates, [0.5, 0.9, 0.9], top_k=2, upper=0.4)
    assert [r['track_id'] for r in results] == [1, 2]
    assert [r['rank'] for r in results] == [1, 2]
    assert all(r['audio_similarity_score'] == 100 for r in results)


def test_audio_cosine_uses_vector_direction():
    query = torch.tensor([[3., 0.]])
    candidates = torch.tensor([[2., 0.], [0., 4.], [-1., 0.]])
    assert audio_cosine_similarities(query, candidates).tolist() == pytest.approx([1., 0., -1.])


@pytest.mark.parametrize('candidate', [torch.zeros(1, 2), torch.tensor([[float('nan'), 1.]]), torch.ones(1, 3)])
def test_invalid_embeddings_rejected(candidate):
    with pytest.raises(ValueError):
        audio_cosine_similarities(torch.ones(1, 2), candidate)


def test_identical_audio_bytes_excluded_even_with_different_filename(tmp_path):
    query = tmp_path / 'query.wav'
    duplicate = tmp_path / 'copy.wav'
    other = tmp_path / 'other.wav'
    query.write_bytes(b'same'); duplicate.write_bytes(b'same'); other.write_bytes(b'other')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'tracks': [
        {'track_id': 1, 'audio_path': str(duplicate)},
        {'track_id': 2, 'audio_path': str(other)},
    ]}))
    candidates, excluded, _ = load_candidates(manifest, query)
    assert excluded == [1]
    assert [r['track_id'] for r in candidates] == [2]


def test_duplicate_ids_and_count_mismatch_rejected():
    candidate = {'track_id': 1, 'audio_path': 'one.wav'}
    with pytest.raises(ValueError):
        rank_audio_candidates([candidate, candidate], [0.2, 0.3])
    with pytest.raises(ValueError):
        rank_audio_candidates([candidate], [])
