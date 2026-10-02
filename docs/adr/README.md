# Architecture Decision Records

Python AI/Matching Server 및 AI Matching 시스템에 영향을 주는
기술적 결정과 그 근거를 기록한다.

팀에서 확정된 결정은 개별 ADR 문서에 기록하며,
아직 확정되지 않은 사항은 확정된 결정과 구분하여 관리한다.

## 관련 결정

| ADR | 관련 이슈 | 결정 내용 | 상태 |
| --- | --- | --- | --- |
| [ADR-0001](./0001-pgvector-adoption.md) | NSUAI-19 | PostgreSQL + pgvector 채택 및 DB 운영 구조 | 승인 |
| [ADR-0002](./0002-ai-matching-server-architecture.md) | NSUAI-18, NSUAI-22 | Spring Boot ↔ Python AI Server 통신 및 Matching 처리 구조 | 승인 |
| [ADR-0003](./0003-embedding-and-scoring-policy.md) | NSUAI-17, NSUAI-20, NSUAI-21, NSUAI-2, NSUAI-12 | MSCLAP, Embedding 생성·저장 및 Matching Score 처리 방향 | 부분 승인 |
| [ADR-0004](./0004-korean-input-english-msclap.md) | NSUAI-1, NSUAI-2 | 한국어 음악 요청을 영어로 변환한 뒤 MSCLAP 입력 | 입력 정책 승인, 번역 방식 미정 |

## 현재 확정된 상위 구조

운영 환경은 다음과 같이 구성한다.

- EC2 #1: Spring Boot Server
- EC2 #2: Python AI/Matching Server
- RDS: PostgreSQL + pgvector

Spring Boot와 Python AI/Matching Server는 동일한 RDS PostgreSQL에 접근한다.

AI Matching 요청은 Spring Boot에서 Python AI/Matching Server로
HTTP를 통해 전달한다.

Python AI/Matching Server는 MSCLAP 기반 Embedding,
Vector Similarity Search, Matching Score 및 추천 Ranking 처리를 담당한다.

## ADR 작성 원칙

새로운 아키텍처 결정이 필요한 경우 `NNNN-주제.md` 형식으로 추가한다.

```markdown
# NNNN. 결정 제목

## 상태

제안 / 승인 / 부분 승인 / 대체됨

## 관련 근거

- Linear Issue:
- 사람의 확정 결정:

## 배경

## 결정 및 근거

## 미확정 사항

## 영향

## 검증
