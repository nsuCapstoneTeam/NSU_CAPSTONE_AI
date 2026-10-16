import copy
import gc
import json
import os
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


@pytest.mark.parametrize("query_id", [None, "", "   "])
def test_active_query_id_must_be_nonblank(document, query_id):
    changed = copy.deepcopy(document)
    row = next(item for item in changed["queries"] if item["selection_status"] == "active_v1")
    row["query_id"] = query_id
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="query_id is missing or blank"):
        tool.select_approved_queries(changed)


@pytest.mark.parametrize(
    "draft_version, missing",
    [("draft-v1", False), (None, False), ("", False), ("   ", False), (None, True)],
)
def test_active_draft_version_must_be_present_and_nonblank(document, draft_version, missing):
    changed = copy.deepcopy(document)
    row = next(item for item in changed["queries"] if item["selection_status"] == "active_v1")
    if missing:
        row["msclap_model_input"].pop("draft_version")
    else:
        row["msclap_model_input"]["draft_version"] = draft_version
    if draft_version == "draft-v1" and not missing:
        assert tool.select_approved_queries(changed)[0]["draft_version"] == "draft-v1"
    else:
        with pytest.raises(tool.CalibrationTextEmbeddingError, match="draft_version.*missing or blank"):
            tool.select_approved_queries(changed)


@pytest.mark.parametrize(
    "field, value",
    [
        ("query_set_version", None),
        ("query_set_version", ""),
        ("query_set_version", "   "),
        ("active_set_version", None),
        ("active_set_version", ""),
        ("active_set_version", "   "),
    ],
)
def test_required_query_set_identity_must_be_nonblank(document, field, value):
    changed = copy.deepcopy(document)
    changed[field] = value
    with pytest.raises(tool.CalibrationTextEmbeddingError, match=f"{field} is missing or blank"):
        tool.query_set_identity(changed)


def test_current_canonical_evidence_has_nonblank_required_identities(tmp_path, monkeypatch):
    evidence_path = DATA_PATH.with_name("text-embedding-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    input_identity = evidence["input_identity"]
    runtime = evidence["model_runtime"]
    artifact = evidence["embedding_output"]["artifact"]

    tool.require_full_git_sha(input_identity["git_commit_sha"])
    tool.require_sha256(input_identity["event_queries_bytes_sha256"], "event-queries.json SHA-256")
    tool.require_sha256(runtime["runner_sha256"], "runner SHA-256")
    tool.require_sha256(runtime["checkpoint_sha256"], "checkpoint SHA-256")
    tool.require_sha256(runtime["gpt2_pretrained_model"]["sha256"], "GPT-2 model weight SHA-256")
    assert runtime["gpt2_pretrained_model"]["resolved_revision"] == tool.TOKENIZER_REVISION
    assert runtime["gpt2_pretrained_model"]["filename"] == tool.GPT2_MODEL_FILENAME
    tool.require_sha256(artifact["sha256"], "artifact SHA-256")
    artifact_relative_path = Path(artifact["path"])
    assert artifact_relative_path == tool.DEFAULT_EMBEDDING_PATH
    repo_root = DATA_PATH.parents[3]
    assert (repo_root / "AGENTS.md").is_file()
    artifact_path = repo_root / artifact_relative_path
    monkeypatch.chdir(tmp_path)
    assert artifact_path.is_file()
    assert tool.sha256_file(artifact_path) == artifact["sha256"]
    assert input_identity["working_tree_clean_before_and_after_inference"] is True
    assert input_identity["active_query_count"] == 16
    assert evidence["preflight_validation"]["status"] == "PASS"
    assert evidence["embedding_output"]["repeat_batch"]["exact_equal"] is True
    for field in ("query_set_version", "active_set_version"):
        tool.require_non_blank_string(input_identity[field], field)
    for field in (
        "package_version", "model_version", "checkpoint_file", "text_model", "python_version",
        "torch_version", "transformers_version", "numpy_version", "dtype", "device",
        "runtime_tokenizer_backend_sha256", "msclap_config_sha256", "model_config_sha256",
    ):
        tool.require_non_blank_string(runtime[field], field)
    assert runtime["tokenizer_snapshot"]["resolved_revision"]
    assert runtime["tokenizer_snapshot"]["snapshot_files_sha256"]["tokenizer.json"]
    assert runtime["msclap_package_source"]["file_count"] > 0
    tool.require_non_blank_string(artifact["path"], "artifact path")
    assert len(input_identity["queries"]) == 16
    for query in input_identity["queries"]:
        for field in ("query_id", "draft_version", "text"):
            tool.require_non_blank_string(query[field], f"{field} in canonical evidence")
    assert evidence["embedding_output"]["shape"] == [16, 1024]
    tool.require_non_blank_string(evidence["embedding_output"]["dtype"], "embedding dtype")
    tool.require_non_blank_string(evidence["embedding_output"]["device"], "embedding device")
    assert evidence["embedding_output"]["all_finite"] is True
    assert evidence["embedding_output"]["zero_vector_count"] == 0
    with np.load(artifact_path, allow_pickle=False) as stored:
        assert stored["embeddings"].shape == (16, 1024)
        assert stored["embeddings"].dtype == np.float32
        assert np.isfinite(stored["embeddings"]).all()
        assert stored["query_ids"].tolist() == [query["query_id"] for query in input_identity["queries"]]


def test_default_embedding_path_is_persistent_calibration_artifact():
    assert tool.DEFAULT_EMBEDDING_PATH == (
        tool.CALIBRATION_ROOT / "artifacts/calibration-v1-text-embeddings.npz"
    )


@pytest.mark.parametrize(
    "validator, value, message",
    [
        (tool.require_non_blank_string, None, "identity is missing or blank"),
        (tool.require_non_blank_string, "   ", "identity is missing or blank"),
        (tool.require_sha256, "", "identity is missing or blank"),
        (tool.require_sha256, "not-a-digest", "not a SHA-256 digest"),
        (lambda value, _field: tool.require_full_git_sha(value), "short-sha", "not a full SHA"),
    ],
)
def test_required_identity_values_fail_when_missing_or_invalid(validator, value, message):
    with pytest.raises(tool.CalibrationTextEmbeddingError, match=message):
        validator(value, "identity")


@pytest.mark.parametrize("field", ["MSCLAP model version", "checkpoint filename", "msclap package version"])
def test_blank_model_and_checkpoint_identity_fails(field):
    with pytest.raises(tool.CalibrationTextEmbeddingError, match=f"{field} is missing or blank"):
        tool.require_non_blank_string("   ", field)


@pytest.mark.parametrize("value", [None, True, 0, -1])
def test_required_positive_integer_identity_fails(value):
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="positive integer"):
        tool.require_positive_integer(value, "configured embedding dimension")


