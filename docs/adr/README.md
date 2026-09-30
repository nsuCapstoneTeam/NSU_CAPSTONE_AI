# Architecture Decision Records

Python AI/Matching Server에 영향을 주는 기술 결정과 근거를 기록한다.

사람이 확정하기 전의 결정은 `제안` 상태로 유지하며,
팀에서 확정된 결정은 개별 ADR 문서에 근거와 함께 기록한다.

## 관련 결정

| 이슈 | 결정할 내용 | 현재 상태 |
| --- | --- | --- |
| NSUAI-17 | 임베딩 비동기 처리, 생성·갱신 트리거, 실패·재처리 | 팀 합의 필요 |
| NSUAI-18 | 유사도 계산 위치 및 서버 책임 경계 | Python AI/Matching Server에서 수행하기로 확정 |
| NSUAI-19 | pgvector 채택, 데이터 저장·조회 책임 및 운영 구성 | 확정 / ADR 0001 참고 |

NSUAI-19의 pgvector 관련 결정 및 근거는
[0001. pgvector 채택 및 데이터 책임 결정](./0001-pgvector-adoption.md)을 참고한다.

구현 시점에는 관련 Linear Issue의 최신 상태를 다시 확인한다.

Spring Boot와 Python AI/Matching Server의 상위 책임 경계와
pgvector 기반 Embedding 저장 및 Vector Similarity Search 책임은 확정되었다.

AI 서버 프레임워크, 비동기 처리 방식, 재시도 정책 및
구체적인 API 계약은 관련 이슈에서 별도로 결정한다.

## 작성 형식

새로운 아키텍처 결정이 필요한 경우 `NNNN-주제.md` 형식으로 추가한다.

```markdown
# NNNN. 결정 제목

## 상태
제안 / 승인 / 대체됨

## 관련 근거
- Linear Issue:
- Requirement ID:
- 사람의 확정 결정 링크:

## 배경

## 검토한 대안

## 결정 및 근거

## 영향
API 호환성, 모델 재분석, 저장소, 운영·실패 처리에 미치는 영향

## 검증
검증 방법과 결과 또는 후속 작업