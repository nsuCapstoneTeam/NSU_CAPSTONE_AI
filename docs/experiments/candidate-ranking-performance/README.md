# NSUAI-32 후보 검색 성능·메모리·동시성 측정

## 목적과 범위

2026-11-18, 저장된 synthetic Audio embedding과 준비된 Text embedding으로 NSUAI-30 진단 및 NSUAI-31 ranking의 처리 비용을 측정했다. 운영 최대 후보 수나 성능 SLA를 확정하는 실험이 아니다.

production의 `check_candidate_compatibility()`, `rank_candidates()`, `prepare_text_embedding()`을 무패치 호출한다. cursor 관찰자로 실제 SQL·binding·execute/fetch 시간을 수집하며 검색 SQL을 복제하지 않는다. 하네스의 all-or-nothing 분기는 실험 제어이며 NSUAI-48 HTTP orchestration 구현이 아니다. production 코드·migration·index·OpenAPI·ADR는 변경하지 않았다.

## 환경과 실행 identity

- 기반 commit: `39ee7efab045a06d785bd6e1f0db3a9656a9b085`
- 측정 하네스 SHA-256: `4cb99b1acf2bf2e8ce3d6a7814c4e9bb984d38931eccd78149cb21b5468b659b`
- 측정 당시 하네스는 위 기반 commit에 대한 미커밋 소스였으며 현재 파일 hash와 일치한다.
- 호스트: Windows 11 Home, Intel i7-1165G7 4코어/8논리 CPU, 물리 RAM 약 15.70GiB
- Docker Desktop Linux/WSL2, Engine 29.8.1, VM 메모리 약 7.61GiB
- PostgreSQL 컨테이너: 2 CPU, 2GiB, shared memory 256MiB
- 측정 클라이언트: 2 CPU, 4GiB, torch thread 1
- PostgreSQL 18.6 / pgvector 0.8.6 / Python 3.11.18 / Psycopg 3.3.8 / libpq 18.6
- torch 2.1.2+cpu / NumPy 1.26.4 / profile의 MSCLAP package identity 1.3.3
- DB: max_connections=100, work_mem=4MB, shared_buffers=128MB, statement_timeout=30s, lock_timeout=5s, prepare_threshold=5

상세 환경은 [기본 결과](benchmark-result.json)의 environment와 [컨테이너 관찰](container-observations.json)을 따른다. Docker 집계 memory와 프로세스 RSS는 다른 지표다. 일부 시점의 container memory 관찰은 최대치나 query 전용 메모리를 보장하지 않는다.

## Synthetic dataset과 격리

seed=320, 1024차원 float32, finite·nonzero·L2 normalized Audio vector다. query는 첫 축 단위 벡터다. high/medium/low/negative/random 및 정확히 같은 vector의 tie를 포함한다. 음악 다운로드나 MSCLAP inference는 없다. metadata는 production validation과 호환성 경계를 통과하도록 구성했으며 synthetic임을 기록했다.

기본 scale/concurrency는 요청 pair당 compatible profile 1개다. 기본 DB에는 정상 5,000개와 요청 밖 최고 cosine·다른 revision 행을 포함해 source/embedding 각각 5,002개를 준비했다. 다른 profile·invalid 검증 행은 rollback하여 기본 부하와 섞지 않는다. 별도 profile 부하에서 1,000 pair에 incompatible profile을 추가해 총 3개/5개를 비교했다. 최종 기본 DB 행 수 source 5,002개/embedding 9,002개는 profile 부하 추가 후의 값이다.

전용 benchmark_admin DB가 있는 격리 컨테이너에서 매 실행마다 임의 이름의 임시 DB를 만들고 기존 0001→0002→0003 migration 및 rerun을 확인했다. UUIDv7·PK/UNIQUE/FK/CHECK와 index는 JSON에 보존했다. 데이터 준비·ANALYZE·migration 시간은 latency에서 제외한다. orphan embedding/source-without-embedding은 최종 0개이며 기본·상한 탐색 모두 생성 DB 삭제를 재조회했다. 개발/shared DB는 사용하지 않았다.

