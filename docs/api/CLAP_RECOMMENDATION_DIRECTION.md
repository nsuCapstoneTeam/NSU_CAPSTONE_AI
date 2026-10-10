# 현재 AI 작업 기준: 음악 유사도 기반 추천

## 상태와 출처

2026-10-10 현재 서버 간 계약 기준은 [Accepted 012](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba)다. 이 상태는 정책 합의를 뜻하며 AI 업무 API 및 추천 흐름의 구현 완료를 뜻하지 않는다.

서버 간 정책은 [Linear 서버 협의 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 **Accepted** 문서를, 용어는 [Linear 용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 먼저 확인합니다.
012는 raw cosine 순위와 후보 독립 고정 0~100 음악 유사도 변환을 정하고, AI가 최대 100곡을 반환한다. Spring은 AI가 정한 순서를 재정렬하지 않고 구조적 응답 조건을 확인한다. 012의 합의 상태와 미구현된 서비스 흐름은 구분한다.
012가 005의 retrieval 50~100/Backend Top10, 008의 별도 AI Explanation API 호출, 009의 의미/BPM/Rhythm 평균 순위 범위를 대체했다. 006 신규 아티스트 전용 retrieval 제안은 철회됐다. 010은 유지되고, 011은 012 §4.3에 의해 기존 Superseded 상태를 유지한다. 013은 Proposed 상태의 별도 MP3/M4A 검증 협의이며 이번 문서의 기준으로 섞지 않는다.

## 현행 처리 흐름

```text
Spring Eligibility
→ 모든 통과 ACTIVE 후보 쌍 (music_id, audioRevision) 전달
→ AI가 raw cosine으로 정렬하고 최대 100곡 반환
→ Spring이 순서를 유지하고 응답 구조·범위를 검증
→ Spring이 구조화된 근거로 템플릿 설명을 구성
→ 결과 저장·응답; 화면은 상위 10곡부터 표시
```

- Spring은 Eligibility, 권한 및 ACTIVE revision 재검증, AI 응답의 구조적 검사, 곡/Artist 연결, 신뢰 정보 결합, 템플릿 설명, 저장과 응답을 담당한다.
- Spring은 통과한 모든 ACTIVE 후보 쌍을 보낸다. 입력 최대치는 아직 숫자로 확정하지 않았으며 NSUAI-15의 성능·메모리·동시성 실측 후 정한다. 후보 상한 초과 시 503과 운영 경보를 사용하며 임의 절단이나 분할 호출을 하지 않는다.
- AI는 처리 가능한 후보를 raw cosine 내림차순으로 정렬해 최대 100곡을 반환한다. 100곡은 반환 상한이며 입력 후보 최대치와 구분한다. Spring은 순서를 재정렬하지 않는다.
- Spring은 rank/order 연속성, 중복, 후보 범위, 결과 개수, score 범위와 표시 score의 단조성을 검사한다. Spring 계약에는 raw cosine을 추가하지 않으므로 raw cosine 순위 자체는 AI 측 테스트가 검증한다.
- 곡→아티스트 집계를 하지 않는다. Artist별 대표 곡 선정이나 집계 순위를 만들지 않는다.
- 후보 간 비교 설명·항목 diff 문장은 폐기한다. 기준곡과 추천곡의 직접 청취는 별개이며 기능 승인 범위를 확대하지 않는다.
- 검색 결과 표시 자체가 매칭 성사가 아니다. 사용자가 곡에 연결된 Artist를 선택해 별도 매칭 동작을 수행한다.
  버튼의 API·Offer 처리·동의 절차는 Backend/Frontend에서 별도 설계한다.
- 호환되는 저장 벡터의 재사용과 필요한 생성의 구체 실행 방식은 후속 구현에서 정한다.
  전체 곡을 대상으로 한다는 것이 모든 후보를 매 검색마다 강제로 재생성한다는 뜻은 아니다.

## Accepted 서버 정책과 역할 구분

- [001](https://linear.app/nsu-capstone/document/001-audio-revision과-생성-버전-분리-c5c95e36f3e2)·[002](https://linear.app/nsu-capstone/document/002-revision별-벡터-보관과-active-전환-후-정리-e974a4620c8f)·[003](https://linear.app/nsu-capstone/document/003-ai-처리-상태와-backend-활성-상태-분리-3a0c0ca81f50)·[004](https://linear.app/nsu-capstone/document/004-timeout-후-상태-확인과-stale-재처리-bc71a0dcdffd):
  원본 revision/생성 버전 분리, ACTIVE 전환 전 기존 벡터 보존, 상태 조회·stale 복구 원칙 유지.
- [007](https://linear.app/nsu-capstone/document/007-추천-단위는-곡-69137a45b2c6): 곡 단위와 아티스트 집계 없음의 관련 Accepted 근거.
  결과 최대 100곡 및 신규 슬롯 미적용은 Accepted 012의 현재 범위에 따른다.
- [009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd): BPM/Rhythm 측정·요청 비교 상세와 `null`+reason, 공연 형태 Hard Filter 등 유지되는 부분만 참조한다. 의미/BPM/Rhythm 평균은 음악 순위 기준에서 대체됐다.
- [008](https://linear.app/nsu-capstone/document/008-추천-이유-생성-흐름-ae6cde7df2de): 별도 AI Explanation API 호출 범위는 대체됐다. Spring이 AI의 구조화된 상세 정보·행사 요청 해석·실제 통과 조건을 근거로 템플릿 설명을 만든다. LLM은 필수가 아니다.
- [010](https://linear.app/nsu-capstone/document/010-ai-곡-검색-실패시간-초과-시-추천-api-응답-46a63dece138): 검색 장애를 결과 0건으로 숨기지 않는다.
  오류의 `code`·`retryable`·`requestId`, 제한적 재시도 및 503/504 정책을 따른다.

처리 가능한 입력 상한의 수치와 세부 DTO/schema는 실측·인터페이스 설계가 남아 있다. 호환되지 않는 곡이나 실패를 조용히 생략해 정상 처리처럼 보고하지 않는다.
신뢰 정보는 음악 유사도 순위와 분리한다. 음악 유사도를 확률·일치율로 표현하지 않는다.

## 현재 구현과 남은 계약

현재 공통 AudioEmbeddingGenerator는 ADR-0007의 60~80초 validation과 처음 56초의 고정 8 Chunk 집계를 적용한다. 파일/DB 검색 CLI, 임시 표시 점수, Health API도 구현되어 있다.
전체 후보 쌍 HTTP 처리·전체 반환·화면·매칭 버튼은 아직 구현 전이다.
현재 CLI Top5·DB `top_k` 상한·과거 측정값은 로컬 검증 범위이며 새 서비스 목표의 반환 정책으로 취급하지 않는다.

요청의 음악/Text 표현, endpoint·DTO, 측정으로 정할 입력 최대치·자원 한도·동시성·timeout, 누락/실패 표현, version field의 세부 schema, 설명 대상은 별도 인터페이스 설계·검증이 남아 있다.
외부 결과는 단일 `resultVersion`으로 식별하고 AI 내부에서는 model/checkpoint, Embedding generation/preprocessing, transformation/calibration, 상세 분석, 요청 해석 버전을 분리 추적한다. 이는 설계 합의이며 구체 내부 metadata 구현 완료를 뜻하지 않는다.

## 변경 이력

- 2026-10-05: AI 측 CLAP 중심 변경 방향을 제안했다. 당시 반환 개수·팀 합의는 미정이었다.
- 2026-10-10: Linear 서버 협의 012 Accepted에 따라 최대 100곡 결과 반환, raw cosine 순위, Spring의 순서 유지·검증, 요청 원문 해석, Spring 템플릿 설명, 후보 독립 고정 점수, 버전 분리 및 BPM/Rhythm 비순위 상세 범위를 반영했다. 구현 전 상태와 입력 후보 상한의 실측 미결정을 유지한다.
- 당시 논거·청취/피드백 제안은 [과거 회의 자료](../협업-가이드/CLAP_RECOMMENDATION_MEETING_PROPOSAL.md)에 보존한다.