def test_tokenizer_snapshot_identity_records_resolved_commit_and_present_file_hashes(tmp_path):
    revision = "a" * 40
    snapshot = tmp_path / "models--gpt2"
    (snapshot / "refs").mkdir(parents=True)
    (snapshot / "snapshots" / revision).mkdir(parents=True)
    (snapshot / "refs" / "main").write_text(revision, encoding="utf-8")
    (snapshot / "snapshots" / revision / "tokenizer.json").write_bytes(b"tokenizer bytes")
    (snapshot / "snapshots" / revision / "config.json").write_bytes(b"model config")

    result = tool.tokenizer_snapshot_identity("gpt2", tmp_path)

    assert result["resolved_revision"] == revision
    assert result["snapshot_files_sha256"] == {
        "tokenizer.json": tool.sha256_bytes(b"tokenizer bytes"),
        "config.json": tool.sha256_bytes(b"model config"),
    }


def test_gpt2_model_weight_identity_requires_exact_pinned_weight(tmp_path, monkeypatch):
    revision = "a" * 40
    repo_cache = tool._cache_repo_dir(tmp_path, tool.TOKENIZER_REPOSITORY_ID)
    snapshot = repo_cache / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (repo_cache / "refs").mkdir()
    (repo_cache / "refs" / "main").write_text(revision, encoding="utf-8")
    model_bytes = b"pinned GPT-2 model weights"
    (snapshot / tool.GPT2_MODEL_FILENAME).write_bytes(model_bytes)
    monkeypatch.setattr(tool, "TOKENIZER_REVISION", revision)
    monkeypatch.setattr(tool, "GPT2_MODEL_SHA256", tool.sha256_bytes(model_bytes))

    identity = tool.gpt2_model_weight_identity(tmp_path)

    assert identity == {
        "repository_id": "gpt2",
        "resolved_revision": revision,
        "filename": tool.GPT2_MODEL_FILENAME,
        "sha256": tool.sha256_bytes(model_bytes),
    }
    (snapshot / tool.GPT2_MODEL_FILENAME).unlink()
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="pretrained model weights are missing"):
        tool.gpt2_model_weight_identity(tmp_path)
    (snapshot / tool.GPT2_MODEL_FILENAME).write_bytes(model_bytes)
    (snapshot / tool.GPT2_MODEL_FILENAME).write_bytes(b"changed weights")
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="SHA differs"):
        tool.gpt2_model_weight_identity(tmp_path)


def test_tokenizer_snapshot_identity_rejects_mutable_or_missing_revision(tmp_path):
    repo_cache = tmp_path / "models--gpt2"
    (repo_cache / "refs").mkdir(parents=True)
    (repo_cache / "refs" / "main").write_text("main", encoding="utf-8")

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="immutable commit SHA"):
        tool.tokenizer_snapshot_identity("gpt2", tmp_path)


