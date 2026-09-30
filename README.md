# Python Embedding Server — CLAP Audio Analysis Service

아티스트–행사 매칭 플랫폼의 Python AI·오디오 분석 저장소입니다.
CLAP 기반 Audio/Text Embedding 생성, 오디오 분석, 유사도 및 점수 계산을 다룹니다.

[NSU_CAPSTONE](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE)의 협업 문서 구조를 바탕으로
Python 서버에 필요한 설정·PR 템플릿·기술 문서만 구성했습니다.
현재는 로컬 추론 코드와 Docker 기반 Health Check 서버가 있습니다.
분석·매칭 HTTP API와 Spring Boot 연동은 구현 전입니다.

## 현재 코드

| 경로 | 역할 |
| --- | --- |
| `app/inference/clap_model.py` | Microsoft CLAP 2023 로딩, 오디오·텍스트 임베딩, 유사도 계산 |
| `app/classification/classifier.py` | 라벨 유사도 비교, softmax 상대점수, Top K 정렬 |
| `app/classification/labels.py` | 장르·분위기·사운드 등 분류 라벨 |
| `scripts/test_embedding.py` | 샘플 오디오의 장르 Top 3 수동 실행 스크립트 |
| `app/main.py` | FastAPI 앱 생성 및 Health Check 라우터 등록 |
| `app/api/routes/health.py` | 서버 상태와 DB 준비 상태 확인 API |
| `app/api/schemas/health.py` | Health Check 응답 스키마 |
| `app/core/config.py` | DB 환경변수 로딩 및 값 검증 |
| `app/core/database.py` | PostgreSQL 연결과 pgvector 확장 확인 |
| `app/core/exceptions.py` | DB 준비 상태 오류 정의 |
| `scripts/check_database.py` | 실제 DB 연결·pgvector 읽기 전용 검사 |
| `tests/test_config.py`, `tests/test_health.py` | 설정 및 Health Check 자동 테스트 |

라벨 정의가 있다는 것과 해당 특징 추출 기능이 완성되었다는 것은 다릅니다.
현재 분류 상대점수는 행사 매칭용 0–100 정규화 점수와 구분합니다.
실제 모델 추론 검증은 샘플 음원과 모델 가중치가 필요합니다.

## Phase 1 변경 내용 — 기존 main과 비교

비교 기준은 2026-09-30에 가져온 GitHub `origin/main`의
[`f3ca5f9`](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/commit/f3ca5f9)입니다.
아래 표는 해당 커밋 대비 이번 Phase 1 작업의 변경 내용입니다.

| 항목 | 기존 main | Phase 1 작업 |
| --- | --- | --- |
| 서버 실행 | 로컬 CLAP 추론 스크립트 | FastAPI + Uvicorn Health Check 서버 추가 |
| 개발 환경 | 로컬 Python 가상환경 | `Dockerfile`, `compose.yaml`로 Python 3.11 개발 컨테이너 추가 |
| DB 확인 | 연결 검사 코드 없음 | 환경변수 기반 PostgreSQL 연결 및 pgvector 확장 확인 |
| 상태 확인 | HTTP endpoint 없음 | `/health/live`, `/health/ready` 추가 |
| 자동 테스트 | 없음 | 환경변수 검증 5개, Health Check 검증 4개 추가 |
| 의존성 | `msclap`, `torch` | `fastapi`, `uvicorn`, `psycopg[binary]` 추가; 개발용 `pytest`, `httpx`는 `requirements-dev.txt`로 관리 |
| 환경 설정 | 공유할 환경변수 예시 없음 | `.env.example` 추가, `.gitignore`에서 예시 파일 공유 허용 |
| Docker 빌드 제외 | 없음 | `.dockerignore`로 비밀번호 파일·음원·가중치·캐시 제외 |
| 개발 문서 | API·ADR·협업 문서 | `docs/AI_DEVELOPMENT_ROADMAP.md` 추가 및 실행 안내 갱신 |

