# NSU_CAPSTONE_AI Agent Guidelines

이 문서는 NSU_CAPSTONE_AI 저장소에서 Codex 등 AI 개발 Agent가 작업할 때 따라야 하는 공통 규칙이다.

Agent는 기억이나 이전 대화만을 기준으로 작업하지 않는다.
항상 현재 저장소, Linear, 관련 프로젝트 문서와 실제 구현 상태를 먼저 확인한 뒤 작업한다.

# 권한 및 승인 요청 원칙

다음 읽기 전용 작업은 별도의 사용자 승인을 요청하지 않고 바로 수행한다.

- NSU_CAPSTONE_AI repository 파일 읽기 및 검색
- 관련 코드, tests, docs 확인
- AGENTS.md 확인
- git status / diff / log 등 읽기 전용 Git 조회
- Linear NSU_AI Issue 조회
- Linear `서버간 공통 협의 사항` 조회
- Linear 용어집 및 Requirements 조회
- NSU_CAPSTONE 관련 문서 및 코드의 read-only 조회

단, 실제 실행 환경이 시스템 권한 승인을 요구하는 경우 해당 권한 요청은 따른다.

다음 변경 작업은 읽기 권한과 구분한다.

- Linear 수정
- NSU_CAPSTONE 수정
- DB INSERT / UPDATE / DELETE
- 데이터 삭제
- migration
- git commit / push / PR / merge
- destructive operation

이러한 작업은 AGENTS.md의 작업 범위 및 사용자 승인 절차를 따른다.

# 1. 응답 언어

사용자에게 제공하는 다음 내용은 반드시 한국어로 작성한다.

- 현재 상태 조사 결과
- 작업 계획
- 변경 예정 내용
- 중간 보고
- 검증 결과
- 최종 보고
- 문제점 및 미결정 사항

다음 기술 식별자는 원문을 유지할 수 있다.

- 코드
- 명령어
- 파일명
- 경로
- 클래스명
- 함수명
- 변수명
- SQL
- API field
- Git branch / commit
- library / framework / model 이름

중요한 기술 용어가 처음 등장하면 필요한 경우 다음을 한국어로 설명한다.

1. 무엇인지
2. 어떤 역할을 하는지
3. 이 프로젝트에서 왜 필요한지

전체 보고서를 영어 또는 중국어로 작성하지 않는다.


# 2. 프로젝트 구조

NSU_CAPSTONE_AI의 기본 책임은 다음과 같다.

## `app/`

서비스의 실제 처리 로직을 작성한다.

서비스에서 재사용되는 기능은 가능한 한 `app/`에 구현한다.

예:

- Audio Embedding 생성
- similarity 계산
- vector search
- AI preprocessing
- AI domain validation


## `scripts/`

개발자가 기능을 실행하거나 검증하기 위한 CLI 도구를 작성한다.

`scripts/`는 가능한 한 다음 역할에 집중한다.

- CLI argument 처리
- 입력값 처리
- `app/` 기능 호출
- 결과 출력
- report 생성
- exit code 처리

서비스 핵심 알고리즘을 `scripts/`에 중복 구현하지 않는다.


## `tests/`

자동 테스트를 작성한다.

변경된 기능에 적절한 범위의 테스트를 수행한다.


## `docs/`

다음을 기록한다.

- 사용 방법
- 설계 결정
- ADR
- Guide
- 실험 결과
- 검증 evidence
- 개발 Roadmap


## AI 개발 Roadmap

AI 개발 순서와 현재 단계는 다음 문서를 우선 확인한다.

`docs/AI_DEVELOPMENT_ROADMAP.md`

단, Roadmap만 보고 작업하지 않는다.

관련 ADR, Guide, experiment 문서, 실제 코드와 tests를 함께 확인한다.


# 3. 작업 시작 전 필수 확인

모든 작업은 현재 상태 조사부터 시작한다.

기억, 이전 대화, 과거 checkout 또는 과거 보고서만을 기준으로 작업하지 않는다.

최소 다음을 확인한다.

## Repository

