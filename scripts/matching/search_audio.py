"""DB 저장 전 후보 파일 목록으로 음악 간 검색을 검증하는 CLI."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from app.matching.audio_search import audio_cosine_similarities, rank_audio_candidates
from app.embedding.audio_embedding import AudioEmbeddingError, AudioEmbeddingGenerator


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def load_candidates(manifest_path, query_path):
    """모델 로딩 전에 입력을 검사하고 동일 음악이 자기 자신을 추천하지 않도록 제외한다.

    Returns:
        tuple: 비교 후보, 제외된 곡 ID 목록, 입력 파일 SHA-256.
    Raises:
        FileNotFoundError: 입력 또는 후보 파일이 없는 경우.
        ValueError: 빈 목록·잘못된 ID·중복 ID 또는 남은 후보가 없는 경우.
    """
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
        # 경로가 다른 복사본도 같은 음악이므로 파일 내용 기준으로 자기 비교를 제외한다.
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
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error('--top-k must be positive')
    if args.output.exists():
        parser.error('--output already exists; choose a new path')
    candidates, excluded, query_hash = load_candidates(args.manifest, args.audio)
    import torch
    print('Loading MSCLAP 2023 CPU...', file=sys.stderr, flush=True)
    generator = AudioEmbeddingGenerator()
    # 검색과 향후 저장에서 전처리 정책이 갈라지지 않도록 공통 생성기를 재사용한다.
    with torch.inference_mode():
        try:
            query_result = generator.generate(args.audio, expected_sha256=query_hash)
        except AudioEmbeddingError as error:
            print(
                f'Error: query audio embedding failed: {error.reason} ({error.audio_path})',
                file=sys.stderr,
            )
            return 1
        query = query_result.vector
        vectors = []
        candidate_metadata = []
        for track in candidates:
            print('Embedding candidate', track['track_id'], file=sys.stderr, flush=True)
            try:
                generated = generator.generate(track['audio_path'], expected_sha256=track['sha256'])
            except AudioEmbeddingError as error:
                print(
                    f"Error: candidate track_id={track['track_id']} audio embedding failed: "
                    f'{error.reason} ({error.audio_path})',
                    file=sys.stderr,
                )
                return 1
            vectors.append(generated.vector)
            candidate_metadata.append(dict(generated.metadata, track_id=track['track_id']))
        cosines = audio_cosine_similarities(query, torch.cat(vectors)).cpu().tolist()
    result = {
        'query_audio': str(args.audio.resolve()), 'query_sha256': query_hash,
        'model': 'MSCLAP 2023', 'checkpoint_path': query_result.metadata['checkpoint_path'],
        'preprocessing_version': query_result.metadata['preprocessing_version'],
        'preprocessing': query_result.metadata['preprocessing'],
        'comparison': 'audio-audio', 'score_bounds': {'lower': 0.0, 'upper': 1.0, 'status': 'provisional'},
        'candidate_count': len(candidates), 'excluded_identical_track_ids': excluded,
        'candidate_manifest_sha256': digest(args.manifest),
        'embedding_dimension': query.shape[1],
        # 원본·모델·전처리가 바뀐 결과를 같은 조건의 실험으로 오해하지 않도록 함께 남긴다.
        'query_embedding_metadata': query_result.metadata,
        'candidate_embedding_metadata': candidate_metadata,
        'results': rank_audio_candidates(candidates, cosines, top_k=args.top_k),
        'warning': 'Audio similarity index, not event suitability or probability. Track-level results, not artist TOP 5.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # 출력 경로 사전 확인 뒤에도 다른 실행이 파일을 만들 수 있으므로 배타적으로 생성한다.
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, ensure_ascii=False, indent=2)
        target.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
