import csv
import json
from pathlib import Path
import tempfile

import pytest
import torch

from scripts.experiments import msclap_korean_vs_english_retrieval as experiment


class FakeTokenizer:
    def encode_plus(self, *, text, **_kwargs):
        count = 80 if "OVERFLOW" in text else len(text.split()) + 1
        return {
            "attention_mask": torch.ones((1, count), dtype=torch.long),
            "input_ids": torch.ones((1, count), dtype=torch.long),
        }


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory(prefix="nsu-msclap-ko-en-test-") as directory:
        yield Path(directory)


def _write_csv(path: Path, rows):
    fields = ["file_name", "audiocap_id", "youtube_id", "start_time", "caption", "kor_Hang_AYA"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_cohort_keeps_order_and_one_to_one_caption_pairs(temp_workspace, monkeypatch):
    metadata = temp_workspace / "metadata.csv"
    audio_root = temp_workspace / "test"
    (audio_root / "audio").mkdir(parents=True)
    rows = [
        {"file_name": "audio/a.wav", "audiocap_id": str(i), "youtube_id": "yt-a", "start_time": "1",
         "caption": f"English caption {i}", "kor_Hang_AYA": f"한국어 캡션 {i}"}
        for i in (1, 2)
    ] + [
        {"file_name": "audio/b.wav", "audiocap_id": "3", "youtube_id": "yt-b", "start_time": "2",
         "caption": "English third", "kor_Hang_AYA": "한국어 셋째"}
    ]
    _write_csv(metadata, rows)
    for name in ("a.wav", "b.wav"):
        (audio_root / "audio" / name).write_bytes(name.encode())
    monkeypatch.setattr(experiment, "inspect_audio_file", lambda path: {
        "status": "usable", "duration_seconds": 10.0, "sample_rate": 32000,
        "channels": 1, "frame_count": 320000, "file_bytes": path.stat().st_size,
        "sha256": experiment.sha256_file(path),
    })

    cohort = experiment.build_cohort(metadata, audio_root, FakeTokenizer())

    assert [row["audiocap_id"] for row in cohort["paired_queries"]] == ["1", "2", "3"]
    assert cohort["counts"]["dataset_rows"] == 3
    assert cohort["counts"]["unique_audio_references"] == 2
    assert cohort["counts"]["usable_audio_count"] == 2
    assert cohort["counts"]["english_query_count"] == cohort["counts"]["korean_query_count"] == 3
    assert cohort["paired_queries"][0]["korean_caption"] == "한국어 캡션 1"
    experiment.validate_frozen_cohort(cohort)


def test_paired_token_overflow_excludes_both_languages_without_truncation(temp_workspace, monkeypatch):
    metadata = temp_workspace / "metadata.csv"
    audio_root = temp_workspace / "test"
    (audio_root / "audio").mkdir(parents=True)
    _write_csv(metadata, [{
        "file_name": "audio/a.wav", "audiocap_id": "1", "youtube_id": "yt", "start_time": "0",
        "caption": "English OVERFLOW caption", "kor_Hang_AYA": "짧은 한국어",
    }])
    audio = audio_root / "audio" / "a.wav"
    audio.write_bytes(b"audio")
    monkeypatch.setattr(experiment, "inspect_audio_file", lambda path: {"status": "usable", "sha256": experiment.sha256_file(path)})

    cohort = experiment.build_cohort(metadata, audio_root, FakeTokenizer())

    assert cohort["counts"]["paired_query_count"] == 0
    assert cohort["counts"]["dataset_caption_token_overflow_counts"]["english"] == 1
    assert cohort["counts"]["dataset_caption_token_overflow_counts"]["korean"] == 0
    assert cohort["counts"]["excluded_caption_rows_by_reason"] == {"paired_token_overflow": 1}
    assert cohort["counts"]["excluded_audio_count"] == 1
    assert cohort["excluded_audio"][0]["status"] == "no_usable_paired_caption"


def test_metadata_path_rejects_traversal():
    with pytest.raises(experiment.ExperimentError, match="unsafe dataset relative path"):
        experiment.safe_dataset_path(Path("/tmp/dataset"), "../outside.wav")


def test_frozen_cohort_rejects_unpaired_or_count_mismatch():
    cohort = {
        "dataset": {"revision": experiment.DATASET_REVISION},
        "counts": {"paired_query_count": 1, "usable_audio_count": 1,
                   "english_query_count": 1, "korean_query_count": 0},
        "paired_queries": [{"audiocap_id": "1", "audio_file_name": "audio/a.wav"}],
        "audio": [{"file_name": "audio/a.wav"}],
    }
    with pytest.raises(experiment.ExperimentError, match="not paired 1:1"):
        experiment.validate_frozen_cohort(cohort)


def test_retrieval_metrics_and_audio_cluster_bootstrap_are_paired():
    records = [
        {"audio_file_name": "a.wav", "english_rank": 1, "korean_rank": 2},
        {"audio_file_name": "a.wav", "english_rank": 3, "korean_rank": 4},
        {"audio_file_name": "b.wav", "english_rank": 5, "korean_rank": 1},
    ]
    metrics = experiment.retrieval_metrics(records, "english_rank")
    assert metrics["query_count"] == 3
    assert metrics["recall_at_1"] == pytest.approx(1 / 3)
    assert metrics["mrr"] == pytest.approx((1 + 1 / 3 + 1 / 5) / 3)
    interval = experiment.paired_bootstrap(records, replicates=25, seed=42)
    assert interval["method"].startswith("paired cluster bootstrap by unique audio_file_name")
    assert set(interval["intervals"]) == {"recall_at_1", "recall_at_5", "recall_at_10", "mrr"}
    assert all(item["observed_delta"] is None for item in interval["intervals"].values())


def test_artifact_bytes_are_stable_and_sorted():
    value = {"z": 1, "a": "한글"}
    assert experiment.canonical_json_bytes(value) == experiment.canonical_json_bytes(json.loads(experiment.canonical_json_bytes(value)))
