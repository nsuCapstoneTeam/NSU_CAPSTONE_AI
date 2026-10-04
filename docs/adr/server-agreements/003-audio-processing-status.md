# 003. AI 처리 상태와 Backend 활성 상태 분리

## Status

Accepted — 2026-10-04 사용자 전달 백엔드 확인 기준. 구현 전.

## Context

Backend PROCESSING만으로는 AI가 실행 중인지 저장을 완료했는지 구분할 수 없다.
AI 저장 완료가 Backend 음악 활성화 완료를 의미하지도 않는다.

## Decision

AI는 music_id·audioRevision 대상의 processing / ready / failed / deleted 상태를 조회할 수 있게 한다.
ready는 해당 생성 조건의 벡터 저장 완료이고 Backend ACTIVE는 서비스에서 사용할 revision이다.
처리 상태와 검색 가능한 벡터를 분리해 v2 processing·failed 중에도 v1을 유지한다.
등록·검색의 요청/응답은 동기 방식을 유지한다.

## Rationale

각 서버가 완료한 범위를 정확히 표현하고 timeout 이후 실제 저장 결과를 확인하기 위함이다.
상태 조회를 제공한다고 큐 기반 비동기 접수로 전환하는 것은 아니다.

## Consequences

진행·완료·실패를 구분해 복구할 수 있다.
상태 저장·조회와 revision/생성 조건 구분이 추가로 필요하다.
stale 복구 정책은 [ADR 004](004-timeout-and-stale-retry.md)에서 관리한다.

## Server Responsibilities

- Backend: 원본 revision의 PROCESSING·ACTIVE 관리, AI 상태에 따른 서비스 전환.
- AI: 처리 상태 저장·조회, ready 전에 저장 커밋, 분류 가능한 실패 사유 기록.

## Contract

모델 실행 전 processing 기록을 커밋하고 모델 실행 동안 DB 트랜잭션을 유지하지 않는다.
GET은 조회 대상 revision을 식별하며 생성 조건 식별값도 구분할 수 있어야 한다.
상태 응답에 벡터·서버 파일 경로·접속 비밀값을 노출하지 않는다.
필드·오류 형식은 [API 계약](../../api/AUDIO_SYNC_BACKEND_HANDOFF.md)에서 구체화한다.

관련 이슈: [NSUAI-27](https://linear.app/nsu-capstone/issue/NSUAI-27), [AI #20](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/issues/20).