@pytest.mark.parametrize("suffix", ["\n", "\r\n", " "])
@pytest.mark.parametrize("prefix", ["", " "])
def test_tokenizer_snapshot_identity_rejects_revision_whitespace(tmp_path, prefix, suffix):
    revision = "a" * 40
    repo_cache = tmp_path / "models--gpt2"
    (repo_cache / "refs").mkdir(parents=True)
    (repo_cache / "snapshots" / revision).mkdir(parents=True)
    (repo_cache / "refs" / "main").write_text(prefix + revision + suffix, encoding="utf-8")
    (repo_cache / "snapshots" / revision / "tokenizer.json").write_bytes(b"tokenizer bytes")

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="immutable commit SHA"):
        tool.tokenizer_snapshot_identity("gpt2", tmp_path)


def test_cached_main_revision_is_written_without_trailing_whitespace(tmp_path):
    revision = "a" * 40
    tool._write_cached_main_revision(tmp_path, "gpt2", revision)

    ref = tool._cache_repo_dir(tmp_path, "gpt2") / "refs" / "main"
    assert ref.read_bytes() == revision.encode("utf-8")


class FakeTokenizer:
    eos_token_id = 50256
    name_or_path = "gpt2"
    pad_token = "!"
    pad_token_id = 50257
    backend_tokenizer = SimpleNamespace(to_str=lambda: '{"fake":"tokenizer"}')

    def __len__(self):
        return 50257

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


def test_canonical_evidence_is_written_atomically_and_remains_valid(tmp_path):
    path = tmp_path / "evidence.json"
    evidence = {"result_status": "PASS", "artifact": {"sha256": "a" * 64}}

    tool.write_canonical_evidence(path, evidence)

    assert json.loads(path.read_text(encoding="utf-8")) == evidence
    assert list(tmp_path.iterdir()) == [path]


def _prepare_result_pair(tmp_path, values, query_id):
    artifact_path = tmp_path / "vectors.npz"
    evidence_path = tmp_path / "evidence.json"
    embeddings = np.asarray([values], dtype="<f4")
    query_ids = [query_id]
    artifact_temp, artifact_sha = tool.prepare_canonical_artifact(
        artifact_path, embeddings, query_ids, {"exact_equal": True}
    )
    evidence = {
        "input_identity": {"git_commit_sha": "a" * 40, "queries": [{"query_id": query_id}]},
        "embedding_output": {
            "shape": [1, 2],
            "dtype": "torch.float32",
            "artifact": {"path": "vectors.npz", "sha256": artifact_sha},
        },
    }
    evidence_temp = tool.prepare_canonical_evidence(evidence_path, evidence)
    return artifact_path, evidence_path, artifact_temp, evidence_temp, artifact_sha


def _write_old_result_pair(tmp_path):
    artifact_path = tmp_path / "vectors.npz"
    evidence_path = tmp_path / "evidence.json"
    old_embeddings = np.asarray([[1.0, 2.0]], dtype="<f4")
    old_query_ids = ["old-query"]
    digest = tool.write_canonical_artifact(
        artifact_path, old_embeddings, old_query_ids, {"exact_equal": True}
    )
    old_evidence = {
        "input_identity": {"git_commit_sha": "a" * 40, "queries": [{"query_id": "old-query"}]},
        "embedding_output": {
            "shape": [1, 2],
            "dtype": "torch.float32",
            "artifact": {"path": "vectors.npz", "sha256": digest},
        },
    }
    tool.write_canonical_evidence(evidence_path, old_evidence)
    return artifact_path, evidence_path, digest, evidence_path.read_bytes()


def test_transactional_output_pair_publish_succeeds_with_matching_metadata(tmp_path):
    artifact_path, evidence_path, artifact_temp, evidence_temp, expected_sha = _prepare_result_pair(
        tmp_path, [3.0, 4.0], "new-query"
    )

    published_sha = tool.publish_canonical_output_pair(
        artifact_temp, artifact_path, evidence_temp, evidence_path
    )

    assert published_sha == expected_sha
    assert tool.validate_artifact_evidence_pair(artifact_path, evidence_path) == expected_sha
    with np.load(artifact_path, allow_pickle=False) as archive:
        assert archive["query_ids"].tolist() == ["new-query"]


@pytest.mark.parametrize("failed_replace", ["artifact", "evidence"])
def test_transactional_replace_failure_restores_previous_pair(tmp_path, monkeypatch, failed_replace):
    artifact_path, evidence_path, old_sha, old_evidence_bytes = _write_old_result_pair(tmp_path)
    artifact_path, evidence_path, artifact_temp, evidence_temp, _ = _prepare_result_pair(
        tmp_path, [3.0, 4.0], "new-query"
    )
    real_replace = tool.os.replace

    def fail_one_publish(source, destination):
        destination = Path(destination)
        source = Path(source)
        if destination == (artifact_path if failed_replace == "artifact" else evidence_path):
            if source.suffix == ".tmp":
                raise OSError(f"{failed_replace} final replace failed")
        return real_replace(source, destination)

    monkeypatch.setattr(tool.os, "replace", fail_one_publish)
    with pytest.raises(OSError, match="final replace failed"):
        tool.publish_canonical_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path)

    assert tool.validate_artifact_evidence_pair(artifact_path, evidence_path) == old_sha
    assert evidence_path.read_bytes() == old_evidence_bytes


