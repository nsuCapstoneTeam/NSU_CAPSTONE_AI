"""원본 코사인의 임시 표시 점수이며 적합 확률이나 종합 매칭 점수가 아니다."""

import math


def normalize_semantic_score(
    cosine_similarity: float,
    *,
    lower: float = 0.0,
    upper: float = 0.4,
) -> float:
    """음악·영어 텍스트 실험의 임시 기준 A로 코사인을 0~100에 매핑한다.

    MSCLAP의 배율 적용 유사도가 아니라 원본 코사인을 입력해야 한다.
    범위 제한은 동점을 만들 수 있으므로 순위 계산에는 원본 코사인을 사용한다.

    Args:
        cosine_similarity: 원본 코사인 유사도(-1~1).
        lower: 0점에 대응하는 고정 하한.
        upper: 100점에 대응하는 고정 상한.
    Returns:
        float: 0~100으로 제한한 표시 점수. 확률을 의미하지 않는다.
    Raises:
        ValueError: 비유한 값, 코사인 범위 밖 입력 또는 잘못된 기준인 경우.
    """
    if not all(math.isfinite(value) for value in (cosine_similarity, lower, upper)):
        raise ValueError("Cosine similarity and score bounds must be finite.")
    if not -1.0 <= cosine_similarity <= 1.0:
        raise ValueError("Cosine similarity must be between -1 and 1.")
    if not -1.0 <= lower < upper <= 1.0:
        raise ValueError("Score bounds must satisfy -1 <= lower < upper <= 1.")
    return max(0.0, min(100.0, 100.0 * (cosine_similarity - lower) / (upper - lower)))


def normalize_audio_similarity_score(
    cosine_similarity: float,
    *,
    lower: float = 0.0,
    upper: float = 1.0,
) -> float:
    """음악 간 비교가 100점에 몰리지 않도록 음악·텍스트 기준과 상한을 분리한다.

    상한 1은 코사인의 이론 최대치이며 사람 평가로 보정한 적합도는 아니다.
    입력 검증과 범위 제한은 공통 선형 변환 함수의 규칙을 따른다.
    """
    return normalize_semantic_score(cosine_similarity, lower=lower, upper=upper)
