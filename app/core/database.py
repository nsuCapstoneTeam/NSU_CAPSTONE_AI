import psycopg

from app.core.config import DatabaseSettings
from app.core.exceptions import DatabaseNotReady


def connect_database():
    """저장·마이그레이션에서 동일한 접속 설정과 SQL 대기 제한을 사용한다."""
    settings = DatabaseSettings.from_environment()
    return psycopg.connect(
        host=settings.host, port=settings.port, dbname=settings.name,
        user=settings.user, password=settings.password,
        connect_timeout=settings.connect_timeout,
        options='-c statement_timeout=30000 -c lock_timeout=5000',
    )


def check_database() -> str:
    """실제 접속과 대상 DB의 vector 확장 활성화를 모두 확인한다.

    Returns:
        str: 연결 대상 DB에서 활성화된 pgvector 버전.
    Raises:
        DatabaseNotReady: 설정·접속 실패 또는 확장 미활성화인 경우.
    """
    try:
        settings = DatabaseSettings.from_environment()

        with psycopg.connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.name,
            user=settings.user,
            password=settings.password,
            connect_timeout=settings.connect_timeout,
            # 접속은 성공해도 쿼리가 지연될 수 있으므로 준비 상태 검사의 대기를 제한한다.
            options="-c statement_timeout=3000",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

                cursor.execute(
                    "SELECT extversion "
                    "FROM pg_extension "
                    "WHERE extname = 'vector'"
                )
                extension = cursor.fetchone()

    except (psycopg.Error, KeyError, ValueError) as error:
        # 응답에는 접속 정보가 포함될 수 있는 원본 오류 대신 안정적인 사유 코드만 전달한다.
        raise DatabaseNotReady("database_unavailable") from error

    if extension is None:
        # 서버에 설치된 확장도 대상 DB에서 활성화되지 않았다면 벡터 저장에 사용할 수 없다.
        raise DatabaseNotReady("vector_extension_missing")

    return extension[0]