def test_transactional_publish_rollback_failure_is_fatal_and_preserves_backup(tmp_path, monkeypatch):
    artifact_path, evidence_path, _, _ = _write_old_result_pair(tmp_path)
    _, _, artifact_temp, evidence_temp, _ = _prepare_result_pair(
        tmp_path, [3.0, 4.0], "new-query"
    )
    real_replace = tool.os.replace

    def fail_publish_and_rollback(source, destination):
        source = Path(source)
        destination = Path(destination)
        if destination == evidence_path and source.suffix == ".tmp":
            raise OSError("evidence final replace failed")
        if destination == artifact_path and source.suffix == ".rollback":
            raise OSError("artifact rollback failed")
        return real_replace(source, destination)

    monkeypatch.setattr(tool.os, "replace", fail_publish_and_rollback)
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="FATAL:.*rollback failed"):
        tool.publish_canonical_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path)

    assert list(tmp_path.glob("*.rollback")) or list(tmp_path.glob(".*.rollback"))


def test_transactional_pair_rejects_sha_mismatch_without_touching_old_pair(tmp_path):
    artifact_path, evidence_path, old_sha, old_evidence_bytes = _write_old_result_pair(tmp_path)
    artifact_path, evidence_path, artifact_temp, evidence_temp, _ = _prepare_result_pair(
        tmp_path, [3.0, 4.0], "new-query"
    )
    staged = json.loads(evidence_temp.read_text(encoding="utf-8"))
    staged["embedding_output"]["artifact"]["sha256"] = "0" * 64
    evidence_temp.write_text(json.dumps(staged), encoding="utf-8")

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="does not match stored NPZ"):
        tool.publish_canonical_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path)

    assert tool.validate_artifact_evidence_pair(artifact_path, evidence_path) == old_sha
    assert evidence_path.read_bytes() == old_evidence_bytes


@pytest.mark.parametrize("failed_stage", ["artifact", "evidence"])
def test_preparation_failure_does_not_change_existing_pair(tmp_path, monkeypatch, failed_stage):
    artifact_path, evidence_path, old_sha, old_evidence_bytes = _write_old_result_pair(tmp_path)

    if failed_stage == "artifact":
        monkeypatch.setattr(
            tool.np,
            "savez_compressed",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("NPZ temp write failed")),
        )
        with pytest.raises(OSError, match="NPZ temp write failed"):
            tool.prepare_canonical_artifact(
                artifact_path, np.asarray([[3.0, 4.0]], dtype="<f4"), ["new-query"],
                {"exact_equal": True},
            )
    else:
        monkeypatch.setattr(
            tool.tempfile,
            "NamedTemporaryFile",
            lambda **_kwargs: (_ for _ in ()).throw(OSError("evidence temp write failed")),
        )
        with pytest.raises(OSError, match="evidence temp write failed"):
            tool.prepare_canonical_evidence(evidence_path, {"result_status": "PASS"})

    assert tool.validate_artifact_evidence_pair(artifact_path, evidence_path) == old_sha
    assert evidence_path.read_bytes() == old_evidence_bytes


@pytest.mark.parametrize("return_code, should_pass", [(0, True), (1, False)])
def test_execution_commit_must_be_reachable_from_head(monkeypatch, tmp_path, return_code, should_pass):
    monkeypatch.setattr(
        tool.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=return_code),
    )
    if should_pass:
        tool.require_execution_commit_ancestor(tmp_path, "a" * 40, "a" * 40)
    else:
        with pytest.raises(tool.CalibrationTextEmbeddingError, match="not an ancestor"):
            tool.require_execution_commit_ancestor(tmp_path, "a" * 40, "b" * 40)


def test_artifact_evidence_pair_rejects_nonancestor_execution_identity(tmp_path, monkeypatch):
    artifact_path, evidence_path, _, _ = _write_old_result_pair(tmp_path)
    monkeypatch.setattr(tool, "_git_value", lambda *_args: "b" * 40)
    monkeypatch.setattr(
        tool.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="not an ancestor"):
        tool.validate_artifact_evidence_pair(artifact_path, evidence_path, root=tmp_path)


