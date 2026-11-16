# Audio 임베딩 테이블과 동기 저장

이 문서는 현재 내부 저장 identity와 동기 저장 경로를 설명한다.
후속 설계는 revision별 기존·신규 벡터 보관과 Backend ACTIVE 커밋 확인 후 이전 벡터 정리다.
처리 상태·stale 복구·삭제 기록을 포함한 [연동 계약](../api/AUDIO_SYNC_BACKEND_HANDOFF.md)은 미구현이며
아래 테이블·CLI가 이미 보장하는 기능과 구분한다.

Phase 3의 Audio 테이블과 저장 기능을 구현했습니다. Audio 저장은 백엔드 계약이 미정인
상태에서 AI 내부 저장을 검증하기 위한 임시 구조입니다. HTTP 등록 API, 백엔드 음악 FK,
수정·삭제·상태 동기화는 아직 연결하지 않았습니다. Text query는 음악 ID와 분리된
query SHA-256 및 generation profile identity로 별도 pgvector 테이블에 저장합니다.
저장 벡터를 사용하는 CLI는 [DB 후보 검색](DATABASE_AUDIO_SEARCH.md)에 연결했습니다.

## revision·source·생성 profile의 저장 identity

- 내부 행 PK는 PostgreSQL 18의 `uuidv7()`로 생성한다. Backend wire 필드가 아니다.
- `music_id`는 기존 `text`를 유지하며 UUID 형식을 새로 강제하지 않는다.
- `audio_revision`은 Backend가 전달한 Python 정수만 받는다. bool·float·숫자 문자열·0 이하·signed BIGINT 초과는 거절한다. AI의 증가·기본값은 없다.
- `audio_sources` PK는 `(music_id, audio_revision)`이고 하나의 원본 SHA에 대응한다.
- embedding UNIQUE는 `(music_id, audio_revision, generation_profile_sha256)`이다.
- embedding의 `(music_id, audio_revision, source_sha256)` FK가 source와의 일치를 보장한다.
- 다른 revision·profile은 별도 행으로 보존하며 기존 행을 덮어쓰거나 삭제하지 않는다.
- 정확 조회는 `AudioEmbeddingRepository.get(connection, music_id, audio_revision, profile_sha256)`로 수행한다. 최신 revision·profile 자동 선택은 없다.

profile은 기존 전체 JSON(device 포함)을 유지한다. Text와 동일한 `json.dumps(sort_keys=True, separators=(',', ':'), allow_nan=False)`의 UTF-8 bytes를 SHA256한다. source SHA·경로·길이 등 입력별 metadata는 profile에 포함하지 않는다. device의 향후 분리 여부는 별도 결정이며 이번 구현에서 의미를 변경하지 않는다.

저장은 source와 embedding을 같은 savepoint에 포함한다. 호출자가 오류를 잡더라도 source만 남는 부분 저장은 취소하며, repository가 외부 트랜잭션을 commit하지 않는다. 같은 identity·같은 vector는 기존 UUID와 `created=false`를 반환한다.

### migration 안전성

0001·0002는 유지하고 0003을 추가한다. 기존 Audio row가 하나라도 있으면 Backend revision 매핑 없이 진행하지 않고 `audio_revision_mapping_required`로 차단한다. revision=1 추정·데이터 삭제·벡터 재생성은 하지 않는다. 기존 데이터가 있는 환경의 승인된 backfill 절차는 별도 설계가 필요하다. `uuidv7()` 미지원 환경도 차단하며 UUIDv4로 대체하지 않는다.

ACTIVE 전환은 NSUAI-44, 재시도·작업 소유권은 NSUAI-45, 삭제·이전 revision 정리는 NSUAI-46 책임이다. 이번 저장 identity는 검색 가능 상태를 뜻하지 않는다.

## 내부 저장 계약과 협의 필요 사항

- 호출자가 `music_id`를 전달합니다. AI는 음악 ID를 발급하지 않습니다.
- ID는 앞뒤 공백 없는 1~200자 문자열입니다. 숫자·UUID 등 백엔드 ID를 문자열로 전달할 수 있습니다.
- `ai_embeddings` 스키마를 사용해 백엔드 업무 테이블과 이름을 분리했습니다.
- 음악·revision·generation profile별로 저장합니다. 동일 identity·해시·벡터이면 기존 UUID를 반환합니다.
- 같은 음악·revision에 다른 SHA가 오거나 동일 생성 identity에 다른 벡터가 오면 `EmbeddingConflict`를 발생시키고 덮어쓰지 않습니다.
- 동일 파일을 서로 다른 음악 ID로 등록하는 것은 허용합니다. 전역 해시 중복 제거는 하지 않습니다.
- 재요청도 현재는 다시 생성한 뒤 비교합니다. 중복 저장은 막지만 중복 추론 비용은 남습니다.
- 모델·차원이 다른 행도 저장할 수 있습니다. DB 검색에서는 호환되는 생성 조건으로 후보를 제한합니다.

