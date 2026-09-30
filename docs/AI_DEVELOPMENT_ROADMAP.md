# AI Development Roadmap

> Repository: `nsuCapstoneTeam/NSU_CAPSTONE_AI`  
> 기준: Linear `NSU_AI` + GitHub `NSU_CAPSTONE_AI Issues`  
> 목적: AI Matching 기능을 의존성 순서대로 구현하기 위한 개발 기준 문서

---

## 0. 현재 확정된 개발 원칙

### AI Model
- Microsoft `MSCLAP` 사용
- 실제 model/checkpoint, Embedding dimension, similarity 분포는 구현 초기에 검증한다.

### Embedding
- MVP에서는 Audio/Text Embedding을 **등록·수정 시 동기 생성**한다.
- 비동기 처리는 MVP 이후 개선 사항으로 고려한다.

### Similarity
- Similarity 계산은 `NSU_CAPSTONE_AI` Python AI/Matching Server 내부 책임으로 한다.
- Spring Boot는 Similarity를 직접 계산하지 않는다.

### Vector DB
- PostgreSQL + `pgvector` 사용

### Score Normalization
- 우선 고정 수식 기반의 0~100 정규화를 구현·검증한다.
- 단, 아래 값은 실제 MSCLAP 결과를 측정한 후 최종 결정한다.
  - similarity 유효 범위
  - threshold
  - min/max
  - clamp
  - 최종 변환 수식

### Final Matching Score
- PASS/FAIL Hard Filter는 종합 점수 평균 계산에서 제외한다.
- 정규화된 Soft Score 항목들의 평균으로 종합 매칭 점수를 산출한다.

---

# 1. 전체 개발 순서

## Phase 0 — 설계 결정 정리

관련 Linear Issue:
- `NSUAI-18` 유사도 계산 위치 결정
- `NSUAI-17` 임베딩 비동기 처리 방식 결정
- `NSUAI-19` pgvector 채택 아키텍처 결정

목표:
- 구현 전에 서버 책임 경계를 확정한다.
- 이미 결정된 내용은 Linear 상태 및 문서에 최종 반영한다.

완료 기준:
- Similarity → Python AI Server
- Embedding → MVP 동기 처리
- Vector DB → PostgreSQL + pgvector

---

## Phase 1 — Python AI 프로젝트 기반 구축

목표:
- 실제 AI 기능을 넣기 전에 프로젝트 실행 환경을 먼저 만든다.

예상 구조:

```text
NSU_CAPSTONE_AI/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   └── schemas/
│   │
│   ├── core/
│   │   ├── config.py
│   │   └── exceptions.py
│   │
│   ├── models/
│   │   ├── clap/
│   │   └── audio/
│   │
│   ├── embedding/
│   │   ├── audio_embedding.py
│   │   └── text_embedding.py
│   │
│   ├── features/
│   │   ├── bpm.py
│   │   └── rhythm.py
│   │
│   ├── matching/
│   │   ├── similarity.py
│   │   ├── normalization.py
│   │   ├── scoring.py
│   │   ├── ranking.py
│   │   └── explanation.py
│   │
│   ├── repository/
│   │   └── embedding_repository.py
│   │
│   └── main.py
│
├── tests/
├── scripts/
├── docs/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

완료 기준:
- Python 실행 가능
- 가상환경 또는 Docker 환경 구성
- 환경변수 로딩 가능
- PostgreSQL 연결 가능
- pgvector extension 확인
- 테스트 실행 가능
- Health Check 가능

---

## Phase 2 — MSCLAP 단독 검증

관련 Issue:
- `NSUAI-1` CLAP 기반 음악 의미 유사도 계산
- `NSUAI-2` CLAP 유사도 계산 및 점수 정규화 구현

목표:
- 전체 추천 시스템을 만들기 전에 MSCLAP 자체가 정상 동작하는지 검증한다.

검증 흐름:

```text
Audio File
   ↓
MSCLAP
   ↓
Audio Embedding

Text Prompt
   ↓
MSCLAP
   ↓
Text Embedding

Audio/Text Embedding
   ↓
Cosine Similarity
```

반드시 기록할 항목:
- 사용 model/checkpoint
- Audio Embedding dimension
- Text Embedding dimension
- Embedding shape
- 실제 similarity 값
- 유사한 텍스트/오디오 조합
- 관련 없는 텍스트/오디오 조합
- 장르별 또는 분위기별 similarity 분포

중요:
- 이 단계에서는 0~100 최종 공식을 확정하지 않는다.
- 실제 similarity 데이터를 충분히 측정한 뒤 정규화 기준을 결정한다.

---

## Phase 3 — Audio/Text Embedding 생성 및 저장

관련 Issue:
- `NSUAI-25` Audio/Text Embedding 생성 및 저장 구현

목표:
- MSCLAP Embedding을 실제 서비스 구조로 연결한다.

Audio:

```text
Audio
 ↓
Preprocessing
 ↓
MSCLAP
 ↓
Audio Embedding
 ↓