@pytest.mark.parametrize("failure", ["serialization", "write", "replace"])
def test_evidence_write_failure_preserves_existing_file_and_cleans_temp(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "evidence.json"
    original = '{"existing": "canonical evidence"}\n'
    path.write_text(original, encoding="utf-8")

    if failure == "serialization":
        monkeypatch.setattr(tool.json, "dumps", lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("serialize failed")))
    elif failure == "write":
        real_factory = tool.tempfile.NamedTemporaryFile

        def failing_factory(**kwargs):
            stream = real_factory(**kwargs)

            class FailingStream:
                name = stream.name

                def __enter__(self):
                    return self

                def write(self, value):
                    stream.write(value[:5])
                    raise OSError("write failed")

                def __exit__(self, *args):
                    return stream.__exit__(*args)

            return FailingStream()

        monkeypatch.setattr(tool.tempfile, "NamedTemporaryFile", failing_factory)
    else:
        monkeypatch.setattr(tool.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace failed")))

    with pytest.raises((TypeError, OSError)):
        tool.write_canonical_evidence(path, {"result_status": "PASS"})

    assert path.read_text(encoding="utf-8") == original
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("collision", ["evidence_embedding", "evidence_input", "embedding_input", "resolved_alias"])
def test_run_rejects_path_collisions_before_read_or_write(tmp_path, monkeypatch, collision):
    root = tmp_path / "repo"
    query_path = root / "event-queries.json"
    query_path.parent.mkdir(parents=True)
    original = b'{"sentinel": "input must remain untouched"}'
    query_path.write_bytes(original)
    output_dir = root / "tmp"
    output_dir.mkdir()

    if collision == "evidence_embedding":
        evidence_path = output_dir / "same.out"
        embedding_path = output_dir / "same.out"
    elif collision == "evidence_input":
        evidence_path = Path("event-queries.json")
        embedding_path = output_dir / "embedding.npz"
    elif collision == "embedding_input":
        evidence_path = output_dir / "evidence.json"
        embedding_path = Path("event-queries.json")
    else:
        evidence_path = Path("tmp/./same.out")
        embedding_path = output_dir / "same.out"

    monkeypatch.setattr(tool, "INPUT_PATH", Path("event-queries.json"))
    monkeypatch.setattr(tool, "load_calibration_clap_model", lambda: pytest.fail("model must not load on path collision"))

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="path collision"):
        tool.run_experiment(root, evidence_path=evidence_path, embedding_path=embedding_path)

    assert query_path.read_bytes() == original
    assert list(output_dir.iterdir()) == []