백엔드와 ID 형식·발급 주체, 테이블 관리 주체, 수정·삭제·재등록 규칙을 확정한 뒤
외래키와 API 계약을 연결해야 합니다. 이 구조를 최종 서비스 계약으로 확정한 것은 아닙니다.

## 파일이 들어왔을 때 처리 흐름

```text
외부 음악 ID + Backend audioRevision + 음악 파일 경로
  → ID·revision 검사
  → 공통 AudioEmbeddingGenerator.generate()
     파일·해시 검사 → MSCLAP 전처리·추론 → 벡터 검증 → 원본 변경 검사
  → DB 연결·트랜잭션 시작
  → 저장 직전 벡터·메타데이터 검증
  → INSERT ... ON CONFLICT DO NOTHING
     새 identity: source와 생성 결과 저장
     기존 identity: 해시·생성 조건·벡터 일치 여부 검사
  → 성공 시 commit / 실패 시 rollback
  → UUID·음악 ID·revision·profile SHA·생성 여부·원본 SHA·차원 반환
```

### 1. 외부 음악 ID 확인

`AudioEmbeddingStorage.store()`는 `validate_music_id()`를 먼저 호출합니다.
잘못된 ID 때문에 고비용 모델 추론을 실행하지 않도록 순서를 정했습니다.
아티스트 등록 음악을 저장할 때는 백엔드가 부여한 음악 ID를 받는 자리에 해당합니다.
검증용 `dev-reference-001`은 실제 백엔드 음악 ID가 아닙니다.

### 2. 공통 생성기에 파일 전달

```python
result = self.generator.generate(audio_path)
```

음악 파일 검색에서도 사용하던 생성기를 그대로 호출합니다. 저장용 전처리를 별도로
만들면 검색 입력과 저장 후보의 벡터 분포가 달라질 수 있기 때문입니다.
원본 파일의 SHA-256을 계산해 기대 해시와 비교하고 생성 전후 해시를 확인합니다.
SHA-256은 원본 식별·변경 감지에 쓰며 crop 위치나 seed 결정에는 사용하지 않습니다.
현재 생성기는 파일을 decode하고 56~60초 inclusive 길이를 검증한 뒤 처음 56초를 7초 × 8개
non-overlap Chunk로 처리합니다. 각 MSCLAP Chunk Embedding을 L2 정규화하고,
Mean Pooling 후 최종 L2 정규화하여 대표 벡터 하나와 생성 metadata를 반환합니다.
벡터의 유한값·0벡터·shape·차원도 검사합니다.
자세한 동작은 [공통 생성기 설명](AUDIO_EMBEDDING.md)을 참고하세요.

### 3. 생성이 끝난 뒤 DB 트랜잭션 시작

```python
with connect_database() as connection:
    saved = self.repository.save(connection, music_id, audio_revision, result)
```

모델 로딩·디코딩·추론 중에는 DB 연결과 트랜잭션을 잡지 않습니다.
생성 오류는 DB 변경 전에 발생합니다. 저장 오류는 연결 컨텍스트를 벗어나며 롤백되고,
저장이 끝나 정상적으로 벗어나면 커밋됩니다. SQL 대기는 30초, 잠금 대기는 5초로 제한합니다.
DB 실패 후 자동 재시도는 아직 없으며, 같은 ID로 CLI를 다시 실행할 수 있습니다.

### 4. 저장 직전 정합성 확인

`prepare_embedding()`은 벡터와 metadata의 차원·shape, SHA-256 형식,
모델·전처리 버전, 생성 조건 객체, JSON 직렬화 가능 여부를 검사합니다.
pgvector 단정밀도로 변환한 뒤에도 유한값과 0벡터를 확인합니다.
따라서 변환 과정에서 overflow나 underflow가 발생한 벡터도 저장하지 않습니다.

