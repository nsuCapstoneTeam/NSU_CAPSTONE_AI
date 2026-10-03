"""Phase 3 DB 준비 정보를 읽기 전용으로 확인하며 접속 비밀번호는 출력하지 않는다."""

import json
import psycopg
from app.core.config import DatabaseSettings


def main():
    settings = DatabaseSettings.from_environment()
    # 진단이 실수로 테이블·데이터를 변경하지 못하도록 DB 세션 자체를 읽기 전용으로 제한한다.
    with psycopg.connect(host=settings.host, port=settings.port, dbname=settings.name,
                         user=settings.user, password=settings.password,
                         connect_timeout=settings.connect_timeout,
                         options='-c default_transaction_read_only=on -c statement_timeout=3000') as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user')
            database, user = cursor.fetchone()
            cursor.execute("SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'vector'")
            vector = cursor.fetchone()
            cursor.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1, 2")
            tables = cursor.fetchall()
    print(json.dumps({'database': database, 'user': user, 'vector_available': vector is not None,
                      'vector_default_version': vector[0] if vector else None,
                      'vector_installed_version': vector[1] if vector else None,
                      'tables': [{'schema': schema, 'name': name} for schema, name in tables]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