def test_resolved_experiment_paths_accept_three_distinct_paths(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    monkeypatch.setattr(tool, "INPUT_PATH", Path("event-queries.json"))

    input_path, evidence_path, embedding_path = tool.resolve_experiment_paths(
        root, Path("tmp/evidence.json"), Path("tmp/embedding.npz")
    )

    assert input_path == (root / "event-queries.json").resolve()
    assert evidence_path == (root / "tmp/evidence.json").resolve()
    assert embedding_path == (root / "tmp/embedding.npz").resolve()
    assert len({input_path, evidence_path, embedding_path}) == 3


@pytest.mark.parametrize(
    "failure, message",
    [
        ("repeat_mismatch", "not bitwise identical"),
        ("artifact_sha_mismatch", "differs from the existing canonical artifact"),
        ("input_hash", "event-queries.json changed"),
        ("dirty_after_inference", "working tree changed during inference"),
        ("evidence_write", "evidence write failed"),
    ],
)
def test_run_hard_gate_failure_prevents_canonical_artifact_and_success_evidence(
    tmp_path, monkeypatch, document, failure, message
):
    root = tmp_path / "repo"
    query_path = root / "event-queries.json"
    query_path.parent.mkdir(parents=True)
    query_path.write_text(json.dumps(document), encoding="utf-8")
    checkpoint_revision = "e" * 40
    checkpoint = (
        root / "cache" / "models--microsoft--msclap" / "snapshots"
        / checkpoint_revision / "CLAP_weights_2023.pth"
    )
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"test checkpoint")
    runner_path = root / "scripts" / "embedding" / "runner.py"
    runner_path.parent.mkdir(parents=True)
    runner_path.write_bytes(b"test runner")
    package_root = root / "site-packages" / "msclap"
    (package_root / "configs").mkdir(parents=True)
    config_path = package_root / "configs" / "config_2023.yml"
    config_path.write_text("text_len: 77\n", encoding="utf-8")
    wrapper_path = package_root / "CLAPWrapper.py"
    wrapper_path.write_text("# fake wrapper\n", encoding="utf-8")
    dirty_marker = root / "during-inference-change.txt"
    artifact_path = root / "tmp" / "canonical.npz"
    evidence_path = root / "evidence.json"
    old_artifact_sha = None
    old_evidence_bytes = None
    if failure in {"repeat_mismatch", "artifact_sha_mismatch"}:
        artifact_path.parent.mkdir(parents=True)
        old_artifact_sha = tool.write_canonical_artifact(
            artifact_path, np.asarray([[1.0, 2.0]], dtype="<f4"), ["old-query"], {"exact_equal": True}
        )
        old_evidence = {
            "input_identity": {"git_commit_sha": "a" * 40, "queries": [{"query_id": "old-query"}]},
            "embedding_output": {
                "shape": [1, 2],
                "dtype": "torch.float32",
                "artifact": {"path": "tmp/canonical.npz", "sha256": old_artifact_sha},
            },
        }
        tool.write_canonical_evidence(evidence_path, old_evidence)
        old_evidence_bytes = evidence_path.read_bytes()

    class FakeWrapper:
        tokenizer = FakeTokenizer()
        args = SimpleNamespace(text_model="gpt2", text_len=77, d_proj=2)
        model_fp = str(checkpoint)
        clap = SimpleNamespace(training=False)
        file_path = str(wrapper_path)

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
            value = (
                float(self.calls)
                if failure == "repeat_mismatch"
                else 3.0
                if failure == "artifact_sha_mismatch"
                else 1.0
            )
            return torch.full((len(texts), 2), value)

    fake_model = FakeClapModel()
    monkeypatch.setattr(tool, "INPUT_PATH", Path("event-queries.json"))
    monkeypatch.setattr(tool, "__file__", str(runner_path))
    monkeypatch.setattr(tool, "load_calibration_clap_model", lambda: fake_model)
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(root / "cache"))
    monkeypatch.setattr(tool, "TOKENIZER_REVISION", "a" * 40)
    monkeypatch.setattr(tool, "RUNTIME_TOKENIZER_SHA256", tool.sha256_bytes(b'{"fake":"tokenizer"}'))
    monkeypatch.setattr(tool, "CHECKPOINT_REVISION", checkpoint_revision)
    monkeypatch.setattr(tool, "CHECKPOINT_SHA256", tool.sha256_file(checkpoint))
    monkeypatch.setattr(tool, "MSCLAP_CONFIG_SHA256", tool.sha256_file(config_path))
    monkeypatch.setattr(tool, "enable_offline_model_loading", lambda: None)
    monkeypatch.setattr(
        tool,
        "validate_prepared_hf_resources",
        lambda: {"pinned": True, "gpt2_model_sha256": tool.GPT2_MODEL_SHA256},
    )
    monkeypatch.setattr(
        tool,
        "tokenizer_snapshot_identity",
        lambda _model, _cache: {
            "repository_id": "gpt2",
            "resolved_revision": "a" * 40,
            "snapshot_files_sha256": {"tokenizer.json": "b" * 64, "config.json": "c" * 64},
        },
    )
    monkeypatch.setattr(tool, "package_source_identity", lambda _root: {"file_count": 1, "sha256": "d" * 64})
    monkeypatch.setattr(
        tool,
        "_git_value",
        lambda _root, *args: (
            " M during-inference-change.txt"
            if args[0] == "status" and dirty_marker.exists()
            else ""
            if args[0] == "status"
            else "a" * 40
        ),
    )
    monkeypatch.setattr(tool, "_run_calibration_validator", lambda _root: "PASS")
    monkeypatch.setattr(tool, "require_execution_commit_ancestor", lambda *_args: None)
    if failure == "evidence_write":
        monkeypatch.setattr(
            tool,
            "prepare_canonical_evidence",
            lambda *_args: (_ for _ in ()).throw(OSError("evidence write failed")),
        )

    expected_error = OSError if failure == "evidence_write" else tool.CalibrationTextEmbeddingError
    with pytest.raises(expected_error, match=message):
        tool.run_experiment(
            root,
            evidence_path=evidence_path,
            embedding_path=artifact_path,
            overwrite=(failure in {"repeat_mismatch", "artifact_sha_mismatch"}),
        )

    assert fake_model.calls == (2 if failure == "repeat_mismatch" else 18)
    if failure in {"repeat_mismatch", "artifact_sha_mismatch"}:
        assert tool.validate_artifact_evidence_pair(artifact_path, evidence_path) == old_artifact_sha
        assert evidence_path.read_bytes() == old_evidence_bytes
    else:
        assert not artifact_path.exists()
        assert not evidence_path.exists()


def test_empty_huggingface_cache_fails_offline_with_bootstrap_instruction(tmp_path, monkeypatch):
    hub_cache = tmp_path / "hub"
    transformers_cache = tmp_path / "transformers"
    monkeypatch.setenv("HF_HUB_CACHE", str(hub_cache))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(transformers_cache))

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="--prepare-resources"):
        tool.validate_prepared_hf_resources()


def test_canonical_run_with_empty_cache_fails_before_model_load(tmp_path, monkeypatch, document):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "event-queries.json").write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(tool, "INPUT_PATH", Path("event-queries.json"))
    monkeypatch.setenv("HF_HUB_CACHE", str(root / "empty-hub-cache"))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(root / "empty-transformers-cache"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setattr(
        tool,
        "_git_value",
        lambda _root, *args: "" if args[0] == "status" else "a" * 40,
    )
    monkeypatch.setattr(tool, "require_execution_commit_ancestor", lambda *_args: None)
    monkeypatch.setattr(tool, "_run_calibration_validator", lambda _root: "PASS")
    monkeypatch.setattr(tool, "load_calibration_clap_model", lambda: pytest.fail("model must not load"))

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="--prepare-resources"):
        tool.run_experiment(
            root,
            evidence_path=root / "evidence.json",
            embedding_path=root / "vectors.npz",
        )

    assert not (root / "evidence.json").exists()
    assert not (root / "vectors.npz").exists()


