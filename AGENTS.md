# NSU_CAPSTONE_AI Agent Guidelines

이 문서는 `NSU_CAPSTONE_AI` 저장소 전용 규칙이다.

일반적인 코딩 원칙, 최소 변경 원칙, 단순성, 구현 전 사고 및 검증 가능한 목표 설정은 상위 `~/.codex/AGENTS.md`를 따른다.

이 문서에는 NSU_CAPSTONE_AI 프로젝트에서만 필요한 Authority, Linear, ADR/SSOT, Main/Worker Multi-Agent Orchestration, Git Worktree, Review 및 승인 흐름을 정의한다.

---

# 1. 응답 및 Commit 언어

사용자에게 제공하는 다음 내용은 한국어로 작성한다.

- 현재 상태 조사 결과
- 작업 계획
- 변경 예정 내용
- 중간 보고
- Worker 진행 상황
- 검증 결과
- 리뷰 결과
- 최종 보고
- 미결정 사항

코드, 명령어, 파일명, 경로, 함수/클래스/변수명, API field, library/framework/model 이름은 원문을 유지할 수 있다.

Commit message는 다음 형식을 사용한다.

종류(선택적 범위): 한국어 설명

예:

feat(embedding): Audio Highlight 입력 검증 구현
fix(search): 검색 결과 validation 오류 수정
docs: Audio Embedding 정책 정합화
test: Calibration fixture 독립성 보강
chore: 개발 환경 정리

---

# 2. Repository 구조

## `app/`

서비스에서 실제로 재사용되는 AI 처리 로직을 둔다.

예:

- Audio/Text Embedding
- similarity
- vector search
- AI preprocessing
- AI-side validation
- BPM/Rhythm 분석 로직
- AI inference

서비스 핵심 알고리즘을 `scripts/`에 중복 구현하지 않는다.

## `scripts/`

개발·검증용 CLI와 실험 실행 도구를 둔다.

주요 역할:

- argument 처리
- 입력 처리
- `app/` 기능 호출
- 결과/report 출력
- exit code 처리
- experiment orchestration

Codex가 이미 제공하는 Agent/Worktree lifecycle을 별도 프로젝트 스크립트로 중복 구현하지 않는다.

## `tests/`

자동 테스트 및 검증 코드를 둔다.

## `docs/`

다음을 관리한다.

- ADR
- Guide
- API/interface 문서
- 실험 결과
- 검증 evidence
- 개발 Roadmap

AI 개발 순서와 현재 단계는 다음 문서를 우선 참고한다.

`docs/AI_DEVELOPMENT_ROADMAP.md`

단, Roadmap만으로 판단하지 않고 관련 ADR, Guide, API 문서, 실제 코드와 tests를 함께 확인한다.

---

# 3. Authority / SSOT

정보 종류별 Authority는 다음과 같다.

## 서비스 전체 요구사항 / 공통 용어

- Linear Requirements
- Linear 용어집

## 서버 간 책임 / 계약 / 공통 정책

- Linear `서버간 공통 협의 사항`

## 중요한 AI 기술 결정

- `NSU_CAPSTONE_AI/docs/adr/`

## 현재 AI 구현 / 사용 / 검증 방법

- 실제 코드
- tests
- `docs/guides/`

## 실험 및 검증 Evidence

- `docs/experiments/`

## AI 개발 순서

- `docs/AI_DEVELOPMENT_ROADMAP.md`

SSOT는 반드시 `SSOT.md`라는 단일 파일을 의미하지 않는다.

각 정보의 현재 authoritative source를 확인한다.

Authority가 다른 문서끼리 충돌하면 최신처럼 보이는 문장을 임의로 선택하지 않는다.

---

# 4. Linear / NSU_CAPSTONE 확인

Main Agent는 작업을 시작하기 전에 관련 최신 정보를 확인한다.

가능한 경우 최소 다음을 확인한다.

- 관련 NSU_AI Issue
- Linear `서버간 공통 협의 사항`
- 관련 Requirements
- 용어집
- 현재 결정 상태
- 미결정 사항
- 서버 간 계약

Linear와 `NSU_CAPSTONE`은 기본적으로 READ-ONLY reference다.

사용자가 해당 시스템의 수정을 명시적으로 요청하지 않는 한 다음을 수정하지 않는다.

- Linear Issue
- Issue status
- Linear comment
- Requirements
- 서버간 공통 협의 사항
- 용어집
- `NSU_CAPSTONE` 코드
- `NSU_CAPSTONE` 문서

접근할 수 없는 Linear 정보를 최신이라고 추측하지 않는다.

