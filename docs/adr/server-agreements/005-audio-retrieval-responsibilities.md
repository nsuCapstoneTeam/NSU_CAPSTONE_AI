# 005. Audio 후보 검색과 최종 추천 역할 분담

## Status

Accepted — 2026-10-04 사용자 전달 백엔드 확인 기준. 구현 전.
현재 CLI Top5는 연동 검증용으로 유지한다. 후보 필드 형식·충원 정책은 미정이다.

## Context

Audio 유사도만으로 먼저 5곡을 선택하면 행사 조건 적용 후 후보가 부족해질 수 있다.
음악 ID만 전달하면 신규 파일과 기존 ACTIVE 파일을 구분하지 못한다.
Reliability를 Matching Score에 합산하는 것은 기존 정책과도 맞지 않는다.

## Decision

Backend는 Eligibility Filter 이후 ACTIVE인 (music_id, audioRevision) 쌍을 전달한다.
AI는 일치하는 호환 벡터를 검색 전에 제한하고 retrieval 50~100개 후보를 반환한다.
Backend Ranker는 Matching Score 정책으로 최종 Top10을 선정한다.
Reliability·Risk Signal은 별도 정보로 표시하고 최종 순위에 합산하지 않는다.

## Rationale

AI의 의미 유사도 검색과 Backend의 행사 조건·서비스 정책을 구분하고,
검색 결과가 실제 활성 파일과 연결되도록 하기 위함이다.

## Consequences

최종 평가에 충분한 후보를 제공하고 잘못된 revision의 음악 연결을 방지한다.
후보 목록 전달 비용과 반환 후 ACTIVE·Eligibility 재검증이 필요하다.
후보 수 확대만으로 추천 품질이 보장되지는 않으며 곡→아티스트 집계·충원 정책은 별도 정의한다.

## Server Responsibilities

- Backend: Eligibility·ACTIVE 후보 선정, 반환 revision 재검증, Ranker Top10, Reliability·Risk Signal 표시.
- AI: 공통 검색 입력 임베딩, 후보 쌍·생성 호환성 검사, 코사인 순위·revision 반환.

## Contract

music_id 집합과 revision 집합을 독립 필터로 사용하지 않고 쌍 자체를 비교한다.
TopK 이후 후보를 제거하는 방식으로 제한을 대체하지 않는다. 빈 목록은 빈 결과다.
실제 추천 경로에서는 ACTIVE 후보 쌍을 전달하고 검색 결과에도 revision을 포함한다.
Audio 표시 점수는 최종 행사 적합도나 신뢰 확률이 아니다.
상세 입력·출력 형식은 [API 계약](../../api/AUDIO_SYNC_BACKEND_HANDOFF.md)에서 관리한다.

관련 이슈: [NSUAI-27](https://linear.app/nsu-capstone/issue/NSUAI-27), [NSU-63](https://linear.app/nsu-capstone/issue/NSU-63), [AI #20](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/issues/20).
