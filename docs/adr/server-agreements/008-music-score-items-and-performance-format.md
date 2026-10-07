# 008. 음악 점수 항목과 공연 형태의 분리

> 과거 제안 기록 보존. 아래 Status·Decision은 당시 내용이며 현행 기준이 아니다. 로컬 번호는 Linear의 같은 번호와 내용이 다르다. 현행 서버 정책은 [Linear 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 Accepted 문서, 이번 사용자 결정은 [AI 작업 기준](../../api/CLAP_RECOMMENDATION_DIRECTION.md)을 확인한다.
>
> 관련 현행 확인 위치: [Linear 009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd). Proposed 012를 승인하거나 당시 기록을 재작성하지 않는다.


## Status

Proposed — 2026-10-05 AI 협의 6/9에 대한 사용자의 AI 측 개발 기준 선택.
AI 측 방향은 이 기준으로 정리하되 메인 SSOT·백엔드 반영과 팀 전체 합의는 별도 확인한다.
기존 Accepted ADR은 유지하며 구현 완료를 뜻하지 않는다.

## Context

공연 스타일이 음악 분위기인지 실제 공연 형태인지 정의되지 않아 의미 점수와
중복 반영되거나 음원으로 판단하기 어려운 정보를 점수화할 수 있다.

## Decision

- AI는 의미·BPM·리듬 3개 음악 항목 점수를 계산한다.
- 음악 분위기·스타일은 의미 점수에 포함하며 별도 공연 스타일 점수로 중복 반영하지 않는다.
- 밴드·솔로·DJ 등의 공연 형태는 Spring이 프로필과 행사 요청을 비교한다.
  반드시 필요한 조건이면 PASS/FAIL 필터로 처리한다.
- Spring이 곡→아티스트 집계 후 합의된 항목 점수로 종합 점수·Top10을 계산한다.
- 별도 아티스트 적합도는 정의 없이 평균 항목에 추가하지 않는다.

## Rationale

음악의 의미적 유사성과 실제 공연 구성을 구분해 중복 점수 반영을 방지한다.
프로필·행사 조건을 소유한 Spring에서 공연 형태 조건을 판단한다.

## Consequences

AI와 Backend의 입력·책임을 구분할 수 있다. 기존 요구사항의 공연 스타일 항목은
메인 SSOT 소유자와 정합화해야 한다. 음원만으로 실제 공연 능력이나 관객 반응을
점수화하지 않는다. BPM·리듬 점수는 후속 구현이며 고정 수식·기준은 검증이 필요하다.

## Server Responsibilities

- AI: 곡 단위 의미·BPM·리듬 항목 점수와 계산 근거 제공.
- Spring: 공연 형태 비교·필수 조건 필터, 아티스트 집계·종합 점수·최종 Top10.

## Contract

공연 형태 필터를 종합 점수 평균에 넣지 않는다.
프로필 필드·공연 형태 분류·비교 규칙은 미정이다.
누락 점수의 0점 대체·평균 제외·최소 유효 항목 수·추천 가능 여부도 이번에 확정하지 않는다.
항목별 점수 기준 버전·유효 여부·실패 사유의 필드는 추가 협의한다.

관련 이슈: [NSUAI-9](https://linear.app/nsu-capstone/issue/NSUAI-9),
[NSUAI-12](https://linear.app/nsu-capstone/issue/NSUAI-12),
[NSUAI-13](https://linear.app/nsu-capstone/issue/NSUAI-13).
