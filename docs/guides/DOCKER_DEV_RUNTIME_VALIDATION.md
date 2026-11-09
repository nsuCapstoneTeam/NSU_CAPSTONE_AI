# Docker 개발/runtime 1차 정리 검증 기록

## 환경과 범위

- 실행일: 2026-11-05, Windows / Docker Desktop Linux Engine 29.9.2.
- baseline main: `9837ea16e25eb082a5ae6764fcba1bdf903960c2`.
- 구현 검증 commit: `b8f0e8c8b5b31702107ff6fc776627d3d6140520`, branch `feat/docker-dev-runtime-cleanup`.
- Main과 분리된 managed Worker worktree에서 구현했다. 원본 Main은 읽기 전용 reference다.
- base: `python:3.11-slim@sha256:db20d8506e2f15b6db39b40b6015ca46bae855dec6dd326d462cfe79ae972893`, CPython 3.11.18/Linux x86-64.
- ML: msclap 1.3.3, torch/torchaudio 2.1.2+cpu, torchvision 0.16.2+cpu, transformers 4.35.2, numpy 1.26.4. imageio-ffmpeg(dev) 0.6.0.
- 기존 requirement 범위로 설치된 서버 package: fastapi 0.162.0, uvicorn 0.54.0, psycopg 3.3.8. requirement 버전·범위를 upgrade하지 않았다.

이 문서는 Docker 구조·unit 검증 기록이며 모델 inference·추천 품질·실DB 통합 완료 evidence가 아니다. 기존 experiments/ADR/package/expected hash는 변경하지 않았다. Host Python/py가 없어 Python 검증은 컨테이너에서 수행했다.

## 통과한 검사

| 검사 | 명령·방법 | 결과 |
| --- | --- | --- |
| diff | `git diff --check` | PASS |
| runtime build | `docker build --target runtime --tag nsu-capstone-ai:worker-runtime-check .` | PASS |
| dev build | `docker build --target dev --tag nsu-capstone-ai:worker-dev-check .` | PASS |
| dependency | 두 target build의 `pip check`, runtime 컨테이너 `python -m pip check` | PASS |
| runtime import | torch·torchaudio·torchvision·MSCLAP·FastAPI app·DB CLI 3개 import, CPU assert | PASS, 가중치 다운로드 없음 |
| runtime 경계 | installed distribution·파일 집합 검사 | pytest/httpx/jsonschema/imageio-ffmpeg 없음. scripts는 package 초기화 2개·DB CLI 3개뿐. tests/docs 없음 |
| live smoke | 컨테이너 안에서 Uvicorn 시작 후 urllib `/health/live` | HTTP 200, `{"status":"ok"}` |
| 관련 unit | `docker run --rm nsu-capstone-ai:worker-dev-check python -m pytest tests/core/test_config.py tests/api/test_health.py -q -p no:cacheprovider` | 13 passed, Starlette deprecation warning 1개 |
| static | dev Python `compile` 및 PyYAML BaseLoader로 PR/publish gate·권한·tag·OCI label 검사 | PASS |

실제 Compose CLI `config --format json`으로 다음 세 그룹을 모두 PASS했다. `--env-file NUL`과 테스트용 DB_HOST/DB_PASSWORD만 사용했으며 Engine/DB를 시작하지 않았다.

1. base: build/command/source bind 없음, 모델 volume 하나·읽기 전용.
2. base+dev: target/image 정상, source/tests/docs/samples 읽기 전용, datasets 쓰기 가능, cache 하나·쓰기 가능으로 병합.
3. 두 구성 모두 DB_HOST/DB_PASSWORD를 각각 제거하면 interpolation 단계 exit 1.

새 stdlib `test_compose_config.py`는 같은 검사를 자동화한다. dev 이미지에 Docker CLI가 없어 전체 pytest에서는 3개가 skip된다. Host Python도 없어 자동화 진입점 자체를 로컬에서 실행하지는 못했다. 위 실제 CLI 검사는 PowerShell에서 수행했으며 CI는 Docker CLI가 있는 runner host에서 Python 검사를 실행한다.

## 전체 pytest와 baseline

최종 비교는 Git CLI·AGENTS.md·실제 checkout metadata가 있는 환경 기준이다.

| 대상 | passed | failed | skipped | 시간 |
| --- | ---: | ---: | ---: | ---: |
| 원본 main 전체 복사본, 같은 최종 dev package 환경 | 685 | 13 | 22 | 130.27초 |
| 실제 Worker commit 정상 clone | 689 | 13 | 25 | 121.83초 |

실패 testset은 동일하다. 추가 DB_HOST unit 4개는 통과했고 새 Compose CLI 3개는 위 이유로 skip됐다. 기존 실패를 skip/xfail로 바꾸거나 CI suite를 축소하지 않았다.

Worker 재현 명령(원본 repo는 읽기 전용, clone은 컨테이너 임시 공간에만 생성):

```powershell
docker run --rm --mount type=bind,source=C:\Users\kimji\WorkSpace\NSU_CAPSTONE_AI,target=/source,readonly nsu-capstone-ai:worker-dev-check sh -c 'git config --global --add safe.directory /source && git clone --no-local --branch feat/docker-dev-runtime-cleanup /source /tmp/checkout && cd /tmp/checkout && git rev-parse HEAD && python -m pytest tests -q -p no:cacheprovider --tb=short'
```

