# DB에 저장된 음악으로 Top5 검색

## 새 ADR-0007 개발/검증의 입력 선행조건

FMA Historical PoC의 핵심 실험 근거는 Markdown으로 보존하고, 원본·manifest·상세 결과는 2026-10-09 Cleanup에서 삭제한다.
새 개발/검증에는 **FMA와 다른 Dataset의 60~80초(양 경계 포함) 입력**을 사용한다.
[Phase A](../experiments/audio-highlight-phase-a/README.md)의 6곡·60초 fixture와 Phase A 범위 출처·라이선스 확인은 완료됐다. 실제 MSCLAP real-music 검증과 새 정책 PostgreSQL 통합 검증은 아직 미완료다.
기존 FMA를 임의 반복·padding해서 새 검증 입력으로 바꾸지 않는다.

다른 Dataset의 권리·길이 확인 → 새 생성 규칙/metadata 검증 → 개발 벡터 대상·새 입력 매핑 확인 →
개발/테스트 벡터 삭제·재생성 → 저장/검색 검증 순서를 따른다.
적격 입력을 준비하기 전에 기존 벡터를 삭제하지 않는다.
세부 의존 순서는 [Roadmap Phase 3](../AI_DEVELOPMENT_ROADMAP.md)을 따른다.
ADR-0007의 정책·Decision은 그대로이며 Dataset 절차는 Roadmap/Guide에서 관리한다.


현재 DB 검색은 query 음악도 저장 시와 같은 공통 AudioEmbeddingGenerator로 생성합니다.
60~80초 validation 후 처음 56초를 7초 × 8개 non-overlap Chunk로 나누고,
MSCLAP batch Embedding → Chunk L2 → Mean Pooling(N=8) → Final L2 순서로
단일 대표 벡터를 만듭니다. 아래 실제 검증 결과와 저장된 개발 벡터는 이전 generation의 historical 기록입니다.

2026-10-07 사용자 결정의 후속 목표는
ACTIVE (music_id, audioRevision) 쌍을 대상으로 전체 곡 유사도를 계산·정렬해 전체 결과를 Spring에 반환하는 것이다.
Spring은 유사도 순으로 곡을 표시하고 사용자가 별도 버튼으로 해당 Artist와 매칭한다. 아티스트 집계는 하지 않는다.
이 목표는 Linear Accepted로 이미 정합화된 계약이 아니며 [작업 기준](../api/CLAP_RECOMMENDATION_DIRECTION.md)에서 차이를 확인한다.
revision 후보 제한·결과 revision 반환은 아직 미구현이다.
현재 기본 Top5·실험 수치는 변경하지 않는다. [연동 계약](../api/AUDIO_SYNC_BACKEND_HANDOFF.md)을 참고한다.

음악 파일을 입력으로 받아 PostgreSQL에 저장된 Audio 임베딩 후보와 비교합니다.
검색 입력은 공통 생성기로 한 번 임베딩하고, 후보 파일은 다시 읽거나 추론하지 않습니다.
현재는 곡 단위 CLI이며 백엔드 API·아티스트 집계·행사 종합 적합도는 포함하지 않습니다.

## 처리 흐름과 이유

```text
행사 관계자의 음악 파일
 → 공통 AudioEmbeddingGenerator.generate()
 → 읽기 전용 DB 트랜잭션
 → 호환되는 등록 음악의 벡터만 선택
 → 입력 파일과 SHA-256이 같은 행 제외
 → pgvector 코사인 거리 계산·정렬
 → 상위 5곡과 임시 표시 점수 반환
```

서비스 흐름을 가정하면 후보는 아티스트가 등록해 저장한 음악입니다.
현재 개발 DB의 `dev-*` 음악 ID는 검증용이며 실제 백엔드 음악 등록과 연결하지 않았습니다.

