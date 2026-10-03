"""백엔드 연동 전, 외부 음악 ID와 로컬 파일로 동기 저장 흐름을 검증한다."""

import argparse
import json
from dataclasses import asdict

import psycopg

from app.embedding.audio_embedding import AudioEmbeddingError
from app.embedding.storage import AudioEmbeddingStorage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--music-id', required=True)
    parser.add_argument('--audio', required=True)
    args = parser.parse_args()
    try:
        saved = AudioEmbeddingStorage().store(args.music_id, args.audio)
    except AudioEmbeddingError as error:
        print(json.dumps({'status': 'error', 'reason': error.reason}))
        return 1
    except psycopg.Error:
        # 원본 DB 예외에는 접속·SQL 정보가 들어갈 수 있어 CLI에서는 분류 코드만 출력한다.
        print(json.dumps({'status': 'error', 'reason': 'embedding_database_error'}))
        return 1
    except ValueError as error:
        print(json.dumps({'status': 'error', 'reason': str(error)}))
        return 1
    print(json.dumps({'status': 'ok', **asdict(saved)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
