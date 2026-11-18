# 백엔드 전달용 Audio 동기 연동 계약

> 현행 원본 버전 명칭은 `audioRevision`이며 과거 `source_version` 제안과 같은 개념이다. 별도 runtime 필드로 유지하지 않는다. 아래 과거 제안의 HTTP 경로·상태 흐름은 구현 완료를 뜻하지 않으며 최신 017의 계약과 구분한다. 내부 UUIDv7 PK는 Backend wire 필드가 아니다.

> 현행 추천 HTTP 계약은 [Accepted 017](https://linear.app/nsu-capstone/document/017-spring-canonical-검색-입력-기반-ai-recommend-server-요청응답-계약-f96a57425124)을 따른다. 012의 ranking 원칙과 016의 Spring canonical 입력 책임을 유지하며, 업무 HTTP 구현 완료를 뜻하지 않는다.


상태: **NSUAI-43 저장 identity·NSUAI-30 후보 진단·NSUAI-31 내부 ranking 구현 완료. 업무 HTTP와 ACTIVE lifecycle은 후속 구현**.
기존 벡터 단일 교체안은 revision별 보관·ACTIVE 전환 확인 후 정리 방식으로 대체한다.
아래 처리 원칙과 미정인 API 세부 제안을 구분한다. 현재 CLI가 이 계약을 구현한 것은 아니다.

결정 배경·이유·서버별 책임의 현행 관리 위치는 [Linear 서버 협의](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)이다.
[로컬 목록](../adr/server-agreements/readme.md)은 과거 기록이다. 이 문서는 Accepted 원칙과 상세 인터페이스 제안을 구분한다.
2026-10-07의 전체 결과 반환 제안은 당시 이력이다. 현행 정책은 Accepted 012에 따라 전체 통과 ACTIVE 후보 쌍을 입력으로 받고 최대 100곡을 반환하며, 입력 상한은 NSUAI-15 실측 후 정한다. 상세 내용은 [작업 기준](CLAP_RECOMMENDATION_DIRECTION.md)을 따른다.

## 1. 책임과 식별자

백엔드는 음악 Sample ID·아티스트 소유 관계·권한·원본 파일·ACTIVE revision을 관리한다.
AI는 임베딩·처리 상태·생성 조건을 관리한다. 개인정보를 벡터 테이블에 복제하지 않는다.
등록 음악에 행사 Request ID를 붙이지 않으며 검색 입력은 후보 음악으로 저장하지 않는다.

| 식별 정보 | 의미 |
| --- | --- |
| musicId / music_id | API/JSON은 musicId, DB는 music_id. AI 내부 저장은 text이며 1~200자·앞뒤 공백 금지 규칙 유지. wire type은 017의 미확정 범위와 구분 |
| audioRevision / audio_revision | API/JSON은 audioRevision, DB는 audio_revision. Backend가 발급하는 1 이상의 원본 Audio revision이며 AI는 발급·증가시키지 않음 |
| source_sha256 | 정확한 source 파일 bytes의 SHA-256. 전역 unique가 아니며 같은 music_id + audio_revision의 SHA 불일치는 conflict |
| generation_profile / generation_profile_sha256 | model·checkpoint·전처리·생성 조건 JSON과 결정적인 SHA-256. audioRevision과 독립이며 같은 revision에 여러 profile 보존 가능 |
| attempt_id | stale 재처리 시 이전 시도의 결과 반영을 막기 위한 처리 소유권 식별값 제안 |

모델 변경은 model_version·checkpoint revision, 전처리 변경은 preprocessing_version으로 관리한다.
모델 재생성 때문에 audioRevision을 증가시키지 않는다.
재사용 조건은 revision + SHA-256 + 생성 조건 일치다. 같은 파일도 생성 조건이 다르면 재생성한다.

## 2. 등록·교체·활성 전환

```text
Backend: v1 ACTIVE 유지, v2 원본 보관·PROCESSING 커밋
AI: v2 처리 기록 커밋 → 모델 실행 → 최신 요청·삭제·attempt 검사 → v2 ready 커밋
AI: v1 + v2 벡터 함께 보관 → 동기 완료 응답
Backend: v2가 여전히 최신인지 검사 → v2 ACTIVE, v1 INACTIVE를 한 트랜잭션으로 커밋
Backend: 커밋된 활성 전환 정보를 AI에 명시적으로 전달
AI: 전환 확인·유예/검색 재시도 정책에 따라 v1 벡터 정리
```

v2 ready는 백엔드 ACTIVE와 다르다. AI 생성 성공만으로 v1을 덮어쓰거나 삭제하지 않는다.
백엔드 전환 실패·응답 timeout·활성 확인 전달 실패에도 기존 ACTIVE 쌍의 벡터를 유지한다.
새 생성 실패 시 기존 ACTIVE를 유지한다. 최초 등록 실패에는 기존 ACTIVE가 없다.
원본 보관과 두 DB의 처리는 분산 트랜잭션이며 Spring @Transactional로 AI 작업이 묶이지 않는다.

저장 identity는 NSUAI-43에서 이미 구현했다. `audio_sources`의 PK는 `(music_id, audio_revision)`, UNIQUE는 `(music_id, audio_revision, source_sha256)`이다.
`audio_embeddings`는 내부 UUIDv7 PK와 `(music_id, audio_revision, generation_profile_sha256)` UNIQUE를 가지며, source의 세 컬럼을 복합 FK로 참조한다.
원본 revision과 generation 저장 모델의 근거는 [ADR-0010](../adr/ADR-0010-audio-revision-and-embedding-generation-identity.md)이다. 처리 상태와 ACTIVE 전환·기존 revision 보존 lifecycle은 NSUAI-44/45/46의 후속 범위이며 아래 상태·attempt 처리 흐름은 아직 구현되지 않았다.
모델 실행은 DB 트랜잭션 밖에서 수행하고, 최신 revision·삭제·attempt 재검증과 결과 저장은 같은 트랜잭션에서 수행한다.
이미 저장된 이전 ACTIVE 벡터는 신규 생성 요청이 더 최신이라는 이유만으로 검색에서 제외하지 않는다.

## 3. 활성 확인·이전 revision 정리·음악 삭제

**이전 revision 정리와 음악 자체 삭제는 서로 다른 작업이다.**

- 이전 revision 정리는 백엔드 ACTIVE 전환 커밋 확인 후 해당 이전 벡터만 제거한다. 음악 삭제 기록을 만들지 않는다.
- 활성 확인·정리 요청에는 전환된 revision을 명시하고 오래된 요청이 최신 벡터를 지우지 않도록 검사한다.
- 활성 확인·정리 실패는 재요청 가능해야 한다. 확인되지 않은 기존 벡터는 조기 삭제하지 않는다.
- 전환 전에 시작한 검색이 v1 후보를 보낼 수 있으므로 정리 유예 또는 revision 불일치 재검색 정책이 필요하다.
- 음악 자체 삭제는 삭제 revision을 기록하고 해당 음악 벡터를 검색에서 제거한다. 삭제 기록은 유지해 과거 시도의 재등록을 막는다.
- 같은 삭제 요청은 중복 반영하지 않고 오래된 삭제 요청은 최신 revision을 제거하지 못하도록 한다.

활성 확인/정리 엔드포인트·확인 데이터·유예 기간·검색 재시도 규칙은 아직 미정이다.
이미 시작한 검색까지 항상 성공한다는 보장은 이 세부 정책을 구현·검증한 후 판단한다.

## 4. 상태·timeout·stale 재처리

AI GET은 대상 music_id + audioRevision의 processing / ready / failed / deleted를 반환한다.
동일 revision의 모델 재생성도 구분할 수 있도록 응답에 생성 조건 식별값을 포함하는 방향으로 설계한다.
ready는 특정 생성 조건의 벡터 저장 완료다. 벡터·로컬 경로·비밀값은 상태 응답에 포함하지 않는다.

| timeout 이후 상태 | 백엔드 처리 |
| --- | --- |
| ready | 최신 요청 확인 후 ACTIVE 전환 복구, AI 활성 확인 전달 |
| processing·유효기간 내 | 즉시 중복 실행하지 않고 상태 재조회 |
| processing·stale | 동일 revision·SHA-256으로 제한적 재처리 |
| failed | 입력 오류와 일시적 오류 구분 후 수정 또는 제한적 재처리 |
| deleted | 과거 생성 요청 재전송 금지 |

processing 기록은 모델 실행 전에 짧은 트랜잭션으로 커밋한다. 모델 실행 동안 DB 잠금을 유지하지 않는다.
stale 재처리는 새 attempt 소유권을 부여하고 과거 시도의 뒤늦은 완료·실패 기록을 차단한다.
실패·삭제·최신 revision 검사도 최종 저장 시 수행한다.
stale 임계 시간·상태 조회 간격·재시도 횟수는 측정 후 확정한다. stale=true 필드 표현은 AI 제안이다.

## 5. 검색과 최종 추천 책임

Spring은 ACTIVE `(musicId, audioRevision)` pair를 먼저 수집하고 Eligibility로 필터링한 뒤 최종 통과 pair를 AI에 전달한다. Eligibility가 ACTIVE revision을 확정하지 않는다.
AI는 두 값이 모두 일치하고 생성 조건이 호환되는 벡터만 **유사도 계산·정렬 전에** 검색 후보로 제한한다.
ID 집합과 revision 집합을 각각 비교하면 잘못된 쌍이 포함될 수 있으므로 쌍 자체를 검사한다.
AI는 요청 revision이 없거나 사용할 수 없어도 같은 musicId의 다른 audioRevision으로 대체하지 않는다. 현재 검색 조건과 비호환인 generation profile로 fallback하거나 검증에서 선택한 embedding identity를 다른 profile/row로 임의 대체하지 않는다.

NSUAI-30은 모든 입력 후보의 상태를 진단한다. 전체 요청 성공/실패는 NSUAI-48 orchestration의 책임이며, 하나라도 정상 진단이 아니면 NSUAI-31 ranking을 호출하지 않고 전체 요청을 실패시킨다. invalid 후보만 제외한 정상 부분 응답은 허용하지 않는다.
100개 중 3개 invalid일 때 97개 정상 반환, 500개 중 3개 invalid일 때 나머지의 Top100 정상 반환 모두 금지한다.
성공 응답 수는 `min(전달 후보 pair 수, 100)`이다. 검증과 ranking 사이 변경으로 partial success가 생기지 않도록 일관된 조회 전략을 후속 구현에서 적용하며 구체 transaction/snapshot 방식은 아직 정하지 않는다.
AI 후보 오류의 HTTP status/code·retryable 값·invalid pair 및 reason의 외부 schema는 TBD다. Spring 사용자 응답의 `503 RECOMMENDATION_UNAVAILABLE`을 AI 내부 오류 mapping으로 간주하지 않는다.
내부 primitive는 빈 후보에 빈 목록을 반환하지만 HTTP 빈 후보 정책은 017의 TBD로 유지한다. 후보 제한을 생략하거나 전체 DB 검색으로 fallback하지 않는다.
Spring의 호출 중 ACTIVE 변경 등 사후 재검증은 AI 응답 자체의 후보 범위·개수 검사 이후 수행하는 책임과 구분한다.

현행 추천 요청의 후보 field 이름은 017을 따른다. 아래 식별자 값은 구조 설명용이며 wire type 확정을 뜻하지 않는다. multipart 후보 전달은 과거 제안이다.

```json
[
  {"musicId": "music-example-001", "audioRevision": 1},
  {"musicId": "music-example-002", "audioRevision": 3}
]
```

기존 CLI Top5는 Audio 연동 확인용이다. Accepted 012에 따라 Spring은 통과한 모든 ACTIVE 후보 쌍을 AI에 전달하고, AI는 raw cosine 순위로 최대 100곡을 반환한다. 입력 후보 최대치는 NSUAI-15에서 성능·메모리·동시성 실측 후 결정하며 결과 반환 상한 100곡과 구분한다. Spring은 응답 순서를 재정렬하지 않는다.
AI의 raw cosine 순위는 AI 측에서 검증한다. Spring은 rank/order 연속성, 중복, 후보 범위, 결과 개수, 0~100 점수 유효성 및 표시 점수의 단조성을 확인하며 raw cosine은 Spring 계약에 포함하지 않는다.
AI 추천 결과의 API field는 017의 musicId·audioRevision·rank·resultVersion을 따르며 미확정 wire type·상세 schema는 그대로 남긴다. 외부 `resultVersion`은 하나이며 AI 내부 model/checkpoint, Embedding generation/preprocessing, transformation/calibration 및 상세 분석 정보와 구분한다. 검색 입력 의미와 predefined mapping은 Spring 책임이다.
005의 retrieval 50~100/Backend Top10, 009의 의미/BPM/Rhythm 평균 음악 순위, 008의 별도 AI Explanation API 호출은 Accepted 012의 범위로 대체됐다. BPM/Rhythm 측정과 요청 비교는 순위에 반영하지 않는 상세 정보다.
점수는 후보 독립 고정 0~100 음악 유사도이며 확률·적합 가능성이 아니다. 구체 변환/calibration은 NSUAI-12에서 정한다. 장애/timeout은 Accepted 010을 따른다.
**Reliability는 최종 추천 순위에 반영하지 않는다.** Risk Signal과 함께 별도 결과 정보로 표시한다.
현재 표시 점수는 음악 간 유사도이며 종합 적합도나 신뢰 확률이 아니다.

## 6. 내부 API·파일 전달 제안

요청은 완료 또는 실패까지 기다리는 동기 방식이다. 큐·worker·202 작업 접수 방식으로 바꾸지 않는다.
파일 직접 전달(multipart)은 초기 연동 권장안이며 인증·파일 상한·세부 DTO는 추가 검토한다.
백엔드가 원본을 보관하고 AI는 관리되는 임시 파일을 성공·실패 후 정리한다.
사용자가 임의 서버 경로·URL을 지정하도록 허용하지 않는다.

| API 제안 | 목적 |
| --- | --- |
| PUT /internal/v1/audio-embeddings/{music_id} | 파일·audioRevision·source_sha256 전달, revision별 생성·저장 |
| GET /internal/v1/audio-embeddings/{music_id}?audioRevision=2 | 특정 revision 처리 상태 확인 |
| POST /internal/v1/recommendations/search | 017의 현행 계약. canonicalText와 최종 후보 pair 전달, 전체 후보 검증 성공 후 raw cosine 상위 최대 100곡 반환. HTTP 구현은 후속 범위 |
| DELETE /internal/v1/audio-embeddings/{music_id}?audioRevision=3 | 음악 자체 삭제와 삭제 기록 유지 |
| 활성 전환 확인·이전 revision 정리 | 신규 계약 필요. 위 음악 삭제 API를 재사용하지 않음 |

신규 revision 저장은 201, 동일 결과 재사용은 200을 제안하며 DB 커밋 이후 응답한다.
오래된 요청·해시 충돌·유효한 processing 중복 요청은 구분 가능한 409를 제안한다.
해시/디코딩 입력 오류·용량 제한·일시적 장애·예상치 못한 장애를 각각 구분한다.
오류 응답에 비밀번호·DB 접속 문자열·원본 스택을 포함하지 않는다.
서비스 인증은 전용 토큰과 HTTPS/사설망을 권장하되 공급 방식과 오류 스키마는 검토가 필요하다.

## 7. 구현 순서와 이슈

1. NSUAI-43: revision/source/profile 저장 identity와 정확 조회 완료. 이후 처리 상태·시도 소유권·삭제 기록은 후속 lifecycle 범위
2. NSUAI-44/45/46: ACTIVE 확인·기존 revision 보존·재시도·음악 삭제·이전 revision 정리
3. NSUAI-30 진단·NSUAI-31 ranking은 완료. NSUAI-48 전체 성공/실패 제어와 동기 업무 API는 후속 범위
4. 동시 갱신/삭제·stale·timeout·전환 확인 실패·검색 중 정리 테스트
5. 실제 등록→v2 ready→ACTIVE 커밋 확인→검색→v1 정리→음악 삭제 통합 검증

기존 `0001_audio_embeddings.sql` 체크섬은 유지하고 추가 마이그레이션으로 변경한다.
기존 row의 revision은 추정 backfill하지 않는다. 0003은 Backend revision 매핑이 없는 기존 Audio row가 있으면 안전하게 차단하며 데이터를 삭제하지 않는다.
현재 저장소는 동일 music_id의 여러 revision과 동일 revision의 여러 generation profile을 보존한다. 업무 HTTP·ACTIVE lifecycle이 완료됐다는 뜻은 아니다.
Text Embedding 생성·저장 기반(NSUAI-41·42)은 구현됐지만 Spring predefined mapping, canonical input 업무 API 연동은 후속 작업이다. Spring은 UI/요청 값을 검증하고 사전 정의 mapping으로 canonical 의미를 만든다. AI는 전달된 canonical text를 Text Embedding에 사용하며 OPUS-MT/M2M100/Qwen/LLM으로 번역하거나 의미를 재해석하지 않는다. BPM/Rhythm은 측정값과 요청 비교 상세 정보로 다루며 0~100 순위 점수가 아니다. Spring의 추천 이유 템플릿과 미래 LLM 가능성은 별도 범위이며 [설명 계약 문서](RECOMMENDATION_EXPLANATION_CONTRACT.md)를 참조한다.

2026-10-04 Linear NSUAI-25·26·27, NSU-63과 연결 GitHub AI #18·19·20, Backend #68에 이 기준을 반영했다.
기존 단일 벡터 교체안은 더 이상 현재 구현 목표로 사용하지 않는다.

## 변경 이력 — 현행 목표와 이전 계약의 차이

과거 구현 기준에는 "현재 구현은 음악 ID당 벡터 하나의 최초 저장/동일 결과 재사용" 및 `POST /internal/v1/audio-search`·multipart 후보 전달 제안이 있었다. 이는 NSUAI-43/30/31 및 017 이전 이력으로 보존하며 현행 저장·추천 계약이 아니다.

2026-10-04의 retrieval 50~100 → Backend Ranker Top10과 아티스트 집계 계획은 당시 기록이다.
2026-10-07 제안 방향은 2026-10-10 Accepted 서버 협의 012에 따라 동기화했다. 결과 최대 100곡, 모든 ACTIVE 후보 쌍 전달, raw cosine 순위 유지, Spring의 순서 재정렬 금지, Spring 템플릿 설명을 반영했다. API 구현은 별도 상태다.