서버 계약이나 ownership 등 Linear Authority에 의존하는 작업은 Authority를 확인할 수 없으면 해당 정책 결정을 보류한다.

---

# 5. 현재 검색 입력 책임

현재 검색 입력 목표 흐름은 다음과 같다.

Spring predefined mapping
→ canonical English input
→ AI validation
→ MSCLAP Text Embedding
→ similarity / search / ranking

현재 검색 입력에서 AI는 다음을 수행하지 않는 방향이다.

- OPUS-MT 번역
- M2M100 번역
- Qwen/LLM 기반 자연어 해석
- Spring canonical input의 의미 재해석

단, Linear 서버 협의의 Accepted/Proposed 상태를 반드시 확인한다.

현재 코드 또는 ADR의 목표 상태와 서버 간 계약 Authority가 충돌하면 계약이 확정됐다고 가정하여 API를 구현하지 않는다.

자유 자연어 검색이 다시 필요해질 경우 별도 서버 협의와 ADR을 통해 결정한다.

추천 이유 설명용 LLM과 검색 입력 변환 책임은 별개의 문제로 취급한다.

---

# 6. Audio Highlight 현재 기준

현재 Repository의 Audio Highlight 기준은 다음과 같다.

- 사용자 업로드 허용 길이: 56초 이상 60초 이하
- 실제 분석 구간: 처음 56초
- chunk 길이: 7초
- chunk 수: 8개
- chunk 간 overlap 없음
- 각 Chunk Embedding L2 normalization
- 8개 Chunk Mean Pooling
- 최종 대표 Embedding L2 normalization

다음은 현재 채택된 처리 방식으로 사용하지 않는다.

- 60~80초 입력 정책
- 9 chunks
- 53~60초 overlap chunk

과거 Linear, Requirement 또는 문서에 이전 정책이 남아 있으면 현재 코드로 되돌리는 근거로 사용하지 않고 Authority 충돌로 보고한다.

---

# 7. AI Repository 책임 범위

AI 저장소가 독립적으로 관리할 수 있는 주요 영역:

- MSCLAP
- Audio/Text Embedding
- Embedding generation strategy
- Audio Highlight AI processing
- chunking
- normalization
- Mean Pooling
- AI-side validation
- pgvector 기반 AI 검색
- similarity 계산
- BPM/Rhythm 기술 검증
- model/checkpoint
- preprocessing version
- generation version/profile
- AI 구현 및 검증을 위한 기술적 결정

AI 저장소가 서비스 전체 정책으로 독립 결정하지 않는 영역:

- Spring Hard Filter 내부 정책
- Spring business rule
- Frontend UI 동작
- 서비스 전체 추천 정책
- 서버 간 ownership
- Backend lifecycle/state
- 서비스 전체 score 조합
- 미합의 API 계약
- 서버 간 데이터 ownership

API boundary 또는 AI 내부 구현 문서는 유지할 수 있다.

다만 서비스 전체 정책이나 서버 간 계약을 AI 저장소에서 새로 확정하지 않는다.

---

# 8. Authority 충돌 처리

Linear, ADR, Guide, Roadmap, 실제 코드, tests 사이에 충돌이 있으면 다음을 확인한다.

1. 무엇이 충돌하는가
2. 각 내용이 어느 Source에 있는가
3. 각 Source의 현재 상태는 무엇인가
4. 해당 결정의 Authority는 어디인가
5. 현재 작업에 어떤 영향을 주는가

현재 Accepted Policy를 확정할 수 없으면 사용자에게 보고하고 관련 구현을 보류한다.

충돌을 해결하기 위해 임의로 ADR, Linear 또는 API 계약을 수정하지 않는다.

---

# 9. Embedding 공통 기준

Audio Embedding 저장과 검색은 동일한 공통 Embedding generator를 사용한다.

Embedding 관련 작업에서는 필요한 경우 다음을 확인한다.

- model
- checkpoint
- package version
- preprocessing
- generation version
- generation profile
- vector dimension
- normalization
- input integrity

서로 다른 preprocessing 또는 generation profile의 Embedding을 실수로 비교하지 않는다.

모델에서 관측된 값을 근거 없이 영구 프로젝트 상수로 새로 정의하지 않는다.

---

# 10. Data / Evidence

다음 destructive data 작업은 사용자 승인 없이 수행하지 않는다.

- DB row 삭제
- Embedding 전체 삭제
- dev/test Embedding 전체 삭제
- 대량 vector 재생성
- migration
- destructive schema change
- 기존 experiment evidence 삭제

실험 결과는 필요에 따라 다음을 기록한다.