PostgreSQL + pgvector
```

Text:

```text
Event Requirement Text
 ↓
MSCLAP
 ↓
Text Embedding
```

구현 항목:
- Audio Embedding 생성
- Text Embedding 생성
- 모델 버전 저장
- Embedding dimension 관리
- pgvector 저장
- 중복 생성 정책
- 실패 시 재처리 가능한 오류 정보

완료 기준:
- Audio 입력으로 Embedding 생성 가능
- Text 입력으로 Embedding 생성 가능
- 생성된 벡터 저장 가능
- 저장된 Embedding을 Similarity 계산에 사용 가능

---

## Phase 4 — BPM / Rhythm Feature

관련 Issue:
- `NSUAI-8` BPM 및 리듬 적합도 계산
- `NSUAI-9` BPM·리듬 feature 추출 및 적합도 점수화

목표:
- CLAP 외의 Audio Feature 기반 매칭 항목을 구현한다.

구조:

```text
Audio
 ├── MSCLAP
 │     └── Semantic Similarity
 │
 └── Audio Feature Extractor
       ├── BPM
       └── Rhythm
```

완료 기준:
- BPM 추출 가능
- Rhythm Feature 추출 가능
- 행사 요청 조건과 비교 가능
- BPM/Rhythm 점수를 0~100 범위로 제공 가능

---

## Phase 5 — Score Engine

관련 Issue:
- `NSUAI-12` 매칭 항목 점수 정규화 및 종합 점수 산출
- `NSUAI-13` 공통 점수 계약 및 종합 점수 산출 구현

목표:
- 서로 다른 매칭 결과를 하나의 점수 계약으로 통합한다.

예시:

```json
{
  "semanticScore": 82,
  "bpmScore": 91,
  "rhythmScore": 76
}
```

종합 점수 기본 원칙:

```text
matchingScore
=
정규화된 Soft Score 항목의 평균
```

Hard Filter:

```text
Hard Filter
→ 후보 제거

Soft Score
→ 후보 순위 결정
```

완료 기준:
- 모든 점수 항목이 공통 0~100 범위
- PASS/FAIL 항목은 평균 계산에서 제외
- 종합 점수 계산 가능
- 점수 구성 근거 확인 가능

---

## Phase 6 — TOP 5 Ranking

관련 Issue:
- `NSUAI-15` 아티스트 TOP 5 추천 결과 구현
- `NSUAI-16` TOP 5 추천 순위 응답 구현

목표:
- 필수 조건을 통과한 후보를 종합 매칭 점수 기준으로 정렬한다.

흐름:

```text
전체 Artist
   ↓
Hard Filter
   ↓
후보 Artist
   ↓
Matching Score
   ↓
Sort DESC
   ↓
TOP 5
```

완료 기준:
- FAIL 후보 제외
- Matching Score 기준 정렬
- 최대 5명 반환
- 각 후보의 항목별 점수 확인 가능

---

## Phase 7 — 추천 1위 선정 이유

관련 Issue:
- `NSUAI-10` 추천 1위 선정 이유 설명 구현
- `NSUAI-11` 추천 1위 선정 이유 생성 구현

목표:
- 1위 후보의 실제 계산 결과를 기반으로 추천 이유를 생성한다.

원칙:
- 임의 평가 금지
- 실제 계산된 값만 사용
- 높은 기여 항목을 설명에 사용

예시:

```text
Artist A

Semantic 95
BPM      92
Rhythm   87

Final    91
```

---

## Phase 8 — 후보 간 비교 설명

관련 Issue:
- `NSUAI-3` 후보 간 매칭 점수 비교 설명 구현
- `NSUAI-5` 상위 후보 간 항목별 점수 차이(diff) 계산
- `NSUAI-6` 후보 간 비교 설명 문장 생성

목표:
- 상위 후보 간 점수 차이를 실제 계산값으로 설명한다.

예시:

```text
Artist A vs Artist B

Semantic +7
BPM      +12
Rhythm    -2
```

표현 예시:

```text
Artist A는 Artist B보다
음악 스타일 적합도가 7점,
BPM 적합도가 12점 높습니다.
```

완료 기준:
- 동일 항목끼리 비교
- 실제 점수와 diff 일치
- 안정적인 항목 순서
- 구조화 데이터 + 표시 문자열 제공 가능

---

## Phase 9 — Python AI/Matching API Server

관련 Issue:
- `NSUAI-27` Python AI 분석·매칭 API 서버 구현

목표:
- 앞에서 구현한 AI 기능을 Spring Boot가 호출할 수 있도록 API로 노출한다.

전체 구조:

```text
React
  ↓
Spring Boot
  ↓
Python AI Server
  ↓
Matching Pipeline
  ├── MSCLAP
  ├── Embedding
  ├── Audio Feature
  ├── Similarity
  ├── Score
  ├── Ranking
  └── Explanation
  ↓
