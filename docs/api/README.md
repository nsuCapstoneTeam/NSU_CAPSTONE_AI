
### `docs/api/README.md` — 기존 파일 전체 교체

```md
# Python Embedding Server API

상태: **계약 정의 대기**

현재 저장소에는 HTTP 서버나 공개 API가 구현되어 있지 않다.
기존 `ClapModel`과 `AudioClassifier`는 로컬 Python 호출용이다.

## 책임 경계

Spring Boot Server와 Python AI/Matching Server는
2-서버 구조로 구성한다.

Python AI/Matching Server는 AI·오디오 분석,
CLAP Embedding, Similarity 및 Matching 관련 내부 처리를 담당한다.

Spring Boot Server는 서비스 API 및
Python AI/Matching Server 연동을 담당한다.

Vector Similarity Search는 Python AI/Matching Server에서 수행하며,
Spring Boot Server에서는 Vector Similarity를 직접 계산하지 않는다.

Spring Boot 측 HTTP 요청·응답 처리, DTO 및 Service 구현은
메인 `NSU_CAPSTONE` 저장소에서 진행한다.

## 계약 확정 시 기록할 항목

| 항목 | 관련 이슈 | 현재 상태 |
| --- | --- | --- |
| 프레임워크, 엔드포인트, 요청·응답 스키마 | NSUAI-18 / NSUAI-22 | 계약 정의 필요 |
| 오디오·텍스트 입력 전달 방식과 전처리 조건 | NSUAI-20 / NSUAI-22 | 계약 정의 필요 |
| 임베딩 모델·버전·차원 및 점수 의미 | NSUAI-20 | 모델 확정 필요 |
| 오류 응답, 타임아웃, 재시도 정책 | NSUAI-22 / NSU-63 | 미확정 |
| 비동기 요청·완료 전달, 실패·재처리 | NSUAI-17 | 미확정 |
| 저장·조회 책임과 pgvector 사용 여부 | NSUAI-19 | pgvector 채택 및 Python AI Server 책임으로 확정 |

pgvector 채택 및 Embedding 데이터 저장·조회 책임에 대한 결정은
[ADR 0001](../adr/0001-pgvector-adoption.md)을 따른다.

API 계약이 확정되면 이 디렉터리에
요청·응답 예시와 오류 처리 규칙을 추가한다.

현재 확정되지 않은 URL, JSON 필드, 큐, 재시도 정책 등을
확정된 계약으로 작성하지 않는다.

## 현재 출력 해석

`AudioClassifier.classify()`는 `label`, `similarity`, `probability`를 반환한다.

`probability`는 비교 라벨 집합에 대한 softmax 상대점수다.

이 값을 행사 매칭용 0–100 정규화 점수나
보정된 신뢰 확률로 간주하지 않는다.