"""SQL과 적용 이력을 함께 관리해 다른 개발 환경에서도 같은 테이블을 생성한다."""

import hashlib
from pathlib import Path

from app.core.database import connect_database


MIGRATION_DIRECTORY = Path(__file__).resolve().parents[1] / 'repository' / 'migrations'


def apply_migrations():
    """미적용 SQL을 원자적으로 적용하고 이미 적용한 SQL의 수정은 거부한다.

    Returns:
        list[str]: 이번 실행에서 새로 적용한 마이그레이션 이름.
    Raises:
        RuntimeError: pgvector가 없거나 기존 적용 이력과 파일이 달라진 경우.
    """
    applied = []
    with connect_database() as connection:
        with connection.cursor() as cursor:
            # 두 프로세스가 동시에 실행해도 동일 SQL을 중복 적용하지 않도록 DB 잠금을 사용한다.
            cursor.execute('SELECT pg_advisory_xact_lock(726831904)')
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            if cursor.fetchone() is None:
                raise RuntimeError('vector_extension_missing')
            cursor.execute('CREATE SCHEMA IF NOT EXISTS ai_embeddings')
            cursor.execute('''CREATE TABLE IF NOT EXISTS ai_embeddings.schema_migrations (
                name text PRIMARY KEY, sha256 text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )''')
            cursor.execute('SELECT name, sha256 FROM ai_embeddings.schema_migrations')
            history = dict(cursor.fetchall())
            files = sorted(MIGRATION_DIRECTORY.glob('*.sql'))
            if set(history) - {path.name for path in files}:
                raise RuntimeError('unknown_applied_migration')
            for path in files:
                # Windows와 Linux의 줄바꿈 차이를 SQL 변경으로 오인하지 않도록 정규화한다.
                source = path.read_text(encoding='utf-8')
                checksum = hashlib.sha256(source.encode('utf-8')).hexdigest()
                if path.name in history:
                    if history[path.name] != checksum:
                        raise RuntimeError(f'migration_checksum_mismatch: {path.name}')
                    continue
                cursor.execute(source)
                cursor.execute('INSERT INTO ai_embeddings.schema_migrations (name, sha256) VALUES (%s, %s)',
                               (path.name, checksum))
                applied.append(path.name)
        # SQL과 적용 이력을 같은 트랜잭션에 두어 실패 시 반쪽짜리 상태를 남기지 않는다.
    return applied
