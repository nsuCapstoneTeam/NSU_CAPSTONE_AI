# NSU_CAPSTONE_AI

> 2026-10-07의 전체 결과 반환 흐름은 당시 제안 이력입니다. 현재 추천 정책은 [Accepted 012](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba)에 따릅니다. Spring은 전체 통과 ACTIVE 후보 쌍을 전달하고 AI는 최대 100곡을 반환합니다. 입력 후보 상한은 NSUAI-15 실측 후 결정합니다. 상세 기준은 [현재 AI 작업 기준](docs/api/CLAP_RECOMMENDATION_DIRECTION.md)을 참고하세요.


아티스트–행사 매칭 플랫폼의 Python AI 서버입니다. Microsoft MSCLAP 기반 음악·텍스트와
음악·음악 유사도, 파일 검색 CLI, FastAPI Health Check, PostgreSQL + pgvector 준비 상태 검사를 다룹니다.

Phase A Dataset 준비, 실제 6곡 MSCLAP 생성 경로 검증, 전용 PostgreSQL/pgvector 통합 검증을 완료했습니다.
다음은 기존 개발 벡터의 소유권·대상과 새 입력 mapping을 확인하는 단계입니다. 기존 벡터 삭제·재생성은 별도 승인 전에는 수행하지 않습니다.
현행 서비스 흐름은 Spring Eligibility가 통과한 전체 ACTIVE 후보 쌍 전달 → AI raw cosine 정렬·최대 100곡 반환 → Spring의 순서 유지·응답 검증·템플릿 설명입니다. 입력 후보 상한은 NSUAI-15의 성능·메모리·동시성 실측 후 결정합니다.
업무 HTTP API, 입력 해석 및 BPM/Rhythm 상세 분석은 후속 구현이며, AI가 별도 설명 API를 제공하는 흐름은 아닙니다. 0~100 표시 변환은 calibration 실험 후 결정합니다.

## 구현 상태

| 항목 | 상태 |
| --- | --- |
| Health Check·DB/pgvector 준비 상태 | 구현 |
| MSCLAP 2023 CPU 임베딩·유사도 | 구현·FMA 실측, Audio/Text 1024차원 확인 |
| FMA 다운로드·체크섬·표본 선정·측정 보고서 | 구현 |
| 긴 문장의 토큰 제한과 실제 입력 기록 | 검증 스크립트에 구현 |
| 한국어 → 영어 변환 | 입력 정책 확정, 번역 기능 구현 전 |
| Embedding 동기 생성·pgvector 저장 | Audio 테이블·동기 저장 CLI 구현, 임시 ID 계약, Text·백엔드 연동 전 |
| 음악 입력 후 동기 처리 | AI 선설계·동기 방향 확정, 업무 API 구현 전 |
| 공통 Audio 임베딩 생성 | 파일 해시 기반 전처리·벡터 검증·메타데이터 반환, 검색 CLI 연결 |
| 음악 파일로 후보 곡 검색 | CLI 구현, 원본 코사인 순위·음악 간 임시 0~100점 반환 |
| DB 저장 임베딩으로 후보 곡 검색 | 호환 조건 필터·동일 파일 제외·pgvector 정확 검색 CLI 구현 |
| 임시 유사도 표시 점수 | 음악↔텍스트 0~0.4 / 음악↔음악 0~1, 최종 기준 검증 필요 |
| BPM/Rhythm 상세 분석·구조화된 추천 근거 | 후속 구현; 추천 이유는 Accepted 012에 따라 Spring 템플릿 책임이며 별도 AI Explanation API는 사용하지 않음 |
| 전체 ACTIVE 후보 입력·최대 100곡 결과 반환 | Accepted 012 정책 반영; 업무 HTTP API 구현 전; 입력 후보 상한은 NSUAI-15 실측 후 결정; Spring 순서 유지·아티스트 집계/후보 비교 설명 제외 |
| 분석·매칭 HTTP API·Spring Boot 연동 | 후속 구현 |

