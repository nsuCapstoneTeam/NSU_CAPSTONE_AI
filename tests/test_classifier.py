from unittest.mock import Mock

import pytest
import torch

from app.classification.classifier import AudioClassifier


def make_classifier(scores):
    # CLAP의 외부 모델만 대체하고 분류 계산에는 실제 PyTorch를 사용합니다.
    model = Mock()
    model.similarity.return_value = torch.tensor([scores], requires_grad=True)
    return AudioClassifier(model), model


def test_top_k_keeps_label_score_pairs_in_descending_order():
    classifier, model = make_classifier([0.1, 0.9, 0.4])
    audio = object()
    labels = ["rock", "pop", "hip hop"]

    result = classifier.classify(audio, labels, top_k=2)

    assert [item["label"] for item in result] == ["pop", "hip hop"]
    assert [item["similarity"] for item in result] == pytest.approx([0.9, 0.4])
    model.encode_text.assert_called_once_with(labels)
    model.similarity.assert_called_once_with(audio, model.encode_text.return_value)
    assert all(isinstance(item["similarity"], float) for item in result)
    assert all(isinstance(item["probability"], float) for item in result)


def test_probabilities_are_normalized_over_all_labels_before_top_k():
    classifier, _ = make_classifier([0.0, 0.0, 0.0])

    result = classifier.classify(object(), ["rock", "pop", "EDM"], top_k=2)

    # Top K를 자른 뒤 다시 정규화하면 상대점수의 의미가 달라집니다.
    assert [item["probability"] for item in result] == pytest.approx([1 / 3, 1 / 3])
    assert sum(item["probability"] for item in result) == pytest.approx(2 / 3)


def test_top_k_larger_than_label_count_returns_all_candidates():
    classifier, _ = make_classifier([-2.0, -1.0])

    result = classifier.classify(object(), ["rock", "pop"], top_k=10)

    assert [item["label"] for item in result] == ["pop", "rock"]
    assert sum(item["probability"] for item in result) == pytest.approx(1.0)


def test_zero_top_k_returns_no_candidates():
    classifier, _ = make_classifier([0.2, 0.3])

    assert classifier.classify(object(), ["rock", "pop"], top_k=0) == []
