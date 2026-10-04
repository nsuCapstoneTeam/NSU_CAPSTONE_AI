# Server Agreements

이 디렉터리는 서비스 간 통신 및 역할 분담 과정에서 합의된 아키텍처 결정사항을 기록하기 위한 공간입니다.

현재 프로젝트는 Spring Boot 기반의 메인 서버와 ai-recommend-server 등 여러 서비스가 독립적으로 동작할 수 있기 때문에, 서버 간 책임과 통신 규칙을 명확하게 정의해야 합니다.

이 디렉터리에서는 다음과 같은 서버 간 협의사항을 ADR 형태로 관리합니다.

* 각 서버가 담당하는 책임과 역할
* 요청 및 응답 데이터의 책임 범위
* 서버 간 데이터 전달 방식
* 추천 요청 및 결과 반환 방식
* 파일 및 오디오 데이터 처리 방식
* Timeout 정책
* Retry 정책
* 장애 발생 시 처리 방식
* 오류 코드 및 오류 응답 정책
* API Versioning 정책
* 비동기 처리 여부
* 인증 및 서버 간 보안 정책
* 데이터 저장 책임
* 서비스 간 의존성에 영향을 주는 결정

## 목적

서버 간 협의사항을 코드나 구두 합의에만 의존하지 않고 문서로 남겨 다음 문제를 방지하는 것을 목적으로 합니다.

1. 서버별 책임 범위가 불분명해지는 문제
2. 동일한 기능이 여러 서버에서 중복 구현되는 문제
3. 요청/응답 구조 변경으로 다른 서버가 갑자기 동작하지 않는 문제
4. 장애 처리 방식이 서버마다 달라지는 문제
5. 과거에 특정 구조를 선택한 이유를 알 수 없는 문제

## 문서 작성 원칙

각 결정사항은 가능한 한 하나의 주제만 다룹니다.

예를 들어 다음과 같은 내용을 하나의 문서에 모두 작성하지 않습니다.

추천 API + Timeout + Retry + 에러 처리 + 파일 업로드

대신 각각의 결정사항을 독립된 문서로 관리합니다.

```text
001-recommendation-request-contract.md
002-recommendation-response-contract.md
003-audio-upload-responsibility.md
004-error-handling-policy.md
005-timeout-retry-policy.md
```

각 문서는 기본적으로 다음 내용을 포함합니다.

```markdown
# 제목

## Status

Proposed / Accepted / Deprecated / Superseded

## Context

어떤 문제가 있었는가?

## Decision

어떤 방식으로 결정했는가?

## Rationale

왜 이 방식을 선택했는가?

## Consequences

이 결정으로 얻는 장점과 감수해야 하는 단점은 무엇인가?

## Server Responsibilities

각 서버는 무엇을 책임지는가?

## Contract

서버 사이에서 반드시 지켜야 할 규칙은 무엇인가?
```

## 중요한 원칙

이 디렉터리는 단순 API 명세를 저장하기 위한 공간이 아닙니다.

OpenAPI Schema, JSON Schema와 같은 상세 인터페이스 명세는 별도의 API Contract 문서에서 관리할 수 있습니다.

이곳에서는 주로 다음 질문에 대한 답을 기록합니다.

“두 서버가 왜 이렇게 통신하기로 결정했는가?”

그리고 한 번 Accepted 된 결정이 변경되는 경우 기존 문서를 삭제하거나 내용을 덮어쓰기보다는 새로운 ADR을 작성하여 변경 이력을 남기는 것을 원칙으로 합니다.
