# ADR-0007 Audio Embedding PostgreSQL / pgvector 통합 검증

## 현재 결과: PASS

2026-10-09 Phase A 실제 음악 6곡을 production `AudioEmbeddingGenerator`로 새로 처리하고, 격리된 PostgreSQL/pgvector에 저장·검색했습니다. 최초 실행 판정은 cosine 수치 차이에 대한 기준이 승인되지 않아 `REVIEW_REQUIRED`였습니다. 승인된 numerical parity 기준 `absolute tolerance = 1e-6`, `relative tolerance = 0`을 30개 보존된 비교값에 적용해 재판정했으며 30/30이 기준 이내입니다. DB나 MSCLAP 재실행은 하지 않았습니다.

`validation-result.json`에는 원 실행 상태와 재판정 근거, 정책, 측정값이 함께 기록되어 있습니다. 초기 Docker 차단 시도는 [validation-result-blocked-initial.json](validation-result-blocked-initial.json)에 별도 보존합니다.

## 범위와 판정 기준

이번 검증은 ADR-0007의 실제 representative `[1,D]` vector를 production migration 및 repository/search 경로로 저장·검색하는 기술 검증입니다. `[8,D]` chunk vector는 저장하지 않습니다. 이번 실행에서 관측한 `D=1024`는 사용한 MSCLAP 2023 모델의 결과이며 영구 차원 규칙이 아닙니다.

- **Cosine numerical parity:** Python cosine similarity와 PostgreSQL `1 - cosine_distance` 간 절대 차이가 `1e-6` 이하인지 확인합니다. 상대 오차는 적용하지 않습니다 (`rtol=0`). 승인 범위는 이 두 수치의 비교뿐입니다.
- **Ranking parity:** 별도 기준으로 Python 및 PostgreSQL의 전체 candidate ID 순서가 정확히 같아야 합니다. tolerance/epsilon으로 순위 차이를 허용하지 않습니다.
- 위 수치 tolerance는 사용자 표시용 0~100 calibration threshold가 아니며, 검색 품질이나 음악 유사성 평가 기준도 아닙니다.

## 환경 및 격리

실제 MSCLAP 실행은 Windows CPU 환경(Python 3.11.16, `msclap 1.3.3`, `torch/torchaudio 2.1.2+cpu`)에서 수행했습니다. 별도의 일회성 Docker container `audio-embedding-validation-postgres`와 `audio_embedding_validation` DB를 사용했고 PostgreSQL 18.6 / pgvector 0.8.6을 관측했습니다. `app/repository/migrations`의 production migration `0001_audio_embeddings.sql`을 적용하고 checksum/history와 schema를 확인했습니다. 기존 `backend-postgres-1`, 개발 DB 및 업무 volume은 사용하지 않았습니다.

검증 transaction을 명시적으로 rollback했고 새 connection에서 validation row 0개를 확인했습니다. 전용 container와 ephemeral storage도 정리했습니다. 기존 개발 DB에 연결하거나 이를 변경하지 않았습니다.

## 결과

- Phase A 6개 입력 manifest identity·SHA 확인 및 실행 전후 SHA 보존: 6/6 통과.
- Production generator: 실제 6곡 모두 `[1,1024]`, finite/non-zero, generation profile 확인 통과.
- 저장 round-trip: 6/6 exact equality 및 canonical float32 digest 일치. 차원·norm 유지, 저장 차이는 0.
- Cosine numerical parity: directional comparison 30/30 통과. 6개는 exact equality, 최대 absolute difference는 `1.1920928955078125e-07`.
- Ranking parity: 6/6 query에서 전체 candidate 순서 일치. TopK 1/2/5 일치.
- Synthetic cosine 의미(동일/직교/반대), production `music_id COLLATE "C"` tie-break, generation mismatch 제외 및 compatible control 유지, duplicate 재사용/conflict와 원본 보존, rollback 및 새 연결 row 0개: 모두 통과.

세부 입력 SHA, checkpoint/package 환경, 생성 profile, 각 comparison, 순위, migration, 격리 결과는 [validation-result.json](validation-result.json)에 있습니다. 전체 vector는 Git evidence에 포함하지 않습니다.

## 한계와 제외 범위

이 검증은 한 번의 Windows CPU와 PostgreSQL 18.6/pgvector 0.8.6 실행의 저장/검색 기술 parity를 확인합니다. 다른 OS, CPU/GPU, package 또는 PostgreSQL 환경의 동일 수치 재현성을 보장하지 않습니다. 전체 similarity distribution, 검색/추천 품질, 0~100 calibration, API 및 backend lifecycle은 검증하지 않았습니다. 기존 dev/test Embedding도 삭제하거나 재생성하지 않았습니다. 재생성 대상과 입력 mapping을 확인하고 별도 승인을 받기 전에는 해당 데이터 작업을 수행하지 않습니다.