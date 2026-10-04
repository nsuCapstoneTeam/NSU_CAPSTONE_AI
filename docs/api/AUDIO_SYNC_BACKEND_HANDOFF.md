# 백엔드 전달용 Audio 동기 연동 계약

상태: **사용자 전달 백엔드 확인·후속 결정 반영, 구현 전**. 2026-10-04.
기존 벡터 단일 교체안은 revision별 보관·ACTIVE 전환 확인 후 정리 방식으로 대체한다.
아래 처리 원칙과 미정인 API 세부 제안을 구분한다. 현재 CLI가 이 계약을 구현한 것은 아니다.

## 1. 책임과 식별자

백엔드는 음악 Sample ID·아티스트 소유 관계·권한·원본 파일·ACTIVE revision을 관리한다.
AI는 임베딩·처리 상태·생성 조건을 관리한다. 개인정보를 벡터 테이블에 복제하지 않는다.
등록 음악에 행사 Request ID를 붙이지 않으며 검색 입력은 후보 음악으로 저장하지 않는다.

| 식별 정보 | 의미 |
| --- | --- |
| music_id | 백엔드 Sample ID의 문자열 표현. 현재 코드의 1~200자·앞뒤 공백 금지 규칙 유지 |
| source_version | 백엔드 audioRevision. JPA @Version과 분리하며 원본 Audio 변경·삭제에만 증가 |
| source_sha256 | 원본 바이트의 SHA-256. 백엔드 계산·AI 재계산 검증은 연동 제안 |
| generation_version | 모델·checkpoint·전처리·출력 영향 설정의 식별값. 구체 형식은 AI 후속 설계 |
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

저장은 music_id + audioRevision 단위로 revision별 벡터를 보관하는 구조로 변경해야 한다.
처리 상태와 기존 검색 벡터 상태를 분리한다. 모델 재생성을 위한 generation 단위 저장 정책은 추가 설계한다.
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

백엔드는 Eligibility Filter 이후 현재 ACTIVE인 (music_id, audioRevision) 쌍을 전달한다.
AI는 두 값이 모두 일치하고 생성 조건이 호환되는 벡터만 **TopK 선정 전에** 검색 후보로 제한한다.
ID 집합과 revision 집합을 각각 비교하면 잘못된 쌍이 포함될 수 있으므로 쌍 자체를 검사한다.
빈 후보 배열은 빈 결과이며 실제 추천 경로에서 후보 제한을 생략하지 않는다.
검색 후 백엔드는 현재 ACTIVE·Eligibility를 재검증하고 필요하면 추가 후보를 조회한다.

후보 필드 형식 제안 (`candidates`를 multipart JSON 배열 문자열로 전달):

```json
[
  {"music_id": "123", "source_version": 1},
  {"music_id": "456", "source_version": 3}
]
```

기존 CLI Top5는 Audio 연동 확인용이다. 최종 경로는 AI retrieval top_k=50~100 → Backend Ranker 최종 Top10이다.
AI 결과에는 music_id·source_version·rank·cosine_similarity·임시 audio_similarity_score를 포함하는 방식으로 제안한다.
후보가 부족하면 있는 만큼 반환한다. 종합 점수로 정렬하기 전에 Audio 후보를 5곡으로 자르지 않는다.
곡을 아티스트 추천으로 묶는 방식과 최종 Matching Score는 백엔드 Ranker 계약에서 정의한다.
**Reliability는 최종 추천 순위에 반영하지 않는다.** Risk Signal과 함께 별도 결과 정보로 표시한다.
현재 표시 점수는 음악 간 유사도이며 종합 적합도나 신뢰 확률이 아니다.

## 6. 내부 API·파일 전달 제안

요청은 완료 또는 실패까지 기다리는 동기 방식이다. 큐·worker·202 작업 접수 방식으로 바꾸지 않는다.
파일 직접 전달(multipart)은 초기 연동 권장안이며 인증·파일 상한·세부 DTO는 추가 검토한다.
백엔드가 원본을 보관하고 AI는 관리되는 임시 파일을 성공·실패 후 정리한다.
사용자가 임의 서버 경로·URL을 지정하도록 허용하지 않는다.

| API 제안 | 목적 |
| --- | --- |
| PUT /internal/v1/audio-embeddings/{music_id} | 파일·source_version·source_sha256 전달, revision별 생성·저장 |
| GET /internal/v1/audio-embeddings/{music_id}?source_version=2 | 특정 revision 처리 상태 확인 |
| POST /internal/v1/audio-search | 검색 파일·후보 쌍·top_k 전달, retrieval 결과 반환 |
| DELETE /internal/v1/audio-embeddings/{music_id}?source_version=3 | 음악 자체 삭제와 삭제 기록 유지 |
| 활성 전환 확인·이전 revision 정리 | 신규 계약 필요. 위 음악 삭제 API를 재사용하지 않음 |

신규 revision 저장은 201, 동일 결과 재사용은 200을 제안하며 DB 커밋 이후 응답한다.
오래된 요청·해시 충돌·유효한 processing 중복 요청은 구분 가능한 409를 제안한다.
해시/디코딩 입력 오류·용량 제한·일시적 장애·예상치 못한 장애를 각각 구분한다.
오류 응답에 비밀번호·DB 접속 문자열·원본 스택을 포함하지 않는다.
서비스 인증은 전용 토큰과 HTTPS/사설망을 권장하되 공급 방식과 오류 스키마는 검토가 필요하다.

## 7. 구현 순서와 이슈

1. revision별 벡터·처리 상태·시도 소유권·삭제 기록의 추가 마이그레이션
2. revision별 저장·조회·음악 삭제와 ACTIVE 확인·이전 revision 정리 서비스
3. 후보 쌍 검색·revision 반환·동기 업무 API
4. 동시 갱신/삭제·stale·timeout·전환 확인 실패·검색 중 정리 테스트
5. 실제 등록→v2 ready→ACTIVE 커밋 확인→검색→v1 정리→음악 삭제 통합 검증

기존 `0001_audio_embeddings.sql` 체크섬은 유지하고 추가 마이그레이션으로 변경한다.
기존 CLI 데이터의 초기 revision 부여와 CLI의 검증 우회 방지도 함께 설계한다.
현재 구현은 음악 ID당 벡터 하나의 최초 저장/동일 결과 재사용이며 위 기능은 미구현이다.
Text 저장·번역, BPM/리듬·최종 종합 점수 구현은 이 문서 범위 밖이다.

2026-10-04 Linear NSUAI-25·26·27, NSU-63과 연결 GitHub AI #18·19·20, Backend #68에 이 기준을 반영했다.
기존 단일 벡터 교체안은 더 이상 현재 구현 목표로 사용하지 않는다.
