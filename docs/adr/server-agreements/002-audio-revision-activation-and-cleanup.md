# 002. Revision별 벡터 보관과 ACTIVE 전환 후 정리

## Status

Accepted — 2026-10-04 사용자 후속 결정. 구현 전.
기존 단일 벡터 교체안을 대체한다. 활성 확인 API·정리 유예 정책은 미정이다.

## Context

AI가 v1 벡터를 v2로 교체한 뒤 Backend가 ACTIVE를 전환하기 전에는
Backend의 v1 후보와 일치하는 벡터가 없어 검색에서 빠진다.
두 서버의 DB 커밋은 하나의 트랜잭션이 아니다.

## Decision

1. Backend가 v1 ACTIVE를 유지하고 v2를 PROCESSING으로 보관한다.
2. AI는 v2 생성·저장에 성공해도 v1과 v2 벡터를 함께 보관한다.
3. Backend가 최신 요청·삭제 여부를 확인하고 v2 ACTIVE 전환을 커밋한다.
4. Backend가 커밋된 전환 정보를 AI에 명시적으로 전달한다.
5. AI는 전환 확인 후 유예 또는 재검색 정책에 따라 v1 벡터를 정리한다.

새 생성 실패·timeout·전환 전달 실패만으로 기존 벡터를 삭제하지 않는다.
이전 revision 정리와 음악 자체 삭제는 별개 작업이다.

## Rationale

AI 저장과 Backend 활성화 사이에도 현재 ACTIVE revision을 검색할 수 있도록 하고,
실패한 신규 파일 때문에 정상 파일의 검색을 중단하지 않기 위함이다.

## Consequences

전환 중 기존 음악 검색을 유지할 수 있다.
revision별 저장 공간과 활성 확인·정리 재시도가 필요하다.
이미 시작한 v1 검색과 정리가 충돌할 수 있어 유예 또는 revision 불일치 재검색 정책을 정해야 한다.

## Server Responsibilities

- Backend: ACTIVE의 기준 관리, 최신 요청 검사, 전환 커밋, 전환 완료 전달·복구.
- AI: revision별 벡터 보관, 전환 확인 이전 보존, 안전한 이전 벡터 정리·삭제 기록 유지.

## Contract

ready는 ACTIVE가 아니다. AI 생성 성공만으로 이전 revision을 덮어쓰거나 삭제하지 않는다.
오래된 활성 확인·정리 요청은 최신 벡터를 제거하지 못해야 한다.
음악 자체 삭제는 삭제 revision을 유지해 과거 처리의 재등록을 차단한다.
세부 엔드포인트는 [API 계약](../../api/AUDIO_SYNC_BACKEND_HANDOFF.md)에서 정의하며 현재 미정이다.

관련 이슈: [NSUAI-26](https://linear.app/nsu-capstone/issue/NSUAI-26), [NSU-63](https://linear.app/nsu-capstone/issue/NSU-63), [AI #19](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/issues/19), [Backend #68](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE/issues/68).
