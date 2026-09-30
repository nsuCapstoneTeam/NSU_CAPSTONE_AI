
# 0001. pgvector 채택 및 데이터베이스 운영 구조

## 상태

승인

## 관련 근거

- Linear Issue: NSUAI-19
- 관련 Issue: NSUAI-18, NSUAI-20, NSUAI-21, NSUAI-22
- 팀 회의를 통해 pgvector 사용 및 운영 인프라 구성을 확정함

## 배경

AI 기반 아티스트 추천 시스템에서는 MSCLAP을 통해 생성한
Audio/Text Embedding을 저장하고 Vector Similarity Search를 수행해야 한다.

이를 위해 Embedding 저장소와 Vector Search 기술,
Spring Boot Server와 Python AI/Matching Server의
데이터베이스 사용 방식을 결정할 필요가 있다.

## 결정

### PostgreSQL + pgvector

별도의 Vector Database를 추가하지 않고
PostgreSQL의 pgvector를 사용한다.

pgvector는 다음 용도로 사용한다.

- Audio Embedding 저장
- Text Embedding 저장
- Vector Similarity Search
- AI Matching 후보 검색

## 운영 인프라

운영 환경은 다음과 같이 구성한다.

- EC2 #1: Spring Boot Server
- EC2 #2: Python AI/Matching Server
- RDS: PostgreSQL + pgvector

PostgreSQL은 애플리케이션 EC2 내부에서 직접 실행하지 않고
AWS RDS를 독립적인 데이터베이스 인프라로 사용한다.

```text
Spring Boot EC2 ──┐
                  ├── RDS PostgreSQL + pgvector
Python AI EC2 ────┘