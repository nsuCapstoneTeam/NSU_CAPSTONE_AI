# 004. Timeout 후 상태 확인과 stale 재처리

## Status

Accepted — 2026-10-04 사용자 전달 백엔드 확인 기준. 구현 전.
timeout·stale 임계 시간·조회 간격·재시도 횟수는 미정이다.

## Context

HTTP timeout이 발생해도 AI 작업은 완료될 수 있다.
즉시 재요청하면 중복 추론이 발생하며 서버 중단 시 processing이 계속 남을 수도 있다.

## Decision

Backend는 timeout 후 특정 revision의 상태를 확인한다.
ready면 최신 요청을 검사하고 ACTIVE 전환을 복구한다.
유효한 processing이면 중복 실행하지 않고 재조회한다.
stale processing은 같은 audioRevision·SHA-256으로 제한적 재처리를 허용한다.
failed는 입력 오류와 일시적 오류를 구분하고 deleted에는 과거 생성 요청을 재전송하지 않는다.

## Rationale

timeout을 저장 실패로 단정하지 않고 중복 처리와 과거 결과의 덮어쓰기를 방지하기 위함이다.

## Consequences

중단된 처리의 복구가 가능하지만 실행 시도 소유권과 유효기간 관리가 필요하다.
stale로 판단된 기존 실행이 살아 있을 수 있으므로 늦은 결과를 차단해야 한다.
실측 전 처리시간이나 복구 지연을 보장하지 않는다.

## Server Responsibilities

- Backend: timeout 적용, 상태 확인, 제한된 재요청, ACTIVE 전환·확인 전달 복구.
- AI: stale 판정, 새 처리 소유권 부여, 최종 저장 시 현재 소유권·revision·삭제 검사.

## Contract

동일 입력은 revision·해시·생성 조건으로 판별한다.
과거 시도는 최신 시도의 성공·실패 상태와 벡터를 변경하지 못해야 한다.
처리 소유권 재검증과 결과 반영은 같은 DB 트랜잭션에서 수행한다.
attempt_id·stale 표시 형식과 오류 스키마는 [API 계약](../../api/AUDIO_SYNC_BACKEND_HANDOFF.md)의 후속 설계 사항이다.

관련 이슈: [NSUAI-27](https://linear.app/nsu-capstone/issue/NSUAI-27), [NSU-63](https://linear.app/nsu-capstone/issue/NSU-63), [Backend #68](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE/issues/68).
