"""Exploratory MSCLAP cosine score mapping, not a suitability probability."""

import math


def normalize_semantic_score(
    cosine_similarity: float,
    *,
    lower: float = 0.0,
    upper: float = 0.4,
) -> float:
    """Map raw cosine to 0–100 using fixed bounds and clipping.

    Defaults are provisional MSCLAP 2023 English-input bounds (candidate A).
    Use raw cosine for ranking: clipping this display score can create ties.
    Do not pass MSCLAP's temperature-scaled similarity to this function.
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
    """Display audio/audio cosine using its theoretical maximum as upper bound.

    Provisional display index, not human-calibrated suitability or probability.
    Audio/audio inputs must not use the default 0.4 audio/text upper bound.
    """
    return normalize_semantic_score(cosine_similarity, lower=lower, upper=upper)