- 현재 branch
- local HEAD
- remote 상태가 필요한 작업이면 remote HEAD
- working tree
- staged / unstaged / untracked 변경
- 관련 코드
- 관련 tests
- 관련 docs


## NSU_CAPSTONE_AI 문서

현재 작업과 관련된 다음 문서를 확인한다.

- ADR
- Roadmap
- Guide
- experiment
- README
- API/interface 문서
- 관련 기타 authoritative document


# 4. Linear 필수 확인

작업을 시작하기 전에 현재 작업과 관련된 Linear의 최신 상태를 반드시 확인한다.

최소 다음을 확인한다.

- 관련 NSU_AI Issue
- `서버간 공통 협의 사항`
- Linear 용어집
- 관련 Requirements
- 현재 결정 상태
- 미결정 사항
- 현재 작업에 영향을 주는 서버 간 계약

Linear에 접근할 수 있으면 관련 NSU_AI Issue, `서버간 공통 협의 사항`, 용어집 및 Requirements의 최신 상태를 확인한다. 과거에 확인한 내용을 기억으로 재사용하지 않는다.

Linear에 접근할 수 없는 경우 상태를 추측하거나 최신이라고 가정하지 않는다. 미확인 사실을 보고하고, repository의 현재 SSOT, ADR, Guide 및 Roadmap만 근거로 사용한다.

서버 간 계약, 서비스 정책, ownership 또는 요구사항 변경처럼 Linear authority에 의존하는 작업은 확인이 가능해질 때까지 중단하거나 보류한다. 테스트 보강, 오탈자 수정, 명확한 로컬 리팩터링처럼 Linear 결정에 의존하지 않는 작업은 repository 범위에서 진행할 수 있으며 Linear 미확인 사실을 보고한다.

관련 Linear Issue가 없더라도 자동으로 오류 처리하지 말고 작업의 성격과 authority 의존성에 따라 판단한다.


# 5. Linear / NSU_CAPSTONE 수정 금지

NSU_CAPSTONE_AI 작업에서 다음은 READ-ONLY reference로 취급한다.

- Linear
- NSU_CAPSTONE

AI 저장소 작업을 이유로 다음을 수정하지 않는다.

- Linear Issue
- Linear Issue status
- Linear comment
- Linear approval record
- Linear Requirements
- Linear `서버간 공통 협의 사항`
- Linear 용어집
- NSU_CAPSTONE 코드
- NSU_CAPSTONE 문서

사용자가 해당 시스템의 수정을 명시적으로 별도 요청한 경우에만 그 요청 범위 안에서 처리한다.

Linear 또는 NSU_CAPSTONE에서 오류나 충돌을 발견해도 AI 저장소 작업 중 임의로 수정하지 않는다.


# 6. Authority와 문서 책임

정보가 여러 곳에 존재할 경우 문서의 책임 범위를 구분한다.


## 서비스 전체 요구사항 / 공통 용어

기준:

- Linear Requirements
- Linear 용어집


## 서버 간 책임 / 계약 / 공통 정책

기준:

- Linear `서버간 공통 협의 사항`


## 프로젝트 공통 구현 및 문서

참조:

- NSU_CAPSTONE


## 중요한 AI 기술 결정

기준:

- NSU_CAPSTONE_AI ADR


## 현재 AI 구현 / 사용 / 검증 방법

기준:

- NSU_CAPSTONE_AI Guide


## 실험 및 검증 evidence

기준:

- NSU_CAPSTONE_AI experiments


## AI 개발 순서

기준:

- `docs/AI_DEVELOPMENT_ROADMAP.md`


# 7. AI Repository의 책임 범위

NSU_CAPSTONE_AI가 독립적으로 관리할 수 있는 주요 영역은 다음과 같다.

- MSCLAP
- Audio Embedding
- Embedding generation strategy
- Audio Highlight AI processing
- chunking
- L2 normalization
- Mean Pooling
- AI preprocessing
- pgvector 기반 AI 검색
- AI similarity 계산
- 한국어 → 영어 AI 입력 처리
- AI-side similarity result semantics
- model version
- checkpoint
- preprocessing version
- generation version / profile
- AI 구현 및 검증을 위한 기술적 결정


