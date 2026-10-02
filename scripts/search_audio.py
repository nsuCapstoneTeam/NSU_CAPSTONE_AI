"""Search local candidate audio using an audio file as the query."""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from app.matching.audio_search import audio_cosine_similarities, rank_audio_candidates


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def load_candidates(manifest_path, query_path):
    """Validate local inputs and exclude identical bytes before model loading."""
    if not query_path.is_file():
        raise FileNotFoundError(query_path)
    payload = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    tracks = payload.get('tracks', [])
    if not tracks:
        raise ValueError('Candidate manifest is empty.')
    if any(type(t.get('track_id')) is not int for t in tracks):
        raise ValueError('Candidate track IDs must be integers.')
    if len({t['track_id'] for t in tracks}) != len(tracks):
        raise ValueError('Candidate track IDs must be unique.')
    query_hash = digest(query_path)
    candidates, excluded = [], []
    for track in tracks:
        path = Path(track['audio_path']).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        file_hash = digest(path)
        if file_hash == query_hash:
            excluded.append(track['track_id'])
        else:
            candidates.append(dict(track, audio_path=str(path), sha256=file_hash))
    if not candidates:
        raise ValueError('No candidates remain after identical-file exclusion.')
    return candidates, excluded, query_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True,
                        help='JSON tracks with integer track_id and audio_path; relative paths use current directory')
    parser.add_argument('--output', type=Path, required=True, help='New JSON file, never overwritten')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--seed', type=int, default=43)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error('--top-k must be positive')
    if args.output.exists():
        parser.error('--output already exists; choose a new path')
    candidates, excluded, query_hash = load_candidates(args.manifest, args.audio)
    import torch
    from msclap import CLAP

    print('Loading MSCLAP 2023 CPU...', file=sys.stderr, flush=True)
    model = CLAP(version='2023', use_cuda=False)
    def encode(path, seed):
        random.seed(seed)
        torch.manual_seed(seed)
        return model.get_audio_embeddings([str(path)], resample=True)
    with torch.inference_mode():
        # The same bytes get the same crop regardless of role or filename.
        seed_for = lambda file_hash: args.seed + int(file_hash[:8], 16)
        query = encode(args.audio.resolve(), seed_for(query_hash))
        vectors = []
        for track in candidates:
            print('Embedding candidate', track['track_id'], file=sys.stderr, flush=True)
            vectors.append(encode(track['audio_path'], seed_for(track['sha256'])))
        cosines = audio_cosine_similarities(query, torch.cat(vectors)).cpu().tolist()
    result = {
        'query_audio': str(args.audio.resolve()), 'query_sha256': query_hash,
        'model': 'MSCLAP 2023', 'checkpoint_path': str(getattr(model, 'model_fp', 'unavailable')),
        'seed': args.seed, 'preprocessing': 'resample=True; MSCLAP crop/pad seeded by file SHA-256',
        'comparison': 'audio-audio', 'score_bounds': {'lower': 0.0, 'upper': 1.0, 'status': 'provisional'},
        'candidate_count': len(candidates), 'excluded_identical_track_ids': excluded,
        'candidate_manifest_sha256': digest(args.manifest),
        'embedding_dimension': query.shape[1],
        'results': rank_audio_candidates(candidates, cosines, top_k=args.top_k),
        'warning': 'Audio similarity index, not event suitability or probability. Track-level results, not artist TOP 5.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, ensure_ascii=False, indent=2)
        target.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