- repository commit
- 실행 환경
- package/model/checkpoint
- input identity
- generation profile
- 핵심 측정 결과
- PASS/FAIL 근거
- limitations
- unresolved items

대용량 vector, model cache, 원본 Audio 및 중간 artifact는 필요성을 확인하지 않고 Git에 추가하지 않는다.

완료된 실험의 핵심 결과는 가능한 경우 Markdown으로 사람이 검토할 수 있게 요약한다.

Machine-readable evidence가 필요하면 JSON, CSV 등 적절한 형식을 별도로 사용한다.

Mock 또는 synthetic 결과를 실제 모델/실제 데이터 검증 결과로 표현하지 않는다.

---

# 11. ADR 규칙

ADR은 중요한 기술 결정과 그 이유를 기록한다.

필요한 경우 다음을 포함한다.

- Context
- Decision
- Rationale
- Evidence
- Alternatives
- Consequences
- Limitations
- Future Work

확정된 ADR Decision을 구현 중 임의로 변경하지 않는다.

ADR 변경이 필요해 보이면 변경 이유, Authority, 영향 범위를 먼저 사용자에게 보고한다.

ADR은 단순 사용법 문서로 사용하지 않는다.

---

# 12. 작업 시작 전 Main 조사

Main Agent는 새로운 작업을 받으면 구현 전에 현재 상태부터 조사한다.

## Git

최소 다음을 확인한다.

- current branch
- local HEAD
- origin/main
- working tree
- staged 변경
- unstaged 변경
- untracked 변경
- 등록된 Worktree
- 관련 local/remote branch
- 관련 PR

## Repository

최소 다음을 확인한다.

- 관련 코드
- tests
- ADR
- Guide
- API/interface
- Roadmap
- experiment 문서
- 최근 관련 변경사항

## External Authority

최소 다음을 확인한다.

- 관련 Linear Issue
- 서버간 공통 협의 사항
- Requirements
- 용어집
- 필요 시 `NSU_CAPSTONE` read-only reference

이 조사는 별도의 사용자 승인 없이 수행한다.

기억이나 과거 대화만을 기준으로 현재 구현 상태를 단정하지 않는다.

---

# 13. 변경안 및 작업 예정 내용

실제 구현 전에 Main Agent는 반드시 다음 제목으로 사용자에게 계획을 작성한다.

`변경안 및 작업 예정 내용`

최소 다음을 포함한다.

- 무엇을 변경하는가
- 왜 필요한가
- 어떤 Authority/Evidence에 근거하는가
- 예상 변경 범위
- 예상 변경 파일
- 파일별 변경 이유
- 테스트 계획
- 문서 변경 필요 여부
- 위험 요소
- 미결정 사항
- Worker 작업 단위

이 단계에서는 실제 구현을 시작하지 않는다.

다음을 수행하지 않는다.

- 기능 코드 수정
- Worker 생성
- Worker Worktree 생성
- commit
- push
- PR
- merge

사용자의 명시적 승인 후 Main Agent가 Worker orchestration을 시작한다.

---

# 14. Main Agent 역할

Main Agent는 전체 작업의 유일한 Orchestrator다.

Main Agent 역할:

- Planner
- Orchestrator
- Worker Spawner
- Worktree Coordinator
- Message Router
- Independent Reviewer
- Integration Coordinator

Main Agent의 기본 작업 공간은 `main` branch의 기본 Repository다.

예:

D:\WorkSpace\NSU_CAPSTONE_AI

Main Agent의 책임:

- 사용자 요구사항 분석
- Git/Repository 상태 조사
- Linear 확인
- GitHub 확인
- ADR/SSOT 확인
- 작업 범위 결정
- 구현 계획 작성
- Worker 역할 분할
- Worker 생성
- Worker Worktree isolation 확보
- Worker에게 Task 전달
- Worker 진행 상황 수집
- Worker 간 필요한 정보 중계
- Worker 결과 수집
- Worker 결과 독립 리뷰
- 수정 요청 전달
- PR/CI 검토
- Integration 여부 판단

Main Agent는 `main` worktree에서 기능 구현 코드를 직접 수정하지 않는다.

Main은 Worker Review 중 발견한 문제를 직접 수정하지 않는다.

수정은 해당 Worker에게 다시 전달한다.

---

# 15. Human 역할

Human은 전체 개발 과정의 Approval Gate다.

사용자가 직접 Worker Session이나 Worktree를 관리하는 것을 기본 workflow로 요구하지 않는다.

사용자의 기본 역할:

1. Main에게 개발 요청
2. Main의 조사 및 계획 검토
3. 구현 승인
4. Main의 최종 Review 결과 검토
5. PR 승인
6. Merge 승인

