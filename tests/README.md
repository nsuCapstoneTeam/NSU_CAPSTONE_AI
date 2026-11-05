# 자동 테스트

서비스 코드의 기능을 기준으로 테스트를 나눴습니다.

| 폴더 | 검증 범위 |
| --- | --- |
| api/ | Health Check 응답 |
| core/ | DB 환경 설정 |
| embedding/ | 공통 생성기·저장 흐름·실제 DB 제약과 트랜잭션 |
| matching/ | 후보 검색·순위·점수 정규화 |
| fma/ | 표본 선택·검증 입력 처리 |
| audio/ | Phase A Dataset 도구의 synthetic Audio·frame 경계·PCM·CLI·재현성 검사 |

unit test는 로컬 Python에서도 실행할 수 있습니다. 모델 다운로드·실DB가 필요한 검증은 opt-in이며 mock 결과와 구분합니다.
개발 이미지에서 전체 기본 suite를 실행하는 명령:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps ai python -m pytest tests -q -p no:cacheprovider
```

DB 테스트는 기본적으로 건너뜁니다. 개발 DB에 마이그레이션을 적용한 뒤 명시적으로 실행합니다.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps -e RUN_EMBEDDING_DB_TESTS=1 ai python -m pytest tests -q -p no:cacheprovider
```

특정 기능만 확인할 때는 `tests/embedding` 등 해당 폴더를 지정합니다.

로컬 Python에서는 `python -m pytest tests/core/test_config.py tests/api/test_health.py -q`로 DB 설정·Health unit test를 실행할 수 있습니다. 필요한 Python 의존성 설치는 README를 따릅니다.
`python tests/core/test_compose_config.py`는 Docker Compose CLI만 사용해 기본/dev 병합과 DB_HOST/DB_PASSWORD 누락 거부를 검사합니다. Docker Engine·DB·모델은 필요하지 않습니다. CLI가 없는 환경에서는 이 검사만 skip됩니다.
CI는 Compose 검사를 host에서, 전체 기본 pytest와 runtime import/`pip check`를 각각 dev/runtime 이미지에서 실행합니다. 모델·실DB opt-in 검증과 Spring E2E는 별도입니다.

Git commit을 조회하는 validation CLI 테스트는 실제 checkout metadata가 필요합니다. CI는 전체 history를 checkout하고 `.git` 디렉터리만 읽기 전용 mount합니다. 일반 dev Compose는 host 절대 경로를 담는 worktree `.git` 포인터를 자동 mount하지 않습니다. 따라서 위 standalone dev 명령에서 Git-dependent 검증은 추가 환경 제한이 있습니다. 임시 ROOT를 Git repository 밖으로 바꾸는 기존 테스트와 Linux MSCLAP source identity 문제는 [검증 보고서](../docs/guides/DOCKER_DEV_RUNTIME_VALIDATION.md)에 별도로 기록하며, CI gate를 skip/축소하지 않습니다.
