"""곡 단위 음악 유사도 순위이며 아티스트 집계·행사 종합 적합도와 구분한다."""

from app.matching.normalization import normalize_audio_similarity_score


def rank_audio_candidates(candidates, similarities, *, top_k=5, lower=0.0, upper=1.0):
    """점수 제한으로 순위 정보가 사라지지 않도록 원본 코사인으로 정렬한다.

    Returns:
        list[dict]: 표시 점수와 1부터 시작하는 순위를 포함한 상위 후보.
    Raises:
        ValueError: 후보 ID 중복, 개수 불일치 또는 잘못된 점수 입력인 경우.
    """
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
    # 동점일 때도 입력 목록 순서에 따라 추천 결과가 바뀌지 않도록 ID로 정렬한다.
    rows.sort(key=lambda row: (-row['cosine_similarity'], row['track_id']))
    return [dict(row, rank=index + 1) for index, row in enumerate(rows[:top_k])]


def audio_cosine_similarities(query, candidates):
    """벡터 크기의 영향을 제거한 코사인으로 한 음악과 후보 음악들을 비교한다.

    Args:
        query: 단일 음악의 2차원 임베딩.
        candidates: 같은 차원을 갖는 후보 음악들의 2차원 임베딩.
    Raises:
        ValueError: 형태·차원·값이 잘못되었거나 0벡터가 포함된 경우.
    """
    import torch
    import torch.nn.functional as functional

    for tensor in (query, candidates):
        if tensor.ndim != 2 or tensor.shape[0] < 1 or tensor.shape[1] < 1:
            raise ValueError("Expected nonempty 2D audio embeddings.")
        if not torch.isfinite(tensor).all() or (tensor.norm(dim=1) == 0).any():
            raise ValueError("Audio embeddings must be finite and nonzero.")
    if query.shape[0] != 1 or query.shape[1] != candidates.shape[1]:
        raise ValueError("Expected one query and matching embedding dimensions.")
    # 부동소수점 오차로 이론 범위를 미세하게 벗어날 때 정규화 검사가 실패하지 않도록 한다.
    return (functional.normalize(query, dim=1) @ functional.normalize(candidates, dim=1).T).clamp(-1, 1)[0]