Worker 생성, Worker Task 전달, Worker 진행 확인, Worker Review feedback 전달은 Main Agent의 책임이다.

---

# 16. Main → Worker 자동 Orchestration

사용자가 구현 계획을 승인하면 Main Agent가 Worker를 생성한다.

사용자에게 Worker 생성 명령을 직접 수행하도록 요구하지 않는다.

Main은 가능한 Codex Multi-Agent / Session / Worktree 기능을 사용해 Worker를 생성한다.

목표 구조:

Human
→ Main Agent
→ Worker Agent
→ Isolated Worktree

Main Agent는 Worker 생성 시 다음을 보장한다.

- Main worktree와 분리된 작업 공간
- Worker 전용 branch 또는 managed branch
- Worker 전용 Git Worktree
- 승인된 Task context 전달
- Worker 결과를 Main이 다시 수집할 수 있는 communication path

Main은 Worker가 Main worktree에서 기능 코드를 수정하도록 허용하지 않는다.

---

# 17. Worktree Isolation

모든 실제 기능 구현 Worker는 독립된 Git Worktree를 사용한다.

목표 구조:

Main Repository
└─ main

Worker A
└─ isolated worktree A

Worker B
└─ isolated worktree B

Worker C
└─ isolated worktree C

가능하면 Codex가 제공하는 managed Worktree 기능을 사용한다.

Worktree 생성 방법을 프로젝트 자체 PowerShell script로 중복 구현하지 않는다.

Codex runtime이 현재 환경에서 Worker를 별도 Worktree에 안전하게 격리할 수 없는 경우:

1. Main은 기능 구현을 시작하지 않는다.
2. 현재 제약을 사용자에게 보고한다.
3. Worker를 Main worktree에서 대신 실행하지 않는다.
4. isolation을 우회하지 않는다.

---

# 18. Worker 생성 기준

작업 단위가 하나라면 Worker 하나를 기본으로 한다.

다음과 같이 독립적으로 분리 가능한 경우 여러 Worker를 사용할 수 있다.

예:

- 코드 구현
- 독립적인 테스트 작성
- 외부 기술 조사
- 별도 데이터 검증
- 독립 모듈 구현

단, 단순히 병렬화가 가능하다는 이유만으로 Worker를 과도하게 늘리지 않는다.

다음 조건이면 하나의 Worker를 우선한다.

- 작업 규모가 작음
- 같은 파일을 반복 수정해야 함
- 작업 간 의존성이 높음
- 순차적 결정이 필요함

---

# 19. Worker Task Package

Main은 Worker를 생성할 때 단순히 "구현해"라고 지시하지 않는다.

Worker에게 최소 다음 정보를 전달한다.

## Goal

무엇을 완료해야 하는지.

## Authority

- Linear Issue
- 서버 협의
- ADR
- Guide
- API/interface

## Approved Scope

사용자가 승인한 작업 범위.

## Out of Scope

이번 작업에서 하지 않을 것.

## Expected Files

예상 변경 파일 또는 영역.

## Validation

실행해야 하는 테스트 및 검증.

## Constraints

- destructive operation 금지
- 서버 계약 임의 변경 금지
- Linear 수정 금지
- unrelated refactoring 금지

## Stop Conditions

사람 또는 Main의 결정이 필요해지는 조건.

---

# 20. Main ↔ Worker 통신

Main과 Worker는 독립적으로 작업하되 communication path를 유지한다.

Main은 Worker에게 필요한 추가 정보를 전달할 수 있다.

Worker는 다음 상황에서 Main에 보고한다.

- Authority 충돌
- 요구사항 모호성
- 새로운 정책 결정 필요
- destructive operation 필요
- 범위 밖 변경 필요
- 예상하지 못한 dependency
- 테스트 환경 문제
- 실제 검증 불가능
- 다른 Worker의 결과가 필요함

Main은 Worker 결과를 수집하고 필요하면 추가 Task 또는 Review feedback을 전달한다.

---

# 21. Worker 간 통신

Worker 간 직접적인 자유 통신을 기본으로 가정하지 않는다.

Worker 간 정보 공유가 필요하면 Main Agent가 Message Router 역할을 수행한다.

기본 구조:

Worker A
↕
Main
↕
Worker B

Main은 Worker A 결과 중 Worker B에게 필요한 정보만 구조화해서 전달한다.

Worker A의 전체 conversation history를 Worker B에게 무조건 전달하지 않는다.

서로 독립적인 작업은 필요한 interface/evidence만 공유한다.

---

# 22. Worker Agent 역할

