# ADR-0010. Audio 원본 revision과 Embedding 생성 identity 분리

## 상태

Accepted — NSUAI-43 구현이 PR #82로 `main`에 merge된 결정을 기록한다.

## 관련 이슈와 근거

- Linear 이슈: [NSUAI-43](https://linear.app/nsu-capstone/issue/NSUAI-43/audiorevisionsource-shagenerationprofile-식별-저장-기반-구현)
- 서버 간 협의: [001. Audio revision과 생성 버전 분리](https://linear.app/nsu-capstone/document/001-audio-revision과-생성-버전-분리-c5c95e36f3e2), [002. Revision별 벡터 보관과 ACTIVE 전환 후 정리](https://linear.app/nsu-capstone/document/002-revision별-벡터-보관과-active-전환-후-정리-e974a4620c8f), [012. CLAP 음악 유사도 기반 곡 추천 흐름](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba)
- 구현 근거: [PR #82](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/pull/82), `0003_audio_embedding_identity.sql`, `AudioEmbeddingRepository`, `AudioEmbeddingStorage`
- 관련 AI 결정: [ADR-0003](ADR-0003-embedding-and-scoring-policy.md), [ADR-0006](ADR-0006-asynchronous-audio-processing.md), [ADR-0007](ADR-0007-audio-highlight-embedding-strategy.md), [ADR-0008](ADR-0008-music-similarity-transformation-and-ranking.md)

이 ADR은 merge된 NSUAI-43 내부 저장 결정을 기록한다. 서버 간 계약을 새로 만들거나 위 협의의 범위를 변경하지 않는다.

## 배경

원본 Audio의 교체와 AI 모델·checkpoint·전처리 변경은 서로 다른 사건이다. 둘을 하나의 버전으로 취급하면 모델을 바꿀 때 원본 revision을 잘못 증가시키거나, 같은 원본에 대해 새로 생성한 embedding이 기존 결과를 덮어쓸 수 있다.

저장소에는 원본 revision, 실제 원본 파일, 그리고 그 파일에서 생성한 embedding 결과를 각각 추적할 identity가 필요하다. 또한 하나의 원본 revision에 서로 다른 생성 조건의 결과를 보존하고 정확히 조회할 수 있어야 한다.

## 결정

### 원본 revision 책임

1. `audioRevision`은 같은 음악의 원본 Audio 버전을 식별한다. Backend가 발급하고 원본 Audio version 생성 규칙에 따라 증가시킨다.
2. AI는 `audioRevision`을 발급하거나 증가시키지 않는다. 전달받은 값을 검증하고 저장한다.
3. 모델, 모델 버전, checkpoint, 구현, preprocessing 또는 generation profile이 바뀌어도 `audioRevision`은 증가시키지 않는다.
4. `audioRevision`과 AI 생성 조건은 별개의 identity 축으로 유지한다.

### 원본 파일 identity

1. `source_sha256`은 실제 원본 Audio 파일 바이트의 SHA-256이다.
2. 하나의 `(music_id, audio_revision)`은 하나의 `source_sha256`에만 연결한다. 같은 pair에 다른 SHA가 들어오면 기존 값을 덮어쓰지 않고 충돌로 거부한다.
3. 동일한 SHA가 다른 `music_id` 또는 다른 `audio_revision`에 존재할 수 있으므로 `source_sha256`은 전역 unique identity로 사용하지 않는다.

### Generation identity

1. 생성 조건 전체를 `generation_profile` JSON으로 보존한다.
2. JSON은 결정적인 canonical serialization으로 직렬화한 UTF-8 바이트의 SHA-256인 `generation_profile_sha256`도 함께 저장한다. 현재 구현은 정렬된 key, 고정 separator, NaN 비허용 serialization을 사용한다.
3. embedding 업무 identity는 `(music_id, audio_revision, generation_profile_sha256)`이다.
4. 같은 원본 revision에 여러 generation profile 결과를 함께 저장할 수 있다. 다른 generation 결과를 기존 행에 덮어쓰지 않는다. 같은 identity와 같은 vector의 반복 저장은 기존 row identity를 재사용하고, 같은 identity에서 vector가 다르면 충돌로 처리한다.

### 저장 구조

`audio_sources`는 원본 revision identity를 보관한다.

```text
music_id text
audio_revision bigint
source_sha256 text
PRIMARY KEY (music_id, audio_revision)
UNIQUE (music_id, audio_revision, source_sha256)
```

`audio_embeddings`는 원본 revision으로 생성한 AI 결과를 보관한다. 기존 model, version, preprocessing, dimension, vector, profile, metadata 및 생성 시각 정보도 유지한다.

```text
id uuid
music_id text
audio_revision bigint
source_sha256 text
generation_profile jsonb
generation_profile_sha256 text
embedding vector
PRIMARY KEY (id)
UNIQUE (music_id, audio_revision, generation_profile_sha256)
FOREIGN KEY (music_id, audio_revision, source_sha256)
  REFERENCES audio_sources (music_id, audio_revision, source_sha256)
```

`audio_sources`와 `audio_embeddings`를 분리해 하나의 원본 revision에 속한 원본 파일 identity와 해당 원본에서 생성된 여러 AI 결과를 각각 표현한다. 복합 외래 키는 embedding의 revision 및 SHA가 등록된 원본 identity와 일치하도록 한다.

### Embedding row UUID

`audio_embeddings.id`는 PostgreSQL 18의 `uuidv7()`로 생성하는 AI DB 내부 row 식별자다. `music_id`나 `audioRevision`을 대체하지 않으며, Backend가 발급하거나 API로 전달하는 필드가 아니다.

## 근거

- 원본 교체와 AI 생성 조건 변경을 독립적으로 추적할 수 있다.
- 같은 원본 revision의 여러 generation 결과를 보존해 비교하거나 정확히 조회할 수 있다.
- 모델 교체 시 기존 embedding을 덮어쓰지 않아 과거 결과와 생성 근거가 남는다.
- 원본 SHA와 profile hash, 복합 제약을 사용해 잘못된 재사용 및 동시 저장 충돌을 DB 수준에서 방지한다.
- 생성 설정 JSON과 그 결정적 hash를 함께 보존해 결과의 추적성과 재현성을 높인다.

## 검토했으나 채택하지 않은 대안

### `audioRevision` 하나로 원본과 생성 조건의 모든 버전을 관리

원본 변경과 모델·checkpoint·preprocessing 변경이 같은 revision 축에 섞인다. 원본 변경 없이 생성 조건만 달라진 경우를 정확히 표현할 수 없어 채택하지 않았다.

### `(music_id, audio_revision)`만 embedding identity로 사용

같은 원본 revision에 대한 여러 generation 결과가 공존할 수 없고, 새 결과가 기존 결과를 대체하게 된다. 생성 조건별 결과를 보존하기 위해 채택하지 않았다.

### 전체 `generation_profile` JSON을 기본 키로 사용

profile 전체는 크고 복합 참조 및 조회에 불편하다. JSON 자체는 추적용으로 보존하고 결정적 SHA-256을 업무 identity에 사용한다.

### `source_sha256`을 revision 대신 사용

파일 바이트 hash는 파일 내용을 식별하고 `audioRevision`은 Backend가 관리하는 해당 음악의 원본 version을 식별한다. 역할이 다르며 동일 파일이 서로 다른 음악 또는 revision에 연결될 수 있으므로 대체할 수 없다.

## 결과와 비용

### 결과

- 원본 교체와 AI 모델·전처리 변경을 독립적으로 관리한다.
- 동일 revision의 여러 generation을 나란히 보존하고 조회할 수 있다.
- 모델 교체 시 기존 embedding이 보존된다.
- `(music_id, audio_revision, generation_profile_sha256)`로 정확한 결과를 식별한다.
- overwrite를 피하고 저장 재시도에서 기존 row를 안전하게 재사용한다.
- 원본 및 생성 조건의 추적성과 재현성이 높아진다.

### 비용

- 같은 revision에 여러 embedding 행이 생길 수 있어 저장량과 스키마 복잡도가 증가한다.
- 검색 전에 사용할 generation profile과 검색 공간의 호환성을 판정해야 한다.
- revision의 ACTIVE 전환 및 정리 lifecycle은 별도 책임과 구현이 필요하다.

## 범위 밖

이 ADR은 다음을 결정하지 않는다. 관련 책임은 해당 서버 협의와 후속 이슈에서 다룬다.

- Spring Eligibility와 ACTIVE 전환 알고리즘
- retry, stale 처리 및 late completion
- 삭제 lifecycle과 이전 revision 정리
- candidate 누락·비호환 처리 및 HTTP 오류 정책
- cosine ranking, Top100 및 similarity 0~100 변환
- 외부 `resultVersion`
- `canonicalText` 생성

저장 성공은 해당 revision이 검색 가능한 상태 또는 ACTIVE라는 의미가 아니다.

## 기존 결정과의 관계

- [ADR-0003](ADR-0003-embedding-and-scoring-policy.md)은 MSCLAP과 PostgreSQL + pgvector 기반 embedding 저장·사용 방향을 정한다. 이 ADR은 해당 저장 방향에서 Audio 원본과 생성 결과를 식별하는 구조를 구체화한다.
- [ADR-0006](ADR-0006-asynchronous-audio-processing.md)은 동기 처리 방향과 ACTIVE 전환 전 기존 revision을 보존하는 이력을 다룬다. 이 ADR은 그 lifecycle을 구현하거나 변경하지 않고 저장 identity를 구체화한다.
- [ADR-0007](ADR-0007-audio-highlight-embedding-strategy.md)은 Audio Highlight의 입력 및 embedding 생성 전략을 정한다. 생성 결과를 어떤 revision/profile identity로 보관하는지를 이 ADR이 보완한다.
- [ADR-0008](ADR-0008-music-similarity-transformation-and-ranking.md)은 similarity transformation과 ranking 원칙을 다룬다. 이 ADR은 점수나 순위 정책을 변경하지 않는다.
- 서버 협의 [001](https://linear.app/nsu-capstone/document/001-audio-revision과-생성-버전-분리-c5c95e36f3e2)은 원본 revision과 생성 조건의 분리를 정하고, [002](https://linear.app/nsu-capstone/document/002-revision별-벡터-보관과-active-전환-후-정리-e974a4620c8f)는 revision별 보존과 ACTIVE 전환 후 정리를 다룬다. 이 ADR은 두 협의를 대체하지 않고 AI 저장소의 내부 identity 모델을 기록한다.

## 구현 참고

- `audio_revision`은 PostgreSQL `BIGINT`이며 AI에서 증가·기본값을 부여하지 않는다.
- migration `0001`과 `0002`는 유지하고 `0003_audio_embedding_identity.sql`에서 새 구조를 적용한다.
- 기존 row의 revision을 추정해 backfill하거나 기존 데이터를 삭제하지 않는다. 기존 Audio row가 있으면 mapping 없이 migration을 진행하지 않는다.
- PostgreSQL `uuidv7()`을 사용할 수 없는 환경은 migration을 차단하며 UUIDv4나 애플리케이션 생성 UUID로 대체하지 않는다.

## 참고 자료

- [Linear NSUAI-43](https://linear.app/nsu-capstone/issue/NSUAI-43/audiorevisionsource-shagenerationprofile-식별-저장-기반-구현)
- [서버 협의 001](https://linear.app/nsu-capstone/document/001-audio-revision과-생성-버전-분리-c5c95e36f3e2)
- [서버 협의 002](https://linear.app/nsu-capstone/document/002-revision별-벡터-보관과-active-전환-후-정리-e974a4620c8f)
- [서버 협의 012](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba)
- [Embedding 저장 Guide](../guides/EMBEDDING_STORAGE.md)
- [Audio identity migration](../../app/repository/migrations/0003_audio_embedding_identity.sql)
