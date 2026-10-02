"""Measure unique audio/audio pairs from a local manifest on CPU."""

import argparse
import hashlib
import importlib.metadata
import json
import random
from pathlib import Path

from scripts.validate_fma import check_embedding, write_csv
from app.matching.normalization import normalize_semantic_score, normalize_audio_similarity_score

def measure(manifest_path, output, seed):
    tracks = json.loads(manifest_path.read_text(encoding='utf-8-sig'))['tracks']
    if len(tracks) < 2 or len({t['track_id'] for t in tracks}) != len(tracks):
        raise ValueError('Need at least two tracks with unique IDs.')
    for track in tracks:
        if not Path(track['audio_path']).is_file():
            raise FileNotFoundError(track['audio_path'])
    import torch
    from msclap import CLAP
    output.mkdir(parents=True, exist_ok=False)
    model = CLAP(version='2023', use_cuda=False)
    vectors, hashes = [], []
    with torch.inference_mode():
        for track in tracks:
            track_seed = seed + track['track_id']
            random.seed(track_seed)
            torch.manual_seed(track_seed)
            audio = Path(track['audio_path'])
            embedding = model.get_audio_embeddings([str(audio)], resample=True)
            check_embedding(embedding, 1, vectors[0].shape[1] if vectors else None)
            vectors.append(embedding)
            hashes.append({'track_id': track['track_id'], 'sha256': hashlib.sha256(audio.read_bytes()).hexdigest()})
            print('Embedded', track['track_id'], flush=True)
        matrix = torch.cat(vectors)
        normalized = torch.nn.functional.normalize(matrix, dim=1)
        similarities = (normalized @ normalized.T).cpu()
    rows = []
    for i, first in enumerate(tracks):
        for j in range(i + 1, len(tracks)):
            second = tracks[j]
            value = max(-1.0, min(1.0, float(similarities[i, j])))
            rows.append({'track_id_a': first['track_id'], 'track_id_b': second['track_id'],
                         'genre_a': first['genre'], 'genre_b': second['genre'],
                         'same_genre': first['genre'] == second['genre'],
                         'cosine_similarity': value,
                         'provisional_audio_text_score': normalize_semantic_score(value),
                         'audio_similarity_score': normalize_audio_similarity_score(value)})
    write_csv(output / 'similarities.csv', rows)
    def stats(values):
        if not values:
            return {'count': 0}
        values = sorted(values)
        def quantile(p):
            k = (len(values)-1)*p
            lo = int(k)
            hi = min(lo+1, len(values)-1)
            return values[lo] + (values[hi]-values[lo])*(k-lo)
        return {'count': len(values), 'min': values[0], 'median': quantile(.5),
                'p90': quantile(.9), 'max': values[-1], 'mean': sum(values)/len(values),
                'at_or_above_0_4': sum(v >= .4 for v in values)}
    report = {'model': 'MSCLAP 2023', 'device': 'cpu', 'seed_per_track': f'{seed} + track_id',
              'split': json.loads(manifest_path.read_text(encoding='utf-8-sig')).get('split', 'unspecified'), 'tracks': len(tracks), 'embedding_shape': list(matrix.shape),
              'self_pairs_excluded': True, 'unique_pairs': len(rows),
              'all_pairs': stats([r['cosine_similarity'] for r in rows]),
              'same_genre': stats([r['cosine_similarity'] for r in rows if r['same_genre']]),
              'different_genre': stats([r['cosine_similarity'] for r in rows if not r['same_genre']]),
              'packages': {name: importlib.metadata.version(name) for name in ['msclap','torch','torchaudio','transformers']},
              'checkpoint_path': str(getattr(model, 'model_fp', 'unavailable')),
              'audio_hashes': hashes,
              'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'limitations': ['Same genre is a diagnostic proxy, not human-rated audio similarity.',
                              'Pairs share tracks and are not independent observations.',
                              'Audio-text normalization bounds are applied only to diagnose clipping, not validated for audio-audio.',
                              'FMA excerpts and model crop do not validate full-length audio uploads.']}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['embedding_shape','unique_pairs','all_pairs','same_genre','different_genre']}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=43)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")
    measure(args.manifest, args.output, args.seed)


if __name__ == "__main__":
    main()