Worker Agent는 자신의 독립 Worktree에서만 실제 구현을 수행한다.

Worker 책임:

- 할당된 작업 이해
- 관련 Authority 확인
- 코드 구현
- tests 작성/수정
- 필요한 문서 정합화
- 실제 검증
- 변경사항 설명
- local commit

Worker는 Main에서 승인받은 범위를 임의로 확대하지 않는다.

Worker는 독자적으로 다음을 수행하지 않는다.

- Main worktree 수정
- unrelated refactoring
- unrelated dependency upgrade
- 서버 계약 변경
- Linear 수정
- NSU_CAPSTONE 수정
- 요청하지 않은 migration
- 사용자 승인 없는 PR merge

---

# 23. Worker Stop Conditions

다음 상황에서는 Worker가 임의로 결정하지 않고 Main에 보고한다.

- 평가 기준이 없음
- 데이터셋이 정해지지 않음
- 표본 수가 정해지지 않음
- API 계약이 충돌함
- Accepted / Proposed 문서가 충돌함
- destructive data 작업이 필요함
- 기존 ADR 변경이 필요함
- 서비스 전체 정책 결정이 필요함
- 다른 서버의 결정이 필요함
- Scope가 크게 확대됨

Worker는 이 경우 임의의 숫자, threshold, 계약 또는 정책을 만들지 않는다.

---

# 24. Worker 검증

Worker는 구현 완료 전에 변경 범위에 적절한 검증을 수행한다.

최소 확인 대상:

- 관련 unit test
- 필요한 integration test
- invalid input
- failure case
- result/schema validation
- 실제 실행이 필요한 경우 실제 실행 검증
- 관련 문서와 구현 정합성
- `git diff --check`

실험 작업에서는 자동 테스트와 실제 실험 검증을 구분한다.

예:

unit test 통과
≠ 실제 모델 inference 완료

synthetic fixture 통과
≠ 실제 음악 데이터 검증 완료

mock DB test 통과
≠ 실제 PostgreSQL integration 완료

실행하지 않은 검증은 반드시 미실행으로 보고한다.

테스트 실패가 있으면 완료 처리하지 않는다.

---

# 25. Worker Local Commit

승인된 구현 범위에서는 Worker가 local commit까지 수행할 수 있다.

Commit 전 다음을 확인한다.

- 이번 작업 관련 파일만 포함
- staged diff
- 테스트 결과
- secret 포함 여부
- unrelated file 포함 여부

가능하면 필요한 파일만 명시적으로 stage한다.

무분별한 다음 명령 사용을 피한다.

git add .

git add -A

Commit message 설명은 한국어로 작성한다.

Worker가 local commit까지 수행해도 Main 독립 Review 전에는 Integration 완료로 취급하지 않는다.

Worker는 사용자 승인 없이 PR merge를 수행하지 않는다.

---

# 26. Worker 완료 보고

Worker는 구현 완료 후 Main에 다음을 반환한다.

## 변경 내용

- 변경 파일
- 파일별 역할
- 주요 구현 내용

## 처리 흐름

해당되는 경우:

Input
→ Validation
→ Preprocessing
→ Core Logic
→ Storage/Search
→ Output

## 검증

- 실행 명령
- passed
- skipped
- failed
- 미실행 검증

## Git

- Worker branch
- local commit hash
- working tree 상태
- uncommitted change 여부

## Remaining

- known issue
- 미완료
- 미결정
- 후속 작업
- 범위 밖 발견 사항

---

# 27. Main Worker 상태 관리

Main은 Worker를 생성한 뒤 작업을 잊지 않는다.

Main은 필요에 따라 Worker 상태를 확인한다.

가능한 상태 예:

- Running
- Waiting
- Blocked
- Completed
- Failed
- Needs Review
- Needs Human Decision

Worker가 사용자 입력을 기다리고 있으면 Main이 해당 내용을 사용자에게 전달한다.

Worker가 완료되면 Main이 결과를 회수한다.

Worker가 실패하면 Main은 원인을 확인하고 필요한 경우 재지시한다.

같은 실패를 무한 반복하지 않는다.

---

# 28. Main 독립 리뷰

Worker 작업이 완료되면 Main은 결과를 바로 Integration하지 않는다.

Main Agent가 독립적으로 검토한다.

가능하면 Worker가 만든 Worktree/branch의 실제 diff를 확인한다.

필요한 경우:

git diff main...<worker-branch>

git log main..<worker-branch>

git show <commit>

Main Agent는 최소 다음을 검토한다.