def test_bootstrap_downloads_only_pinned_identities_then_offline_preflight_passes(tmp_path, monkeypatch):
    import huggingface_hub
    from huggingface_hub.errors import LocalEntryNotFoundError
    from transformers import AutoTokenizer

    tokenizer_revision = "a" * 40
    checkpoint_revision = "b" * 40
    tokenizer_bytes = {"tokenizer.json": b"pinned tokenizer", "config.json": b"pinned config"}
    model_bytes = b"pinned GPT-2 model weights"
    checkpoint_bytes = b"pinned checkpoint"
    tokenizer_hashes = {name: tool.sha256_bytes(content) for name, content in tokenizer_bytes.items()}
    checkpoint_hash = tool.sha256_bytes(checkpoint_bytes)
    model_hash = tool.sha256_bytes(model_bytes)
    hub_cache = tmp_path / "hub"
    transformers_cache = tmp_path / "transformers"
    monkeypatch.setenv("HF_HUB_CACHE", str(hub_cache))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(transformers_cache))
    monkeypatch.setattr(tool, "TOKENIZER_REVISION", tokenizer_revision)
    monkeypatch.setattr(tool, "CHECKPOINT_REVISION", checkpoint_revision)
    monkeypatch.setattr(tool, "TOKENIZER_FILE_SHA256", tokenizer_hashes)
    monkeypatch.setattr(tool, "CHECKPOINT_SHA256", checkpoint_hash)
    monkeypatch.setattr(tool, "GPT2_MODEL_SHA256", model_hash)
    monkeypatch.setattr(tool, "initialize_offline_msclap_text_encoder", lambda: None)
    class FakeTokenizer:
        def __len__(self):
            return 3

        def add_special_tokens(self, _special_tokens):
            return 1

    fake_tokenizer = FakeTokenizer()
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", lambda *_args, **_kwargs: fake_tokenizer)
    real_snapshot_download = huggingface_hub.snapshot_download
    real_hf_hub_download = huggingface_hub.hf_hub_download

    def fake_snapshot_download(*, repo_id, revision, cache_dir, allow_patterns, local_files_only=False):
        assert repo_id == tool.TOKENIZER_REPOSITORY_ID
        if local_files_only:
            assert set(allow_patterns) == set(tokenizer_bytes)
            assert revision == "main"
            return real_snapshot_download(
                repo_id=repo_id,
                revision=revision,
                cache_dir=cache_dir,
                allow_patterns=allow_patterns,
                local_files_only=True,
            )
        assert set(allow_patterns) == {*tokenizer_bytes, tool.GPT2_MODEL_FILENAME}
        assert revision == tokenizer_revision
        snapshot = tool._cache_repo_dir(Path(cache_dir), repo_id) / "snapshots" / revision
        snapshot.mkdir(parents=True)
        for name, content in tokenizer_bytes.items():
            (snapshot / name).write_bytes(content)
        (snapshot / tool.GPT2_MODEL_FILENAME).write_bytes(model_bytes)
        return str(snapshot)

    def fake_checkpoint_download(*, repo_id, filename, revision, cache_dir, local_files_only=False):
        if repo_id == tool.TOKENIZER_REPOSITORY_ID:
            assert filename == tool.GPT2_MODEL_FILENAME
            assert local_files_only is True
            return real_hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                cache_dir=cache_dir,
                local_files_only=True,
            )
        assert repo_id == tool.CHECKPOINT_REPOSITORY_ID
        assert filename == tool.CHECKPOINT_FILENAME
        if local_files_only:
            assert revision == "main"
            return real_hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                cache_dir=cache_dir,
                local_files_only=True,
            )
        assert revision == checkpoint_revision
        path = tool._cache_repo_dir(Path(cache_dir), repo_id) / "snapshots" / revision / filename
        path.parent.mkdir(parents=True)
        path.write_bytes(checkpoint_bytes)
        return str(path)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_checkpoint_download)

    report = tool.prepare_hf_resources()

    assert report["tokenizer_revision"] == tokenizer_revision
    assert report["tokenizer_files_sha256"] == tokenizer_hashes
    assert report["gpt2_model_sha256"] == model_hash
    assert report["gpt2_model_revision"] == tokenizer_revision
    assert report["checkpoint_revision"] == checkpoint_revision
    assert report["checkpoint_sha256"] == checkpoint_hash
    tokenizer_ref = tool._cache_repo_dir(transformers_cache, tool.TOKENIZER_REPOSITORY_ID) / "refs" / "main"
    checkpoint_ref = tool._cache_repo_dir(hub_cache, tool.CHECKPOINT_REPOSITORY_ID) / "refs" / "main"
    assert tokenizer_ref.read_bytes() == tokenizer_revision.encode("utf-8")
    assert checkpoint_ref.read_bytes() == checkpoint_revision.encode("utf-8")
    assert report["offline_local_lookup"] == "passed"
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert tool.validate_prepared_hf_resources(initialize_text_encoder=True) == report

    checkpoint_ref.write_bytes((checkpoint_revision + "\n").encode("utf-8"))
    with pytest.raises(LocalEntryNotFoundError):
        real_hf_hub_download(
            repo_id=tool.CHECKPOINT_REPOSITORY_ID,
            filename=tool.CHECKPOINT_FILENAME,
            revision="main",
            cache_dir=str(hub_cache),
            local_files_only=True,
        )
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="not pinned"):
        tool.validate_prepared_hf_resources()


