# 007. 항목 점수·최종 추천·설명 생성의 역할 분담

> 과거 합의 기록 보존. 아래 Status·Decision은 당시 내용이며 현행 기준이 아니다. 로컬 번호는 Linear의 같은 번호와 내용이 다르다. 현행 서버 정책은 [Linear 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 Accepted 문서, 이번 사용자 결정은 [AI 작업 기준](../../api/CLAP_RECOMMENDATION_DIRECTION.md)을 확인한다.
>
> 관련 현행 확인 위치: [Accepted Linear 012](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba). 아래 본문은 당시 합의 이력으로 보존하며 현행 기준은 012를 따른다.


## Status

Accepted — 2026-10-05 사용자가 전달한 AI 협의 2/9 및 메인 SSOT v1.6.1 기준.
책임 분담만 확정하며 상세 설명 API 계약과 구현은 미완료다.
005의 retrieval·Backend Ranker 원칙을 보완하고 이전 AI 최종 Top5 계획을 대체한다.
006은 신규 아티스트 후보 검색의 별도 협의를 위해 사용하지 않는다.

## Context

AI 이슈·프로젝트 소개에 종합 점수와 최종 Top5가 AI 책임으로 남아 있었으나,
메인 SSOT는 Spring의 곡→아티스트 집계·종합 점수·최종 Top10으로 정합화되었다.
AI의 곡 유사도 순위와 최종 아티스트 순위를 구분해야 한다.

## Decision

AI는 CLAP·임베딩·곡 분석, 유사 곡 검색, 의미·BPM·리듬 항목 점수와
추천 이유·후보 비교 설명을 담당한다.
Spring은 Eligibility Filter, 곡→아티스트 집계, 종합 Matching Score 계산,
최종 Top10 선정과 서비스 응답 조립을 담당한다.
Reliability·Risk Signal은 순위 점수에 합산하지 않는다.

## Rationale

행사 조건과 서비스 정책을 소유한 Spring에서 최종 판단을 수행하고,
음악 분석을 소유한 AI에서 분석과 설명을 제공해 점수 계산의 중복을 방지한다.
설명이 실제 선정 결과와 일치하도록 AI는 최종 순위나 종합 점수를 재계산하지 않는다.

## Consequences

AI retrieval 50~100곡과 최종 아티스트 Top10을 구분할 수 있다.
CLI Top5와 과거 실험은 곡 단위 검증 설정으로 유지한다.
최종 추천을 설명하려면 Spring 선정 결과·점수·근거 전달 계약이 필요하다.
항목 점수 누락 처리·전달 필드·호출 순서·동기 응답 포함 여부는 미정이다.
상세 호출 방식은 [설명 계약 제안](../../api/RECOMMENDATION_EXPLANATION_CONTRACT.md)에서
Proposed로 관리한다. 이 링크는 A 방식이나 템플릿 사용의 확정을 의미하지 않는다.

## Server Responsibilities

- AI: 음악 분석·retrieval·항목 점수·실제 근거에 기반한 설명.
- Spring: 자격 조건·ACTIVE 후보·아티스트 집계·종합 점수·최종 Top10.

## Contract

AI가 반환하는 곡 유사도 순위를 최종 아티스트 순위로 해석하지 않는다.
최종 추천 이유·비교 설명은 Spring이 확정한 결과와 근거에 일치해야 한다.
BPM·리듬 점수·설명 생성·업무 HTTP API는 후속 구현이며 담당 범위가 완료를 의미하지 않는다.

근거: [메인 SSOT v1.6.1](https://linear.app/nsu-capstone/document/ssot-아티스트-행사-매칭-플랫폼-mvp-요구사항-e38bb23f87b1),
[Top10 공지](https://nsu-capstone.slack.com/archives/C0BUSGZSA0P/p1791122087150769),
[당시 서버 협의 005](https://linear.app/nsu-capstone/document/005-audio-후보-검색과-최종-추천-역할-분담-801efc93fbe3),
[NSUAI-15](https://linear.app/nsu-capstone/issue/NSUAI-15),
[NSUAI-16](https://linear.app/nsu-capstone/issue/NSUAI-16).
