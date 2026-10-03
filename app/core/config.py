import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    # 설정 객체가 로그에 출력되더라도 DB 비밀번호는 노출하지 않는다.
    password: str = field(repr=False)
    connect_timeout: int

    @classmethod
    def from_environment(cls):
        """비밀번호 기본값을 두지 않고 잘못된 접속 설정을 연결 전에 거부한다."""
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