## 측정 방법

- 각 scale/mode warm-up 5회. 10~2,000은 30회, 5,000은 3회 안전성 smoke 후 10회 측정했다.
- `perf_counter_ns()`로 NSUAI-30/31 전체, execute/fetch와 나머지 시간을 분리했다. Python remainder는 validation·SQL 구성·serialization·object 생성 등을 포함하며 순수 profile 계산 시간이 아니다.
- percentile은 정렬 표본의 (n−1)q 위치 선형 보간이다. 모든 scale의 p99는 100회 이하 표본의 탐색값이며 안정적 운영 tail latency가 아니다.
- `total`은 두 repository 단계와 진단 선택 시간이다. `total_including_connection`은 관찰한 total+connection+commit+close의 합계이며 모든 외부 코드 구간을 포함한 HTTP end-to-end 시간이 아니다.
- reuse는 연결 재사용, included는 매 요청 새 연결이다. reuse와 prepared statement/cache 조건이 다르므로 모드 차이 전체를 연결 비용으로 해석하지 않는다.
- EXPLAIN과 tracemalloc 실행은 latency 표본과 분리했다.

## 후보 규모별 결과

연결 재사용/profile 1개, 단위 ms. RSS는 반복 종료 후 전체 Python 프로세스의 현재 RSS(MiB)다. 동일 프로세스의 순차 실행이므로 규모별 독립 peak나 요청당 추가 메모리가 아니다.

| 후보 | 반복 | p50 | p95 | p99 | mean | max | RSS MiB | errors |
|---|---|---|---|---|---|---|---|---|
| 10 | 30 | 1.609 | 2.231 | 2.368 | 1.711 | 2.376 | 261.19 | 0 |
| 50 | 30 | 4.120 | 5.272 | 5.562 | 4.207 | 5.567 | 262.79 | 0 |
| 100 | 30 | 6.584 | 8.154 | 9.155 | 6.936 | 9.562 | 263.39 | 0 |
| 500 | 30 | 28.715 | 54.374 | 70.928 | 32.206 | 71.248 | 266.09 | 0 |
| 1000 | 30 | 54.193 | 96.484 | 100.198 | 64.406 | 101.367 | 274.96 | 0 |
| 2000 | 30 | 139.880 | 148.030 | 149.997 | 124.569 | 150.570 | 291.02 | 0 |
| 5000 | 10 | 345.983 | 382.394 | 392.205 | 334.475 | 394.657 | 324.91 | 0 |

### NSUAI-30 / NSUAI-31 및 연결 포함 경로

단위 ms. 두 단계 평균과 included 모드의 관찰구간 합계 p95다.

| 후보 | NSUAI-30 mean | NSUAI-31 mean | included 합계 p95 | connection mean |
|---|---|---|---|---|
| 10 | 1.024 | 0.687 | 12.385 | 5.795 |
| 50 | 2.665 | 1.542 | 15.389 | 5.825 |
| 100 | 4.428 | 2.508 | 18.476 | 5.848 |
| 500 | 22.131 | 10.075 | 68.351 | 5.976 |
| 1000 | 36.267 | 28.139 | 115.858 | 6.000 |
| 2000 | 83.060 | 41.509 | 178.578 | 6.468 |
| 5000 | 218.951 | 115.524 | 528.538 | 6.096 |

원시 nanosecond 표본은 [latency CSV](latency-samples.csv), 구간별 요약은 [JSON](benchmark-result.json)에 있다.

## Profile 수 영향

1,000 후보 고정, compatible 1개를 유지한 채 incompatible profile을 추가했다. reuse, 30회/warm-up 5회, 단위 ms다.

| profile 수 | NSUAI-30 mean | 전체 mean |
|---|---|---|
| 1 | 36.267 | 64.406 |
| 3 | 104.825 | 133.152 |
| 5 | 188.257 | 217.206 |

NSUAI-30은 후보 revision의 모든 profile JSON을 받아 hash·호환성을 검사한다. profile 증가와 함께 비용이 증가했지만 순서·cache·DB 전체 행 수 등의 영향도 있어 엄밀하게 고립된 인과 효과로 단정하지 않는다.

