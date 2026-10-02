import math

import pytest

from app.matching.normalization import normalize_audio_similarity_score, normalize_semantic_score


@pytest.mark.parametrize(
    "cosine, expected",
    [(-1.0, 0.0), (-0.1, 0.0), (0.0, 0.0), (0.1, 25.0),
     (0.2, 50.0), (0.3, 75.0), (0.4, 100.0), (1.0, 100.0)],
)
def test_provisional_mapping_and_clipping(cosine, expected):
    assert normalize_semantic_score(cosine) == pytest.approx(expected)


def test_custom_bounds_and_monotonicity():
    assert normalize_semantic_score(0.2, lower=0.1, upper=0.3) == pytest.approx(50.0)
    values = [-1.0, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 1.0]
    scores = [normalize_semantic_score(value) for value in values]
    assert scores == sorted(scores)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1.01, 1.01, 9.7])
def test_invalid_cosine_and_scaled_similarity_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_semantic_score(value)


@pytest.mark.parametrize(
    "lower, upper",
    [(0.4, 0.4), (0.5, 0.4), (-1.1, 0.4), (0.0, 1.1),
     (math.nan, 0.4), (0.0, math.inf)],
)
def test_invalid_bounds_are_rejected(lower, upper):
    with pytest.raises(ValueError):
        normalize_semantic_score(0.2, lower=lower, upper=upper)


@pytest.mark.parametrize("cosine, expected", [(-0.1, 0.0), (0.4, 40.0), (0.94, 94.0), (1.0, 100.0)])
def test_audio_audio_uses_separate_upper_bound(cosine, expected):
    assert normalize_audio_similarity_score(cosine) == pytest.approx(expected)


def test_audio_audio_high_values_remain_distinguishable():
    assert normalize_audio_similarity_score(0.41) < normalize_audio_similarity_score(0.94)
    assert normalize_semantic_score(0.41) == 100.0
    assert normalize_audio_similarity_score(0.4, upper=0.8) == pytest.approx(50.0)
    with pytest.raises(ValueError):
        normalize_audio_similarity_score(math.nan)