# 8. AI Repository에서 독립적으로 결정하지 않는 영역

다음 영역은 AI 저장소에서 서비스 전체 정책으로 새로 결정하지 않는다.

- Spring Hard Filter 내부 정책
- Spring 내부 business rule
- Frontend UI 동작
- Artist matching 버튼 등 사용자 서비스 동작
- 서비스 전체 추천 정책
- 서버 간 책임 분담
- 서비스 전체 score 조합
- Backend lifecycle / state 정책

AI 구현에 필요한 API boundary 또는 interface 문서는 유지할 수 있다.

그러나 서버 간 계약이나 서비스 전체 정책을 AI 저장소에서 중복 결정하지 않는다.


# 9. 충돌 처리

Linear, NSU_CAPSTONE, ADR, Guide, 실제 구현 사이에서 충돌을 발견하면 임의로 하나를 선택해서 수정하지 않는다.

먼저 다음을 확인한다.

1. 어떤 내용이 충돌하는가
2. 각각 어느 source에 있는가
3. 각 source의 현재 상태는 무엇인가
4. 어느 source가 해당 결정에 대한 authority를 가지는가
5. 현재 작업에 어떤 영향을 주는가

현재 accepted policy를 확정할 수 없으면 임의로 결정하지 않는다.

사용자에게 충돌을 보고하고 STOP한다.


# 10. 구현 기본 원칙

다음 원칙을 따른다.

1. 실제 파일과 현재 구현 상태를 확인한 후 작업한다.
2. 요청 범위에 필요한 변경만 수행한다.
3. 서비스에서 재사용할 로직은 `app/`에 작성한다.
4. `scripts/`는 입력 처리, `app/` 호출, 결과 출력과 종료 코드 처리를 담당한다.
5. 실패 판단과 예외는 해당 책임을 가진 모듈에서 정의한다.
6. CLI는 실패 사유를 이해하기 쉽게 출력한다.
7. CLI 실패 시 0이 아닌 exit code를 반환한다.
8. 비밀번호, token, DB 접속 정보 등 민감한 값을 출력하지 않는다.
9. 저장과 검색은 동일한 공통 Embedding generator를 사용한다.
10. Backend와 미정인 계약을 임의로 확정하지 않는다.
11. 임시 가정이 필요한 경우 문서에 명확히 표시한다.
12. 기존 작업 내용과 데이터를 임의로 삭제하거나 덮어쓰지 않는다.
13. 파일 이동 시 import, 상대 경로, 실행 명령 및 관련 문서를 함께 확인한다.
14. 한국어 주석은 코드 자체를 반복하기보다 구현 이유를 설명한다.
15. 기존 public interface를 변경할 필요가 없다면 유지한다.
16. 실험용 로직 때문에 production 결과가 달라지지 않도록 한다.


# 11. Embedding 관련 공통 원칙

Audio Embedding 저장과 검색은 동일한 공통 Embedding 생성기를 사용한다.

서로 다른 preprocessing 또는 generation 정책으로 생성된 Embedding을 실수로 비교하지 않도록 한다.

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

vector dimension 등 모델에서 관측된 값을 근거 없이 프로젝트의 영구 상수로 새로 정의하지 않는다.


# 12. 데이터 보호

기존 데이터는 명시적인 승인 없이 삭제하거나 덮어쓰지 않는다.

특히 다음 작업은 별도 승인이 필요하다.

- DB row 삭제
- Embedding 전체 삭제
- 기존 dev/test Embedding 삭제
- 대량 재생성
- migration
- destructive schema change
- 기존 experiment evidence 삭제

실험은 가능한 한 다음과 같은 격리 방법을 사용한다.

- dedicated test environment
- isolated test DB
- transaction / rollback
- test-specific data

실제 방법은 현재 프로젝트 구조를 조사한 뒤 결정한다.


# 13. Evidence 원칙

