# 0001. pgvector 채택 및 데이터 책임 결정

## 상태

승인

## 관련 근거

- Linear Issue: NSUAI-19
- 관련 Issue: NSUAI-18, NSUAI-20, NSUAI-21, NSUAI-22
- 팀 합의를 통해 pgvector 사용 및 운영 인프라 구성을 확정함

## 배경

AI 기반 아티스트 추천 시스템에서는 CLAP을 통해 생성한
Audio/Text Embedding을 저장하고 Vector Similarity Search를 수행해야 한다.

이를 위해 Embedding 저장소와 Vector Search 기술을 결정하고,
Spring Boot Server와 Python AI/Matching Server 사이의
데이터 저장·조회 책임을 정의할 필요가 있다.

## 검토한 대안

- 별도의 Vector Database 사용
- PostgreSQL + pgvector 사용

MVP에서는 별도의 Vector Database를 추가하지 않고
PostgreSQL의 pgvector extension을 사용하는 것으로 결정하였다.

## 결정 및 근거

### 인프라 구성

운영 환경은 다음과 같이 구성한다.

- EC2 #1: Spring Boot Server
- EC2 #2: Python AI/Matching Server
- RDS: PostgreSQL + pgvector

PostgreSQL은 애플리케이션 EC2 내부에서 직접 실행하지 않고
AWS RDS를 독립된 데이터베이스 인프라로 사용한다.

### Spring Boot Server 책임

Spring Boot Server는 서비스 도메인 데이터를 담당한다.

주요 책임은 다음과 같다.

- 사용자 데이터 관리
- 아티스트 데이터 관리
- 행사 데이터 관리
- AI Sample 관련 서비스 메타데이터 관리
- Python AI/Matching Server에 분석 및 매칭 요청
- Python AI/Matching Server의 분석 및 추천 결과 수신

Spring Boot Server에서는 CLAP Embedding 생성이나
Vector Similarity Search를 직접 수행하지 않는다.

### Python AI/Matching Server 책임

Python AI/Matching Server는 AI 및 Embedding 관련 처리를 담당한다.

주요 책임은 다음과 같다.

- CLAP Audio/Text Embedding 생성
- Embedding 저장 및 조회
- Embedding 갱신 및 삭제
- Embedding 모델 및 버전 정보 관리
- pgvector 기반 Vector Similarity Search
- Similarity 및 Matching Score 계산
- 추천 Ranking 계산

Embedding 및 Vector Similarity Search에 대한 애플리케이션 책임은
Python AI/Matching Server에 둔다.

### 데이터베이스 사용

Spring Boot Server와 Python AI/Matching Server는
동일한 RDS PostgreSQL을 사용한다.

동일한 RDS를 사용하더라도 서비스 도메인 데이터와
AI/Embedding 데이터의 논리적 책임은 분리한다.

Spring Boot와 Python AI/Matching Server 간 AI 처리 요청 및
결과 전달은 HTTP API를 통해 수행한다.

## 운영 고려사항

### Embedding 변경 및 삭제

AI Sample이 변경된 경우 기존 Embedding이 이후 Vector Search에
잘못 사용되지 않도록 처리하고 새로운 Embedding을 생성해야 한다.

AI Sample이 삭제된 경우 해당 Sample과 연결된 Embedding도
삭제하여 이후 Vector Search 결과에 포함되지 않도록 한다.

구체적인 Embedding 갱신 및 삭제 정책은 관련 구현 이슈에서 정의한다.

### Embedding 모델 관리

Embedding 데이터에는 사용한 모델을 식별할 수 있도록
모델 및 버전 정보를 함께 관리한다.

향후 CLAP 모델 또는 모델 버전이 변경될 경우 기존 Embedding과
새로운 Embedding을 구분할 수 있어야 한다.

실제 Vector dimension은 사용할 CLAP 모델이 확정된 후 결정한다.

### 장애 및 재처리

Embedding 생성 또는 저장 과정에서 실패가 발생할 경우
실패 상태를 식별하고 재처리할 수 있도록 고려한다.

구체적인 비동기 처리, 재시도 및 중복 생성 정책은
관련 이슈에서 별도로 정의한다.

### 개발 환경

로컬 개발 환경에서는 Docker Compose 기반
PostgreSQL + pgvector를 사용한다.

로컬 환경은 운영 RDS에 적용할 PostgreSQL/pgvector 기능 및
Schema를 개발·검증하는 용도로 사용한다.

현재 테스트 환경의 `VECTOR(3)`은 pgvector 동작 확인을 위한
테스트 값이며 실제 CLAP Embedding Schema의 Vector dimension으로
사용하지 않는다.

## 영향

- Spring Boot는 Vector Similarity 계산 방식에 직접 의존하지 않는다.
- Python AI/Matching Server가 Embedding 및 Vector Search를 담당한다.
- 운영 DB는 애플리케이션 EC2와 분리된 RDS PostgreSQL을 사용한다.
- 별도의 Vector Database를 추가하지 않아 MVP 인프라 복잡도를 줄인다.
- AI Sample 변경 및 삭제 시 관련 Embedding도 갱신 또는 삭제되어야 한다.
- CLAP 모델 변경 시 기존 Embedding의 재생성 여부를 고려해야 한다.

## 검증

- pgvector 채택 여부 팀 합의 완료
- EC2 2대 + RDS PostgreSQL 1대 구성 합의 완료
- Spring Boot / Python AI/Matching Server 책임 경계 확인
- Embedding 저장·조회 및 Vector Similarity Search를
  Python AI/Matching Server 책임으로 확인

구체적인 Embedding 생성·저장 구현은 NSUAI-20,
Embedding 갱신·삭제 구현은 NSUAI-21,
Python AI API 구현은 NSUAI-22에서 진행한다.