분류 코드의 softmax는 라벨 사이의 상대점수이며 행사 적합도 백분율이 아닙니다.
MSCLAP의 배율 적용 유사도와 순수 cosine도 구분합니다.

음악 파일 검색 실행 방법은 [음악 검색 안내](docs/guides/AUDIO_SEARCH.md),
임시 점수 기준은 [정규화 안내](docs/guides/SEMANTIC_SCORE_NORMALIZATION.md)를 참고하세요.
공통 생성 함수와 반환 정보는 [Audio 임베딩 안내](docs/guides/AUDIO_EMBEDDING.md)를 참고하세요.
테이블 생성·음악 파일 저장·처리 이유는 [임베딩 저장 안내](docs/guides/EMBEDDING_STORAGE.md)를 참고하세요.
저장된 후보 벡터로 검색하는 방법은 [DB 음악 검색](docs/guides/DATABASE_AUDIO_SEARCH.md)을 참고하세요.
음악 입력 처리의 동기 방향과 AI 선설계 결정은 [ADR 0006](docs/adr/ADR-0006-asynchronous-audio-processing.md)에 기록했습니다.
현재 검색은 곡 단위 개발 CLI입니다. 기본 Top5와 `--top-k`는 CLI 검증 설정이며, 서비스의 최대 100곡 반환 흐름은 아직 구현되지 않았습니다.

2026-10-04 [백엔드 연동 결정](docs/api/AUDIO_SYNC_BACKEND_HANDOFF.md): revision별 v1·v2 벡터를
함께 보관하고 Backend ACTIVE 전환 커밋 확인 후 이전 벡터를 정리합니다.
AI 상태 조회·stale 재처리·ACTIVE revision 쌍 검색은 구현 전입니다.
현행 목표는 전체 통과 ACTIVE 후보 쌍을 입력받아 raw cosine으로 정렬하고 최대 100곡을 반환하는 것입니다. Spring은 순서를 유지하며 Reliability·Risk Signal은 별도 표시합니다. 입력 후보 상한은 NSUAI-15 실측 후 정합니다.
점수·누락 점수·오류의 현행 Accepted 정책은 [작업 기준](docs/api/CLAP_RECOMMENDATION_DIRECTION.md)에 기록합니다.

## 과거 구현 변경 기록 (PR #28 이후 Audio 저장·검색)