`app/matching/database_audio_search.py`는 입력 생성·DB 호출·점수 반환을 연결합니다.
`app/repository/embedding_repository.py`의 `search()`는 후보 선택과 SQL 계산을 담당합니다.
`scripts/matching/search_database_audio.py`는 CLI 인자·출력·실패 종료 코드를 담당합니다.

### 후보의 생성 조건 확인

저장과 검색에서 모델, 모델 버전, checkpoint revision, 패키지 버전,
전처리 버전·내용, dimension, dtype, device가 일치해야 합니다.
동일 차원이라고 해서 다른 모델의 벡터를 비교하지 않습니다.
generation profile은 모든 고정 생성 조건을 그대로 비교합니다. source SHA-256과 원본 길이는
파일별 metadata이며 공통 profile 호환 조건이 아닙니다.
revision이 확인되지 않은 체크포인트는 기존 생성기의 한계가 그대로 적용됩니다.
파일 경로나 원본 음악 파일의 존재 여부는 DB 후보 검색에 필요하지 않습니다.

SQL은 호환 후보를 `MATERIALIZED` CTE로 먼저 확정합니다. 차원이 다른 벡터가
거리 계산에 들어오는 것을 막기 위해서입니다. 후보 수와 순위도 한 SQL 스냅샷에서 계산합니다.

### 순위와 표시 점수

pgvector의 `<=>` 코사인 거리에서 `1 - 거리`로 원본 유사도를 계산합니다.
가까운 거리부터 정렬하며 동점은 음악 ID의 C collation 순서로 고정합니다.
부동소수점 오차는 이론 범위 -1~1로 제한합니다. 표시 점수는 기존 공통 함수를 사용해
음악 간 임시 하한 0·상한 1을 적용합니다. 표시 점수가 아니라 원본 거리로 순위를 정합니다.
이 점수는 비슷함의 확률이나 행사 적합도가 아닙니다.

현재는 근사 검색 인덱스 없이 호환 후보 전체를 비교하는 정확 검색입니다.
작은 후보 목록의 정확성을 먼저 검증하기 위한 방식이며 대규모 성능은 검증하지 않았습니다.
후보 수가 증가하면 필터·차원별 인덱스를 별도로 설계해야 합니다.

### 동일 파일과 빈 목록

입력과 SHA-256이 같은 후보는 ID·파일명이 달라도 모두 제외합니다.
같은 음악을 자기 자신에게 추천하지 않기 위한 처리입니다.
후보가 5곡 미만이면 실제 후보 수만 반환합니다.
후보가 없으면 오류를 만들거나 가짜 결과를 채우지 않고 아래처럼 반환합니다.

```json
{"status": "no_candidates", "candidate_count": 0, "results": []}
```

DB가 비어 있는 경우와 모든 후보가 비호환·동일 파일인 경우는 이 단계에서 같은 상태입니다.
검색 입력은 DB에 저장하지 않습니다. 트랜잭션도 읽기 전용입니다.

## 실행 방법

먼저 [임베딩 저장 안내](EMBEDDING_STORAGE.md)에 따라 테이블을 생성하고 후보 음악을 저장합니다.

```powershell
docker compose run --rm --no-deps ai python -m scripts.database.migrate_embeddings
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.embedding.store_audio_embedding --music-id dev-music-002 --audio samples/candidate.mp3
```

검색할 음악을 `samples/reference.mp3`에 넣고 실행합니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.matching.search_database_audio --audio samples/reference.mp3
```

옵션으로 TopK(1~100, 기본 5)와 새로운 결과 파일을 지정할 수 있습니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.matching.search_database_audio --audio samples/reference.mp3 --top-k 5 --output /workspace/datasets/audio-search-results/search-database-new.json
```

이 예제의 `compose.fma.yaml`은 host의 `./datasets`를 `/workspace/datasets`에 쓰기 가능하게 mount합니다.
결과는 host의 `datasets/audio-search-results/`에 저장되어 `run --rm` 종료 후에도 남습니다.
CLI가 결과 폴더를 생성하며, 이 로컬 결과 디렉터리는 Git에서 제외됩니다.

