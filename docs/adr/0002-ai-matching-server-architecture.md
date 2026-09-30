# 0002. AI Matching Server 통신 및 처리 구조

## 상태

승인

## 관련 근거

- Linear Issue: NSUAI-18
- Linear Issue: NSUAI-22
- Spring Boot ↔ Python AI Server 연동 관련 MVP Issue
- 팀 API·데이터 계약 회의 결과

## 배경

Spring Boot Server와 Python AI/Matching Server를 분리하여 운영하기 때문에
두 서버 사이의 AI Matching 요청 방식, 데이터 전달 방식,
응답 및 오류 처리 기준을 정의할 필요가 있다.

본 프로젝트는 캡스톤 MVP의 개발 규모와 구현 복잡도를 고려하여
가능한 단순한 구조로 구현한다.

## 1. API 호출 방식

Spring Boot에서 Python AI/Matching Server를
동기 HTTP 방식으로 호출한다.

```text
Spring Boot
    ↓
AI Matching 요청
    ↓
Python AI/Matching Server
    ↓
AI 분석 및 Matching
    ↓
TOP 5 생성
    ↓
Spring Boot에 응답