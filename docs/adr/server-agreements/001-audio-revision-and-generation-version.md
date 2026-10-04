# 001. Audio revision과 생성 버전 분리

## Status

Accepted — 2026-10-04 사용자 전달 백엔드 확인 기준. 구현 전.
generation_version의 구체 형식은 미정이다.

## Context

음악 파일 변경, JPA 엔티티 수정, AI 모델 변경을 같은 버전으로 관리하면
제목 수정에도 재생성하거나 새 모델에서 이전 벡터를 재사용할 수 있다.

## Decision

audioRevision은 원본 Audio 변경·삭제에만 증가시키고 JPA @Version과 분리한다.
모델·checkpoint·전처리 조건은 별도로 관리한다.
벡터 재사용은 music_id·audioRevision·SHA-256·생성 조건이 모두 같을 때만 허용한다.
동일 파일이라도 생성 조건이 다르면 재생성한다.

## Rationale

서비스 데이터의 수정과 파일 변경, 모델 변경의 원인을 구분해
필요한 재생성만 수행하고 다른 생성 조건의 벡터를 혼동하지 않기 위함이다.

## Consequences

불필요한 재생성과 잘못된 재사용을 줄인다.
백엔드는 파일 revision을 별도로 관리해야 하며 AI는 생성 조건과 검색 호환성을 기록해야 한다.
모델 재생성 결과의 저장·전환 세부 정책은 추가 설계가 필요하다.

## Server Responsibilities

- Backend: Sample ID·audioRevision 발급, 원본 파일 관리, JPA 잠금 버전과 분리.
- AI: 원본 해시·모델·전처리 조건 검증과 기록, 재사용·재생성 판단.

## Contract

source_version은 API에서 audioRevision을 나타내는 필드 제안이며 모델 버전으로 사용하지 않는다.
같은 revision에 다른 파일 해시를 연결하지 않는다.
모델 변경 때문에 원본 audioRevision을 증가시키지 않는다.
생성 조건 식별값과 SHA 전달 방식은 [API 계약](../../api/AUDIO_SYNC_BACKEND_HANDOFF.md)에서 구체화한다.

관련 이슈: [NSUAI-25](https://linear.app/nsu-capstone/issue/NSUAI-25), [AI #18](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/issues/18).
