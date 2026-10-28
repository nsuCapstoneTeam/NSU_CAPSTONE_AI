# NSU_CAPSTONE_AI Agent Guidelines

이 문서는 `NSU_CAPSTONE_AI` 저장소 전용 규칙이다.

일반적인 코딩 원칙, 최소 변경 원칙, 단순성, 구현 전 사고 및 검증 가능한 목표 설정은 상위 `~/.codex/AGENTS.md`를 따른다.

이 문서에는 NSU_CAPSTONE_AI 프로젝트에서만 필요한 Authority, Linear, ADR/SSOT, Main/Worker Agent Session, Git Worktree 및 승인 흐름을 정의한다.

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

서비스 핵심 알고리즘을 `scripts/`에 중복 구현하지 않는다.

## `scripts/`

개발·검증용 CLI와 실험 실행 도구를 둔다.

주요 역할:

- argument 처리
- 입력 처리
- `app/` 기능 호출
- 결과/report 출력
- exit code 처리
- 실험 실행 orchestration

VS Code Agent Session이나 Git Worktree lifecycle을 자체 스크립트로 중복 구현하지 않는다.

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

- 현재 worktree
- current branch
- local HEAD
- origin/main
- working tree
- staged 변경
- unstaged 변경
- untracked 변경
- 현재 Worktree 목록
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
- 권장 Worker Session 이름

이 단계에서는 실제 구현을 시작하지 않는다.

다음을 수행하지 않는다.

- 기능 코드 수정
- Worker Worktree 생성
- Worker Session 시작
- commit
- push
- PR
- merge

사용자의 명시적 승인 후 Worker Agent Session을 시작한다.

---

# 14. Main Agent 역할

Main Agent는 Planner, Orchestrator, Reviewer 역할을 담당한다.

Main Agent의 기본 작업 공간은 `main` branch의 기본 Repository다.

예:

D:\WorkSpace\NSU_CAPSTONE_AI

Main Agent의 역할:

- 요구사항 분석
- Git/Repository 상태 조사
- Linear 확인
- GitHub 확인
- ADR/SSOT 확인
- 작업 범위 결정
- 구현 계획 작성
- Worker Session 작업 명세 작성
- Worker 진행 상태 확인
- Worker 결과 독립 리뷰
- PR/CI 검토
- Integration 여부 판단

Main Agent는 `main` worktree에서 기능 구현 코드를 직접 수정하지 않는다.

Worker Review에서 문제가 발견되어도 Main이 직접 Worker 코드를 수정하지 않는다.

수정은 해당 Worker Agent Session으로 돌려보낸다.

---

# 15. Worker Agent Session 생성

사용자가 구현 계획을 승인하면 Worker는 VS Code Agent Session의 Git Worktree isolation을 기본으로 사용한다.

기본 절차:

1. VS Code Agents Window를 연다.
2. 새로운 Agent Session을 생성한다.
3. 대상 Repository로 `NSU_CAPSTONE_AI`를 선택한다.
4. Code isolation으로 `New Worktree`를 선택한다.
5. Base branch는 최신 `main`을 사용한다.
6. Session 이름은 Issue와 작업 목적이 드러나게 지정한다.
7. 승인된 작업 계획을 Worker Session에 전달한다.

예시 Session 이름:

NSUAI-50 BPM Rhythm Validation

NSUAI-27 Matching API

NSUAI-43 Audio Revision Storage

Worker Agent Session은 Main과 별도의 conversation context와 Git Worktree를 사용한다.

작업별 isolation은 VS Code/Codex가 제공하는 Worktree lifecycle을 우선 사용하며, 별도의 `start-worker.ps1` 같은 자체 lifecycle script를 기본 방식으로 사용하지 않는다.

---

# 16. Worker Agent 역할

Worker Agent는 자신에게 할당된 Worktree 안에서만 실제 구현을 수행한다.

Worker 책임:

- 승인된 작업 범위 확인
- 관련 Authority 재확인
- 코드 구현
- tests 작성/수정
- 필요한 문서 정합화
- 실제 검증
- 변경사항 설명
- 필요한 경우 local commit

Worker는 Main에서 승인받은 작업 범위를 임의로 확대하지 않는다.

Worker는 독자적으로 다음을 수행하지 않는다.

- Main worktree 수정
- unrelated refactoring
- unrelated dependency upgrade
- 서버 계약 변경
- Linear 수정
- NSU_CAPSTONE 수정
- 요청하지 않은 migration
- 사용자 승인 없는 merge

작업 도중 다음이 발견되면 구현 범위를 확대하지 않고 Main에 보고한다.

- Authority 충돌
- 새로운 정책 결정 필요
- destructive operation 필요
- 예상하지 못한 API 계약 변경
- 데이터 삭제 필요
- 범위 밖 대규모 refactoring 필요

