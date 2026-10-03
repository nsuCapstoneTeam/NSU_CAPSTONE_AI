"""음악 파일을 받아 DB에 저장된 호환 가능한 후보의 TopK를 출력한다."""

import argparse
import json
from pathlib import Path

import psycopg

from app.embedding.audio_embedding import AudioEmbeddingError
from app.matching.database_audio_search import DatabaseAudioSearch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--output', type=Path, help='New JSON file, never overwritten')
    args = parser.parse_args()
    if not 1 <= args.top_k <= 100:
        parser.error('--top-k must be between 1 and 100')
    if args.output is not None and args.output.exists():
        parser.error('--output already exists; choose a new path')
    try:
        result = DatabaseAudioSearch().search(args.audio, top_k=args.top_k)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as target:
                json.dump(result, target, ensure_ascii=False, indent=2)
                target.write('\n')
    except AudioEmbeddingError as error:
        print(json.dumps({'status': 'error', 'reason': error.reason}))
        return 1
    except psycopg.Error:
        print(json.dumps({'status': 'error', 'reason': 'embedding_database_error'}))
        return 1
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'error', 'reason': str(error)}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
