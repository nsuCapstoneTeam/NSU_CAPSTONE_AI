"""AI 전용 테이블의 버전 관리 SQL을 명시적으로 적용한다."""

import json

from app.core.migrations import apply_migrations


def main():
    print(json.dumps({'applied': apply_migrations()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
