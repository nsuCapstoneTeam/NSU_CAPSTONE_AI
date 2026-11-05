# AI 개발 환경과 runtime 이미지

개발 기준은 React Local, Spring Local, Backend PostgreSQL/pgvector·Redis Docker, AI Docker다.
AI 저장소는 DB/Redis 서비스를 중복 생성하지 않는다. Backend의 설정·서비스 계약·운영 인프라 결정을 이 문서에서 변경하지 않는다.

## 최초 환경 준비

아래는 Windows PowerShell 기준이며 두 저장소가 같은 부모 디렉터리에 clone돼 있고 최초 terminal이 `NSU_CAPSTONE_AI` 루트에서 시작한다고 가정한다. 프로젝트 위치가 다르면 `cd` 경로를 맞춘다.

1. `NSU_CAPSTONE/backend/README.md`에 따라 Backend `.env`와 로컬 개발 secret을 준비하고 Docker Desktop을 실행한다.

```powershell
cd ..\NSU_CAPSTONE\backend
docker compose up -d
```

PostgreSQL/pgvector와 Redis는 Backend Compose가 관리한다. DB의 기본 공개 port는 5432다. 이미 로컬 PostgreSQL이 사용 중이면 Backend 설정과 AI `DB_PORT`를 함께 맞춘다. pgvector extension은 Backend의 Flyway 설정을 확인한다. AI 테이블 migration은 별도 대상 DB·권한 확인과 승인 후 명시적으로 실행하며 AI 시작 시 자동 적용하지 않는다.

2. AI 저장소로 이동하여 `.env`를 준비한다. 기존 파일은 덮어쓰지 않는다.

```powershell
cd ..\..\NSU_CAPSTONE_AI
Copy-Item .env.example .env
notepad .env
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
```

`DB_PASSWORD`, `DB_USER`, `DB_NAME`, `DB_PORT`를 Backend DB와 맞춘다. `DB_HOST`는 필수다.

| 실행 위치 | DB_HOST |
| --- | --- |
| Windows Docker Desktop의 AI | `host.docker.internal` |
| Local Python | `localhost` |
| 같은 명시적 Docker network | `postgres` 등 실제 service DNS |
| 운영 | RDS endpoint |

서로 다른 Compose 프로젝트의 service 이름은 자동 공유되지 않는다. Linux Docker Engine은 host gateway 연결을 별도로 구성해야 할 수 있다. 코드가 hostname을 추측하지 않는다. `.env`는 Compose 보간용이며 Python 코드가 자동 로딩하지 않는다. Local Python 실행은 필요한 환경변수를 shell/IDE에 직접 주입한다. 실제 secret은 commit하지 않는다.