## PostgreSQL EXPLAIN

일반 latency 측정과 별도로 ANALYZE/BUFFERS/VERBOSE/SETTINGS/FORMAT JSON을 실행했다. 단위 ms다.

| 후보 | 단계 | planning ms | execution ms |
|---|---|---|---|
| 100 | compatibility | 0.294 | 1.071 |
| 100 | ranking | 0.443 | 0.728 |
| 1000 | compatibility | 1.162 | 4.935 |
| 1000 | ranking | 1.901 | 6.46 |
| 5000 | compatibility | 12.73 | 20.752 |
| 5000 | ranking | 11.932 | 26.092 |

기본 5,000 후보 compatibility는 Hash Join·Seq Scan 후 external merge 정렬이며 sort Disk 5,800kB, temp read 725/write 726 blocks다. ranking은 exact identity Hash Join·Seq Scan과 MATERIALIZED CTE를 거쳐 top-N heapsort 70kB, temp 0이다. 기본 scan row는 5,002개다.

상한 탐색의 10,002 저장행 DB에서도 5,000 후보 compatibility에 같은 5,800kB external merge와 temp read/write가 관측됐다. 따라서 “DB 크기가 커져 처음 spill이 발생했다”고 해석하지 않는다. 이 실행의 ranking도 temp 0이며 scan row는 10,002개다. HNSW/IVFFlat은 없고 추가하지 않았다.

## 메모리

latency 표본과 분리한 실행이다. 같은 프로세스의 앞선 데이터 생성·측정과 allocator·누적 peak가 반영된다. 단위 MiB다.

| 후보 | baseline RSS | ranking 후 RSS | 누적 peak RSS | tracemalloc peak |
|---|---|---|---|---|
| 10 | 262.77 | 262.77 | 272.51 | 0.11 |
| 50 | 263.38 | 263.38 | 272.51 | 0.24 |
| 100 | 263.98 | 263.98 | 272.51 | 0.48 |
| 500 | 271.38 | 271.38 | 272.51 | 2.48 |
| 1000 | 284.23 | 284.23 | 284.23 | 5.05 |
| 2000 | 307.35 | 307.35 | 307.35 | 9.79 |
| 5000 | 329.68 | 342.39 | 367.94 | 25.72 |

tracemalloc은 Python allocation이며 torch/native·PostgreSQL 메모리를 대표하지 않는다. /proc current/peak RSS 및 resource maxrss를 함께 기록했지만 sampling 사이 순간 할당을 놓칠 수 있다. PostgreSQL 전체 query memory를 sort memory에서 추산하지 않았다.

## 동시성

1,000 후보/profile 1개. worker별 독립 connection을 열고 worker 안에서 10요청을 재사용 실행했다. pool은 없다. 단위 ms, 처리량 req/s다.

| 동시성 | 성공 요청 | p50 | p95 | req/s | 연결 mean | 오류/timeout/deadlock |
|---|---|---|---|---|---|---|
| 1 | 10 | 60.727 | 107.445 | 13.29 | 6.197 | 0/0/0 |
| 2 | 20 | 113.194 | 159.836 | 15.79 | 7.690 | 0/0/0 |
| 5 | 50 | 298.729 | 373.138 | 15.51 | 15.572 | 0/0/0 |
| 10 | 100 | 654.038 | 772.358 | 14.36 | 17.124 | 0/0/0 |

각 단계의 결과 identity는 동일했다. 25ms pg_stat_activity sampling에서 Lock wait가 관측되지 않았고 monitor 오류도 없었다. 이는 모든 순간의 lock wait 부재를 증명하지 않는다. 처리량에는 접속·commit·sanity 검사·monitor 부하가 포함되며 latency는 run_request 관찰구간이다. 순수 DB 처리 용량과 동일하지 않다.

2 CPU quota에서 동시성 증가에 따른 처리량 개선이 작고 지연이 증가하여 20단계는 실행하지 않았다. 원인을 CPU/GIL 또는 DB 중 하나로 확정하지 않는다.

## Correctness와 no-fallback