---

# 17. Worker 검증

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

실험 작업은 자동 테스트와 실제 실험 검증을 구분한다.

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

# 18. Worker Local Commit

승인된 구현 범위에서는 Worker가 local commit까지 수행할 수 있다.

Commit 전 다음을 확인한다.

- 작업 관련 파일만 포함됐는지
- staged diff
- 테스트 결과
- secret 포함 여부
- unrelated file 포함 여부

가능하면 필요한 파일만 명시적으로 stage한다.

무분별한 다음 명령 사용은 피한다.

git add .

git add -A

Commit message 설명은 한국어로 작성한다.

Worker가 local commit까지 수행했더라도 Main 독립 리뷰 전에는 Integration 완료로 취급하지 않는다.

---

# 19. Worker 완료 보고

Worker는 구현 완료 후 최소 다음 내용을 보고한다.

## 변경 내용

- 변경 파일
- 파일별 역할
- 주요 구현 내용

## 처리 흐름

해당되는 경우 입력부터 출력까지 실제 처리 흐름을 설명한다.

예:

Input
→ Validation
→ Preprocessing
→ Core Logic
→ Storage/Search
→ Output

## 검증

- 실행한 명령
- passed
- skipped
- failed
- 실행하지 않은 검증

## Git

- Worker branch
- commit 상태
- commit hash
- working tree 상태

## Remaining

- known issue
- 미완료
- 미결정
- 후속 작업
- 범위 밖 발견 사항

---

# 20. Main 독립 리뷰

Worker 작업이 완료되면 바로 Integration하지 않는다.

Main Agent가 Worker 결과를 독립적으로 검토한다.

우선 VS Code Agent Session의 Changes/Diff 기능을 사용할 수 있다.

필요한 경우 Git에서 다음과 같은 비교를 수행한다.

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

Main Agent는 Review 중 Worker 코드를 직접 수정하지 않는다.

문제가 있으면 해당 Worker Session에 Review feedback을 전달한다.

흐름:

Main Review
→ Worker 수정
→ Worker 검증
→ Worker local commit
→ Main 재리뷰

문제가 없어질 때까지 반복한다.

---

# 21. Human Approval Gate

Main 독립 리뷰가 완료되면 사용자에게 최소 다음을 보고한다.

- 구현 요약
- 변경 파일
- commit 목록
- 테스트 결과
- Main 리뷰 결과
- known limitation
- 미결정 사항
- PR 준비 여부

사용자의 명시적 승인 전에는 Integration을 완료하지 않는다.

특히 다음 작업은 사용자 승인 후 진행한다.

- PR 생성
- merge

Push가 PR 생성 과정에서 필요한 경우 승인된 PR 절차 범위 안에서 수행한다.

Force push, force merge, branch protection 우회는 별도 명시적 승인 없이는 수행하지 않는다.

---

# 22. Pull Request

Main Review를 통과하고 사용자가 승인하면 PR을 생성한다.

가능하면 VS Code Agent Session 또는 GitHub integration의 PR 생성 기능을 사용할 수 있다.

PR 기본 방향:

base: main

head: Worker branch

PR에는 최소 다음을 포함한다.

- Summary
- 변경 이유
- 주요 구현
- 테스트 결과
- 문서/ADR 영향
- known limitation
- 미결정 사항
- Out of scope

PR을 생성하기 전에 변경 파일과 commit 범위를 다시 확인한다.

---

# 23. PR / CI Review

PR 생성 후 다음을 확인한다.

- CI status
- GitHub review
- requested changes
- merge conflict
- branch behind 여부
- 추가 regression

문제가 발견되면 해당 Worker Agent Session에서 수정한다.

Main Agent는 수정 결과를 다시 독립 리뷰한다.

PR Review가 통과해도 사용자 승인 없이 merge하지 않는다.

---

# 24. Merge

사용자가 merge를 승인한 후에만 merge한다.

Merge 이후 Main Agent는 기본 Repository에서 `main`을 최신화한다.

확인 대상:

- `main`이 `origin/main`과 동기화됐는지
- working tree가 clean인지
- merge된 변경이 실제 Main에 반영됐는지
- 관련 테스트 또는 필요한 smoke validation이 가능한지

Merge 결과가 확인되기 전에 Worker Session 또는 Worktree를 삭제하지 않는다.

---

# 25. Worker Session / Worktree 정리

작업 완료 후에는 VS Code Agent Session lifecycle을 우선 사용한다.

완료된 Worker Session은 필요에 따라 다음 상태로 관리한다.

- Mark as Done
- Archive

Session history가 향후 참고에 필요하면 즉시 삭제하지 않고 Archive를 우선한다.

불필요해진 Worktree는 VS Code의 Worktree Cleanup 기능을 우선 사용한다.