실험 또는 검증을 수행한 경우 결과를 재검토할 수 있도록 적절한 evidence를 남긴다.

필요에 따라 다음을 기록한다.

- repository commit
- 실행 환경
- package versions
- model / checkpoint
- input identity / SHA
- generation version/profile
- 측정 결과
- PASS / FAIL 근거
- limitations
- unresolved items

전체 대용량 vector, model cache, 원본 Audio 등은 필요성을 검토하지 않고 Git에 추가하지 않는다.

machine-readable evidence가 필요한 실험은 JSON 등 적절한 형식을 사용한다.

Markdown에는 사람이 이해해야 하는 조건, 결과, 결론 및 한계를 기록한다.

실험 결과가 향후 다른 목적의 evidence를 대체하지 않는다면 그 한계를 명확히 기록한다.


# 14. ADR 원칙

ADR은 중요한 기술적 결정과 그 이유를 기록한다.

ADR에는 필요한 경우 다음이 포함된다.

- Context
- Decision
- Rationale
- Evidence
- Alternatives
- Consequences
- Limitations
- Future Work

ADR을 단순 사용법 문서로 사용하지 않는다.

이미 확정된 ADR Decision을 구현 작업 중 임의로 변경하지 않는다.

Decision 변경이 필요해 보이면 먼저 변경 필요성과 근거를 사용자에게 보고한다.


# 15. SSOT 원칙

SSOT는 반드시 파일명이 `SSOT.md`인 문서를 의미하지 않는다.

각 정보의 현재 authoritative source를 확인한다.

ADR의 내용을 다른 문서에 기계적으로 전부 복제하지 않는다.

문서별 책임에 필요한 내용만 유지한다.


# 16. 작업 계획과 승인 절차

중요한 코드 변경, ADR 변경, DB 작업, 데이터 변경, 실험 또는 구조 변경은 다음 순서를 따른다.

현재 상태 확인
→ Linear / NSU_CAPSTONE reference 확인
→ NSU_CAPSTONE_AI 관련 문서 확인
→ 실제 코드와 tests 확인
→ 충돌 여부 확인
→ 변경안 및 작업 예정 내용 작성
→ 사용자에게 보고
→ STOP
→ 사용자 승인
→ 실제 작업
→ 검증
→ 완료 보고

사용자가 조사와 계획만 요청한 경우 승인 전 작업을 시작하지 않는다.

변경 전 보고에는 가능한 한 다음을 포함한다.

- 무엇을 변경하는가
- 왜 필요한가
- 어떤 authority / evidence에 근거하는가
- 영향 범위
- 예상 변경 파일
- 파일별 변경 이유
- 위험 요소
- 미결정 사항


# 17. ADR / authoritative document 변경 전 규칙

ADR 또는 authoritative document를 변경해야 한다고 판단해도 바로 수정하지 않는다.

먼저 다음을 보고한다.

- 왜 수정이 필요한가
- 어떤 authority에 근거하는가
- 어떤 파일을 수정할 예정인가
- 파일별 변경 이유
- 기존 Decision과 충돌하는가
- 다른 문서에 미치는 영향

사용자 승인 후 변경한다.


# 18. 테스트 및 실제 검증

변경 내용에 적절한 자동 테스트와 실제 실행 검증을 수행한다.

검증 수준을 명확히 구분한다.

예:

- unit test
- mock test
- integration test
- real model inference
- DB integration validation
- manual evaluation

mock test를 통과했다고 실제 모델 검증을 완료했다고 표현하지 않는다.

코드가 실행될 것으로 예상된다는 이유만으로 실행 검증 완료라고 기록하지 않는다.

실행하지 않은 검증은 반드시 미실행 상태로 보고한다.

테스트 실패를 무시하고 완료 처리하지 않는다.


# 19. CLI 원칙

CLI는 개발자가 문제 원인을 이해할 수 있도록 한다.

CLI에서 실패할 경우:

- 실패 원인을 명확히 출력한다.
- 민감한 정보는 출력하지 않는다.
- non-zero exit code를 반환한다.

