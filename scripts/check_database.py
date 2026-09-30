"""Read-only database and pgvector check: python -m scripts.check_database."""

import json

from app.core.database import check_database
from app.core.exceptions import DatabaseNotReady


def main() -> int:
    try:
        version = check_database()
    except DatabaseNotReady as error:
        print(json.dumps({"status": "not_ready", "reason": error.reason}))
        return 1

    print(json.dumps({"status": "ok", "database": "ok", "pgvector": version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
