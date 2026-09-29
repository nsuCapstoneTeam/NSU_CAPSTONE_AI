# Architecture Decision Records

Python Embedding Server에 영향을 주는 기술 결정과 근거를 기록한다.
이 문서는 결정 대기 목록이며, 아래 선택지가 승인되었다는 의미는 아니다.

## 관련 결정

| 이슈 | 결정할 내용 | 2026-09-29 확인 상태 |
| --- | --- | --- |
| [NSU-60](https://linear.app/nsu-capstone/issue/NSU-60) | 임베딩 비동기 처리, 생성·갱신 트리거, 실패·재처리 | Todo / 팀 합의 필요 |
| [NSU-61](https://linear.app/nsu-capstone/issue/NSU-61) | 유사도 계산 세부 위치, AI 서버 프레임워크, 서버 간 계약 | 2-서버 상위 구조 확정, 세부 결정 대기 |
| [NSU-62](https://linear.app/nsu-capstone/issue/NSU-62) | pgvector 채택 여부, 데이터 저장·조회 책임 | Todo / 팀 합의 필요 |

구현 시점에는 링크의 최신 상태를 다시 확인한다.
이슈에 기록된 확정 사항은 Spring Boot와 AI 서버의 상위 책임 경계이며,
프레임워크·큐·저장소 선택은 별도 결정 대상이다.

## 작성 형식

실제 결정 검토가 시작되면 `NNNN-주제.md`로 추가한다.

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
```

사람이 확정하기 전에는 상태를 `제안`으로 유지한다. 결정 문서는 제품 요구사항 원문을 대체하지 않는다.
