"""Phase 2: deterministic FMA sampling and MSCLAP measurement (no score calibration)."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import random
import statistics
from pathlib import Path


GENRES = {
    "Electronic": "전자 음악", "Experimental": "실험 음악",
    "Folk": "포크 음악", "Hip-Hop": "힙합 음악", "Instrumental": "기악 음악",
    "International": "세계 음악", "Pop": "팝 음악", "Rock": "록 음악",
}


def select_tracks(metadata, audio_root, per_genre, seed, split):
    """Read the official three-row, two-level tracks.csv header without pandas."""
    groups = {genre: [] for genre in GENRES}
    with Path(metadata).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        columns = list(zip(next(reader), next(reader)))
        next(reader)  # index name row (track_id)
        required = [("set", "subset"), ("set", "split"), ("track", "genre_top"),
                    ("track", "title"), ("track", "license")]
        indices = {key: columns.index(key) for key in required}
        for row in reader:
            genre = row[indices[("track", "genre_top")]]
            if row[indices[("set", "subset")]] != "small" or genre not in groups:
                continue
            if split != "all" and row[indices[("set", "split")]] != split:
                continue
            track_id = int(row[0])
            filename = f"{track_id:06d}"
            path = Path(audio_root).resolve() / filename[:3] / f"{filename}.mp3"
            if path.is_file():
                groups[genre].append({"track_id": track_id, "genre": genre,
                    "title": row[indices[("track", "title")]],
                    "license": row[indices[("track", "license")]], "audio_path": str(path)})
    rng = random.Random(seed)
    selected = []
    for genre, tracks in groups.items():
        if len(tracks) < per_genre:
            raise ValueError(f"{genre}: need {per_genre} local files, found {len(tracks)}")
        selected.extend(rng.sample(sorted(tracks, key=lambda item: item["track_id"]), per_genre))
    return selected


def prompts():
    return [{"genre": genre, "language": language, "text": text}
            for genre, korean in GENRES.items()
            for language, text in [("en", f"This is a recording of {genre.lower()} music."),
                                   ("ko", f"이 음원은 {korean}입니다.")]]


def check_embedding(tensor, rows, dimension=None):
    import torch
    if tensor.ndim != 2 or tensor.shape[0] != rows or tensor.shape[1] == 0:
        raise ValueError(f"Invalid embedding shape: {tuple(tensor.shape)}")
    if dimension is not None and tensor.shape[1] != dimension:
        raise ValueError("Audio/text embedding dimensions differ")
    if not torch.isfinite(tensor).all() or (tensor.norm(dim=1) == 0).any():
        raise ValueError("Embedding contains non-finite values or zero vectors")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def bounded_text_embeddings(model, texts):
    """Use MSCLAP's public embedding API with explicit tokenizer truncation.

    MSCLAP 1.3.3 pads to text_len but does not truncate longer queries.
    Preserve its special-token handling and record exactly what was retained.
    """
    tokenizer = model.tokenizer
    audit = []

    class BoundedTokenizer:
        def encode_plus(self, *args, **kwargs):
            text = kwargs.get("text", args[0] if args else None)
            original = tokenizer.encode(text, add_special_tokens=kwargs.get("add_special_tokens", True))
            kwargs["truncation"] = True
            result = tokenizer.encode_plus(*args, **kwargs)
            ids = result["input_ids"].reshape(-1).tolist()
            mask = result["attention_mask"].reshape(-1).tolist()
            retained = [token for token, active in zip(ids, mask) if active]
            audit.append({"prompt_index": len(audit), "original_tokens": len(original),
                          "retained_tokens": len(retained),
                          "truncated": len(original) > model.args.text_len,
                          "effective_text": tokenizer.decode(retained, skip_special_tokens=True)})
            return result

    model.tokenizer = BoundedTokenizer()
    try:
        embeddings = model.get_text_embeddings(texts)
    finally:
        model.tokenizer = tokenizer
    return embeddings, {"max_tokens": model.args.text_len, "truncation": True, "prompts": audit}


def measure(manifest, output):
    # Fail before loading/downloading the model if inputs are missing.
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    tracks = payload["tracks"]
    if not tracks:
        raise ValueError("Empty manifest")
    for track in tracks:
        if not Path(track["audio_path"]).is_file():
            raise FileNotFoundError(track["audio_path"])
    import torch
    import torch.nn.functional as functional
    from msclap import CLAP

    seed = payload["seed"]
    random.seed(seed)
    torch.manual_seed(seed)
    model = CLAP(version="2023", use_cuda=False)
    queries = payload["prompts"]
    results, errors, embedding_info = [], [], []
    with torch.inference_mode():
        text, text_preprocessing = bounded_text_embeddings(model, [query["text"] for query in queries])
        truncated = sum(item["truncated"] for item in text_preprocessing["prompts"])
        print(f"Text inputs: {len(queries)}; truncated={truncated}; max_tokens={model.args.text_len}", flush=True)
        check_embedding(text, len(queries))
        for track in tracks:
            print(f"Measuring {track['track_id']} ({track['genre']})", flush=True)
            try:
                # Track-specific seed keeps crop selection stable even if a previous file fails.
                random.seed(seed + track["track_id"])
                torch.manual_seed(seed + track["track_id"])
                audio = model.get_audio_embeddings([track["audio_path"]], resample=True)
                check_embedding(audio, 1, text.shape[1])
                cosine = functional.normalize(audio, dim=1) @ functional.normalize(text, dim=1).T
                scaled = model.compute_similarity(audio, text)
                if scaled.shape != cosine.shape or not torch.isfinite(scaled).all():
                    raise ValueError("Invalid MSCLAP similarity output")
                digest = hashlib.sha256(Path(track["audio_path"]).read_bytes()).hexdigest()
                embedding_info.append({"track_id": track["track_id"], "sha256": digest,
                    "shape": list(audio.shape), "norm": float(audio.norm()), "dtype": str(audio.dtype)})
                for index, query in enumerate(queries):
                    results.append({"track_id": track["track_id"], "genre": track["genre"],
                        "prompt_genre": query["genre"], "language": query["language"],
                        "text": query["text"], "same_genre": track["genre"] == query["genre"],
                        "cosine_similarity": float(cosine[0, index]),
                        "msclap_similarity": float(scaled[0, index])})
            except Exception as error:
                errors.append({"track_id": track["track_id"], "error": f"{type(error).__name__}: {error}"})
    output.mkdir(parents=True, exist_ok=False)
    if results:
        write_csv(output / "similarities.csv", results)
    distributions = []
    for genre in GENRES:
        for language in ("en", "ko"):
            for matching in (True, False):
                values = [r["cosine_similarity"] for r in results
                          if r["genre"] == genre and r["language"] == language and r["same_genre"] == matching]
                if values:
                    distributions.append({"genre": genre, "language": language, "same_genre": matching,
                        "count": len(values), "min": min(values), "max": max(values),
                        "mean": statistics.mean(values), "stdev": statistics.pstdev(values)})
    if distributions:
        write_csv(output / "distributions.csv", distributions)
    report = {"model": "MSCLAP", "version": "2023", "device": "cpu", "seed": seed,
        "packages": {name: importlib.metadata.version(name) for name in ("msclap", "torch", "torchaudio", "transformers")},
        "manifest": payload, "text_shape": list(text.shape), "text_preprocessing": text_preprocessing,
        "audio_embeddings": embedding_info,
        "checkpoint_path": str(getattr(model, "model_fp", "unavailable")),
        "preprocessing": "MSCLAP default crop/pad, resample=True; seeded per track",
        "successful_tracks": len(embedding_info), "errors": errors,
        "warning": "Genre agreement is a diagnostic proxy, not event suitability or a calibrated 0-100 score."}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved results: {output}; successful={len(embedding_info)}, failed={len(errors)}")
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Select local FMA files; no model required")
    prepare.add_argument("--metadata", type=Path, required=True)
    prepare.add_argument("--audio-root", type=Path, required=True)
    prepare.add_argument("--per-genre", type=int, default=2)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--split", choices=("training", "validation", "test", "all"), default="test")
    prepare.add_argument("--manifest", type=Path, required=True)
    run = commands.add_parser("run", help="Measure embeddings and raw similarities on CPU")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.per_genre < 1:
            parser.error("--per-genre must be positive")
        tracks = select_tracks(args.metadata, args.audio_root, args.per_genre, args.seed, args.split)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        with args.manifest.open("x", encoding="utf-8") as target:
            json.dump({"source": "https://github.com/mdeff/fma", "subset": "small",
                "split": args.split, "seed": args.seed, "tracks": tracks, "prompts": prompts()},
                target, ensure_ascii=False, indent=2)
        print(f"Selected {len(tracks)} tracks: {args.manifest}")
        return 0
    if args.output.exists():
        parser.error("--output must be a new directory")
    return measure(args.manifest, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
