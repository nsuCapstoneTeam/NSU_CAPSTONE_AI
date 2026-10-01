import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str = field(repr=False)
    connect_timeout: int

    @classmethod
    def from_environment(cls):
        password = os.environ["DB_PASSWORD"]
        port = int(os.environ.get("DB_PORT", "5432"))
        timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", "3"))

        if not password:
            raise ValueError("DB_PASSWORD가 비어 있습니다.")

        if not 1 <= port <= 65535:
            raise ValueError("DB_PORT는 1~65535 사이여야 합니다.")

        if timeout < 1:
            raise ValueError("DB_CONNECT_TIMEOUT은 1 이상이어야 합니다.")

        return cls(
            host=os.environ.get("DB_HOST", "host.docker.internal"),
            port=port,
            name=os.environ.get("DB_NAME", "capstone_db"),
            user=os.environ.get("DB_USER", "capstone"),
            password=password,
            connect_timeout=timeout,
        )