CLI가 서비스 로직을 다시 구현하지 않도록 한다.

가능한 구조:

CLI
→ argument validation
→ app 기능 호출
→ 결과/report 출력
→ exit code


# 20. 문서와 코드 동기화

코드 변경으로 다음이 영향을 받는 경우 관련 문서도 확인한다.

- 실행 명령
- 파일 경로
- public interface
- generation policy
- validation procedure
- Roadmap status
- Guide

그러나 변경과 관계없는 문서를 불필요하게 수정하지 않는다.


# 21. Git 작업 규칙

다음 작업은 사용자가 별도로 요청하거나 승인한 경우에만 수행한다.

- git add
- commit
- push
- PR 생성
- merge

작업 중 기존 사용자 변경을 발견하면 임의로 되돌리거나 commit에 포함하지 않는다.

이번 작업과 관련된 파일만 stage한다.

commit 전 다음을 확인한다.

- staged files
- `git diff --cached`
- 테스트 결과
- 의도하지 않은 파일 포함 여부
- secret 포함 여부

merge는 별도 승인 없이 수행하지 않는다.


# 22. 작업 진행 방식

실제 작업을 승인받은 경우 다음 방식으로 진행한다.

1. 현재 상태를 다시 확인한다.
2. 승인받은 범위를 확인한다.
3. 단계별로 구현한다.
4. 각 단계가 필요한 이유를 설명한다.
5. 적절한 테스트를 수행한다.
6. 필요한 실제 실행 검증을 수행한다.
7. 결과를 evidence와 문서에 반영한다.
8. 범위를 벗어난 문제는 별도 항목으로 보고한다.

작업 중 예상하지 못한 authority 충돌 또는 destructive change 필요성이 발견되면 작업을 확대하지 말고 STOP하고 보고한다.


# 23. 완료 보고

작업 완료 후 최소 다음을 보고한다.

## 현재 상태

- branch
- HEAD
- working tree


## 변경 파일

변경한 파일과 각각의 역할을 설명한다.


## 처리 흐름

입력부터 출력까지 실제 처리 흐름을 설명한다.

예:

Input
→ Validation
→ Preprocessing
→ Core Logic
→ Storage/Search
→ Output


## 주요 구현 결정

어떤 방식을 선택했으며 왜 선택했는지 설명한다.


## 실행 방법

실제 실행 가능한 명령어를 제공한다.


## 검증 결과

실제로 수행한 테스트와 검증 결과를 보고한다.

실행하지 않은 검증은 실행하지 않았다고 명시한다.


## 영향 범위

기존 기능, 데이터, API, DB 등에 어떤 영향이 있는지 설명한다.


## 미완료 / 미결정 사항

아직 완료되지 않은 항목과 결정되지 않은 항목을 구분한다.


## 다음 단계

`docs/AI_DEVELOPMENT_ROADMAP.md`와 현재 작업 결과를 기준으로 다음 단계를 설명한다.


# 24. 금지 사항

다음을 하지 않는다.

- 확인하지 않은 내용을 완료됐다고 보고
- 기억만으로 현재 구현을 단정
- Backend와 미정인 계약을 임의로 확정
- Linear 정책을 AI repository에서 다시 정의
- 기존 데이터를 승인 없이 삭제
- production 로직과 실험 로직을 이유 없이 중복 구현
- secret 출력
- unrelated refactoring
- unrelated dependency upgrade
- 요청하지 않은 migration
- 요청하지 않은 API 변경
- 사용자 변경을 임의로 revert
- 테스트 실패를 숨기고 완료 처리
- 사용자 승인 없이 merge


# 25. 기본 원칙 요약

항상 다음 순서를 기억한다.

Current State
→ Authority
→ Scope
→ Plan
→ User Approval
→ Implementation
→ Validation
→ Evidence
→ Final Report

정확성을 위해 필요한 경우 작업을 멈추고 확인한다.

모르는 계약을 추측해서 구현하는 것보다
미결정 사항으로 명확히 남기는 것을 우선한다.