3. 개발 이미지를 build하고 공용 모델 cache를 준비한다.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build ai
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps ai python -m scripts.embedding.validate_calibration_text_embeddings --prepare-resources
```

위 명령은 기존 도구의 자원 준비 기능이며 새 model preparation CLI가 아니다. 네트워크에서 해당 도구에 기록된 MSCLAP/GPT-2/tokenizer snapshot을 내려받고 기존 검증 절차를 수행한다. `--prepare-resources`만 지정하면 calibration evidence/Embedding 결과를 다시 쓰지 않는다. 모델 cache의 `refs/main`은 해당 도구의 기존 정책에 따라 지정 revision을 가리키도록 갱신되므로, 다른 실험과 공용으로 쓰는 기존 cache 대신 새 개발 volume에서 실행한다.

모델 파일은 이미지에 넣지 않는다. Compose의 `huggingface_cache` named volume을 `/var/cache/huggingface`에 연결하고 `HF_HOME`을 이 경로로 지정한다. 실제 volume 이름은 Compose project name으로 격리된다. runtime은 읽기 전용, dev는 준비·재사용을 위해 쓰기 가능하다. fresh clone은 모델·Audio·dataset을 포함하지 않는다. Health-only 서버 기동에는 모델 cache가 필요 없지만 실제 Embedding에는 준비된 자원이 필요하다.

`datasets/fma/huggingface`의 기존 데이터와 과거 evidence는 이동·삭제·재작성하지 않는다. 일반 저장/검색 CLI는 `HF_HOME` volume을 사용한다. 과거 경로를 기본값으로 갖는 검증 도구는 다음처럼 구분한다.

- `validate_audio_highlight_msclap`은 일반 cache를 사용할 때 `--cache /var/cache/huggingface`를 명시할 수 있다.
- `validate_audio_embedding_postgres` 등 historical 경로에 고정된 전용 실험은 해당 실험 문서의 입력·cache 준비 조건을 그대로 따른다. 새 공용 volume만 준비했다고 과거 실험을 재현했다고 간주하지 않는다. 기존 `./datasets` bind mount는 유지하므로 별도로 보관된 historical cache를 그대로 참조할 수 있다.

runtime Compose만 실행할 경우에도 같은 project의 준비된 volume이 필요하다. 다른 host/project에 배포할 때 모델 자원 공급은 별도로 준비해야 한다. 자동 다운로드·preload·model readiness를 이번 구성에서 구현하지 않는다.

4. AI 개발 서버를 실행한다.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

`AI_PORT`를 바꿨으면 URL도 맞춘다. `live`는 프로세스 응답, `ready`는 DB 연결·vector extension만 확인한다. Docker healthcheck는 live 기준이다. 모델·AI 테이블 준비나 실제 추론 성공을 보장하지 않는다.

5. 별도 terminal 두 개를 각각 `NSU_CAPSTONE_AI` 루트에서 열고 Spring과 React를 Local로 실행한다. 각각 해당 프로젝트의 최초 설정을 먼저 따른다.

```powershell
cd ..\NSU_CAPSTONE\backend
.\gradlew.bat bootRun
```

```powershell
cd ..\NSU_CAPSTONE\frontend
npm run dev
```

Spring→AI 업무 API 연동은 별도 구현 범위다. 서버가 실행된다는 사실을 E2E 완료로 표현하지 않는다.

## 일상 실행

각 프로젝트 디렉터리에서 실행한다.

| 위치 | 명령 |
| --- | --- |
| `NSU_CAPSTONE/backend` | `docker compose up -d` |
| `NSU_CAPSTONE_AI` | `docker compose -f compose.yaml -f compose.dev.yaml up -d --build` |
| `NSU_CAPSTONE/backend` | `./gradlew bootRun` (Windows PowerShell: `.\gradlew.bat bootRun`) |
| `NSU_CAPSTONE/frontend` | `npm run dev` |

소스·tests·docs·samples는 읽기 전용 mount이며 host 편집은 가능하다. reload는 `app/`만 감시한다. datasets는 결과 저장용으로 쓰기 가능하다. pytest cache 쓰기는 `-p no:cacheprovider`로 끄고 임시 파일은 `/tmp`를 사용한다. Python 의존성·Dockerfile 변경은 dev image rebuild가 필요하다.

## runtime과 CI

`Dockerfile`은 `base → runtime-deps` 뒤에 `dev`와 `runtime`을 분기하며 마지막 stage가 runtime이다. runtime에는 `app/`와 DB 확인·읽기 전용 진단·명시적 migration CLI만 넣는다. dev는 전체 개발 scripts/tests/docs와 pytest/httpx/jsonschema/imageio-ffmpeg 및 commit 조회용 Git CLI를 설치한다. 기존 ML package 버전·ffmpeg·libsndfile1은 유지한다. 간접 dependency까지 제거된다고 보장하지 않으며 실제 package metadata/`pip check` 검증이 필요하다. Git CLI 설치와 repository metadata 제공은 별개다. 이미지에는 `.git`을 복사하지 않으므로 Git 기반 실험 CLI 실행은 해당 도구의 checkout/metadata 조건을 추가로 확인한다.

`compose.yaml`은 GHCR runtime 이미지, env, port, 읽기 전용 모델 volume, 임시 `/tmp`, live healthcheck만 담당한다. source mount·reload·dev writable cache는 없다. 운영은 검증된 `AI_IMAGE` SHA tag 또는 digest로 지정한다. runtime에서 테스트·실험 CLI를 실행하지 않는다.

CI의 PR은 테스트·runtime build 검증만 수행하고 게시하지 않는다. main push는 같은 검증 job 성공 후 별도 권한의 job에서 runtime을 build/push한다. Git-dependent validation을 위해 CI는 실제 checkout의 전체 history와 읽기 전용 `.git` mount를 제공하고 컨테이너의 `/workspace`만 safe.directory로 등록한다. `GIT_DIR`/`GIT_WORK_TREE`를 전역 지정하거나 가짜 commit을 만들지 않는다. 일반 dev Compose에는 host 절대 경로를 가진 worktree `.git` 포인터를 자동 mount하지 않는다. 이미지 내용에 영향을 주는 `app/`, runtime DB scripts, Dockerfile, requirements, `.dockerignore`, workflow를 감지한다. 개발 scripts/tests/Compose/실험 fixture 문서 변경도 검증을 위해 감지하므로 이들만 바뀐 main push에도 runtime을 다시 게시한다. 일반 README/guide 변경만으로는 게시하지 않는다.

tag는 `latest`, 기존 consumer 호환용 `phase1`, `sha-<전체 commit SHA>`다. source/revision OCI label을 넣는다. `phase1`은 consumer 확인 후 후속 폐기 검토한다. 테스트와 게시가 별도 runner에서 build하므로 lock 없는 전이 의존성이 두 build 사이에 달라질 가능성이 남는다. dependency lock·동일 artifact 승격은 후속 작업이다.

## 이번 범위 밖

dependency lock·버전 upgrade·새 모델 준비 CLI·startup preload·model readiness·production hardening은 별도 작업이다. 기존 ADR/Embedding/검색 정책·BPM/Rhythm·번역/LLM 운영 기능은 변경하지 않는다. Docker Engine 오류 시 Desktop 설정·volume을 자동 복구하거나 삭제하지 않는다.

이번 구조 검증에서 기존 Git-dependent test fixture와 Linux MSCLAP source identity 문제가 관측됐다. 전체 pytest·CI 성공이나 실제 모델 추론 완료로 간주하지 않는다. 실행 명령·원본 main 비교·영향은 [검증 보고서](../validation/DOCKER_DEV_RUNTIME_CLEANUP.md)를 따른다.