PostgreSQL + pgvector
```

API 응답 예시:

```json
{
  "recommendations": [
    {
      "artistId": 10,
      "rank": 1,
      "matchingScore": 91,
      "scores": {
        "semantic": 95,
        "bpm": 92,
        "rhythm": 87
      },
      "reason": "..."
    }
  ]
}
```

구현 항목:
- 분석/매칭 요청 endpoint
- 내부 Matching Pipeline 연결
- Request/Response Schema
- Error Response
- Health Check

---

## Phase 10 — Embedding 수정/삭제 Lifecycle

관련 Issue:
- `NSUAI-26` AI Sample 변경·삭제 시 Embedding 갱신 및 삭제 구현

목표:
- Sample Lifecycle과 Embedding Lifecycle을 일치시킨다.

흐름:

```text
Sample 등록
→ Embedding 생성

Sample 수정
→ 기존 Embedding 무효화 또는 삭제
→ 새 Embedding 생성

Sample 삭제
→ Embedding 삭제
```

완료 기준:
- 이전 Embedding이 추천에 남지 않음
- 수정된 Sample의 Embedding 재생성
- 삭제 시 연결된 Embedding 제거
- 실패 상태 식별 및 재처리 가능

---

## Phase 11 — Spring Boot 연동 및 E2E Test

목표:
- 전체 서비스 흐름을 검증한다.

최종 흐름:

```text
React
 ↓
Spring Boot
 ↓
Python AI Server
 ↓
PostgreSQL + pgvector
 ↓
Matching Result
 ↓
Spring Boot
 ↓
React
```

검증 항목:
- Spring → Python 요청
- Timeout/Error 처리
- Artist ID 전달
- TOP 5 결과 반환
- 항목별 Score 반환
- 추천 이유 반환
- Sample 등록/수정/삭제 후 Embedding 상태
- 실제 Audio/Text 데이터 기반 Matching 결과

---

# 2. 실제 구현 시작 순서

개발을 처음 시작할 때는 아래 순서를 따른다.

```text
1. 프로젝트 실행 환경 구축
        ↓
2. MSCLAP 설치 / 모델 로딩
        ↓
3. Audio Embedding 생성
        ↓
4. Text Embedding 생성
        ↓
5. Cosine Similarity 측정
        ↓
6. 여러 테스트 데이터로 Similarity 분포 확인
        ↓
7. 0~100 정규화 방식 결정
        ↓
8. PostgreSQL + pgvector 저장
        ↓
9. BPM / Rhythm Feature
        ↓
10. Score Engine
        ↓
11. TOP 5 Ranking
        ↓
12. 추천 이유
        ↓
13. 후보 비교 설명
        ↓
14. Python API Server
        ↓
15. Spring Boot 연동
        ↓
16. Embedding 수정/삭제
        ↓
17. E2E Test
```

---

# 3. 개발 시 주의사항

## API부터 만들지 않는다
Python 내부의 Matching Pipeline을 먼저 함수 수준에서 완성한 뒤 HTTP API 계층을 연결한다.

## 정규화 수식을 임의로 확정하지 않는다
`cosine_similarity * 100` 등 임의 공식으로 최종 확정하지 않는다.

실제 MSCLAP similarity 분포를 측정한 후 결정한다.

## Embedding Dimension을 하드코딩하지 않는다
현재 pgvector 테스트에서 사용한 임시 dimension은 MSCLAP 실제 dimension으로 간주하지 않는다.

MSCLAP 모델을 실제 로딩한 뒤 확인한다.

## Hard Filter와 Soft Score를 분리한다
- Hard Filter = 후보 포함 여부
- Soft Score = 후보 순위 계산

## 설명은 실제 점수만 사용한다
추천 이유와 후보 비교 설명에서 임의의 AI 평가를 추가하지 않는다.

---

# 4. 현재 Issue 상태 참고

중복 처리된 Linear Issue는 구현 대상으로 사용하지 않는다.

Duplicate:
- `NSUAI-20`
- `NSUAI-21`
- `NSUAI-22`
- `NSUAI-23`

현재 구현은 다음 Issue를 기준으로 진행한다.

- `NSUAI-1`
- `NSUAI-2`
- `NSUAI-3`
- `NSUAI-5`
- `NSUAI-6`
- `NSUAI-8`
- `NSUAI-9`
- `NSUAI-10`
- `NSUAI-11`
- `NSUAI-12`
- `NSUAI-13`
- `NSUAI-15`
- `NSUAI-16`
- `NSUAI-25`
- `NSUAI-26`
- `NSUAI-27`

---

# 5. 가장 먼저 할 작업

현재 개발의 첫 번째 실질 목표는 다음이다.

> **MSCLAP PoC를 성공시키고 Audio/Text Embedding과 실제 Similarity 값을 확인한다.**

첫 구현 완료 기준:

```text
test audio
+
test text
↓
MSCLAP
↓
Audio Embedding
Text Embedding
↓
Cosine Similarity
↓
실제 similarity 값 출력
```

이 단계가 검증된 후 다음 단계인 pgvector 저장과 점수 정규화로 진행한다.
