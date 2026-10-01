import psycopg

from app.core.config import DatabaseSettings
from app.core.exceptions import DatabaseNotReady


def check_database() -> str:
    try:
        settings = DatabaseSettings.from_environment()

        with psycopg.connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.name,
            user=settings.user,
            password=settings.password,
            connect_timeout=settings.connect_timeout,
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
        raise DatabaseNotReady("database_unavailable") from error

    if extension is None:
        raise DatabaseNotReady("vector_extension_missing")

    return extension[0]