- raw cosine DESC, 1-based 연속 rank, Top100, 후보가 100 미만이면 가능한 수만 반환
- music_id C collation → audio_revision → embedding id의 deterministic ordering
- 요청 밖 최고 cosine·다른 revision·다른 profile 제외, empty 반환, 중복 identity 결과 증식 없음
- missing revision에 다른 revision fallback 없음
- 여섯 invalid 진단 및 benchmark 경로 ranking 미호출: MISSING_SOURCE, MISSING_EMBEDDING, INCOMPATIBLE_PROFILE, INVALID_DIMENSION, AMBIGUOUS_PROFILE, DUPLICATE
- SQL cosine과 torch 기준값 abs=1e-6, rel=0 비교; 기준값 계산은 latency에서 제외

이 tolerance는 correctness 기준이며 성능 합격 기준이 아니다. 실제 HTTP 부분 성공 차단·검증 이후 identity 소실의 일관성은 NSUAI-48/49 후속 검증이다.

## Parameter 구조와 한계

실제 cursor 관찰에서 compatibility=2U, ranking=4K+2를 확인했다. U는 unique pair 수, K는 ranking identity 수다. query vector 전체는 parameter 1개다. SQL bytes도 JSON scenarios에 보존한다. PostgreSQL parameter 65,535 기준 이론 경계는 compatibility 32,767 pair, ranking 16,383 identity이며 운영 한도가 아니다.

## 10,000 상한 탐색

[별도 결과](upper-bound-result.json), [별도 CSV](upper-bound-latency-samples.csv), upper-bound-explain/에 보존했다. 10,000 저장행을 준비한 DB에서 후보 5,000개를 먼저 측정했으며 compatibility temp write 감지로 자원 안전성 gate가 중단했다. **후보 10,000개 검색은 미실행**이다. 운영 성능 FAIL 판정이 아니며 기본 5,000 결과와 합쳐 평균내지 않는다. gate의 메모리 여유 조건도 운영 SLA가 아니다.

## 관찰·가설·후속 작업

사실: 후보 수·profile 수와 전체 시간이 함께 증가했고 5,000 compatibility에서 disk sort를 관측했다. 요청 subset을 제한하더라도 planner는 이 DB 조건에서 저장 테이블 Seq Scan을 선택했다.

가설: profile JSON 전송·hash 검사, VALUES/binding/planning, 정렬 및 Python 처리 비중이 커질 수 있다. EXPLAIN과 repository 전체 시간은 같은 범위가 아니며 하나를 단독 병목으로 확정하지 않는다.

후속 후보: profile 조회량·binding 전략·정렬 비용·connection 정책을 별도 검토한다. 이번에는 production 최적화·index·schema를 변경하지 않았다.

## 운영 최대 입력값과 한계

운영 최대 candidate 수를 이번 결과만으로 확정하지 않는다. 측정 evidence를 NSUAI-15의 한도 결정 근거로 제공한다. 성능 합격 threshold는 없으며 측정 완료, correctness 통과와 운영 성능 합격을 구분한다.

- Text Embedding inference·HTTP latency·모델 inference concurrency·음악 추천 품질 미포함
- Windows/WSL2 Docker 단일 호스트·고정 자원 실험이며 production 배포 부하가 아님
- 순차 실행이며 cold-cache 재시작 실험이나 장시간 soak test가 아님
- 표본이 작고 p99는 탐색값; 1,000회 추가 tail 측정은 수행하지 않음
- DB 전체 행 수·profile 크기·운영 데이터 분포가 달라지면 결과도 달라질 수 있음
- NSUAI-48 transaction/snapshot 방식과 AI 외부 오류 schema는 결정하지 않음

## 재현 방법

기존 dev 이미지와 pgvector 0.8.6-pg18 이미지를 사용한다. 새 dependency·모델 다운로드는 없다. /proc·resource·tracemalloc을 사용하므로 Linux 컨테이너 실행을 전제로 한다. 비밀번호는 전용 임시값을 환경으로 전달하고 출력하지 않는다. 기존 evidence를 덮어쓰지 않도록 별도 빈 output 디렉터리를 사용한다.