기존 CLAP 모델과 분류 코드는 이번 작업에서 변경하지 않았습니다.
분석·매칭 API와 Spring Boot 연동은 이후 단계에서 구현합니다.

## 관련 Linear 작업

2026-09-29에 확인한 관련 작업입니다. 최신 범위와 Acceptance Criteria는 각 이슈를 확인합니다.
요구사항 원문은 [Linear Requirements](https://linear.app/nsu-capstone/document/ssot-아티스트-행사-매칭-플랫폼-mvp-요구사항-e38bb23f87b1)입니다.

| 이슈 | 이 저장소와의 관계 |
| --- | --- |
| [NSU-10](https://linear.app/nsu-capstone/issue/NSU-10), [NSU-45](https://linear.app/nsu-capstone/issue/NSU-45) | CLAP 의미 유사도, 입력 전처리, 0–100 점수 정규화 |
| [NSU-8](https://linear.app/nsu-capstone/issue/NSU-8), [NSU-42](https://linear.app/nsu-capstone/issue/NSU-42) | BPM·리듬 특징 추출 및 적합도 계산 — 구현 전 |
| [NSU-22](https://linear.app/nsu-capstone/issue/NSU-22), [NSU-47](https://linear.app/nsu-capstone/issue/NSU-47) | 분석 결과를 사용하는 공통 점수 계약·종합 점수 연계 |
| [NSU-60](https://linear.app/nsu-capstone/issue/NSU-60) | 임베딩 비동기 처리 방식 — 팀 결정 대기 |
| [NSU-61](https://linear.app/nsu-capstone/issue/NSU-61) | 2-서버 상위 책임 확정, 유사도 세부 위치·API 계약 결정 대기 |
| [NSU-62](https://linear.app/nsu-capstone/issue/NSU-62) | pgvector 채택·저장 책임 — 팀 결정 대기 |
| [NSU-63](https://linear.app/nsu-capstone/issue/NSU-63) | Spring Boot 연동 시 API 계약 협의; Java 구현은 메인 저장소 범위 |

현재 사용 기술은 Python 3.11, Microsoft CLAP(`msclap`), PyTorch입니다.
Phase 1 서버는 FastAPI를 사용하며, 기존 메인 저장소의 PostgreSQL + pgvector에 연결합니다.
비동기 큐는 도입하지 않습니다.
Frontend, 회원가입·프로필·게시판, Spring Boot DTO/Service는 이 저장소 범위에 포함하지 않습니다.

## Project Structure

```text
NSU_CAPSTONE_AI/
├── .github/
│   └── PULL_REQUEST_TEMPLATE/
│       ├── 구현_PR.md
│       └── 문서_PR.md
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── routes/health.py
│   │   └── schemas/health.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── exceptions.py
│   ├── inference/
│   │   ├── __init__.py
│   │   └── clap_model.py
│   └── classification/
│       ├── classifier.py
│       └── labels.py
├── docs/
│   ├── AI_DEVELOPMENT_ROADMAP.md
│   ├── api/README.md
│   ├── adr/README.md
│   └── 협업-가이드/README.md
├── scripts/
│   ├── check_database.py
│   └── test_embedding.py
├── tests/
│   ├── test_config.py
│   └── test_health.py
├── .dockerignore
├── .env.example
├── Dockerfile
├── compose.yaml
├── .editorconfig
├── .gitattributes
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 협업 및 기술 문서

- [협업 가이드](docs/협업-가이드/README.md): GitHub Flow, Linear, PR 및 검증 규칙
- [API 문서](docs/api/README.md): Python–Spring Boot 책임 경계와 계약 정의 항목
- [ADR 안내](docs/adr/README.md): 비동기·계산 위치·저장소 결정 대기 목록

리뷰 담당자가 확정되지 않은 `CODEOWNERS`, 빈 서비스 모듈, 배포·CI 설정은 추가하지 않았습니다.
실제 구현과 운영 결정에 맞춰 필요한 파일을 추가합니다.

## 설치 및 실행

### Docker 개발 환경 (Phase 1)

Docker Desktop을 실행하세요. IntelliJ나 Spring Boot 실행은 필요하지 않습니다.
DB는 `NSU_CAPSTONE/database`의 기존 Compose로 실행합니다.
아래 경로는 Windows 예시이므로 자신의 저장소 위치에 맞춰 바꾸세요.

```powershell
cd D:\WorkSpace\NSU_CAPSTONE\database
docker compose up -d
docker compose ps
```

AI 저장소로 이동해서 `.env`를 준비합니다. 이미 `.env`가 있으면 복사하지 말고 기존 파일을 수정하세요.

```powershell
cd D:\WorkSpace\NSU_CAPSTONE_AI
Copy-Item .env.example .env
notepad .env
```

`DB_PASSWORD`에는 기존 DB `.env`의 `POSTGRES_PASSWORD`와 같은 비밀번호를 입력합니다.
`DB_PORT`, `DB_USER`, `DB_NAME`도 기존 DB의 실제 설정과 맞추세요.
비밀번호의 작은따옴표는 유지하고 안쪽 값을 바꾸세요.
Windows Docker Desktop에서 기존 DB의 공개 포트에 접속하므로 `DB_HOST=host.docker.internal`을 사용합니다.
AI 저장소의 `.env`는 Compose가 읽고 컨테이너 환경변수로 전달합니다.

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `DB_HOST` | `host.docker.internal` | 컨테이너에서 Windows 호스트의 DB에 접근 |
| `DB_PORT` | `5432` | 기존 DB 컨테이너가 호스트에 공개한 포트 |
| `DB_NAME` | `capstone_db` | 접속할 DB 이름 |
| `DB_USER` | `capstone` | DB 접속 사용자 |
| `DB_PASSWORD` | 없음, 필수 | 기존 DB 비밀번호 |
| `DB_CONNECT_TIMEOUT` | `3` | 연결 제한 시간(초), 1 이상 |
| `AI_PORT` | `8000` | 호스트에서 접근할 AI 서버 포트 |

실제 `.env`는 Git과 Docker 빌드에서 제외되며, 팀에는 `.env.example`을 공유합니다.
이 Compose는 AI 서버만 실행하므로 기존 DB는 별도로 실행해야 합니다.

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail 50 ai
```

첫 빌드에는 Python 이미지, PyTorch 및 MSCLAP 패키지 다운로드로 시간이 걸릴 수 있습니다.
Health Check는 CLAP을 로딩하거나 모델 가중치를 다운로드하지 않습니다.

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

`live`는 서버 응답 가능 여부, `ready`는 DB 연결과 vector 확장 활성화를 확인합니다.
DB 연결 실패 또는 확장 누락 시 `ready`는 503을 반환합니다.
Compose의 `healthy`는 `live` 기준이므로 DB 준비 상태는 `ready`로 별도 확인하세요.
API 문서는 `http://localhost:8000/docs`에서 확인합니다.
`AI_PORT`를 바꿨다면 확인 주소의 포트도 바꾸세요.

정상 응답 예시:

`GET /health/live`:

```json
{"status": "ok"}
```

`GET /health/ready` (pgvector 버전은 설치 환경에 따라 다름):

```json
{"status": "ok", "database": "ok", "pgvector": "0.8.6"}
```

`ready`가 503이면 응답의 `reason`을 확인하세요.
`database_unavailable`은 DB 연결 또는 환경설정 실패,
`vector_extension_missing`은 접속한 DB에 vector 확장이 없는 경우입니다.
이 검사는 테이블이나 확장을 생성하지 않습니다.

코드는 bind mount와 `--reload`로 수정 사항이 반영됩니다.
패키지나 Dockerfile을 수정하면 `docker compose up -d --build`로 다시 빌드하세요.
평소 재실행은 `docker compose up -d`, 중지는 `docker compose stop`입니다.
서버 포트는 호스트의 `127.0.0.1`에만 공개됩니다.
모델 검증은 후속 작업입니다. 기존 테스트용 `VECTOR(3)`는 실제 CLAP 차원이 아닙니다.

### 자동 테스트

프로젝트 루트에서 실행 중인 개발 컨테이너를 사용합니다.
Dockerfile은 `requirements-dev.txt`를 설치하고, Compose는 로컬 `tests/`를 연결합니다.

```powershell
docker compose exec -T ai python -m pytest tests -q
```

| 파일 | 검사 내용 | 개수 |
| --- | --- | --- |
| `tests/test_config.py` | 환경변수 로딩, 비밀번호 누락, 잘못된 포트(`0`, `65536`, `abc`) 거부 | 5 |
| `tests/test_health.py` | DB 조회 없이 live 응답, ready 정상 응답, DB 연결 실패·vector 누락 시 503 응답 | 4 |

자동 테스트는 환경변수와 DB 검사 함수를 대체해 실행합니다.
실제 DB 연결이나 CLAP 모델·음원·가중치가 필요하지 않으며, 모델 추론 성공을 검증하지 않습니다.
Compose로 컨테이너를 실행할 때는 `.env`의 `DB_PASSWORD`가 필요합니다.
이 테스트는 팀원이 설정과 API 코드를 변경한 뒤 재실행하는 공용 검증 코드입니다.

실제 DB와 pgvector는 아래 명령으로 별도 확인합니다.
컨테이너에 전달된 환경변수를 사용하며 성공 시 종료 코드 0, 실패 시 1을 반환합니다.

```powershell
docker compose exec -T ai python -m scripts.check_database
```

기존 컨테이너에서 `No module named pytest` 또는 `tests` 경로 오류가 발생하면
최신 개발 설정으로 다시 빌드·생성한 뒤 테스트를 실행하세요.

```powershell
docker compose up -d --build
docker compose exec -T ai python -m pytest tests -q
```

2026-09-30 검증 결과: 자동 테스트 **9개 통과**, 실제 `/health/live`와
`/health/ready` 정상 응답, DB 검사에서 pgvector **0.8.6** 확인.
테스트 실행 시 Starlette TestClient의 `httpx` 사용에 대한 deprecation 경고 1개가 있었으며 실패는 없었습니다.
검증 당시 기존 컨테이너에는 테스트 의존성과 폴더가 없어 개발 패키지 설치 및 테스트 폴더 복사 후 실행했습니다.
위 `--build` 안내는 새 개발 환경을 구성하는 절차이며, 전체 이미지 재빌드는 이번 검증에서 실행하지 않았습니다.

### 로컬 Python 실행

Python 3.11을 권장합니다. 프로젝트 루트에서 실행하세요.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.test_embedding
```

실행 전에 `samples/sample.wav`를 준비하세요. 첫 모델 실행 시 가중치가 자동으로 다운로드됩니다.
기존 가상환경의 Python 경로가 없다는 오류가 나면 Python 3.11을 설치하거나 복구한 뒤 가상환경을 다시 생성해야 합니다.

현재 코드는 Microsoft의 `msclap`을 사용합니다. `requirements.txt`는 전체 환경의
설치 목록 대신 프로젝트의 직접 의존성을 선언하며, 하위 의존성은 pip가 설치합니다.
전체 버전을 고정한 lock 파일은 아닙니다.

로컬에서 자동 테스트를 실행하려면 개발 의존성도 설치하세요.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

로컬 Python은 `.env`를 자동으로 읽지 않습니다. 실제 DB 검사 시에는
현재 셸에 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` 등을 설정해야 합니다.
호스트에서 로컬 DB에 접속한다면 `DB_HOST=localhost`를 사용합니다.

현재 실행 스크립트는 모델을 직접 로드하는 수동 확인용이며 자동 단위 테스트가 아닙니다.
이 문서의 실행 안내는 기존 코드 기준이고, 이번 저장소 구조 정리가 추론 성공을 보증하지는 않습니다.