- 승인된 요구사항 충족 여부
- Linear 계약 정합성
- ADR / SSOT 정합성
- API/interface 호환성
- 의도하지 않은 Scope 확장
- 오류 처리
- regression risk
- 테스트 충분성
- 문서 정합성
- secret 포함 여부
- unrelated 변경 여부
- 실험 결과와 evidence 일치 여부

Worker의 완료 보고만 믿고 승인하지 않는다.

실제 diff와 test/evidence를 확인한다.

---

# 29. Review Feedback Loop

Main Review에서 문제가 발견되면 Main이 직접 코드를 수정하지 않는다.

해당 Worker에게 Review feedback을 전달한다.

흐름:

Worker 구현
→ Worker 테스트
→ Worker commit
→ Main Review
→ Review Issue 발견
→ Main이 Worker에게 Feedback
→ Worker 수정
→ Worker 재검증
→ Worker 추가 commit
→ Main 재리뷰

문제가 없어질 때까지 반복한다.

---

# 30. 여러 Worker 병렬 실행

서로 독립적인 작업은 Main이 여러 Worker로 나누어 병렬 실행할 수 있다.

예:

Main Agent
├─ Worker A / Worktree A
├─ Worker B / Worktree B
└─ Worker C / Worktree C

조건:

- 각 Worker는 독립 Worktree 사용
- 동일 파일을 여러 Worker가 동시에 수정하는 구조는 피함
- 서로 다른 책임으로 나눌 수 있어야 함
- 작업 간 의존성이 강하면 순차 실행
- 각 Worker 결과는 Main이 독립 Review
- 최종 Integration 전 전체 영향 검토

Main은 병렬화 자체를 목표로 하지 않는다.

작업 품질과 충돌 방지가 우선이다.

---

# 31. Worker dependency

Worker B가 Worker A의 결과에 의존하는 경우 Main은 이를 명시적으로 관리한다.

예:

Worker A
= 데이터 분석

Worker B
= A 결과를 사용하는 구현

이 경우 기본 흐름:

Worker A 완료
→ Main Review
→ 필요한 결과 확정
→ Worker B에게 전달

A와 B를 무조건 동시에 실행하지 않는다.

---

# 32. Human Approval Gate

Main 독립 Review가 완료되면 사용자에게 최소 다음을 보고한다.

- 구현 요약
- Worker 목록
- Worker별 결과
- 변경 파일
- commit 목록
- 테스트 결과
- 실제 검증 결과
- Main Review 결과
- known limitation
- unresolved item
- PR 준비 여부

사용자의 명시적 승인 전에는 다음 단계로 넘어가지 않는다.

특히 다음은 사용자 승인 후 진행한다.

- PR 생성
- merge

Force push, force merge, branch protection 우회는 별도 명시적 승인 없이는 수행하지 않는다.

---

# 33. Pull Request

Main Review를 통과하고 사용자가 승인하면 PR을 생성한다.

PR 기본 방향:

base: main

head: Worker branch

PR에는 최소 다음을 포함한다.

- Summary
- 변경 이유
- 주요 구현
- 테스트 결과
- 실제 검증 결과
- ADR/문서 영향
- known limitation
- unresolved item
- Out of scope

PR을 생성하기 전에 Main이 변경 파일과 commit 범위를 다시 확인한다.

---

# 34. PR / CI Review

PR 생성 후 Main은 다음을 확인한다.

- CI status
- GitHub review
- requested changes
- merge conflict
- branch behind 여부
- 추가 regression

문제가 발견되면 해당 Worker에게 다시 수정 요청을 전달한다.

Main이 Worker 대신 직접 기능 코드를 수정하지 않는다.

Worker 수정 후 Main이 재Review한다.

PR Review가 통과해도 사용자 승인 없이 merge하지 않는다.

---

# 35. Merge

사용자가 Merge를 승인한 후에만 Merge한다.

branch protection이나 CI를 임의로 우회하지 않는다.

Merge 이후 Main은 기본 Repository의 `main`을 최신 상태로 맞춘다.

확인 대상:

- `main == origin/main`
- working tree clean
- merge된 변경이 Main에 반영됨
- 필요한 smoke test 가능 여부
- 관련 문서 상태

Merge 결과가 확인되기 전에 Worker Worktree를 삭제하지 않는다.

---

# 36. Worker 종료 / Cleanup

Worker의 작업 lifecycle은 Main이 관리한다.

Merge와 Main 반영 확인이 완료된 이후 Worker를 종료한다.

Cleanup 전에 다음을 확인한다.

- Worker 작업 완료
- Main Review 완료
- 필요한 commit 보존
- PR Merge 완료
- Main 최신화 완료
- Worker working tree clean
- outgoing 작업 없음

