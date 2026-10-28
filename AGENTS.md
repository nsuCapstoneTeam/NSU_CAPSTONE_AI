# NSU_CAPSTONE_AI Agent Guidelines

이 문서는 `NSU_CAPSTONE_AI` 저장소 전용 규칙이다.

일반적인 코딩 원칙, 최소 변경 원칙, 단순성, 구현 전 사고 및 검증 가능한 목표 설정은 상위 `~/.codex/AGENTS.md`를 따른다.

이 문서에는 NSU_CAPSTONE_AI 프로젝트에서만 필요한 authority, Linear, ADR/SSOT, Main/Worker, Git worktree 및 승인 흐름을 정의한다.

---

# 1. 응답 및 Commit 언어

사용자에게 제공하는 다음 내용은 한국어로 작성한다.

- 현재 상태 조사 결과
- 작업 계획
- 변경 예정 내용
- 중간 보고
- 검증 결과
- 리뷰 결과
- 최종 보고
- 미결정 사항

코드, 명령어, 파일명, 경로, 함수/클래스/변수명, API field, library/model 이름은 원문을 유지할 수 있다.

Commit message는 다음 형식을 사용한다.

종류(선택적 범위): 한국어 설명

예:

feat(embedding): Audio Highlight 입력 검증 구현
fix(search): 검색 결과 validation 오류 수정
docs: Audio Embedding 정책 정합화
test: Calibration fixture 독립성 보강
chore: 테스트 실행 환경 정리

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

서비스 핵심 알고리즘을 `scripts/`에 중복 구현하지 않는다.

## `scripts/`

개발·검증용 CLI와 개발 자동화 스크립트를 둔다.

주요 역할:

- argument 처리
- 입력 처리
- `app/` 기능 호출
- 결과/report 출력
- exit code 처리
- 개발 workflow 자동화

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

정보 종류별 authority는 다음과 같다.

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

## 실험 및 검증 evidence

- `docs/experiments/`

## AI 개발 순서

- `docs/AI_DEVELOPMENT_ROADMAP.md`

SSOT는 반드시 `SSOT.md`라는 단일 파일을 의미하지 않는다.

각 정보의 현재 authoritative source를 확인한다.

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
- comment
- Requirements
- 서버간 공통 협의 사항
- 용어집
- `NSU_CAPSTONE` 코드
- `NSU_CAPSTONE` 문서

접근할 수 없는 Linear 정보를 최신이라고 추측하지 않는다.

---

# 5. 현재 검색 입력 책임

현재 검색 입력 흐름은 다음을 따른다.

Spring predefined mapping
→ canonical English input
→ AI validation
→ MSCLAP Text Embedding
→ similarity / search / ranking

현재 검색 입력에서 AI는 다음을 수행하지 않는다.

- OPUS-MT 번역
- M2M100 번역
- Qwen/LLM 기반 자연어 해석
- Spring canonical input의 의미 재해석

자유 자연어 검색이 다시 필요해질 경우 별도 서버 협의와 ADR을 통해 결정한다.

추천 이유 설명용 LLM 가능성과 검색 입력 변환 책임은 별개의 문제로 취급한다.

---

# 6. AI Repository 책임 범위

AI 저장소가 독립적으로 관리할 수 있는 영역:

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

---

# 7. Authority 충돌 처리

Linear, ADR, Guide, 실제 코드, tests 사이에 충돌이 있으면 먼저 다음을 확인한다.

1. 무엇이 충돌하는가
2. 각 내용이 어느 source에 있는가
3. 각 source의 현재 상태는 무엇인가
4. 해당 결정의 authority는 어디인가
5. 현재 작업에 어떤 영향을 주는가

현재 accepted policy를 확정할 수 없으면 사용자에게 보고하고 해당 정책 변경을 보류한다.

---

# 8. Embedding 공통 기준

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

---

# 9. Data / Evidence

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

완료된 실험의 핵심 결과는 가능한 경우 Markdown에 요약한다.

---

# 10. ADR 규칙

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

변경 필요성이 있으면 사용자에게 변경 이유와 영향 범위를 먼저 보고한다.

---

# 11. 작업 시작 전 Main 조사

Main Agent는 새 작업을 받으면 구현 전에 최소 다음을 확인한다.

## Git

- current branch
- local HEAD
- working tree
- staged / unstaged / untracked
- 필요 시 remote HEAD