1. 전용 Docker network와 PostgreSQL 컨테이너를 만들고 POSTGRES_DB=benchmark_admin을 지정한다. DB 2 CPU/2GiB/shared memory 256MiB, client 2 CPU/4GiB로 제한한다. 개발/shared DB를 연결하지 않는다.
2. Worker checkout을 /workspace에 읽기 전용 mount하고 별도 output만 쓰기 허용한다. DB_HOST는 전용 PG 컨테이너, DB_PORT=5432, DB_NAME=benchmark_admin, DB_USER/DB_PASSWORD는 전용 자격을 사용한다.
3. 모델 inference 없이 다음 모듈을 실행한다.

```sh
python -m scripts.matching.benchmark_candidate_ranking \
  --output /evidence/base \
  --repository-commit 39ee7efab045a06d785bd6e1f0db3a9656a9b085 \
  --counts 10 50 100 500 1000 2000 5000 \
  --iterations 30 --warmup 5
```

4. 5,000의 오류·메모리·temp 사용을 검토한 후에만 별도 output에서 --counts 5000 --include-10000으로 상한 탐색한다. 하네스도 5,000 plan과 memory gate를 확인한다.
5. 임시 DB 삭제 확인 후 이 실험이 만든 컨테이너/network만 정리한다.

실제 기본 실행은 --output을 repository의 evidence 디렉터리로 지정했다. 별도 임시 output의 상한 탐색은 upper-bound-*로 보존했다. 개별 elapsed_ns와 실행 identity는 JSON/CSV를 기준으로 한다.

## 관련 문서

- [검색 Guide](../../guides/DATABASE_AUDIO_SEARCH.md)
- [하네스](../../../scripts/matching/benchmark_candidate_ranking.py)
- [빠른 단위 테스트](../../../tests/matching/test_benchmark_candidate_ranking.py)

## 테스트와 파일 검증

- 하네스 빠른 단위 테스트 13개 통과. 장시간 benchmark는 일반 unit suite에 넣지 않았다.
- 최초 targeted 실행: 767 passed / 1 skipped / 3 setup errors. 세 오류는 AUDIO_VALIDATION_EXPECTED_DATABASE 환경변수 누락으로 기존 전용 DB safety guard가 expected_database=''를 차단한 것이다.
- production/test 코드 수정 없이 해당 환경변수만 지정한 validation integration 재실행: 3 passed (2.78s).
- 같은 격리 PostgreSQL의 broad 회귀: 816 passed / 4 skipped / 0 failed (124.62s).
- skipped: Docker Compose CLI가 없는 개발 컨테이너의 compose 검사 3개, 네트워크 및 pinned GPT-2/MSCLAP resource 다운로드가 필요한 명시적 opt-in 검사 1개. 이 실행에서 모델을 다운로드하지 않았다.
- 기존 Starlette/httpx deprecation 경고 1개가 있으며 이번에 dependency를 변경하지 않았다.
- compileall 정상 종료. JSON 11개 plain UTF-8 parser 검증, 로컬 링크 20개 존재 검사, 측정 하네스 SHA와 두 evidence의 일치 확인.
- Main 독립 대조에서 CSV의 scale/profile/concurrency 요약 통계와 JSON의 불일치 0개를 확인했다.

Git-dependent 테스트는 Worker 소스의 컨테이너 임시 복사본과 실제 Git common metadata 읽기 전용 mount를 사용했다. 임시 복사본의 .git 포인터만 해당 실제 metadata로 연결했으며 host의 Main·Git metadata는 수정하지 않았다. GIT_DIR/GIT_WORK_TREE 전역 지정이나 가짜 commit은 사용하지 않았다.

회귀 후 validation source/embedding 행은 각각 0개, identity migration 임시 DB와 benchmark 임시 DB도 각각 0개였다. 이 작업의 PostgreSQL 컨테이너 두 개는 정상 stop 시 자동 제거됐으며 전용 network도 제거했다. 기존 이미지·공용 DB·volume은 정리 대상으로 삼지 않았다.