그 후 Codex가 제공하는 Session/Worktree cleanup 기능을 우선 사용한다.

다음 상태에서는 Worker를 강제 삭제하지 않는다.

- uncommitted change 존재
- outgoing commit 존재
- 관련 PR open
- merge 여부 확인 불가
- Agent 작업 진행 중
- Worker가 사람의 결정을 기다리는 중
- 다른 process가 해당 Worktree를 사용 중

강제 삭제보다 보존 후 확인을 우선한다.

---

# 37. Codex 기능 우선 사용

Main/Worker orchestration에서는 Codex가 제공하는 다음 종류의 기능을 우선 사용한다.

- Agent spawning
- Agent/session management
- Agent messaging
- task follow-up
- managed worktree
- session fork
- Worker status/result collection

프로젝트 자체에서 이러한 lifecycle을 PowerShell script로 다시 구현하지 않는다.

Codex의 실제 현재 runtime에서 지원되는 기능과 command/tool을 먼저 확인하고 사용한다.

지원되지 않는 기능을 존재한다고 가정하지 않는다.

---

# 38. Capability 확인

Main이 Worker를 생성하기 전에 현재 Codex runtime에서 필요한 기능을 사용할 수 있는지 확인한다.

최소 필요한 capability:

- Worker Agent 생성
- Worker와 Main 간 결과 전달
- Git Worktree isolation
- Worker 작업 상태 확인

일부 capability가 현재 runtime에서 제공되지 않는 경우:

1. 기능이 있다고 가정하지 않는다.
2. 사용자 몰래 수동 workflow로 변경하지 않는다.
3. Main worktree에서 Worker 역할을 대신 수행하지 않는다.
4. 어떤 capability가 부족한지 사용자에게 보고한다.
5. 가능한 가장 가까운 안전한 orchestration 방법을 제시한다.

---

# 39. Main Context 관리

Main은 전체 프로젝트 context와 Authority를 유지한다.

Worker에게 모든 Project history를 그대로 전달할 필요는 없다.

Main은 각 Worker에게 필요한 context만 구조화해서 전달한다.

Worker 결과 중 프로젝트 전체 정책에 영향을 주는 내용은 Main에서 다시 검토한다.

Main은 다음을 기억해야 한다.

- 현재 사용자 승인 범위
- 활성 Worker
- Worker별 Task
- Worker별 Worktree
- Worker 상태
- Review 결과
- unresolved decision

---

# 40. Worker Context 관리

Worker는 하나의 명확한 Task에 집중한다.

독립적인 새 Issue가 생기면 기존 Worker에 무조건 추가하지 않는다.

필요하면 Main이 새로운 Worker를 생성한다.

Worker context에는 최소 다음이 있어야 한다.

- Goal
- Authority
- Scope
- Out of Scope
- Constraints
- Validation
- Stop Conditions

---

# 41. GitHub / Linear / ADR 역할 분리

Linear는 다음을 관리한다.

- 요구사항
- Issue
- Priority
- 서버 협의
- 서비스 정책
- 미결정 사항

GitHub는 다음을 관리한다.

- source code
- commit
- branch
- Pull Request
- CI
- code review
- merge history

ADR은 다음을 관리한다.

- 중요한 AI 기술 결정
- 결정 이유
- 대안
- 근거
- 결과

실험 문서는 다음을 관리한다.

- 검증 방법
- 데이터
- 실행 환경
- 결과
- 한계

같은 정보를 모든 시스템에 기계적으로 복제하지 않는다.

각 시스템의 책임에 필요한 내용만 유지한다.

---

# 42. 완료 기준

Agent는 코드가 작성됐다는 이유만으로 작업을 완료 처리하지 않는다.

완료 판단에는 작업에 필요한 범위에서 다음이 포함될 수 있다.

- 요구사항 충족
- 관련 테스트 통과
- 필요한 실제 검증 완료
- 문서 정합성 확인
- Worker 완료
- Main 독립 Review 통과
- PR/CI Review 통과
- 사용자 승인
- Merge
- Main 반영 확인

미실행 검증이나 unresolved item이 있으면 명확히 남긴다.

---

# 43. 금지 사항

다음을 하지 않는다.

