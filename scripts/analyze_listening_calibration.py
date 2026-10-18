"""Validate and summarize the frozen calibration listening ratings."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.stats import pearsonr, spearmanr


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/experiments/audio-similarity-calibration/artifacts"
EVALUATORS = ("evaluator-01", "evaluator-02", "evaluator-03")
OUTPUTS = (
    "listening-evaluation-results.csv",
    "listening-evaluation-analysis.json",
    "listening-calibration-scatter.png",
    "listening-calibration-rank-groups.png",
    "listening-calibration-cosine-bins.png",
    "listening-evaluation-joined-evidence.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"비표준 JSON 숫자 {value}: {path}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def corr(x: list[float], y: list[float]) -> dict[str, float | int | None]:
    require(len(x) == len(y), "상관 분석 입력 길이가 다릅니다.")
    if len(x) < 2 or len(set(x)) < 2 or len(set(y)) < 2:
        return {"n": len(x), "pearson_r": None, "spearman_rho": None}
    p = float(pearsonr(x, y).statistic)
    s = float(spearmanr(x, y).statistic)
    return {"n": len(x), "pearson_r": p, "spearman_rho": s}


def describe(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None, "sample_stddev": None}
    return {
        "n": len(values),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "sample_stddev": float(statistics.stdev(values)) if len(values) > 1 else None,
    }


def read_ratings(mapping_pairs: list[dict[str, Any]]) -> dict[str, dict[str, int | None | bool | str]]:
    expected = {pair["pair_id"] for pair in mapping_pairs}
    require(len(expected) == 96, f"frozen mapping pair가 96개가 아닙니다: {len(expected)}")
    responses: dict[str, dict[str, int | None | bool]] = {pair_id: {} for pair_id in expected}
    for evaluator in EVALUATORS:
        path = ARTIFACTS / f"listening-{evaluator}.csv"
        require(path.is_file(), f"평가 CSV 없음: {path.relative_to(ROOT)}")
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == ["evaluator_id", "pair_id", "rating", "unable_to_judge"], f"{path.name}: 예상하지 못한 CSV columns {reader.fieldnames}")
            rows = list(reader)
        require(len(rows) == 96, f"{path.name}: row 수 {len(rows)}, 기대 96")
        seen: set[str] = set()
        for line, row in enumerate(rows, start=2):
            pair_id = row["pair_id"]
            require(row["evaluator_id"] == evaluator, f"{path.name}:{line}: evaluator_id 불일치")
            require(pair_id in expected, f"{path.name}:{line}: mapping에 없는 pair_id {pair_id}")
            require(pair_id not in seen, f"{path.name}:{line}: 중복 pair_id {pair_id}")
            seen.add(pair_id)
            raw_unable = row["unable_to_judge"].strip().lower()
            require(raw_unable in {"true", "false"}, f"{path.name}:{line}: unable_to_judge 값 오류")
            unable = raw_unable == "true"
            raw_rating = row["rating"]
            if unable:
                require(raw_rating == "", f"{path.name}:{line}: 판단 불가와 rating이 함께 입력됨 ({pair_id})")
                rating: int | None = None
            else:
                require(raw_rating in {"1", "2", "3", "4", "5"}, f"{path.name}:{line}: rating은 1~5 또는 판단 불가여야 함 ({pair_id})")
                rating = int(raw_rating.strip())
            responses[pair_id][evaluator] = {
                "rating": rating,
                "unable_to_judge": unable,
                "raw_rating": raw_rating,
                "raw_unable_to_judge": row["unable_to_judge"],
            }
        require(seen == expected, f"{path.name}: mapping과 pair 집합이 다릅니다. missing={sorted(expected-seen)} extra={sorted(seen-expected)}")
    for pair_id in expected:
        require(set(responses[pair_id]) == set(EVALUATORS), f"{pair_id}: evaluator 배정이 3명과 다릅니다.")
    require(sum(len(rows) for rows in responses.values()) == 288, "전체 평가 row가 288개가 아닙니다.")
    return responses


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]], np.ndarray, list[dict[str, str]]]:
    mapping_path = ARTIFACTS / "listening-evaluation-mapping.json"
    assignment_path = ARTIFACTS / "listening-evaluation-assignments.csv"
    cosine_path = ARTIFACTS / "calibration-v1-raw-cosine.json"
    event_path = ROOT / "docs/experiments/audio-similarity-calibration/event-queries.json"
    mapping = load_json(mapping_path)
    cosine = load_json(cosine_path)
    events = load_json(event_path)
    pairs = mapping["pairs"]
    require(len(pairs) == 96 and len({p["pair_id"] for p in pairs}) == 96, "mapping pair가 96개 고유 pair가 아닙니다.")
    expected_evaluations: dict[str, tuple[dict[str, Any], str]] = {}
    for pair in pairs:
        require(pair.get("evaluator_ids") == list(EVALUATORS) and len(pair.get("evaluation_ids", [])) == 3, f"mapping evaluator assignment 오류: {pair['pair_id']}")
        for evaluator, evaluation_id in zip(pair["evaluator_ids"], pair["evaluation_ids"]):
            require(evaluation_id not in expected_evaluations, f"mapping evaluation_id 중복: {evaluation_id}")
            expected_evaluations[evaluation_id] = (pair, evaluator)
    with assignment_path.open("r", encoding="utf-8-sig", newline="") as stream:
        assignment_reader = csv.DictReader(stream)
        assignment_rows = list(assignment_reader)
    require(len(assignment_rows) == 288 and set(assignment_reader.fieldnames or []) >= {"evaluation_id", "evaluator_id", "presentation_order", "query_id", "event_query_text", "sample_id", "playback_path", "playback_completed", "evaluation_time_utc", "evaluation_environment_id"}, "frozen assignment row/schema 오류")
    require(len({row["evaluation_id"] for row in assignment_rows}) == 288 and {row["evaluation_id"] for row in assignment_rows} == set(expected_evaluations), "assignment와 mapping evaluation ID가 다릅니다.")
    for row in assignment_rows:
        pair, evaluator = expected_evaluations[row["evaluation_id"]]
        require(row["evaluator_id"] == evaluator and row["query_id"] == pair["query_id"] and row["event_query_text"] == pair["query_text"] and row["sample_id"] == pair["blind_audio_id"] and row["playback_path"] == pair["playback_path"], f"frozen assignment과 mapping이 다릅니다: {row['evaluation_id']}")
    input_hash_checks = (
        ("raw_cosine_sha256", cosine_path),
        ("event_queries_sha256", event_path),
        ("audio_artifact_sha256", ROOT / mapping["inputs"]["audio_artifact_path"]),
        ("text_artifact_sha256", ROOT / mapping["inputs"]["text_artifact_path"]),
    )
    for field, path in input_hash_checks:
        require(path.is_file(), f"분석 입력 파일 없음: {path.relative_to(ROOT)}")
        require(sha256(path) == mapping["inputs"][field], f"입력 SHA-256 불일치: {path.relative_to(ROOT)}")
    manifest_path = ROOT / mapping["inputs"]["manifest_path"]
    require(manifest_path.is_file() and sha256(manifest_path) == mapping["inputs"]["manifest_sha256"], "canonical manifest identity 불일치")
    audio_evidence_path = ROOT / mapping["inputs"]["audio_evidence_path"]
    text_evidence_path = ROOT / mapping["inputs"]["text_evidence_path"]
    audio_evidence = load_json(audio_evidence_path)
    text_evidence = load_json(text_evidence_path)
    require(audio_evidence["artifact"]["sha256"] == mapping["inputs"]["audio_artifact_sha256"], "Audio evidence와 artifact SHA가 다릅니다.")
    require(audio_evidence["artifact"]["shape"] == [50, 1024], "Audio evidence shape 불일치")
    require(audio_evidence["artifact"]["content_digest"] == mapping["inputs"]["audio_content_digest"], "Audio content digest identity 불일치")
    require(audio_evidence["embedding_output"]["finite"] and audio_evidence["embedding_output"]["zero_vector_count"] == 0, "Audio evidence finite/zero-vector 검증 실패")
    require(audio_evidence["input_identity"]["manifest_bytes_sha256"] == mapping["inputs"]["manifest_sha256"], "Audio evidence manifest identity 불일치")
    require(text_evidence["embedding_output"]["artifact"]["sha256"] == mapping["inputs"]["text_artifact_sha256"], "Text evidence와 artifact SHA가 다릅니다.")
    require(text_evidence["input_identity"]["event_queries_bytes_sha256"] == mapping["inputs"]["event_queries_sha256"], "Text evidence query source identity 불일치")
    require(text_evidence["input_identity"]["active_query_count"] == 16, "Text evidence ACTIVE query count 불일치")
    query_ids = cosine["query_ids"]
    sample_ids = cosine["sample_ids"]
    matrix = np.asarray(cosine["cosine_matrix"], dtype=np.float64)
    require(matrix.shape == (16, 50), f"raw cosine shape 오류: {matrix.shape}")
    require(np.isfinite(matrix).all(), "raw cosine에 NaN/Inf가 있습니다.")
    require(np.all((matrix >= -1.0) & (matrix <= 1.0)), "raw cosine 범위 오류")
    require(cosine["pair_count"] == 800, "raw cosine pair_count가 800이 아닙니다.")
    require(cosine["inputs"]["text"]["artifact_sha256"] == mapping["inputs"]["text_artifact_sha256"], "raw cosine의 Text artifact identity가 mapping과 다릅니다.")
    require(cosine["inputs"]["audio"]["artifact_sha256"] == mapping["inputs"]["audio_artifact_sha256"], "raw cosine의 Audio artifact identity가 mapping과 다릅니다.")
    require(cosine["inputs"]["audio"]["manifest_sha256"] == mapping["inputs"]["manifest_sha256"], "raw cosine의 manifest identity가 mapping과 다릅니다.")
    require(len(set(query_ids)) == 16 and len(set(sample_ids)) == 50, "canonical query/sample ID 중복")
    query_by_id = {q["query_id"]: q for q in events["queries"] if q.get("selection_status") == "active_v1"}
    require(list(query_by_id) == query_ids, "canonical ACTIVE16 query 순서가 raw cosine과 다릅니다.")
    audio_path = ROOT / mapping["inputs"]["audio_artifact_path"]
    text_path = ROOT / mapping["inputs"]["text_artifact_path"]
    with np.load(audio_path, allow_pickle=False) as data:
        audio_embeddings = data["embeddings"]
        audio_ids = data["sample_ids"].tolist()
    with np.load(text_path, allow_pickle=False) as data:
        text_embeddings = data["embeddings"]
        text_ids = data["query_ids"].tolist()
    require(audio_embeddings.shape == (50, 1024) and audio_embeddings.dtype == np.float32 and np.isfinite(audio_embeddings).all(), "canonical Audio Embedding 검증 실패")
    require(text_embeddings.shape == (16, 1024) and text_embeddings.dtype == np.float32 and np.isfinite(text_embeddings).all(), "canonical Text Embedding 검증 실패")
    require(audio_ids == sample_ids and text_ids == query_ids, "Embedding artifact order가 raw cosine과 다릅니다.")
    audio_norms = np.linalg.norm(audio_embeddings, axis=1)
    require(np.all(audio_norms > 0) and np.allclose(audio_norms, 1.0, rtol=0, atol=1e-6), "Audio vector L2 norm 검증 실패")
    evidence_queries = text_evidence["input_identity"]["queries"]
    require([item["query_id"] for item in evidence_queries] == query_ids, "Text evidence query order 불일치")
    recomputed = (text_embeddings / np.linalg.norm(text_embeddings, axis=1, keepdims=True)) @ audio_embeddings.T
    require(np.allclose(recomputed, matrix, rtol=0, atol=1e-7), "NPZ에서 재계산한 cosine이 저장된 raw cosine과 다릅니다.")
    ranking_by_query = {item["query_id"]: item["descending"] for item in cosine["rankings"]}
    require(set(ranking_by_query) == set(query_ids), "raw cosine rankings의 query set 불일치")
    for pair in pairs:
        require(pair["query_id"] in query_ids and pair["sample_id"] in sample_ids, f"mapping의 query/sample ID가 canonical artifact에 없습니다: {pair['pair_id']}")
        qi, si = query_ids.index(pair["query_id"]), sample_ids.index(pair["sample_id"])
        expected_cosine = float(matrix[qi, si])
        require(math.isclose(float(pair["raw_cosine"]), expected_cosine, rel_tol=0, abs_tol=1e-12), f"mapping cosine 불일치: {pair['pair_id']}")
        rank_rows = ranking_by_query[pair["query_id"]]
        rank_matches = [(rank, item) for rank, item in enumerate(rank_rows, start=1) if item["sample_id"] == pair["sample_id"]]
        require(len(rank_matches) == 1 and rank_matches[0][0] == int(pair["rank"]), f"mapping rank 불일치: {pair['pair_id']}")
        require(math.isclose(float(rank_matches[0][1]["raw_cosine"]), expected_cosine, rel_tol=0, abs_tol=1e-12), f"ranking cosine 불일치: {pair['pair_id']}")
        query_text = query_by_id[pair["query_id"]]["msclap_model_input"]["text"]
        require(pair["query_text"] == query_text, f"mapping query text가 canonical query와 다릅니다: {pair['pair_id']}")
    require(all(item["text"] == query_by_id[item["query_id"]]["msclap_model_input"]["text"] for item in evidence_queries), "Text evidence의 canonical query text 불일치")
    require(len({(p["query_id"], p["sample_id"]) for p in pairs}) == 96, "mapping 내 query-song pair 중복")
    playback_files = mapping["playback"]["files"]
    require(len(playback_files) == 40 and mapping["playback"]["duration_seconds"] == 56, "frozen playback inventory/duration 오류")
    require(len({item["blind_audio_id"] for item in playback_files}) == 40, "중복 playback identity")
    for item in playback_files:
        require(len(item.get("sha256", "")) == 64 and all(char in "0123456789abcdef" for char in item["sha256"]), f"playback SHA-256 형식 오류: {item['blind_audio_id']}")
    return mapping, cosine, pairs, query_by_id, matrix, assignment_rows


def reproducibility_provenance() -> dict[str, Any]:
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    require(not status.strip(), "분석은 tracked/untracked 변경이 없는 clean worktree에서 실행해야 합니다.")
    tracked_paths = [
        Path(__file__).resolve(),
        ARTIFACTS / "listening-evaluation-assignments.csv",
        *(ARTIFACTS / f"listening-{evaluator}.csv" for evaluator in EVALUATORS),
        ARTIFACTS / "listening-evaluation-mapping.json",
        ARTIFACTS / "calibration-v1-raw-cosine.json",
        ROOT / "docs/experiments/audio-similarity-calibration/event-queries.json",
        ROOT / "docs/experiments/audio-similarity-calibration/manifest.json",
        ROOT / "docs/experiments/audio-similarity-calibration/audio-embedding-evidence.json",
        ROOT / "docs/experiments/audio-similarity-calibration/text-embedding-evidence.json",
        ROOT / "docs/experiments/audio-similarity-calibration/artifacts/calibration-v1-audio-embeddings.npz",
        ROOT / "docs/experiments/audio-similarity-calibration/artifacts/calibration-v1-text-embeddings.npz",
    ]
    for path in tracked_paths:
        relative = path.relative_to(ROOT).as_posix()
        subprocess.run(["git", "ls-files", "--error-unmatch", "--", relative], cwd=ROOT, check=True, capture_output=True, text=True)
    commit_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    require(len(commit_sha) == 40, "재현 commit SHA가 full SHA-1 형식이 아닙니다.")
    return {
        "analysis_code_and_input_commit_sha": commit_sha,
        "worktree_clean": True,
        "analysis_script_sha256": sha256(Path(__file__).resolve()),
        "reproduction_command": "python -m scripts.analyze_listening_calibration --overwrite",
    }


def write_joined_evidence(
    mapping: dict[str, Any],
    pairs: list[dict[str, Any]],
    assignment_rows: list[dict[str, str]],
    responses: dict[str, dict[str, int | None | bool | str]],
) -> dict[str, Any]:
    pair_by_evaluation = {
        evaluation_id: (pair, evaluator)
        for pair in pairs
        for evaluator, evaluation_id in zip(pair["evaluator_ids"], pair["evaluation_ids"])
    }
    playback_by_blind_id = {item["blind_audio_id"]: item for item in mapping["playback"]["files"]}
    columns = [
        "evaluator_id", "pair_id", "query_id", "sample_id", "evaluation_id",
        "presentation_order", "blind_audio_id", "playback_path", "playback_sha256",
        "playback_duration_seconds", "playback_range_start_seconds",
        "playback_range_end_exclusive_seconds", "playback_completed",
        "evaluation_time_utc", "evaluation_environment_id", "raw_rating", "unable_to_judge",
    ]
    output_path = ARTIFACTS / "listening-evaluation-joined-evidence.csv"
    require(len(assignment_rows) == 288, "derived evidence assignment count must be 288")
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for assignment in assignment_rows:
            evaluation_id = assignment["evaluation_id"]
            pair, evaluator = pair_by_evaluation[evaluation_id]
            require(assignment["evaluator_id"] == evaluator, f"derived evidence evaluator mismatch: {evaluation_id}")
            playback = playback_by_blind_id[pair["blind_audio_id"]]
            require(
                playback["path"] == pair["playback_path"]
                and playback["sample_id"] == pair["sample_id"]
                and playback["prepared_sha256"] == pair["prepared_sha256"],
                f"derived evidence playback identity mismatch: {pair['pair_id']}",
            )
            raw = responses[pair["pair_id"]][evaluator]
            writer.writerow({
                "evaluator_id": evaluator,
                "pair_id": pair["pair_id"],
                "query_id": pair["query_id"],
                "sample_id": pair["sample_id"],
                "evaluation_id": evaluation_id,
                "presentation_order": assignment["presentation_order"],
                "blind_audio_id": pair["blind_audio_id"],
                "playback_path": pair["playback_path"],
                "playback_sha256": playback["sha256"],
                "playback_duration_seconds": mapping["playback"]["duration_seconds"],
                "playback_range_start_seconds": 0,
                "playback_range_end_exclusive_seconds": mapping["playback"]["duration_seconds"],
                "playback_completed": assignment["playback_completed"].strip() or "not_captured",
                "evaluation_time_utc": assignment["evaluation_time_utc"].strip() or "not_captured",
                "evaluation_environment_id": assignment["evaluation_environment_id"].strip() or "not_captured",
                "raw_rating": raw["raw_rating"],
                "unable_to_judge": raw["raw_unable_to_judge"],
            })
    return {
        "path": output_path.relative_to(ROOT).as_posix(),
        "sha256": sha256(output_path),
        "row_count": len(assignment_rows),
        "rating_source": "listening-evaluator-01/02/03.csv; raw values preserved",
        "derived_join": "pair_id + frozen evaluation_id/presentation assignment + frozen playback mapping",
        "not_captured_fields": ["playback_completed", "evaluation_time_utc", "evaluation_environment_id"],
    }


def draw_chart(path: Path, title: str, x_label: str, y_label: str, points: list[tuple[float, float]], *, bars: bool = False, categories: list[str] | None = None, errors: list[float | None] | None = None) -> None:
    width, height = 1200, 760
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font_bold_path = Path("C:/Windows/Fonts/arialbd.ttf")
    font = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
    title_font = ImageFont.truetype(str(font_bold_path), 27) if font_bold_path.exists() else font
    left, top, right, bottom = 110, 100, 1140, 650
    draw.text((left, 28), title, fill="#172554", font=title_font)
    draw.line((left, bottom, right, bottom), fill="#475569", width=2)
    draw.line((left, top, left, bottom), fill="#475569", width=2)
    xmin, xmax = 0.0, 0.60
    if bars:
        xmin, xmax = 0.0, float(max(len(points), 1))
    if not bars:
        for tick in range(0, 7):
            x = tick / 10
            px = left + (x - xmin) / (xmax - xmin) * (right - left)
            draw.line((px, top, px, bottom), fill="#e2e8f0", width=1)
            draw.text((px - 18, bottom + 12), f"{x:.1f}", fill="#334155", font=font)
    for tick in range(1, 6):
        y = float(tick)
        py = bottom - (y - 1) / 4 * (bottom - top)
        draw.line((left, py, right, py), fill="#e2e8f0", width=1)
        draw.text((left - 34, py - 10), f"{y:.0f}", fill="#334155", font=font)
    label_box = draw.textbbox((0, 0), x_label, font=font)
    label_width = label_box[2] - label_box[0]
    draw.text(((left + right - label_width) / 2, bottom + 48), x_label, fill="#334155", font=font)
    draw.text((16, top - 35), y_label, fill="#334155", font=font)
    if bars:
        slot = (right - left) / max(len(points), 1)
        for idx, (x, value) in enumerate(points):
            if not math.isfinite(value):
                continue
            center = left + (idx + 0.5) * slot
            py = bottom - (value - 1) / 4 * (bottom - top)
            draw.rectangle((center - slot * .28, py, center + slot * .28, bottom), fill="#2563eb")
            if errors and errors[idx] is not None:
                e = errors[idx]
                upper = bottom - (min(5, value + e) - 1) / 4 * (bottom - top)
                lower = bottom - (max(1, value - e) - 1) / 4 * (bottom - top)
                draw.line((center, upper, center, lower), fill="#0f172a", width=2)
                draw.line((center - 7, upper, center + 7, upper), fill="#0f172a", width=2)
                draw.line((center - 7, lower, center + 7, lower), fill="#0f172a", width=2)
            label = categories[idx] if categories else str(idx + 1)
            draw.text((center - 52, bottom + 12), label, fill="#334155", font=font)
            draw.text((center - 20, py - 28), f"{value:.2f}", fill="#0f172a", font=font)
    else:
        for x, y in points:
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            px = left + (x - xmin) / (xmax - xmin) * (right - left)
            py = bottom - (y - 1) / 4 * (bottom - top)
            draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill="#2563eb", outline="white", width=1)
        # Use separate point paths for a connected bin-mean chart only.
        if categories:
            ordered = sorted(points)
            coords = [(left + (x - xmin) / (xmax - xmin) * (right - left), bottom - (y - 1) / 4 * (bottom - top)) for x, y in ordered]
            if len(coords) > 1:
                draw.line(coords, fill="#dc2626", width=3)
    image.save(path, format="PNG", optimize=False)


def main() -> int:
    try:
        parser = argparse.ArgumentParser(description="Validate and summarize calibration listening ratings.")
        parser.add_argument("--overwrite", action="store_true", help="기존 분석 산출물을 명시적으로 교체합니다.")
        args = parser.parse_args()
        for filename in OUTPUTS:
            require(args.overwrite or not (ARTIFACTS / filename).exists(), f"출력 파일이 이미 존재합니다. --overwrite가 필요합니다: {filename}")
        mapping, cosine, pairs, query_by_id, matrix, assignment_rows = validate_inputs()
        responses = read_ratings(pairs)
        provenance = reproducibility_provenance()
        joined_evidence = write_joined_evidence(mapping, pairs, assignment_rows, responses)
        pair_rows: list[dict[str, Any]] = []
        for pair in pairs:
            pair_id = pair["pair_id"]
            ratings = {ev: responses[pair_id][ev]["rating"] for ev in EVALUATORS}
            valid = [value for value in ratings.values() if value is not None]
            human_mean = float(statistics.mean(valid)) if valid else None
            pair_rows.append({
                **pair,
                "ratings": ratings,
                "unable": {ev: bool(responses[pair_id][ev]["unable_to_judge"]) for ev in EVALUATORS},
                "valid_rating_count": len(valid),
                "human_mean_rating": human_mean,
                "display_score_candidate": min(100.0, max(0.0, float(pair["raw_cosine"]) / 0.4 * 100.0)),
            })
        analyzable = [row for row in pair_rows if row["human_mean_rating"] is not None]
        evaluator_stats: dict[str, Any] = {}
        for evaluator in EVALUATORS:
            values = [responses[row["pair_id"]][evaluator]["rating"] for row in pairs]
            numeric = [int(value) for value in values if value is not None]
            evaluator_stats[evaluator] = {
                "row_count": len(values),
                "rating_counts": {str(score): sum(value == score for value in values) for score in range(1, 6)},
                "unable_to_judge_count": sum(bool(responses[row["pair_id"]][evaluator]["unable_to_judge"]) for row in pairs),
                "mean": float(statistics.mean(numeric)) if numeric else None,
                "median": float(statistics.median(numeric)) if numeric else None,
            }
        pairwise_agreement: dict[str, Any] = {}
        for i, left in enumerate(EVALUATORS):
            for right in EVALUATORS[i + 1:]:
                shared = [(responses[row["pair_id"]][left]["rating"], responses[row["pair_id"]][right]["rating"]) for row in pairs]
                shared = [(int(a), int(b)) for a, b in shared if a is not None and b is not None]
                pairwise_agreement[f"{left}_vs_{right}"] = corr([a for a, _ in shared], [b for _, b in shared])
        overall_means = [float(row["human_mean_rating"]) for row in analyzable]
        cosines = [float(row["raw_cosine"]) for row in analyzable]
        human_values = [float(row["human_mean_rating"]) for row in analyzable]
        raw_human_corr = corr(cosines, human_values)
        display_values = [float(row["display_score_candidate"]) for row in analyzable]
        display_human_corr = corr(display_values, human_values)
        raw_cosine_overall = describe(matrix.astype(float).ravel().tolist())
        raw_cosine_by_query = {
            query_id: describe(matrix[index].astype(float).tolist())
            for index, query_id in enumerate(cosine["query_ids"])
        }
        rank_exact: dict[str, Any] = {}
        for rank in (1, 2, 25, 26, 49, 50):
            values = [float(row["human_mean_rating"]) for row in analyzable if int(row["rank"]) == rank]
            rank_exact[str(rank)] = describe(values)
        rank_groups = {
            "top_rank_1_2": [float(r["human_mean_rating"]) for r in analyzable if int(r["rank"]) in (1, 2)],
            "middle_rank_25_26": [float(r["human_mean_rating"]) for r in analyzable if int(r["rank"]) in (25, 26)],
            "bottom_rank_49_50": [float(r["human_mean_rating"]) for r in analyzable if int(r["rank"]) in (49, 50)],
        }
        rank_group_stats = {name: describe(values) for name, values in rank_groups.items()}
        rank_cosine_groups = {
            "top_rank_1_2": [float(r["raw_cosine"]) for r in pair_rows if int(r["rank"]) in (1, 2)],
            "middle_rank_25_26": [float(r["raw_cosine"]) for r in pair_rows if int(r["rank"]) in (25, 26)],
            "bottom_rank_49_50": [float(r["raw_cosine"]) for r in pair_rows if int(r["rank"]) in (49, 50)],
        }
        cosine_bounds = [0, .1, .2, .3, .4, .5, math.inf]
        cosine_labels = ["<0.10", "0.10–<0.20", "0.20–<0.30", "0.30–<0.40", "0.40–<0.50", ">=0.50"]
        cosine_bins: list[dict[str, Any]] = []
        for idx, label in enumerate(cosine_labels):
            values = [float(r["human_mean_rating"]) for r in analyzable if cosine_bounds[idx] <= float(r["raw_cosine"]) < cosine_bounds[idx + 1]]
            summary = describe(values)
            cosine_bins.append({"interval": label, **summary, "small_sample_warning": len(values) < 10})
        human_bins = [(1.0, 2.0, "1.0–<2.0"), (2.0, 3.0, "2.0–<3.0"), (3.0, 4.0, "3.0–<4.0"), (4.0, 5.0000000001, "4.0–5.0")]
        rating_bins: list[dict[str, Any]] = []
        for low, high, label in human_bins:
            values = [float(r["raw_cosine"]) for r in analyzable if low <= float(r["human_mean_rating"]) < high]
            rating_bins.append({"interval": label, **describe(values)})
        case_fields = ("pair_id", "query_id", "query_text", "artist", "title", "rank", "raw_cosine", "human_mean_rating")
        concordant_top = [r for r in pair_rows if int(r["rank"]) in (1, 2) and r["human_mean_rating"] is not None and float(r["human_mean_rating"]) >= 4.0]
        concordant_bottom = [r for r in pair_rows if int(r["rank"]) in (49, 50) and r["human_mean_rating"] is not None and float(r["human_mean_rating"]) <= 2.0]
        discordant_top = [r for r in pair_rows if int(r["rank"]) in (1, 2) and r["human_mean_rating"] is not None and float(r["human_mean_rating"]) <= 2.0]
        discordant_bottom = [r for r in pair_rows if int(r["rank"]) in (49, 50) and r["human_mean_rating"] is not None and float(r["human_mean_rating"]) >= 4.0]
        def cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            rows = sorted(rows, key=lambda row: (float(row["raw_cosine"]), row["pair_id"]))
            return [{key: row[key] for key in case_fields} for row in rows[:5]]
        provisional = {
            "name": "기존 임시 선형 clamp A",
            "formula": "clamp(100 * cosine / 0.4, 0, 100)",
            "fixed_bounds": {"lower": 0.0, "upper": 0.4},
            "candidate_independent": True,
            "monotonic_increasing": True,
            "same_cosine_same_score": True,
            "status": "임시 calibration candidate; 최종 확정 아님",
            "reason": "기존 저장소의 임시 기준 A를 비교 기준으로만 적용했다. 이 human calibration cohort만으로 최종 변환을 확정할 수 없고, 별도 validation이 필요하다.",
            "display_score_vs_human_correlation": display_human_corr,
        }
        piecewise = {
            "status": "이번 자료로 anchor를 확정하지 않음",
            "reason": "고정 cosine 구간의 사람 평균은 상위 구간에서 단조 증가하지 않아 단조 piecewise anchor로 바로 쓸 수 없다. 같은 96 pair에 anchor를 맞추면 과적합 위험이 있고 독립 validation cohort도 없어 이번에는 적합하지 않았다.",
            "observed_fixed_bin_means_are_monotonic": all(a["mean"] is None or b["mean"] is None or a["mean"] <= b["mean"] for a, b in zip(cosine_bins, cosine_bins[1:])),
            "anchors": [],
            "candidate_independent_if_later_fixed": True,
            "monotonic_increasing_required": True,
        }
        summary = {
            "schema_version": 2,
            "analysis_version": "listening-calibration-summary-v2",
            "analysis_provenance": provenance,
            "data_scope": {"pair_count": len(pair_rows), "assignment_count": 288, "evaluator_count": 3, "all_three_unable_pair_ids": [r["pair_id"] for r in pair_rows if r["valid_rating_count"] == 0], "analyzed_pair_count": len(analyzable), "calibration_only": True, "independent_validation_performed": False},
            "joined_evidence": joined_evidence,
            "inputs": {"assignment_sha256": sha256(ARTIFACTS / "listening-evaluation-assignments.csv"), "evaluator_csv_sha256": {evaluator: sha256(ARTIFACTS / f"listening-{evaluator}.csv") for evaluator in EVALUATORS}, "mapping_sha256": sha256(ARTIFACTS / "listening-evaluation-mapping.json"), "raw_cosine_sha256": sha256(ARTIFACTS / "calibration-v1-raw-cosine.json"), "event_queries_sha256": sha256(ROOT / "docs/experiments/audio-similarity-calibration/event-queries.json"), "text_artifact_sha256": sha256(ROOT / mapping["inputs"]["text_artifact_path"]), "audio_artifact_sha256": sha256(ROOT / mapping["inputs"]["audio_artifact_path"]), "raw_cosine_execution_commit_sha": cosine["execution_commit_sha"]},
            "evaluator_statistics": evaluator_stats,
            "overall_pair_human_mean_rating": describe(overall_means),
            "evaluator_pairwise_agreement": pairwise_agreement,
            "raw_cosine_vs_human_mean_rating": raw_human_corr,
            "raw_cosine_distribution_overall": raw_cosine_overall,
            "raw_cosine_distribution_by_query": raw_cosine_by_query,
            "raw_cosine_distribution_by_rank_group": {name: describe(values) for name, values in rank_cosine_groups.items()},
            "rank_specific_human_mean_rating": rank_exact,
            "rank_group_human_mean_rating": rank_group_stats,
            "fixed_raw_cosine_bins_human_rating": cosine_bins,
            "human_rating_bins_cosine_distribution": rating_bins,
            "model_human_examples": {"agree_model_top_high_human": cases(concordant_top), "agree_model_bottom_low_human": cases(concordant_bottom), "disagree_model_top_low_human": cases(discordant_top), "disagree_model_bottom_high_human": cases(discordant_bottom)},
            "calibration_candidates": {"recommended_temporary_candidate": provisional, "piecewise_linear_alternative": piecewise, "final_calibration_status": "확정 불가", "limitation": "96개 stratified pair는 같은 query/song을 반복 포함하는 calibration 자료다. 독립 validation 결과 없이 generalization이나 최종 0~100 의미를 주장하지 않는다. Likert 평균은 ordinal label의 기술 통계이며 확률/정밀 효용이 아니다."},
            "illustrative_display_score_examples": [
                {key: row[key] for key in ("pair_id", "query_id", "rank", "raw_cosine", "human_mean_rating", "display_score_candidate")}
                for row in [pair_rows[i] for i in (0, 24, 48, 72, 95)]
            ],
        }
        csv_path = ARTIFACTS / OUTPUTS[0]
        columns = ["pair_id", "query_id", "query_text", "sample_id", "artist", "title", "rank", "raw_cosine", "evaluator_01_rating", "evaluator_01_unable_to_judge", "evaluator_02_rating", "evaluator_02_unable_to_judge", "evaluator_03_rating", "evaluator_03_unable_to_judge", "valid_rating_count", "human_mean_rating", "display_score_candidate"]
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for row in pair_rows:
                output = {key: row.get(key) for key in ("pair_id", "query_id", "query_text", "sample_id", "artist", "title", "rank", "raw_cosine", "valid_rating_count", "human_mean_rating", "display_score_candidate")}
                for idx, evaluator in enumerate(EVALUATORS, start=1):
                    output[f"evaluator_{idx:02d}_rating"] = row["ratings"][evaluator]
                    output[f"evaluator_{idx:02d}_unable_to_judge"] = str(row["unable"][evaluator]).lower()
                writer.writerow(output)
        json_path = ARTIFACTS / OUTPUTS[1]
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        scatter_points = [(float(r["raw_cosine"]), float(r["human_mean_rating"])) for r in analyzable]
        draw_chart(ARTIFACTS / OUTPUTS[2], "Raw cosine vs mean human rating", "Raw cosine", "Mean rating (1–5)", scatter_points)
        rank_order = list(rank_groups)
        rank_values = [rank_group_stats[key]["mean"] for key in rank_order]
        rank_stds = [rank_group_stats[key]["sample_stddev"] for key in rank_order]
        draw_chart(ARTIFACTS / OUTPUTS[3], "Human rating by model rank group", "Rank group", "Mean rating (1–5)", [(float(i), float(v) if v is not None else math.nan) for i, v in enumerate(rank_values)], bars=True, categories=["Top 1–2", "Middle 25–26", "Bottom 49–50"], errors=rank_stds)
        bin_points = []
        for i, item in enumerate(cosine_bins):
            if item["mean"] is not None:
                centers = (.05, .15, .25, .35, .45, .55)
                bin_points.append((centers[i], float(item["mean"])))
        draw_chart(ARTIFACTS / OUTPUTS[4], "Mean human rating by fixed cosine interval", "Raw cosine interval midpoint", "Mean rating (1–5)", bin_points, categories=["fixed bins"])
        print(json.dumps({"outputs": [str((ARTIFACTS / name).relative_to(ROOT)) for name in OUTPUTS], "evaluator_statistics": evaluator_stats, "pair_count": len(pair_rows), "unable_to_judge_count": sum(v["unable_to_judge_count"] for v in evaluator_stats.values()), "overall_human_mean": describe(overall_means), "agreement": pairwise_agreement, "cosine_human": raw_human_corr, "raw_cosine_overall": raw_cosine_overall, "rank_cosine_groups": summary["raw_cosine_distribution_by_rank_group"], "rank_groups": rank_group_stats, "cosine_bins": cosine_bins, "rating_bins": rating_bins, "calibration_status": summary["calibration_candidates"]["final_calibration_status"], "candidate": provisional, "display_score_vs_human": display_human_corr}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        print(f"listening calibration analysis failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