VS Code Command Palette에서 사용할 수 있는 Worktree Cleanup 기능을 확인한다.

자동 Cleanup이 불가능한 경우 Git 상태를 먼저 확인한다.

다음 상태에서는 Worktree를 강제로 삭제하지 않는다.

- uncommitted change 존재
- outgoing commit 존재
- 관련 PR이 아직 open
- merge 여부 확인 불가
- Agent 작업 진행 중
- Worker가 사용자 입력을 기다리는 중
- 다른 process가 해당 Worktree를 사용 중

강제 삭제보다 보존 후 확인을 우선한다.

작업 완료 후에도 session history와 Git history는 서로 다른 목적을 가진다.

Git에는 코드 변경 이력을 남기고, Agent Session에는 작업 맥락과 review history가 남을 수 있다.

---

# 26. 여러 Worker Agent Session

서로 독립적인 작업은 여러 Worker Session으로 병렬 실행할 수 있다.

예:

Main Agent
├─ Worker Session A / Worktree A
├─ Worker Session B / Worktree B
└─ Worker Session C / Worktree C

병렬 작업 조건:

- 각 독립 작업은 별도의 Worktree 사용
- 동일 파일을 여러 Worker가 동시에 수정하는 구조는 피함
- 의존성이 강한 작업은 순차 실행
- 각 Worker 결과는 독립적으로 리뷰
- Integration 후 전체 영향 범위를 다시 검증

작은 단일 작업에 불필요하게 여러 Worker를 만들지 않는다.

---

# 27. Agent Session 운영 원칙

Agent Session은 하나의 작업 단위를 기준으로 유지한다.

하나의 Worker Session에 서로 관련 없는 여러 Issue를 계속 누적하지 않는다.

새로운 독립 Issue는 새로운 Worker Session을 사용한다.

Worker Session 이름은 검색과 추적이 가능하도록 Issue 번호와 목적을 포함한다.

예:

NSUAI-50 BPM Rhythm Validation

Session을 생성할 때 Worker에게 최소 다음 context를 전달한다.

- 작업 목표
- 관련 Linear Issue
- Authority
- 승인된 변경 범위
- 범위 밖 항목
- 예상 검증
- 위험 요소
- 미결정 사항

Worker에게 현재 대화의 전체 history를 무조건 복사하기보다 작업 수행에 필요한 context를 구조화해서 전달한다.

---

# 28. GitHub / Linear 역할 분리

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

# 29. 완료 기준

Agent는 코드가 작성됐다는 이유만으로 작업을 완료 처리하지 않는다.

완료 판단에는 해당 작업에 필요한 범위에서 다음이 포함될 수 있다.

- 요구사항 충족
- 관련 테스트 통과
- 필요한 실제 검증 완료
- 문서 정합성 확인
- Main 독립 리뷰 통과
- PR/CI Review 통과
- 사용자 승인
- Main 반영 확인

미실행 검증이나 unresolved item이 있으면 명확히 남긴다.

---

# 30. 금지 사항

다음을 하지 않는다.

- Main worktree에서 직접 기능 구현
- 사용자 승인 전 Worker 구현 시작
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
- Main Review 없이 Integration 완료 처리
- PR merge 전 Worker Worktree 삭제
- 안전 확인 없이 Worktree 강제 삭제
- 사용자 승인 없이 merge
- VS Code가 이미 제공하는 Agent Session/Worktree lifecycle을 이유 없이 자체 스크립트로 중복 구현

---

# 31. 역할 요약

Human
= Approval Gate
+ Final Decision Maker

Main Agent
= Planner
+ Orchestrator
+ Independent Reviewer

Worker Agent Session
= Implementer
+ Tester
+ Local Committer

VS Code Agent Session / Git Worktree
= Isolation
+ Execution Environment
+ Session Lifecycle

GitHub PR / CI
= Integration Gate

Linear
= Requirement / Coordination Authority

ADR
= AI Technical Decision Record

---

# 32. 최종 Workflow

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
사용자 승인
↓
VS Code에서 Worker Agent Session 생성
↓
Code Isolation: New Worktree
↓
Worker에게 승인된 작업 명세 전달
↓
Worker 구현
↓
Worker 테스트 / 실제 검증
↓
Worker local commit
↓
Main Agent 독립 리뷰
↓
문제 발견 시 Worker Session으로 feedback
↓
Worker 수정 / 재검증
↓
Main 재리뷰
↓
사용자에게 구현/검증/리뷰 결과 보고
↓
사용자 PR 승인
↓
Pull Request
↓
CI / GitHub Review
↓
필요 시 Worker 수정 및 Main 재리뷰
↓
사용자 Merge 승인
↓
Merge
↓
Main 최신화
↓
Main 반영 상태 확인
↓
Worker Session Mark as Done 또는 Archive
↓
안전한 Worktree Cleanup
↓
다음 작업