출력 HEAD는 위 구현 검증 commit과 일치했다. baseline은 readonly main 전체(`.git`, AGENTS.md, tracked fixtures 포함)를 `/tmp/baseline`에 복사한 뒤 같은 pytest 명령을 실행했다. 원본 파일은 수정하지 않았다.

### 기존 Git fixture 실패 12개

`tests/embedding/test_audio_embedding_postgres_validation.py`가 `tool.ROOT=tmp_path`로 바꾼 뒤 기존 CLI의 commit 조회가 Git repository 밖에서 실행된다.

대표 trace: `scripts/database/validate_audio_embedding_postgres.py:670`, `subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT)` → `CalledProcessError`, exit 128, `not a git repository`.

- `test_cli_writes_structured_migration_failure_without_credentials`
- `test_blocked_cli_does_not_migrate_or_infer`
- `test_programming_error_not_hidden`
- `test_cli_db_error_status_tracks_whether_execution_started` 9 cases: operational False/preflight 및 True/migration·msclap_generation·database_measurements·rollback_verification, safety False/preflight·True/database_preflight, database False/preflight·True/integration_tests.

가짜 SHA/repository나 전역 GIT_DIR/GIT_WORK_TREE로 우회하지 않았다. fixture/CLI 오류 처리의 별도 후속 수정이 필요하다.

### 기존 Linux MSCLAP source identity 실패 1개

`tests/embedding/test_text_embedding.py::test_installed_msclap_source_identity_matches_calibration`이 `app/embedding/text_embedding.py:105`의 `MSCLAP implementation source differs from the validated calibration identity`로 실패한다.

| 읽기 전용 진단 | 결과 |
| --- | --- |
| 실제/기대 파일 수 | 13 / 13 |
| 실제/기대 config SHA-256 | `41fbc893997f75fe144d93bf2ec44d5ca27fe61beb8870dd815a53c064cb030f` (일치) |
| 기대 aggregate | `e867cdbb71f7bcee529afb92a096578faab46c69feb35d8192d4f220de56c181` |
| Linux Path 정렬 aggregate | `1f8dcc9110545074a963407ebfecb7625c9d8cc97c8f37e662b27afb8a53ec12` |
| relative path casefold 정렬 aggregate | `e867cdbb71f7bcee529afb92a096578faab46c69feb35d8192d4f220de56c181` (기대값과 일치) |

다음 Python을 dev 컨테이너 `python -` stdin에 전달해 진단했다. 파일은 읽기만 한다.

```python
import hashlib
import importlib
from pathlib import Path
root = Path(importlib.import_module('msclap.CLAPWrapper').__file__).resolve().parent
files = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in {'.py', '.yml', '.yaml'}]
def aggregate(order):
    digest = hashlib.sha256()
    for path in order:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b'\n')
    return digest.hexdigest()
print(len(files))
print(hashlib.sha256((root / 'configs/config_2023.yml').read_bytes()).hexdigest())
print(aggregate(sorted(files)))
print(aggregate(sorted(files, key=lambda p: p.relative_to(root).as_posix().casefold())))
```

동일 파일 내용에서 정렬만 바꾸어 기대 aggregate가 재현됐다. Windows/Linux Path 정렬 차이의 portability 수정은 별도 검토가 필요하다. **현재 Linux의 실제 Text/Audio 모델 초기화도 이 verifier에서 거부될 수 있다.** runtime import/live PASS를 실제 추론 준비 완료로 표현하지 않는다. verifier·expected hash·evidence는 변경하지 않았다.

## 환경 보강·이미지·한계

초기 dev의 Git CLI·AGENTS.md 누락은 개발 stage에만 보강했다. Git metadata 없는 standalone dev에서는 Highlight validation CLI 테스트 1개가 추가 실패한다. CI는 실제 checkout 전체 history와 readonly `.git` mount, `/workspace` safe.directory만 제공해 이 환경 문제를 해소한다. 일반 dev Compose는 worktree `.git`의 host 절대 경로를 자동 mount하지 않는다.

| 검증 tag | image ID |
| --- | --- |
| `nsu-capstone-ai:worker-runtime-check` | `sha256:8fa75c8a52a2cc2f985fc7393fb4a2f038bef744c0dd4f542de1377217dac8a4` |
| `nsu-capstone-ai:worker-dev-check` | `sha256:bf5a26bf088fc9c5a9aaa3e16361ba9717500b9a606406bd14065124b4b3020a` |

이 문서·링크만 검증 뒤 추가했다. build 검증 시점의 dev 문서 내용과 최종 검증 문서는 차이가 있으나 실행 코드·의존성·테스트는 동일하다.

- **전체 suite는 FAIL이며 현재 CI test gate는 기존 13개 실패로 게시 단계에 도달하지 못한다.** 구조/관련 unit 통과와 전체 검증 완료를 구분한다.
- 실제 DB integration·migration 실행·모델 inference·cache 준비/download·Spring E2E·원격 Actions·GHCR push·PR·merge는 미실행이다.
- 기존 container/image/tag/volume·cache·실험 evidence는 삭제하지 않았다. 새 검증 컨테이너만 `--rm`으로 정리했다.
- dependency lock·model preparation·startup preload·model readiness·production hardening·source identity portability·Git fixture 개선은 후속 작업이다.
