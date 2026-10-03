# 자동 테스트

서비스 코드의 기능을 기준으로 테스트를 나눴습니다.

| 폴더 | 검증 범위 |
| --- | --- |
| api/ | Health Check 응답 |
| core/ | DB 환경 설정 |
| embedding/ | 공통 생성기·저장 흐름·실제 DB 제약과 트랜잭션 |
| matching/ | 후보 검색·순위·점수 정규화 |
| fma/ | 표본 선택·검증 입력 처리 |

전체 테스트 명령은 그대로입니다.

```powershell
docker compose run --rm --no-deps ai python -m pytest tests -q
```

DB 테스트는 기본적으로 건너뜁니다. 개발 DB에 마이그레이션을 적용한 뒤 명시적으로 실행합니다.

```powershell
docker compose run --rm --no-deps -e RUN_EMBEDDING_DB_TESTS=1 ai python -m pytest tests -q
```

특정 기능만 확인할 때는 `tests/embedding` 등 해당 폴더를 지정합니다.
