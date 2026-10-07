# Python Embedding Server 협업 가이드

[NSU_CAPSTONE 협업 가이드](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE/blob/main/docs/협업-가이드/README.md)의 흐름을 이 저장소 범위에 맞게 적용한다.

## 도구와 기준 원문

| 도구 | 역할 |
| --- | --- |
| Slack | 논의와 사람의 최종 결정 |
| Linear Requirements | 제품 요구사항의 기준 원문 |
| Linear Issue | 작업 범위, Acceptance Criteria, 담당자, 진행 상태 |
| GitHub 코드 / PR | 구현, 검증 결과, 리뷰 |
| docs / ADR | 기술 문서와 결정 근거 |

최신 Slack의 사람이 확정한 결정과 기존 문서가 충돌하면 해당 결정을 Linear에 반영하여 동기화한다. Agent의 제안만으로 요구사항을 확정하지 않는다.

서버 계약·점수·누락 점수·오류 정책은 [Linear 서버 협의](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 Accepted 문서를,
공통 용어는 [Linear 용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 우선 확인한다. Proposed는 확정 정책이 아니다.
문서와 최신 사용자 결정에 차이가 있으면 출처와 적용 범위를 명시하고 승인 상태를 임의로 변경하지 않는다.
2026-10-07 이번 문서 정리에서는 Linear와 NSU_CAPSTONE은 확인만 하며, 사용자 결정의
[AI 작업 기준](../api/CLAP_RECOMMENDATION_DIRECTION.md)을 정합화한다.

## 저장소 범위

Python 내부 CLAP 모델, 임베딩, 오디오 전처리·분석, 유사도 및 점수 계산을 다룬다.
Spring Boot 측 요청·응답 처리와 DTO는 메인 백엔드에서 구현하고, 서버 간 계약은 함께 검토한다.
관련 이슈와 현재 구현 상태는 [README](../../README.md)를 기준으로 확인한다.

## 작업 흐름

1. Linear Issue와 Acceptance Criteria, 필요한 요구사항을 확인한다.
2. 최신 `main`에서 목적별 작업 브랜치를 만든다.
3. 구현과 필요한 검증을 수행하고 기술 문서를 갱신한다.
4. PR에 실제 이슈 링크, 변경 내용, 검증 결과, 문서 영향을 기록한다.
5. 사람이 요구사항·코드·문서를 검토한 뒤 Squash Merge한다.
6. 실제 완료 조건을 충족했을 때 Linear 상태를 정리한다.

GitHub Flow를 사용하며 장기 브랜치는 `main` 하나로 둔다. `main` 직접 push는 하지 않는다.
브랜치 예: `feat/NSU-45-clap-similarity`, `docs/python-server-scaffold`.
Linear 일반 상태는 `Todo → In Progress → Done`을 사용한다. 문서 생성만으로 기능 이슈를 완료 처리하지 않는다.

## PR 템플릿

- [구현 PR](../../.github/PULL_REQUEST_TEMPLATE/구현_PR.md): Python 코드, 모델, 실행 설정 변경
- [문서 PR](../../.github/PULL_REQUEST_TEMPLATE/문서_PR.md): 문서와 협업 규칙 변경

GitHub PR 생성 URL의 `template` 파라미터로 `구현_PR.md` 또는 `문서_PR.md`를 지정하거나 내용을 복사한다.
여러 템플릿이 있는 구조이므로 기본 본문이 자동 선택된다고 가정하지 않는다.
CodeRabbit, 브랜치 보호, 자동 이슈 동기화는 이 저장소의 적용 여부를 별도로 확인한다. 파일 생성만으로 활성화되지 않는다.

## Python / 모델 검증

- 모델 변경 시 버전, 입력 조건, CPU/GPU와 결과 변화를 기록한다.
- 라벨 상대점수와 행사 매칭의 정규화 점수는 의미를 구분한다.
- API 변경 시 요청·응답 및 오류 처리를 [API 문서](../api/README.md)에 반영한다.
- 비동기·저장소 등 결정 사항은 [ADR 안내](../adr/README.md)에 따라 기록한다.
- 비밀정보, 실제 음원, 데이터셋, 가중치는 커밋하지 않는다.
- 필요한 검증만 실행하고 미실행 사유를 PR에 남긴다.
