# NSU_CAPSTONE_AI

아티스트–행사 매칭 플랫폼의 Python AI 서버입니다. Microsoft MSCLAP 기반 음악·텍스트와
음악·음악 유사도, 파일 검색 CLI, FastAPI Health Check, PostgreSQL + pgvector 준비 상태 검사를 다룹니다.

현재는 **Phase 2 모델 단독 검증** 단계입니다. FMA 실험 결과를 근거로
**한국어 요청 → 영어 변환 → MSCLAP** 입력 정책을 확정했습니다.
번역 방식·구현은 미정으로 보류합니다. 임시 점수 변환과 곡 단위 검색 CLI까지 구현했고,
서비스용 Embedding 저장, BPM·리듬 분석, 최종 종합 점수와 매칭 API는 후속 작업입니다.

## 구현 상태

| 항목 | 상태 |
| --- | --- |
| Health Check·DB/pgvector 준비 상태 | 구현 |
| MSCLAP 2023 CPU 임베딩·유사도 | 구현·FMA 실측, Audio/Text 1024차원 확인 |
| FMA 다운로드·체크섬·표본 선정·측정 보고서 | 구현 |
| 긴 문장의 토큰 제한과 실제 입력 기록 | 검증 스크립트에 구현 |
| 한국어 → 영어 변환 | 입력 정책 확정, 번역 기능 구현 전 |
| Embedding 동기 생성·pgvector 저장 | 후속 구현 |
| 음악 파일로 후보 곡 검색 | CLI 구현, 원본 코사인 순위·음악 간 임시 0~100점 반환 |
| 임시 유사도 표시 점수 | 음악↔텍스트 0~0.4 / 음악↔음악 0~1, 최종 기준 검증 필요 |
| 종합 매칭 점수·아티스트 TOP 5·추천 이유 | 후속 구현 |
| 분석·매칭 HTTP API·Spring Boot 연동 | 후속 구현 |

분류 코드의 softmax는 라벨 사이의 상대점수이며 행사 적합도 백분율이 아닙니다.
MSCLAP의 배율 적용 유사도와 순수 cosine도 구분합니다.

음악 파일 검색 실행 방법은 [음악 검색 안내](docs/AUDIO_SEARCH.md),
임시 점수 기준은 [정규화 안내](docs/SEMANTIC_SCORE_NORMALIZATION.md)를 참고하세요.
현재 검색은 곡 단위이며 아티스트 TOP 5나 최종 종합 매칭 API는 아닙니다.

## 최신 main 대비 추가·수정

비교 기준: 2026-10-02 확인한 main
[`e24a120`](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/commit/e24a120784fb4e5e4208f2eecc8310fbfbf92cd7).
기존 FMA 다운로드·음악/텍스트 검증 도구와 영어 입력 정책은 이미 main에 포함되어 있습니다.

| 영역 | main | 이번 변경 |
| --- | --- | --- |
| 점수 변환 | 최종 방식 미구현 | 음악·텍스트 비교 방식에 따른 임시 상한 분리 |
| 음악 파일 검색 | 없음 | 동일 파일 제외·코사인 정렬·TOP 5 JSON CLI |
| 음악 간 검증 | 없음 | 새 validation 24곡·276쌍 재현 도구 |
| 실험 근거 | 기존 음악·텍스트 실험 | 정규화 후보 비교·음악 간 측정·청취 평가 24개 |
| 번역 | 입력 정책만 확정 | 공급자·구현은 미정으로 보류 |

최신 main의 Dockerfile·CPU 패키지 고정·모델 로딩 검사 코드는 유지했습니다.
긴 입력 수정은 `scripts/validate_fma.py`에 적용되며 서비스용
`ClapModel.encode_text`에 번역·축약 처리를 연결한 것은 아닙니다.

## 음악 파일 검색 사용법

FMA 데이터를 별도로 준비하고 `samples/reference.mp3`에 검색할 음악을 넣습니다.
프로젝트 루트에서 실행하며 Compose 설정을 위해 `.env`의 `DB_PASSWORD`가 필요합니다.
검색은 DB에 접속하지 않고 공유한 검증용 후보 24곡을 사용합니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.search_audio --audio samples/reference.mp3 --manifest docs/experiments/audio-search-phase2/manifest24.json --output datasets/fma/results/search-reference-new.json
```

결과 JSON은 곡 ID·원본 코사인·표시 점수·순위를 반환합니다. 출력은 덮어쓰지 않으므로
반복 실행 시 새 이름을 사용하세요. 동일 파일은 SHA-256으로 제외합니다.
현재 점수는 내부 검증용 지표이고, 사용자에게 보여줄 최종 적합도는 미확정입니다.
자체 후보 목록과 공개 FMA 음원 예시는 [사용 안내](docs/AUDIO_SEARCH.md)에 있습니다.

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

- [실험 기록·재현 방법](docs/experiments/fma-phase2/README.md)
- [공유용 입력 JSON](docs/experiments/fma-phase2/manifest16-descriptions.json)
- [설명별 순위](docs/experiments/fma-phase2/rankings.csv)
- [입력 언어 정책 ADR](docs/adr/0004-korean-input-english-msclap.md)

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
docker compose exec -T ai python -m scripts.check_database
```