출력 파일은 덮어쓰지 않습니다. `candidate_count`는 조건이 맞고 동일 파일 제외를 마친
전체 후보 수이며 `results`에는 `music_id`, `cosine_similarity`, `audio_similarity_score`, `rank`가 있습니다.
음악 제목·아티스트·재생 URL은 향후 백엔드 음악 정보와 연결해야 합니다.
DB 접속·SQL 오류와 모델 생성 오류는 실패 상태와 종료 코드 1로 출력합니다.

기존 `scripts.matching.search_audio`는 로컬 manifest 후보를 매번 생성하는 별도 검증 도구로 유지합니다.
DB 검색에는 manifest가 필요 없습니다. 기존 개발 DB·pgvector와 같은 환경을 사용하며
새 테이블·마이그레이션이나 패키지를 추가하지 않았습니다.

## 테스트

```powershell
docker compose run --rm --no-deps -e RUN_EMBEDDING_DB_TESTS=1 ai python -m pytest tests -q
```

현재 테스트는 DB 거리와 Python 코사인의 일치, Top5·TopK, 동점 정렬,
모델·checkpoint revision·generation profile·package·차원 불일치 제외,
동일 파일 복사본 제외, 빈 목록과 적은 후보 수를 검사합니다.
테스트용 행은 트랜잭션 종료 시 롤백합니다.

## 실제 검증 결과

2026-10-03, Docker CPU / PostgreSQL 18 / pgvector 0.8.6에서 전체 테스트 98개가
통과했습니다. 기존 Starlette deprecation 경고 1개가 있습니다.
당시 실제 `reference.mp3`와 FMA 6곡을 기존 단일 crop 공통 생성기로 임베딩한 뒤 DB에 후보를 저장했습니다.
아래는 과거 검증 기록이며 현재 살아 있는 DB 행을 다시 조회한 결과가 아닙니다.
이 30초 FMA 원본들은 새 최소 60초 validation에서 실패하므로 새 방식 재생성 원본으로 사용할 수 없습니다.
검색 입력은 1024차원이며 동일 파일 후보는 제외되었습니다.
호환 후보 6곡 pilot에서 DB와 Torch의 Top5 순위가 모두 일치했고 당시 측정된 원본 코사인의 최대 차이는 약 `1.4543e-7`입니다.
이번 검증은 저장·검색 경로의 수치 일치 확인이며 새로운 추천 품질 평가가 아닙니다.
전체 FMA를 검색하거나 큰 DB의 성능을 측정한 것은 아닙니다.
검증용 후보 6개는 DB에 남겼으며 원본 음악은 Git에 포함하지 않습니다.
[Historical DB 경로 검증 요약](../experiments/audio-search-phase2/README.md#당시-공통-생성기db-경로-검증)을 보존하며 상세 JSON은 삭제했습니다. Cleanup에서 기존 DB 행은 변경하지 않습니다.

FMA 상세 track 목록·pairwise raw cosine·파일 hash·개별 rating·과거 Embedding은 Cleanup에서 의도적으로 제거했습니다. 현재 checkout에는 핵심 실험 조건·집계 결과·결론·한계의 Historical Markdown 요약만 남아 있어 개별 데이터 수준의 재계산/audit이나 완전 재현을 지원하지 않습니다. 이는 현재 checkout의 보존 범위이며 과거 Git history 자체를 삭제했다는 의미는 아닙니다.

FMA Historical 집계는 과거 의사결정 설명용이며 향후 calibration input으로 사용하지 않습니다. 향후 calibration은 ADR-0007 generation policy에 따라 새로 생성한 Embedding·새 similarity distribution·새 evaluation evidence를 기반으로 수행하고, 해당 evidence는 별도로 생성·보존합니다.

구현 근거: [pgvector 공식 문서](https://github.com/pgvector/pgvector)의 코사인 거리·정확 검색 규칙.