`generation_profile`에는 모델·revision·패키지·전처리 조건·차원·dtype·device를
기록합니다. 파일 경로는 파일 이동에도 달라질 수 있어 동일성 비교에서 제외합니다.
원본 metadata는 별도로 모두 저장합니다. 로컬 절대 경로가 포함될 수 있으므로
이를 사용자 응답에 그대로 노출하는 API는 만들지 않았습니다.

### 5. 동시 등록과 중복 요청 처리

```sql
INSERT INTO ai_embeddings.audio_embeddings (...) VALUES (...)
ON CONFLICT (music_id, audio_revision, generation_profile_sha256) DO NOTHING RETURNING id;
```

사전 조회만으로는 두 요청이 동시에 '없음'을 확인할 수 있습니다.
따라서 source의 복합 PK, embedding의 업무 UNIQUE 및 source FK를 최종 무결성 기준으로 사용합니다.
source PK와 embedding UNIQUE·FK로 경합을 제어합니다. 기존 행이면 잠금을 걸어 해시·generation_profile·벡터를 비교합니다.
같으면 `created=false`, 다르면 충돌 예외를 반환합니다.
다른 파일에 이전 임베딩을 연결하거나 협의 전 데이터를 교체하지 않기 위한 규칙입니다.
음악 ID·JSON·벡터 값은 SQL 파라미터로 전달합니다.

## 테이블에 저장하는 정보

| 컬럼 | 목적 |
| --- | --- |
| id | DB 발급 UUIDv7 기본키 |
| music_id | 외부 음악 ID, 기존 text 유지 |
| audio_revision | Backend 발급 원본 버전, BIGINT |
| generation_profile_sha256 | canonical generation profile SHA256 |
| source_sha256 | 원본 파일 내용 식별 |
| model / model_version | 모델 계열·버전 구분 |
| preprocessing_version | 전처리 정책 구분 |
| dimension / embedding | 실제 차원과 pgvector 벡터 |
| generation_profile | 동일 결과 재요청 판정에 사용하는 생성 조건 |
| metadata | 체크포인트·패키지·원본 경로 등 전체 생성 정보 |
| created_at | 최초 저장 시각 |

벡터 차원은 SQL CHECK로도 검증합니다. 현재 실측은 1024차원이지만 이후 모델 변경을
막지 않도록 `vector` 컬럼에 행별 차원을 기록합니다. 벡터 검색 인덱스는 아직 만들지 않았습니다.
해시 조회용 일반 인덱스만 있습니다. 검색과 성능 검증 단계에서 후보 조건·차원을 정한 뒤
벡터 인덱스를 설계해야 합니다.

## 테이블 생성과 Git 관리

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps ai python -m scripts.database.migrate_embeddings
```

SQL migration은 `app/repository/migrations/`의 번호가 붙은 파일로 관리하며 Git에 포함합니다.
실제 DB 행·음원·모델 가중치·`.env` 비밀번호를 Git에 올리는 것은 아닙니다.
마이그레이션 도구는 DB 적용 이력과 SQL checksum을 저장합니다. 재실행은 미적용 파일만
실행하며, 기존 SQL이 변경되면 거부합니다. 후속 변경은 새로운 번호의 SQL 파일로 추가합니다.
Windows/Linux 줄바꿈은 checksum 계산 전에 정규화합니다.
pgvector는 대상 DB에 미리 활성화되어 있어야 합니다. 서버 시작 시 자동 적용하지 않습니다.

Text 저장은 `TextEmbeddingStorage.store(query_text)`에서 기존 `TextEmbeddingGenerator`를
호출한 뒤 `TextEmbeddingRepository`를 통해 수행합니다. 입력 SHA와 정렬된 generation profile의
SHA가 저장 identity이며, 같은 identity의 같은 vector는 재사용하고 다른 vector는 충돌로 거부합니다.
현재 text-to-audio repository 검색은 현재 Text generation/profile과 공통 MSCLAP model,
checkpoint revision/SHA-256, MSCLAP package version, pinned implementation/config identity, dimension 및 Audio preprocessing version이 맞는 행만 후보로 봅니다.
이 경계는 내부 AI 저장·검색이며 Event ID나 서버 API 계약을 정하지 않습니다.

## 실제 파일 저장

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps ai python -m scripts.embedding.store_audio_embedding --music-id dev-reference-001 --audio-revision 1 --audio samples/reference.mp3
```

