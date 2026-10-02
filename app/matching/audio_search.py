"""Audio-to-audio ranking; no artist aggregation or event suitability scoring."""

from app.matching.normalization import normalize_audio_similarity_score


def rank_audio_candidates(candidates, similarities, *, top_k=5, lower=0.0, upper=1.0):
    """Rank candidates by raw cosine, with stable track-ID tie breaking."""
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    if len(candidates) != len(similarities):
        raise ValueError("Candidate and similarity counts differ.")
    if len({item['track_id'] for item in candidates}) != len(candidates):
        raise ValueError("Candidate track IDs must be unique.")
    rows = []
    for item, value in zip(candidates, similarities):
        cosine = float(value)
        rows.append({"track_id": item['track_id'], "audio_path": item['audio_path'],
                     "cosine_similarity": cosine,
                     "audio_similarity_score": normalize_audio_similarity_score(cosine, lower=lower, upper=upper)})
    rows.sort(key=lambda row: (-row['cosine_similarity'], row['track_id']))
    return [dict(row, rank=index + 1) for index, row in enumerate(rows[:top_k])]


def audio_cosine_similarities(query, candidates):
    """Compare one audio vector against N audio vectors, rejecting bad inputs."""
    import torch
    import torch.nn.functional as functional

    for tensor in (query, candidates):
        if tensor.ndim != 2 or tensor.shape[0] < 1 or tensor.shape[1] < 1:
            raise ValueError("Expected nonempty 2D audio embeddings.")
        if not torch.isfinite(tensor).all() or (tensor.norm(dim=1) == 0).any():
            raise ValueError("Audio embeddings must be finite and nonzero.")
    if query.shape[0] != 1 or query.shape[1] != candidates.shape[1]:
        raise ValueError("Expected one query and matching embedding dimensions.")
    # Roundoff can exceed the theoretical cosine bounds slightly.
    return (functional.normalize(query, dim=1) @ functional.normalize(candidates, dim=1).T).clamp(-1, 1)[0]