## Repository

- 관련 코드
- tests
- ADR
- Guide
- API/interface
- Roadmap
- experiment 문서

## External authority

- 관련 Linear Issue
- 서버간 공통 협의 사항
- Requirements
- 용어집
- 필요 시 `NSU_CAPSTONE` read-only reference

이 조사는 별도의 사용자 승인 없이 수행한다.

---

# 12. 변경안 및 작업 예정 내용

실제 구현 전에 Main Agent는 반드시 다음 제목으로 계획을 작성한다.

변경안 및 작업 예정 내용

최소 포함:

- 무엇을 변경하는가
- 왜 필요한가
- 어떤 authority/evidence에 근거하는가
- 예상 변경 파일
- 파일별 변경 이유
- 테스트 계획
- 위험 요소
- 미결정 사항
- Worker branch/worktree 이름

이 단계에서는 구현하지 않는다.

사용자의 명시적 승인 후 Worker 작업을 시작한다.

---

# 13. Main / Worker Workflow

## Main worktree

기본 Main worktree:

D:\WorkSpace\NSU_CAPSTONE_AI

기본 branch:

main

Main은 다음 역할만 담당한다.

- 요구사항 분석
- Linear/GitHub/ADR/SSOT 조사
- 구현 계획 작성
- Worker orchestration
- Worker 결과 독립 리뷰
- PR/merge 이후 cleanup

Main은 `main`에서 기능 구현 코드를 직접 수정하지 않는다.

---

## Worker worktree

사용자가 구현 계획을 승인하면 Main Agent가 작업별 feature branch와 worktree를 생성한다.

형식:

Branch:
feat/<issue-or-task>-<short-name>

Worktree:
D:\WorkSpace\NSU_CAPSTONE_AI-<issue-or-task>

예:

Branch:
feat/nsuai-27-matching-api

Worktree:
D:\WorkSpace\NSU_CAPSTONE_AI-nsuai-27

worktree는 최신 `main` 기준으로 생성한다.

서로 관계없는 작업을 하나의 Worker worktree에 섞지 않는다.

---

# 14. Worker 자동화 스크립트

새 Worker 환경 생성은 가능한 경우 다음 스크립트를 사용한다.

scripts/dev/start-worker.ps1

사용 예:

.\scripts\dev\start-worker.ps1 `
  -Issue "nsuai-27" `
  -Name "matching-api"

`start-worker.ps1`의 역할:

- Main branch 여부 확인
- Main working tree clean 여부 확인
- `origin` fetch
- feature branch 생성
- Git worktree 생성
- VS Code Workspace에 Worker folder 추가
- Worker 전용 local VS Code task 생성
- Worker Codex terminal 실행 준비

Main Agent가 동일한 작업을 매번 수동으로 반복하지 않는다.

Worker 전용 `.vscode/tasks.json`은 로컬 개발 편의를 위한 임시 파일로 취급하며 feature commit에 포함하지 않는다.

---

# 15. Worker Agent 역할

Worker Agent는 전용 worktree에서만 실제 구현을 수행한다.

Worker 책임:

- 코드 구현
- tests 작성/수정
- 관련 문서 정합화
- 실제 검증
- local commit

Worker는 Main에서 승인받은 작업 범위를 벗어나지 않는다.

작업 중 새로운 authority 충돌, 서버 계약 변경 또는 destructive change가 필요해지면 Main에게 보고한다.

Worker는 독자적으로 다음을 수행하지 않는다.

- main 수정
- push
- PR 생성
- merge
- unrelated 작업

---

# 16. Worker Local Commit

사용자가 구현 계획을 승인한 범위에서는 Worker가 local commit까지 수행할 수 있다.

Commit 전에 다음을 확인한다.

- 이번 작업 관련 파일만 stage
- staged diff
- 테스트 결과
- secret 포함 여부
- unrelated file 포함 여부

무분별한 다음 명령 사용을 피한다.

git add .
git add -A

가능하면 필요한 파일을 명시적으로 stage한다.

push는 수행하지 않는다.

---

# 17. Worker 완료 보고

Worker는 구현 완료 후 Main에게 최소 다음을 전달한다.

## 변경 내용

- 변경 파일
- 파일별 역할

## 주요 구현

- 실제 처리 흐름
- 주요 기술 결정

