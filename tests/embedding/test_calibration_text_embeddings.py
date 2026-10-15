import copy
import json
from pathlib import Path

import pytest
import torch

from scripts.embedding import validate_calibration_text_embeddings as tool


DATA_PATH = Path(__file__).parents[2] / "docs/experiments/audio-similarity-calibration/event-queries.json"


@pytest.fixture
def document():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_selects_exactly_approved_active_sixteen(document):
    selected = tool.select_approved_queries(document)
    assert len(selected) == 16
    assert all(row["text"].strip() for row in selected)
    assert not {"event-10", "event-11", "event-18", "event-19"}.intersection(
        row["query_id"] for row in selected
    )


@pytest.mark.parametrize("active_count", [15, 17])
def test_wrong_active_count_fails(document, active_count):
    changed = copy.deepcopy(document)
    inactive = [row for row in changed["queries"] if row["selection_status"] != "active_v1"]
    if active_count == 15:
        changed["queries"].remove(next(row for row in changed["queries"] if row["selection_status"] == "active_v1"))
    else:
        extra = copy.deepcopy(inactive[0])
        extra["selection_status"] = "active_v1"
        changed["queries"].append(extra)
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="exactly 16"):
        tool.select_approved_queries(changed)


def test_approved_reserve_or_replace_fails(document):
    changed = copy.deepcopy(document)
    inactive = next(row for row in changed["queries"] if row["selection_status"] != "active_v1")
    inactive["msclap_model_input"]["status"] = tool.APPROVED_STATUS
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="RESERVE/REPLACE"):
        tool.select_approved_queries(changed)


@pytest.mark.parametrize("mutation, message", [
    (lambda row: row["msclap_model_input"].update(text="   "), "blank"),
    (lambda row: row["msclap_model_input"].update(status="draft_not_confirmed_model_input"), "not approved"),
    (lambda row: row["msclap_model_input"].update(human_review_status="not_reviewed"), "semantic fidelity"),
    (lambda row: row["structured_interpretation"].update(review_status="not_reviewed"), "Raw-support"),
])
def test_invalid_active_input_fails(document, mutation, message):
    changed = copy.deepcopy(document)
    row = next(item for item in changed["queries"] if item["selection_status"] == "active_v1")
    mutation(row)
    with pytest.raises(tool.CalibrationTextEmbeddingError, match=message):
        tool.select_approved_queries(changed)


class FakeTokenizer:
    eos_token_id = 50256

    def encode_plus(self, *, text, add_special_tokens, max_length, padding, return_tensors):
        assert add_special_tokens is True
        assert padding == "max_length"
        assert return_tensors == "pt"
        count = 78 if "OVER_LIMIT" in text else 77 if "AT_LIMIT" in text else 8
        sequence_length = max_length if count <= max_length else count
        mask = torch.zeros((1, sequence_length), dtype=torch.long)
        mask[:, :count] = 1
        return {
            "input_ids": torch.ones((1, sequence_length), dtype=torch.long),
            "attention_mask": mask,
        }

    def num_special_tokens_to_add(self, pair=False):
        return 0


def test_tokenizer_preflight_counts_gpt_end_marker_without_truncating():
    rows = tool.tokenizer_preflight(
        FakeTokenizer(), [{"query_id": "event-test", "text": "short"}], "gpt2", 77
    )
    assert rows[0]["gpt_end_marker_appended_by_msclap"] == "<|endoftext|>"
    assert rows[0]["token_count_including_model_end_marker_and_tokenizer_specials"] == 8


def test_tokenizer_preflight_accepts_exact_77_token_boundary():
    rows = tool.tokenizer_preflight(
        FakeTokenizer(), [{"query_id": "event-boundary", "text": "AT_LIMIT"}], "gpt2", 77
    )
    assert rows[0]["token_count_including_model_end_marker_and_tokenizer_specials"] == 77


def test_tokenizer_preflight_rejects_over_limit_without_truncation():
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="without truncation"):
        tool.tokenizer_preflight(
            FakeTokenizer(), [{"query_id": "event-long", "text": "OVER_LIMIT"}], "gpt2", 77
        )


@pytest.mark.parametrize("values", [
    [[float("nan"), 1.0]],
    [[float("inf"), 1.0]],
    [[float("-inf"), 1.0]],
    [[0.0, 0.0]],
])
def test_invalid_embedding_vectors_fail(values):
    with pytest.raises(tool.CalibrationTextEmbeddingError):
        tool.validate_embedding_matrix(torch.tensor(values), expected_count=1, expected_dimension=2)


def test_valid_embedding_matrix_and_difference_report():
    value = torch.tensor([[3.0, 4.0]], dtype=torch.float32)
    assert tuple(tool.validate_embedding_matrix(value, 1, 2).shape) == (1, 2)
    result = tool.difference_report(value, value.clone())
    assert result["exact_equal"] is True
    assert result["max_absolute_difference"] == 0.0