- Main worktree에서 기능 구현
- 사용자 승인 전 Worker 구현 시작
- 사용자가 직접 Worker를 수동 관리해야 하는 것을 기본 workflow로 만들기
- Worker isolation 없이 병렬 구현
- 기억만으로 현재 구현 상태 단정
- 미정 서버 계약 임의 확정
- Linear 정책을 AI Repository에서 새로 정의
- 관련 없는 refactoring
- 관련 없는 dependency upgrade
- 요청하지 않은 migration
- 사용자 변경 임의 revert
- 기존 데이터 승인 없이 삭제
- secret 출력 또는 commit
- 테스트 실패 은폐
- Mock 검증을 실제 검증으로 표현
- Worker 완료 보고만 보고 diff 없이 승인
- Main Review 없이 Integration 완료 처리
- PR Merge 전 Worker Worktree 삭제
- 안전 확인 없이 Worktree 강제 삭제
- 사용자 승인 없이 merge
- Worker가 결정해야 하지 않는 서비스 정책을 임의로 확정
- Codex가 지원하지 않는 기능을 지원한다고 가정
- Codex Agent/Worktree lifecycle을 이유 없이 자체 script로 재구현

---

# 44. 역할 요약

Human
= Approval Gate
+ Final Decision Maker

Main Agent
= Planner
+ Orchestrator
+ Worker Spawner
+ Worktree Coordinator
+ Message Router
+ Independent Reviewer
+ Integration Coordinator

Worker Agent
= Isolated Implementer
+ Tester
+ Local Committer

Codex Multi-Agent Runtime
= Agent Lifecycle
+ Agent Communication
+ Task Coordination

Git Worktree
= Code Isolation

GitHub PR / CI
= Integration Gate

Linear
= Requirement / Coordination Authority

ADR
= AI Technical Decision Record

---

# 45. 최종 Workflow

사용자 요청
↓
Main Agent 현재 상태 조사
↓
Git / Linear / ADR / Guide / Roadmap / 코드 / tests 확인
↓
Authority 충돌 확인
↓
다음 작업 범위 결정
↓
`변경안 및 작업 예정 내용`
↓
STOP
↓
사용자 승인
↓
Main Agent가 Worker Agent 생성
↓
Main Agent가 Worker 전용 Worktree isolation 확보
↓
Main이 Worker에게 Task Package 전달
↓
Worker 구현
↓
Worker 테스트 / 실제 검증
↓
필요 시 Worker → Main 질문/Blocker 보고
↓
Main이 답변 또는 Human Decision 요청
↓
Worker 계속 진행
↓
Worker local commit
↓
Worker 결과 Main에 반환
↓
Main 독립 Review
↓
문제 발견
→ Main이 Worker에게 Review Feedback 전달
→ Worker 수정
→ Worker 재검증
→ Worker 추가 commit
→ Main 재Review
↓
Main Review 통과
↓
사용자에게 구현 / 검증 / Review 결과 보고
↓
STOP
↓
사용자 PR 승인
↓
Main이 PR 생성/조정
↓
CI / GitHub Review
↓
문제 발생 시 Worker에게 수정 요청
↓
Main 재Review
↓
사용자 Merge 승인
↓
Merge
↓
Main 최신화
↓
Main 반영 상태 확인
↓
Main이 Worker Session 종료
↓
안전한 Worker Worktree Cleanup
↓
다음 작업

---

# 46. Multi-Worker Workflow

독립적인 여러 작업을 병렬 처리하는 경우:

사용자 요청
↓
Main 조사
↓
Main이 작업 dependency 분석
↓
Task A / Task B / Task C 분리
↓
사용자 승인
↓
Main
├─ Worker A / Worktree A
├─ Worker B / Worktree B
└─ Worker C / Worktree C
↓
각 Worker 독립 작업
↓
각 Worker 결과 Main에 반환
↓
Main이 결과 통합 Review
↓
Worker 간 충돌/의존성 확인
↓
필요 시 특정 Worker에게 수정 요청
↓
Main 최종 Review
↓
Human Approval
↓
PR / CI / Merge

Worker끼리 필요한 정보를 직접 임의 공유하는 대신 Main이 필요한 정보만 중계한다.

---

# 47. 핵심 원칙

사용자는 Main Agent와 대화한다.

Main Agent는 Worker를 관리한다.

Worker는 구현에 집중한다.

Main은 Worker를 신뢰만 하지 않고 검증한다.

Worker는 Main의 계획을 임의로 확대하지 않는다.

Main은 Human의 승인 범위를 넘지 않는다.

Git Worktree는 코드 isolation을 담당한다.

Codex Multi-Agent 기능은 Agent orchestration을 담당한다.

GitHub PR/CI는 Integration을 검증한다.

Linear와 ADR은 무엇을 왜 구현해야 하는지에 대한 Authority를 제공한다.

최종 개발 흐름은 다음 한 줄로 요약한다.

Human
→ Main
→ Worker(s)
→ Main Review
→ Human Approval
→ PR/CI
→ Human Approval
→ Merge