`live`는 서버 응답, `ready`는 DB 연결·vector 확장을 확인합니다.
DB 장애나 확장 누락이면 ready는 503이며 Docker healthy는 live 기준입니다.
API 문서는 `http://localhost:8000/docs`에서 확인합니다.

## FMA 검증 실행

전체 절차는 [FMA 검증 가이드](docs/FMA_VALIDATION.md)에 있습니다.
데이터·모델 캐시는 Git에서 제외됩니다. 모델 검증은 DB에 접속하지 않지만
Compose 설정 평가를 위해 `.env`의 `DB_PASSWORD` 값은 필요합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_fma.ps1
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.validate_fma prepare --metadata datasets/fma/fma_metadata/tracks.csv --audio-root datasets/fma/fma_small --per-genre 10 --seed 42 --manifest datasets/fma/manifests/manifest80-new.json
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.validate_fma run --manifest datasets/fma/manifests/manifest80-new.json --output datasets/fma/results/genre80-new
```

manifest와 output은 새로운 이름을 사용합니다. 기존 결과를 덮어쓰지 않습니다.
0–100 기준 조정에는 validation split을 사용하고, test 결과에 맞춰 조정하지 않습니다.
샘플만 확인하려면 `samples/sample.wav`를 준비하고
`python -m scripts.check_audio_embedding`을 실행합니다.

## 자동 테스트

```powershell
docker compose run --rm --no-deps ai python -m pytest tests -q
```

설정·Health Check·FMA 표본 선정·검증 입력 처리를 검사합니다.
모델 가중치·음원·실DB는 필요하지 않으며 실제 추론 실험과 구분합니다.
음악 검색·임시 정규화까지 포함한 **46개 통과**, Starlette TestClient deprecation 경고 1개를 확인했습니다.

로컬 Python 3.11을 쓰려면 CPU 패키지를 먼저 설치합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.1.2+cpu torchaudio==2.1.2+cpu torchvision==0.16.2+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest tests -q
```

## 파일 구성

| 경로 | 용도 |
| --- | --- |
| app/ | FastAPI, DB 준비 상태, MSCLAP wrapper·분류 |
| scripts/check_database.py | DB/pgvector 읽기 전용 검사 |
| scripts/check_msclap.py | main의 모델 로딩 검사 |
| scripts/check_audio_embedding.py | 샘플 오디오 Embedding 검사 |
| scripts/download_fma.ps1 | ZIP 다운로드·SHA-1·압축 해제 |
| scripts/validate_fma.py | 표본 선정·임베딩·유사도 측정 |
| app/matching/ | 임시 점수 변환·음악 간 코사인·순위 계산 |
| scripts/search_audio.py | 음악 파일을 입력받는 후보 곡 검색 CLI |
| scripts/validate_audio_similarity.py | 음악 간 쌍별 유사도 재측정 |
| tests/ | 데이터 없는 자동 테스트 |
| docs/experiments/fma-phase2/ | 공유용 실험 근거, 음원 제외 |
| docs/experiments/audio-search-phase2/ | 정규화·음악 검색의 공유용 근거, 음원 제외 |
| docs/adr/ | 기술 결정·미확정 사항 |
| compose.fma.yaml | FMA 데이터·모델 캐시 연결 |
| datasets/fma/ | 로컬 데이터·결과·평가 페이지, Git 제외 |

## 관련 자료와 다음 작업

- [NSUAI-1](https://linear.app/nsu-capstone/issue/NSUAI-1), [NSUAI-2](https://linear.app/nsu-capstone/issue/NSUAI-2): CLAP 의미 유사도·정규화
- [개발 로드맵](docs/AI_DEVELOPMENT_ROADMAP.md)
- [API 책임 경계](docs/api/README.md)
- [협업 가이드](docs/협업-가이드/README.md)

다음은 Phase 3 서비스용 Embedding 생성·pgvector 저장입니다. 이후 BPM·리듬 분석,
항목별 점수 통합, 아티스트 TOP 5·설명, API 연결 순서로 진행합니다.
최종 점수와 더 큰 후보 집합의 검색 품질은 추가 검증이 필요하며 번역 구현은 보류합니다.