당시 비교 기준: 로컬 main
[`a86be58`](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/commit/a86be58d9db19dcf2d767f117cf083c63ecc48aa) (PR #28 병합).
FMA 검증 도구·영어 입력 정책·음악 파일 검색·임시 점수 변환은 이미 main에 포함되어 있습니다.

| 영역 | main | 이번 변경 |
| --- | --- | --- |
| Audio 생성 | 검색 도구 내부 처리 | 저장·검색 공통 생성기, 파일 해시 기반 전처리·벡터 검증 |
| 임베딩 저장 | 없음 | pgvector 테이블·체크섬 마이그레이션·동기 저장·중복/충돌 검사 |
| DB 후보 검색 | 파일 목록 기반 검색 | 저장 벡터의 호환 조건 필터·동일 원본 제외·Top5 정확 검색 |
| 파일 구조 | scripts·tests 루트 중심 | 기능별 하위 폴더, 명령·import·문서 경로 갱신 |
| 연동 계약 | 미구현 | AI 선설계·동기 계약 초안, 백엔드 검토 전 |
| 검증 근거 | Phase 2 음악 검색 실험 | DB 통합 테스트·실제 6곡 후보의 Torch/pgvector 결과 비교 |

기준 main의 Dockerfile·CPU 패키지 고정·모델 로딩 검사 동작은 유지하고 주석을 보완했습니다.
긴 입력 수정은 `scripts/fma/validate_fma.py`에 적용되며 서비스용
`ClapModel.encode_text`에 번역·축약 처리를 연결한 것은 아닙니다.

## 음악 파일 검색

### 현재 사용 조건

현재 `search_audio.py`를 실행하려면 query Audio와 manifest의 모든 candidate Audio가 각각
**60~80초(양 경계 포함)**여야 합니다. 생성기는 ADR-0007 정책에 따라 처음 56초를 7초씩
8개의 겹치지 않는 구간으로 처리하고, Chunk별 L2 정규화 → Mean Pooling → 최종 L2
정규화로 대표 Embedding 하나를 만듭니다.

Phase A에서 별도 6곡·60초 fixture를 준비했습니다. 실제 MSCLAP 및 PostgreSQL 새 정책 검증은 아직 미완료입니다.
Phase A manifest는 검색 후보 manifest와 형식이 다르므로 직접 전달하지 않습니다. 검색 절차와 입력 형식은 [사용 안내](docs/guides/AUDIO_SEARCH.md)를
참고하세요.

### Historical FMA PoC

30초 FMA·단일 crop 실험의 [핵심 조건·결과·한계](docs/experiments/audio-search-phase2/README.md)를 보존합니다.
원본·manifest·상세 산출물은 Cleanup으로 삭제하며 완전 재현은 지원하지 않습니다. 현재 8-Chunk 검증과 구분합니다.

당시 결과와 평가 근거는 [Phase 2 실험 기록](docs/experiments/audio-search-phase2/README.md)에,
현재 입력 요건과 구분은 [검색 가이드](docs/guides/AUDIO_SEARCH.md)에 보존되어 있습니다.

## 이번 음악 검색·점수 실험

- 음악↔텍스트: 기존 256조합 중 96개 청취 평가로 세 가지 변환 후보를 비교하고
  임시 0~0.4 기준을 선택했습니다. 기존 test 자료를 사용한 탐색이며 독립 검증이 아닙니다.
- 음악↔음악: 기존 80곡과 중복 없는 validation 24곡의 276쌍을 측정했습니다.
  코사인 범위는 0.04977~0.93937, 중앙값은 0.53068입니다.
- 상한 0.4라면 215/276쌍(약 78%)이 100점이 되어, 음악 간 표시 상한은 1로 분리했습니다.
- 8개 기준 음악 × 후보 3곡 청취 평가: 비슷함 5개 평균 72.75점,
  애매함 8개 63.22점, 다름 11개 49.60점입니다. 평가자 1명이며 범위가 겹칩니다.
- 실제 사용자 음악 검색: 24곡에서 TOP 5 반환을 확인했습니다. 1위는 64.27점이며
  사용자는 다소 비슷하지만 애매하다고 판단했습니다. 정식 청취 평가에는 합산하지 않았습니다.

선형 변환은 모델 판별력을 개선하지 않습니다. 음악 간 순위는 원본 코사인으로 계산하며,
현재 장르 정보는 점수 계산에 넣지 않습니다. BPM·리듬 특징도 별도로 추출하지 않습니다.
검색 CLI와 쌍별 실험은 crop seed 방식이 달라 값이 정확히 일치하지 않을 수 있습니다.
[전체 근거·한계·재현 명령](docs/experiments/audio-search-phase2/README.md)을 참고하세요.

## 실험 결과와 결정 근거

2026-10-02 KST, MSCLAP 2023 / CPU / seed 42 / FMA 공식 test split 기준입니다.
Python 3.11, msclap 1.3.3, torch·torchaudio 2.1.2+cpu, transformers 4.35.2를 사용했습니다.

| 실험 | 곡 | 문장 | 비교 | 실패 |
| --- | ---: | ---: | ---: | ---: |
| 장르 진단 1차 | 16 | 16 | 256 | 0 |
| 장르 진단 확대 | 80 | 16 | 1,280 | 0 |
| 사용자 원문 설명 | 16 | 32 | 512 | 0 |
| 한·영 의미를 맞춘 짧은 설명 | 16 | 32 | 512 | 0 |

원문에는 영어 문장 1개의 의미 불일치와 한국어 16문장의 길이 초과가 있었습니다.
수정본은 최대 65토큰이며 77토큰 제한에 의한 잘림이 없었습니다.

| 수정본 결과 | 한국어 | 영어 |
| --- | ---: | ---: |
| 설명을 작성한 원곡이 1위 | 1/16 | 10/16 |
| 원곡이 상위 3위 | 3/16 | 13/16 |
| 청취 평가 완료 | 3/48 | 48/48 |
| 청취 평가에서 잘 맞음 | 1/3 | 42/48 |
| 애매함 / 안 맞음 | 2 / 0 | 4 / 2 |

한국어 16개 설명은 모두 동일한 세 곡을 상위 후보로 골랐습니다.
영어의 1위 후보는 14/16개 설명에서 잘 맞음으로 평가됐습니다.
이 초기 결과를 근거로 영어 모델 입력을 선택했습니다.

**원곡 검색 지표와 실제 적합성 판단은 다릅니다.** 다른 곡도 설명에 맞을 수 있습니다.
단일 평가자·작은 표본이고 한국어 청취 평가는 대부분 미작성입니다.
영어 설명은 사람이 작성·수정했으므로 자동 번역 성능을 검증한 결과가 아닙니다.
서비스 전체 성능이나 최종 정규화 공식을 확정하는 근거로 일반화하지 않습니다.

- [Historical 실험 조건·검색 결과·청취 평가](docs/experiments/fma-phase2/README.md)
- [입력 언어 정책 ADR](docs/adr/ADR-0004-korean-input-english-msclap.md)

## 설치·서버 실행

Docker Desktop을 켜고 기존 PostgreSQL + pgvector DB를 별도로 실행합니다.
처음 설정할 때만 아래처럼 복사합니다. 기존 `.env`는 덮어쓰지 마세요.

```powershell
Copy-Item .env.example .env
notepad .env
docker compose config --quiet
docker compose up -d
```

`DB_PASSWORD`, `DB_USER`, `DB_NAME`, `DB_PORT`는 기존 DB 설정과 맞춥니다.
Windows Docker Desktop에서 호스트 DB에 연결할 때 `DB_HOST=host.docker.internal`을 사용합니다.

| 설정 | 기본값 | 용도 |
| --- | --- | --- |
| DB_HOST / DB_PORT | host.docker.internal / 5432 | PostgreSQL 연결 |
| DB_NAME / DB_USER | capstone_db / capstone | DB 이름·사용자 |
| DB_PASSWORD | 필수 | DB 비밀번호 |
| DB_CONNECT_TIMEOUT | 3 | 연결 제한 시간(초) |
| AI_PORT | 8000 | 로컬 서버 포트 |

Compose는 GHCR 이미지를 사용하므로 `up --build`만으로 로컬 Dockerfile을 빌드하지 않습니다.
로컬 변경으로 개발 이미지를 다시 만들 때는 다음 명령을 사용합니다.

```powershell
docker build -t ghcr.io/nsucapstoneteam/nsu-capstone-ai:phase1 .
docker compose up -d --force-recreate
```

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
docker compose exec -T ai python -m scripts.database.check_database
```

`live`는 서버 응답, `ready`는 DB 연결·vector 확장을 확인합니다.
DB 장애나 확장 누락이면 ready는 503이며 Docker healthy는 live 기준입니다.
API 문서는 `http://localhost:8000/docs`에서 확인합니다.

## FMA Historical 근거

[FMA Historical 안내](docs/guides/FMA_VALIDATION.md)에서 보존된 실험 보고서와 현재 Phase A 경로를 확인합니다.
다운로드·측정 코드와 모델 캐시 연결은 유지하지만 삭제한 입력을 사용하는 실행 예제는 제공하지 않습니다.

## 자동 테스트

```powershell
docker compose run --rm --no-deps ai python -m pytest tests -q
```

설정·Health Check·FMA 표본 선정·검증 입력 처리를 검사합니다.
모델 가중치·음원·실DB는 필요하지 않으며 실제 추론 실험과 구분합니다.
공통 Audio 생성·음악 검색·임시 정규화·저장과 실제 DB 검사까지 포함해
`RUN_EMBEDDING_DB_TESTS=1`로 **98개 통과**, Starlette TestClient deprecation 경고 1개를 확인했습니다.
기본 실행에서는 실제 DB 테스트 16개를 건너뜁니다.

로컬 Python 3.11을 쓰려면 CPU 패키지를 먼저 설치합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.1.2+cpu torchaudio==2.1.2+cpu torchvision==0.16.2+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest tests -q
```

## 파일 구성

서비스 코드는 `app/`의 책임별 계층을 유지하고, 실행 도구와 테스트는 기능별 폴더로 나눴습니다.
전체 파일 역할은 [개발 도구 목록](scripts/README.md), [테스트 목록](tests/README.md),
[문서 목록](docs/README.md)에서 확인할 수 있습니다.
실행 도구 이동에 따라 `python -m scripts.<기능>.<모듈>` 형식으로 명령을 변경했습니다.

| 경로 | 용도 |
| --- | --- |
| app/ | FastAPI, DB 준비 상태, MSCLAP wrapper·분류 |
| scripts/database/check_database.py | DB/pgvector 읽기 전용 검사 |
| scripts/embedding/check_msclap.py | main의 모델 로딩 검사 |
| scripts/embedding/check_audio_embedding.py | 샘플 오디오 Embedding 검사 |
| scripts/fma/download_fma.ps1 | ZIP 다운로드·SHA-1·압축 해제 |
| scripts/fma/validate_fma.py | 표본 선정·임베딩·유사도 측정 |
| app/matching/ | 임시 점수 변환·음악 간 코사인·순위 계산 |
| app/repository/ | Audio 임베딩 저장·버전 관리 SQL |
| app/embedding/storage.py | 공통 생성과 DB 트랜잭션 연결 |
| scripts/database/migrate_embeddings.py | AI 스키마·테이블의 명시적 생성 |
| scripts/embedding/store_audio_embedding.py | 외부 음악 ID·파일 경로로 동기 저장 |
| scripts/matching/search_audio.py | 음악 파일을 입력받는 후보 곡 검색 CLI |
| scripts/matching/search_database_audio.py | DB에 저장된 후보 벡터로 검색하는 CLI |
| scripts/matching/validate_audio_similarity.py | 음악 간 쌍별 유사도 재측정 |
| tests/ | 데이터 없는 자동 테스트 |
| docs/experiments/fma-phase2/ | 공유용 실험 근거, 음원 제외 |
| docs/experiments/audio-search-phase2/ | 정규화·음악 검색의 공유용 근거, 음원 제외 |
| docs/adr/ | 기술 결정·미확정 사항 |
| compose.fma.yaml | FMA 데이터·모델 캐시 연결 |
| datasets/fma/huggingface/ | 공유 MSCLAP/GPT-2 모델 캐시, Git 제외 |

## 관련 자료와 다음 작업

- [NSUAI-1](https://linear.app/nsu-capstone/issue/NSUAI-1), [NSUAI-2](https://linear.app/nsu-capstone/issue/NSUAI-2): CLAP 의미 유사도·정규화
- [개발 로드맵](docs/AI_DEVELOPMENT_ROADMAP.md)
- [API 책임 경계](docs/api/README.md)
- [협업 가이드](docs/협업-가이드/README.md)

현재 다음 작업은 Phase 3의 다른 Dataset 60~80초 입력 준비 → 실제 음악 품질·PostgreSQL 통합 검증 → 개발 벡터 재생성 → 새 generation 기반 저장·검색 확인입니다.
백엔드 ID·수정/삭제 계약, Text 생성·번역, Accepted 항목 점수·곡별 설명과 전체 통과 곡 반환/API 연동은 Roadmap의 의존 순서에 따라 진행합니다.
기존 30초 FMA의 핵심 실험 근거만 Markdown으로 유지하며 새 생성 정책 검증에 사용하지 않습니다.
최종 점수와 더 큰 후보 집합의 검색 품질은 추가 검증이 필요하며 번역 구현은 보류합니다.
