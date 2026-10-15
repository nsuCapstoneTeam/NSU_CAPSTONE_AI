import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
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


def test_exact_repeat_is_a_hard_pass_gate():
    repeated = {"exact_equal": True}
    assert tool.experiment_result_status(repeated, [{"exact_equal": True}]) == "PASS"


def test_batch_single_difference_is_recorded_without_repeat_failure():
    repeated = {"exact_equal": True}
    singles = [{"exact_equal": False, "max_absolute_difference": 1e-6}]
    assert tool.experiment_result_status(repeated, singles) == "PASS_WITH_BATCH_SINGLE_DIFFERENCE_RECORDED"


def test_repeated_batch_mismatch_fails_and_cannot_write_canonical_artifact(tmp_path):
    artifact_path = tmp_path / "canonical.npz"
    repeated = {"exact_equal": False}

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="not bitwise identical"):
        tool.experiment_result_status(repeated, [{"exact_equal": False}])
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="not bitwise identical"):
        tool.write_canonical_artifact(
            artifact_path,
            np.ones((1, 2), dtype="<f4"),
            ["event-test"],
            repeated,
        )

    assert not artifact_path.exists()


def test_repeated_batch_outputs_require_valid_vectors_even_when_equal():
    invalid = torch.zeros((1, 2), dtype=torch.float32)
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="zero vector"):
        tool.validate_repeated_batch_outputs(invalid, invalid.clone(), 1, 2)


def test_token_overflow_fails_even_when_repeat_report_is_exact():
    tool.require_exact_batch_repeat({"exact_equal": True})
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="without truncation"):
        tool.tokenizer_preflight(
            FakeTokenizer(), [{"query_id": "event-long", "text": "OVER_LIMIT"}], "gpt2", 77
        )


def test_canonical_artifact_preserves_query_row_order_and_hash(tmp_path):
    path = tmp_path / "vectors.npz"
    query_ids = ["event-02", "event-01"]
    embeddings = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype="<f4")

    digest = tool.write_canonical_artifact(
        path, embeddings, query_ids, {"exact_equal": True}
    )

    with np.load(path, allow_pickle=False) as archive:
        assert archive["query_ids"].tolist() == query_ids
        np.testing.assert_array_equal(archive["embeddings"], embeddings)
    assert digest == tool.sha256_file(path)


@pytest.mark.parametrize(
    "failure, message",
    [
        ("repeat_mismatch", "not bitwise identical"),
        ("input_hash", "event-queries.json changed"),
        ("dirty_after_inference", "working tree changed during inference"),
    ],
)
def test_run_hard_gate_failure_prevents_canonical_artifact_and_success_evidence(
    tmp_path, monkeypatch, document, failure, message
):
    root = tmp_path / "repo"
    query_path = root / "event-queries.json"
    query_path.parent.mkdir(parents=True)
    query_path.write_text(json.dumps(document), encoding="utf-8")
    checkpoint = root / "checkpoint.pth"
    checkpoint.write_bytes(b"test checkpoint")
    dirty_marker = root / "during-inference-change.txt"
    artifact_path = root / "tmp" / "canonical.npz"
    evidence_path = root / "evidence.json"

    class FakeWrapper:
        tokenizer = FakeTokenizer()
        args = SimpleNamespace(text_model="gpt2", text_len=77, d_proj=2)
        model_fp = str(checkpoint)
        clap = SimpleNamespace(training=False)

    class FakeClapModel:
        def __init__(self):
            self.model = FakeWrapper()
            self.calls = 0

        def encode_text(self, texts):
            self.calls += 1
            if self.calls == 1 and failure == "input_hash":
                query_path.write_bytes(b"{}")
            if self.calls == 1 and failure == "dirty_after_inference":
                dirty_marker.write_text("modified", encoding="utf-8")
            value = float(self.calls) if failure == "repeat_mismatch" else 1.0
            return torch.full((len(texts), 2), value)

    fake_model = FakeClapModel()
    monkeypatch.setattr(tool, "INPUT_PATH", Path("event-queries.json"))
    monkeypatch.setattr(tool, "ClapModel", lambda: fake_model)
    monkeypatch.setattr(
        tool,
        "_git_value",
        lambda _root, *args: (
            " M during-inference-change.txt"
            if args[0] == "status" and dirty_marker.exists()
            else ""
            if args[0] == "status"
            else "test-commit"
        ),
    )
    monkeypatch.setattr(tool, "_run_calibration_validator", lambda _root: "PASS")

    with pytest.raises(tool.CalibrationTextEmbeddingError, match=message):
        tool.run_experiment(root, evidence_path=evidence_path, embedding_path=artifact_path)

    assert fake_model.calls == (2 if failure == "repeat_mismatch" else 18)
    assert not artifact_path.exists()
    assert not evidence_path.exists()