## Test

- 실행 명령
- passed
- skipped
- failed
- 실행하지 않은 검증

## Git

- branch
- local commit hash
- working tree 상태

## Remaining

- known issue
- 미완료
- 미결정
- 후속 작업

---

# 18. Main 독립 리뷰

Worker가 local commit을 완료하면 Main Agent가 독립 리뷰한다.

기본 비교:

git diff main...<feature-branch>

필요하면 다음도 확인한다.

git log main..<feature-branch>
git show <commit>

최소 검토 항목:

- 승인된 요구사항 충족
- Linear 계약 일치
- ADR/SSOT 일치
- API/interface 호환성
- unintended scope expansion
- 오류 처리
- regression risk
- 테스트 충분성
- 문서 정합성
- secret 포함 여부
- unrelated file 포함 여부

Main은 Worker 코드를 직접 수정하지 않는다.

문제가 있으면 Worker에게 review feedback을 전달한다.

Main Review
→ Worker 수정
→ Worker 테스트/local commit
→ Main 재리뷰

문제가 없어질 때까지 반복한다.

---

# 19. Human Approval Gate

Main 리뷰가 완료되면 사용자에게 다음을 보고한다.

- 구현 요약
- commit 목록
- 테스트 결과
- 리뷰 결과
- known limitation
- push/PR 준비 여부

사용자의 명시적 승인 전에는 다음을 수행하지 않는다.

- push
- PR 생성
- merge

---

# 20. Push / PR

사용자 승인 후 feature branch를 push한다.

예:

git push -u origin feat/nsuai-27-matching-api

PR은 다음 구조를 사용한다.

base: main
head: feature branch

PR 본문에는 최소 다음을 포함한다.

- Summary
- 변경 이유
- 주요 구현
- 테스트 결과
- ADR/문서 영향
- known limitation
- Out of scope

PR/CI 리뷰에서 문제가 발견되면 Worker가 수정하고 Main이 다시 리뷰한다.

---

# 21. Merge

Merge는 사용자 승인 후 수행한다.

branch protection이나 CI를 임의로 우회하지 않는다.

force push / force merge는 별도 승인 없이는 사용하지 않는다.

---

# 22. Merge 후 Worker 정리

PR merge 이후 Worker 정리는 가능한 경우 다음 스크립트를 사용한다.

scripts/dev/finish-worker.ps1

사용 예:

.\scripts\dev\finish-worker.ps1 `
  -Issue "nsuai-27" `
  -Name "matching-api"

정리 전 다음을 확인한다.

- Main working tree clean
- Main 최신화 가능
- Worker working tree clean
- 필요한 commit이 모두 보존됨
- PR merge 완료

정리 대상:

- Worker worktree
- local feature branch
- Git worktree metadata
- Worker 전용 local VS Code 설정

Worker가 dirty 상태이거나 branch가 merge되지 않은 경우 강제 삭제하지 않는다.

PR merge 전에는 Worker worktree를 삭제하지 않는다.

---

# 23. 여러 Worker

독립적인 작업은 여러 Worker로 나눌 수 있다.

Main
├─ Worker A
├─ Worker B
└─ Worker C

조건:

- 서로 같은 파일을 동시에 수정하지 않는다.
- 의존성이 강한 작업은 순차 처리한다.
- 각 Worker는 별도 branch/worktree를 사용한다.
- Main이 최종 integration을 검토한다.
- 작은 단일 작업에는 불필요하게 Worker를 늘리지 않는다.

---

# 24. 역할 요약

Human
= Approval Gate

Main Agent
= Planner
+ Orchestrator
+ Independent Reviewer

Worker Agent
= Implementer
+ Tester
+ Local Committer

GitHub PR / CI
= Integration Gate

최종 workflow:

사용자 요청
↓
Main 조사
↓
변경안 및 작업 예정 내용
↓
사용자 승인
↓
Main이 start-worker.ps1 실행
↓
Worker branch/worktree 생성
↓
Worker 구현/테스트/local commit
↓
Main 독립 리뷰
↓
필요 시 Worker 수정
↓
Main 재리뷰
↓
사용자 승인
↓
Push / PR
↓
CI / Review
↓
사용자 승인
↓
Merge
↓
Main 최신화
↓
finish-worker.ps1 실행
↓
Worker worktree/branch 정리