@pytest.mark.skipif(
    os.environ.get("RUN_CALIBRATION_HF_INTEGRATION") != "1",
    reason="requires network access and downloads pinned GPT-2/MSCLAP resources",
)
def test_fresh_cache_bootstrap_and_offline_msclap_text_encoder_initialization(tmp_path, monkeypatch):
    cache_root = tmp_path / "fresh-hf-cache"
    hub_cache = cache_root / "hub"
    transformers_cache = cache_root / "transformers"
    assert not cache_root.exists()
    monkeypatch.setenv("HF_HOME", str(cache_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub_cache))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(transformers_cache))
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")

    report = tool.prepare_hf_resources()

    assert report["tokenizer_revision"] == tool.TOKENIZER_REVISION
    assert report["gpt2_model_filename"] == "model.safetensors"
    assert report["gpt2_model_sha256"] == tool.GPT2_MODEL_SHA256
    assert report["checkpoint_sha256"] == tool.CHECKPOINT_SHA256
    assert report["offline_local_lookup"] == "passed"
    assert report["offline_msclap_text_encoder_initialization"] == "passed"
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"

    # Exercise Transformers' consumer API directly as well as through MSCLAP's
    # TextEncoder. The explicit pinned revision prevents this check from relying
    # on a mutable Hub ref; both lookups are local-only after bootstrap.
    from transformers import AutoModel, AutoTokenizer

    model = AutoModel.from_pretrained(
        tool.TOKENIZER_REPOSITORY_ID,
        revision=tool.TOKENIZER_REVISION,
        cache_dir=str(transformers_cache),
        local_files_only=True,
    )
    assert model.config.model_type == "gpt2"
    del model
    gc.collect()

    tokenizer = AutoTokenizer.from_pretrained(
        tool.TOKENIZER_REPOSITORY_ID,
        revision=tool.TOKENIZER_REVISION,
        cache_dir=str(transformers_cache),
        local_files_only=True,
    )
    assert len(tokenizer) > 0
    del tokenizer

    assert tool.validate_prepared_hf_resources()["gpt2_model_sha256"] == tool.GPT2_MODEL_SHA256


def test_default_run_refuses_existing_outputs_without_loading_model(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    artifact_path = root / "canonical.npz"
    evidence_path = root / "evidence.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(b"original artifact")
    evidence_path.write_bytes(b"original evidence")
    original_artifact = artifact_path.read_bytes()
    original_evidence = evidence_path.read_bytes()
    monkeypatch.setattr(tool, "load_calibration_clap_model", lambda: pytest.fail("model must not load"))

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="refusing to overwrite"):
        tool.run_experiment(root, evidence_path=evidence_path, embedding_path=artifact_path)

    assert artifact_path.read_bytes() == original_artifact
    assert evidence_path.read_bytes() == original_evidence


def test_explicit_overwrite_accepts_only_a_complete_valid_identical_pair(tmp_path, monkeypatch):
    artifact_path, evidence_path, old_sha, old_evidence_bytes = _write_old_result_pair(tmp_path)
    monkeypatch.setattr(tool, "_git_value", lambda *_args: "a" * 40)
    monkeypatch.setattr(tool, "require_execution_commit_ancestor", lambda *_args: None)

    existing_sha = tool.validate_existing_output_pair(
        evidence_path, artifact_path, overwrite=True, root=tmp_path
    )
    assert existing_sha == old_sha
    tool.require_same_artifact_for_overwrite(existing_sha, old_sha)
    with pytest.raises(tool.CalibrationTextEmbeddingError, match="differs from the existing canonical artifact"):
        tool.require_same_artifact_for_overwrite(existing_sha, "0" * 64)
    assert tool.validate_artifact_evidence_pair(artifact_path, evidence_path) == old_sha
    assert evidence_path.read_bytes() == old_evidence_bytes


def test_overwrite_refuses_incomplete_pair_even_with_explicit_flag(tmp_path):
    artifact_path = tmp_path / "vectors.npz"
    evidence_path = tmp_path / "evidence.json"
    artifact_path.write_bytes(b"artifact without matching evidence")

    with pytest.raises(tool.CalibrationTextEmbeddingError, match="outputs are incomplete"):
        tool.validate_existing_output_pair(
            evidence_path, artifact_path, overwrite=True, root=tmp_path
        )


def test_output_pair_overwrite_flag_defaults_to_false():
    import inspect

    assert inspect.signature(tool.run_experiment).parameters["overwrite"].default is False
