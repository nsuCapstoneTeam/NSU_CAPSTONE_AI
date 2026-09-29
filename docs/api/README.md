# Python Embedding Server API

상태: **계약 정의 대기**. 현재 저장소에는 HTTP 서버나 공개 API가 구현되어 있지 않다.
기존 `ClapModel`과 `AudioClassifier`는 로컬 Python 호출용이다.

## 책임 경계

[NSU-61](https://linear.app/nsu-capstone/issue/NSU-61)의 확정된 상위 구조는 Spring Boot 서버와 AI 기반 아티스트 매칭 서버의 2-서버 구조다.
Python은 AI·오디오 분석 내부 처리를 담당하고, Spring Boot는 서비스 API 및 AI 서버 연동을 담당한다.
[NSU-63](https://linear.app/nsu-capstone/issue/NSU-63)의 Spring Boot 측 구현은 이 저장소에 추가하지 않는다.

## 계약 확정 시 기록할 항목

| 항목 | 관련 이슈 | 현재 상태 |
| --- | --- | --- |
| 프레임워크, 엔드포인트, 요청·응답 스키마 | NSU-61 / NSU-63 | 미확정 |
| 오디오·텍스트 입력 전달 방식과 전처리 조건 | NSU-45 / NSU-61 | 계약 정의 필요 |
| 임베딩 모델·버전·차원 및 점수 의미 | NSU-45 / NSU-61 | 계약 정의 필요 |
| 오류 응답, 타임아웃, 재시도 정책 | NSU-63 | 미확정 |
| 비동기 요청·완료 전달, 실패·재처리 | NSU-60 | 미확정 |
| 저장·조회 책임과 pgvector 사용 여부 | NSU-62 | 미확정 |

계약이 확정되면 이 디렉터리에 요청·응답 예시와 오류 규칙을 추가한다.
현재 임의의 URL, JSON 필드, 큐, DB 스키마를 확정 계약으로 제시하지 않는다.

## 현재 출력 해석

`AudioClassifier.classify()`는 `label`, `similarity`, `probability`를 반환한다.
`probability`는 비교 라벨 집합에 대한 softmax 상대점수다.
이 값을 NSU-45의 행사 매칭용 0–100 정규화 점수나 보정된 신뢰 확률로 간주하지 않는다.
