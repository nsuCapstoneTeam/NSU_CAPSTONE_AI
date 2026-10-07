# 현재 AI 작업 기준: 전체 곡 유사도 정렬과 반환

## 상태와 출처

2026-10-07 이 작업 대화에서 사용자가 아래 흐름을 결정하고 문서 정합화를 승인했다.
**사용자 결정 반영, 구현 전**이며 팀 전체 Linear 승인이나 업무 API 구현 완료를 뜻하지 않는다.

서버 간 정책은 [Linear 서버 협의 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 **Accepted** 문서를, 용어는 [Linear 용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 먼저 확인합니다.
이번 전체 곡 반환·유사도 정렬·집계 없음·비교 설명 폐기는 **2026-10-07 이 작업 대화의 사용자 결정**입니다. Linear의 승인 상태를 변경하거나 기존 Accepted 결정으로 표시하지 않습니다.
Accepted 005의 retrieval 50~100/Backend Top10, 009의 항목 평균 순위 및 용어집의 최대 100곡 설명과 차이가 남아 있습니다. 저장소의 현행 작업 목표는 이번 사용자 결정으로 구분하고 서버 협의 정합화 필요 사항을 표시합니다.
Proposed 011·012의 수치 정밀도·결과 버전·100곡 상한·설명 주체 변경 등은 확정 계약으로 가져오지 않습니다.

## 현행 처리 흐름

```text
Spring Hard Filter
→ 통과한 전체 ACTIVE 곡 (music_id, audioRevision) 전달
→ AI가 전체 곡의 공통 Embedding/유사도 계산 및 정렬
→ 전체 결과 Spring 반환
→ Spring이 유사도 기준으로 곡 표시
→ 사용자가 별도 버튼으로 해당 곡의 Artist와 매칭
```

- Spring은 Hard Filter·권한·ACTIVE revision 확인·곡/Artist 정보 연결·표시와 매칭 동작을 담당한다.
- AI는 전체 전달 곡을 분석 대상으로 삼고 유사도 순으로 정렬해 전체 결과를 반환한다.
  서비스 목표에 CLI Top5, retrieval 50~100 또는 Proposed 012의 상위 100곡 잘라내기를 적용하지 않는다.
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
  Top10·신규 슬롯 전체를 이번 결정으로 승인하거나 폐기하지 않는다.
- [009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd): 의미·BPM·리듬 항목, 계산하지 못한 점수는 `null`과 사유,
  의미 점수가 없는 곡의 후보 제외 원칙을 참조한다.
  유효 항목 평균은 기존 Accepted 내용으로 구분하며 이번 유사도 정렬 목표의 순위 수식으로 사용하지 않는다.
- [008](https://linear.app/nsu-capstone/document/008-추천-이유-생성-흐름-ae6cde7df2de): 곡별 추천 이유는 추가 AI 호출·템플릿 우선, 실패 시 이유만 `null`.
  후보 비교 설명 폐기와 추천 이유 자체의 폐기는 다르다. 구체 설명 대상·호출 데이터는 전체 결과 흐름과 정합화가 필요하다.
- [010](https://linear.app/nsu-capstone/document/010-ai-곡-검색-실패시간-초과-시-추천-api-응답-46a63dece138): 검색 장애를 결과 0건으로 숨기지 않는다.
  오류의 `code`·`retryable`·`requestId`, 제한적 재시도 및 503/504 정책을 따른다.

전체 처리 목표와 누락 시 후보 제외·실패 정책의 응답 표현은 서버 협의 정합화 과제다.
호환되지 않는 곡이나 실패를 조용히 생략해 정상적인 전체 처리처럼 보고하지 않는다.
신뢰 정보는 음악 유사도 순위와 분리한다. 음악 유사도를 확률·일치율로 표현하지 않는다.

## 현재 구현과 남은 계약

현재는 단일 crop 공통 생성기, 파일/DB 검색 CLI, 임시 표시 점수, Health API가 구현되어 있다.
전체 후보 쌍 HTTP 처리·전체 반환·화면·매칭 버튼과 ADR-0007의 길이 validation/8 Chunk는 구현 전이다.
현재 CLI Top5·DB `top_k` 상한·과거 측정값은 그대로이며 새 목표를 구현한 것으로 설명하지 않는다.

요청의 음악/Text 표현, endpoint·DTO, 허용 후보 수·자원 한도·동시성·timeout,
누락/실패 곡의 응답 표현, 점수 정밀도·동점 처리·설명 대상은 별도 계약/검증이 필요하다.
Proposed 값을 임의로 채택하지 않는다.

## 변경 이력

- 2026-10-05: AI 측 CLAP 중심 변경 방향을 제안했다. 당시 반환 개수·팀 합의는 미정이었다.
- 2026-10-07: 사용자가 전체 통과 곡 분석·정렬·전체 반환, Spring 곡 표시·별도 사용자 매칭,
  아티스트 집계 없음·후보 비교 설명 폐기를 확정했다. 이전 50~100/Ranker Top10을 현행 실행 목표로 사용하지 않는다.
  Linear/NSU_CAPSTONE은 이번 문서 작업에서 수정하지 않는다.
- 당시 논거·청취/피드백 제안은 [과거 회의 자료](../협업-가이드/CLAP_RECOMMENDATION_MEETING_PROPOSAL.md)에 보존한다.