성공 결과는 `status`, `music_id`, `created`, `source_sha256`, `dimension`을 반환합니다.
첫 저장은 `created=true`, 같은 결과의 재요청은 `false`입니다.
현재 파일 경로는 AI 실행 환경에서 읽을 수 있어야 합니다. 파일 업로드·객체 스토리지 다운로드
기능을 구현한 것은 아닙니다. 모델 cache는 `compose.dev.yaml`의 외부 named volume으로 연결합니다. 준비는 [개발 환경 가이드](DEVELOPMENT_ENVIRONMENT.md)를 따릅니다.

## 테스트

일반 테스트는 실제 DB 없이 실행하며 DB 테스트는 건너뜁니다.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps ai python -m pytest tests -q -p no:cacheprovider
```

기존 데이터가 없는 격리 테스트 DB에 테이블을 적용한 뒤에만 아래 명령을 실행합니다. 테스트 행은 롤백하거나
테스트가 생성한 ID만 삭제합니다. 기존 행은 수정하지 않습니다.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps -e RUN_EMBEDDING_DB_TESTS=1 ai python -m pytest tests -q -p no:cacheprovider
```

벡터·메타데이터 오류, 생성 실패 시 DB 미접속, 저장 실패 전달, 재요청,
충돌 시 원본 유지, 차원 제약, 같은 파일의 다른 ID 등록, 트랜잭션 롤백,
동시 동일 요청의 단일 행 저장을 검사합니다.

2026-10-03, 현재 Docker PostgreSQL 18 / pgvector 0.8.6에서 실제 DB 테스트를
포함한 79개가 통과했습니다. 기존 Starlette deprecation 경고 1개가 있습니다.
마이그레이션 최초 적용과 재실행 무변경을 확인했고, 실제 `reference.mp3`를
`dev-reference-001`로 저장해 1024차원 행을 생성했습니다. 별도 프로세스에서 같은 파일을
다시 저장했을 때 `created=false`로 기존 행을 재사용했습니다.
기본 테스트는 71개 통과·DB 테스트 8개 건너뜀입니다. 개발 검증용 행 1개는 DB에 남겨두었습니다.

구현 기준: [pgvector 공식 문서](https://github.com/pgvector/pgvector),
[Psycopg 트랜잭션 문서](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

## NSUAI-43 격리 검증 (2026-11-16)

기존 개발 DB 접속은 실패하여 실제 버전·행 수·적용 이력을 확인하지 못했고 해당 DB에는 migration을 적용하지 않았다. 검증은 기존 데이터 mount와 외부 port가 없는 별도 임시 PostgreSQL 18.6 / pgvector 0.8.6에서 수행했다. `uuid_extract_version(uuidv7()) = 7`, 빈 DB의 0001 → 0002 → 0003 적용과 재실행을 확인했다.

- 개발 이미지의 전체 pytest: 755 passed, 7 skipped, 실패 0. 이후 검증 fixture의 유효한 checkpoint revision 및 실제 검증 함수 회귀를 보강하고 관련 migration 5개를 다시 통과했다.
- migration 검증: 새 schema/catalog, 재실행, 기존 행 차단과 원본·이력 보존, checksum 변경 거부, 실패 시 DDL·이력 rollback을 확인했다.
- repository 검증: 동일 UUID 재사용·동시 동일 요청, 다른 SHA 경합, 다른 revision/profile 보존, 정확 조회, FK, source만 남지 않는 savepoint rollback을 확인했다.
- 검증 도구의 schema 검사, synthetic known-vector 검사와 저장 전후 cosine/roundtrip도 별도 무작위 임시 DB에서 실행했다. 실제 모델 inference 완료를 뜻하지 않는다.
- 7개 skip은 개발 이미지에 Docker CLI가 없어 Compose 검사 3개, 전용 validation DB의 별도 live guard opt-in 3개, pinned 모델 다운로드 opt-in 1개다. 앞의 검증 함수 직접 실행을 HTTP/전용 live guard 통합 완료로 표현하지 않는다.
- Python 88개 파일 구문 검사와 변경 모듈 import, `git diff --check`를 수행했다. OpenAPI·0001/0002·Audio 생성 알고리즘은 변경하지 않았다.

migration 전용 검증은 같은 격리 DB 설정으로 `RUN_IDENTITY_MIGRATION_TESTS=1`을 명시하고 `python -m pytest tests/embedding/test_audio_identity_migrations.py -q -p no:cacheprovider`로 실행한다. 테스트마다 무작위 임시 DB를 만들고 해당 DB만 정리하므로 테스트 계정에 CREATE/DROP DATABASE 권한이 필요하다. 개발·운영 DB와 그 데이터를 테스트 fixture로 사용하지 않는다.
