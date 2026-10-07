# AI Development Roadmap

> 2026-10-07 이 작업 대화의 사용자 결정, 구현 전: 전체 통과 곡 Embedding/유사도 계산·정렬·전체 반환 → Spring 곡 표시 → 별도 사용자 Artist 매칭. 집계·후보 비교 설명은 하지 않습니다. [작업 기준](api/CLAP_RECOMMENDATION_DIRECTION.md)은 Linear Accepted와의 차이를 명시합니다. Proposed는 확정 정책이 아닙니다.


> Repository: `nsuCapstoneTeam/NSU_CAPSTONE_AI`  
> 기준: Linear `NSU_AI` + GitHub `NSU_CAPSTONE_AI Issues`  
> 목적: AI Matching 기능을 의존성 순서대로 구현하기 위한 개발 기준 문서

---

## 0. 현재 확정된 개발 원칙

### AI Model
- Microsoft `MSCLAP` 사용
- Phase 2에서 MSCLAP 2023 CPU·Audio/Text 1024차원을 측정했다. 환경 변경 시 재검증하며 새 aggregation 분포는 후속 검증이다.

### Embedding
- 음악 파일 입력 후 전처리·Audio Embedding 처리에는 **동기 방식**을 사용한다.
  [ADR 0006](adr/ADR-0006-asynchronous-audio-processing.md)을 따른다.
  현재 생성·저장·검색 함수는 동기 실행이며 업무 HTTP API는 후속 구현이다.
- AI에서 연동 계약을 먼저 작성하고 백엔드 검토 후 확정한다.
- 사용자 음악 요청은 한국어로 받고, 의미를 유지한 영어 설명으로 변환한 뒤
  MSCLAP Text Embedding을 생성한다. 입력 정책은
  [ADR 0004](adr/ADR-0004-korean-input-english-msclap.md)를 따른다.
  번역 방식 및 자동 번역 경로의 검증은 후속 구현 작업이다.

### Similarity
- Similarity 계산은 `NSU_CAPSTONE_AI` Python AI/Matching Server 내부 책임으로 한다.
- Spring Boot는 Similarity를 직접 계산하지 않는다.

### Vector DB
- PostgreSQL + `pgvector` 사용

### Score Normalization
- 현재 Phase 2 개발용 함수는 음악↔텍스트 0~0.4, 음악↔음악 0~1의 임시 기준을 사용한다.
  [실험 근거](experiments/audio-search-phase2/README.md) 및
  [ADR 0005](adr/ADR-0005-audio-similarity-display-score.md)를 참고한다.
  최종 기준 확정이나 사용자용 종합 점수 구현 완료를 뜻하지 않는다.
- 우선 고정 수식 기반의 0~100 정규화를 구현·검증한다.
- 단, 아래 값은 실제 MSCLAP 결과를 측정한 후 최종 결정한다.
  - similarity 유효 범위
  - threshold
  - min/max
  - clamp
  - 최종 변환 수식

### 현행 흐름과 서버 정책

- Spring Hard Filter → AI 전체 통과 곡 Embedding/유사도 계산·정렬 → 전체 결과 Spring 반환 → 유사도 순 곡 표시 → 별도 사용자 버튼으로 해당 Artist와 매칭.
- 전체 반환·유사도 정렬·아티스트 집계 없음·후보 비교 설명 폐기의 출처는 **이번 사용자 결정**이다. Linear Accepted로 이미 반영됐다고 설명하지 않는다.
- 정책·용어는 [Linear 서버 협의](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 Accepted 문서와 [용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 먼저 확인한다.
- [Accepted 009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd)의 의미·BPM·리듬 항목, 누락 `null`과 사유, 의미 점수 없는 곡 제외를 따른다.
- 기존 Accepted 005/009의 반환 제한·평균 순위와 용어집의 100곡 설명은 새 흐름과 차이가 있다. 평균을 현행 순위 수식으로 사용하지 않는다.
- 곡별 추천 이유는 [Accepted 008](https://linear.app/nsu-capstone/document/008-추천-이유-생성-흐름-ae6cde7df2de), 오류/timeout은 [Accepted 010](https://linear.app/nsu-capstone/document/010-ai-곡-검색-실패시간-초과-시-추천-api-응답-46a63dece138)을 참조한다.
- Proposed 011·012의 정밀도·반환 상한·설명 주체 변경을 확정하지 않는다.
- 요청 표현·처리 한도·실패/누락 응답·설명 대상은 서버 협의 정합화가 필요하다.

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
- Audio 입력 처리 → 동기 방식, 처리 완료 후 결과 반환
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
│   │   ├── retrieval.py
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

현재 진행: 임시 정규화 함수와 음악 파일 검색 CLI를 구현하고 새 음악 24곡의 쌍별
유사도·청취 평가를 수행했다. 이는 곡 단위 검증이며 Phase 6 추천용 후보 제공 또는
Phase 9 HTTP API 완료가 아니다. 한국어→영어 자동 변환 구현은 미정으로 보류한다.

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

현재 Audio 공통 생성·테이블·동기 저장·DB 후보 검색 CLI를 구현했습니다.
현재 Audio 생성은 기존 단일 crop 방식입니다. 승인된
[ADR-0007](adr/ADR-0007-audio-highlight-embedding-strategy.md)의 Audio Highlight 생성 정책 적용은
아래 남은 작업에 포함하며, 아직 구현하지 않았습니다.
음악 입력은 동기로 처리하며 AI에서 연동 계약 초안을 먼저 작성합니다.
[저장 안내](guides/EMBEDDING_STORAGE.md), [DB 검색 검증](guides/DATABASE_AUDIO_SEARCH.md)을 참고합니다.
Text 생성·번역, 백엔드 ID/FK·수정/삭제 계약, 오류 기록·자동 재처리는 미완료입니다.
Phase 3 전체 완료를 의미하지 않습니다.

남은 작업:
- [ ] 기존 30초 FMA와 다른 Dataset의 권리·접근 조건을 확인하고 60~80초 적격 입력 fixture 준비·길이 검증
- [ ] 개발 벡터 재생성 대상과 새 입력 매핑 확인: 같은 FMA 원본으로 재생성하지 않음
- [ ] ADR-0007 D1에 따른 60~80초 inclusive 길이 validation 구현
- [ ] ADR-0007 D2·D3·D4에 따른 처음 56초 사용 및 7초 × 8개 non-overlap Chunk 생성
- [ ] ADR-0007 D6·D7·D8에 따른 Chunk별 L2 → Mean Pooling(N=8) → 최종 L2 및 대표 벡터 1개 생성
- [ ] 저장·검색의 공통 생성 경로와 preprocessing/generation metadata 정합화: ADR-0007 Future Work 참조
- [ ] 적격 새 입력·대상 매핑·새 생성 방식 검증 완료 후 ADR-0007 D9의 개발/테스트 벡터 삭제·재생성
- [ ] revision별 벡터 보관·처리 상태·attempt 소유권·삭제 기록 추가
- [ ] Backend ACTIVE 전환 커밋 확인 후 이전 revision 정리와 실패 복구
- [ ] ACTIVE (music_id, audioRevision) 후보 쌍 필터와 검색 결과 revision 반환
- [ ] 백엔드 연동 계약 확정: 음악 ID·파일 전달·버전·오류·타임아웃
- [ ] 음악 수정·삭제 처리와 오래된 요청의 덮어쓰기·재등록 방지
- [ ] Text 임베딩 생성·저장 연동: 한국어→영어 변환 방식은 미정
- [ ] 동기 업무 HTTP API 구현: 등록·검색·수정·삭제
- [ ] 실패 기록·재시도·중복 요청·시간 초과 후 재요청 정책
- [ ] 실제 백엔드 음악 ID를 사용한 등록→검색→수정→삭제 통합 검증

관련 Issue:
- `NSUAI-25` Audio/Text Embedding 생성 및 저장 구현

Audio 정책 적용 순서:
다른 Dataset의 권리·60~80초 입력 준비 → 생성 규칙·metadata 구현 → 검증 → 재생성 대상/입력 매핑 확인 → 개발/테스트 벡터 삭제·재생성 → 저장·검색 확인.
기존 30초 FMA 음원·manifest·결과는 과거 PoC로 보존한다. 새 Dataset 이름은 미정이며 임의 반복/padding으로 FMA를 새 fixture로 바꾸지 않는다.
Dataset 선행조건은 Roadmap과 [FMA 안내](guides/FMA_VALIDATION.md)·[DB 검증 안내](guides/DATABASE_AUDIO_SEARCH.md)에서 관리하고 ADR-0007은 변경하지 않는다.
운영 ACTIVE revision 보관·전환 정책과 구분하며 metadata 형식과 수치 안정성 세부 기준은
ADR-0007 Future Work에 따라 구현 단계에서 결정·검증합니다.

목표:
- MSCLAP Embedding을 실제 서비스 구조로 연결한다.

Audio:

```text
Audio Highlight
 ↓
ADR-0007 기준 공통 생성
(길이 검증·분할·Chunk 추론·정규화/집계)
 ↓
대표 Audio Embedding 1개
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
- ADR-0007 기준 공통 Audio Embedding 생성 — 저장·검색에서 재사용
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
- ADR-0007의 길이 경계·분석 범위·고정 Chunk·aggregation·재현성을 검증하고 저장·검색에 동일 규칙이 적용됨을 확인
- 다른 Dataset의 60~80초 입력·대상 매핑, preprocessing/generation metadata 정합화·새 방식 개발 벡터 재생성 완료; 운영 ACTIVE revision 정책과 구분

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

## Phase 5 — Accepted 항목 점수·누락 정책 정합화

관련 Issue: `NSUAI-12`, `NSUAI-13`.

목표:
- [Accepted 009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd)의 의미·BPM·리듬 항목과 0~100 범위·누락 정책을 구현·검증한다.
- 누락은 `null`과 사유로 전달하고 의미 점수 없는 곡은 후보 제외 원칙을 따른다.
- 기존 Accepted의 유효 항목 평균과 이번 유사도 정렬은 다른 기준이다. 평균을 현행 순위 계산 작업으로 두지 않는다.
- 누락/제외 표현을 전체 곡 처리·반환 목표와 서버 계약에서 정합화한다.

완료 기준:
- 유효 점수의 범위·계산 근거를 확인하고 누락을 임의 0점으로 대체하지 않는다.
- 의미 점수 누락을 정상 결과로 숨기지 않는다.
- Hard Filter와 음악 유사도/항목 점수를 구분한다.
- 정밀도·산식 버전 등 Proposed 011 항목은 승인 없이 확정하지 않는다.

---

## Phase 6 — 전체 통과 곡 유사도 정렬·전체 반환

출처: 2026-10-07 이 작업 대화의 사용자 결정, 구현 전. 기존 Accepted 005의 50~100/Backend Top10이 새 흐름으로 승인됐다는 뜻은 아니다.
관련 Issue: `NSUAI-15`, `NSUAI-16`. 실제 Issue/AC와 차이는 별도 정합화가 필요하며 이번에 Linear를 변경하지 않는다.

```text
Spring Hard Filter·ACTIVE 후보 쌍
→ AI 전체 곡의 공통 Embedding/유사도 계산·정렬
→ 전체 결과·곡 식별자·revision Spring 반환
→ Spring 유사도 순 곡 표시
→ 사용자가 별도 버튼으로 해당 Artist와 매칭
```

완료 기준:
- ACTIVE 후보 쌍을 계산 전에 정확히 제한하고 결과 revision 반환.
- 전체 전달 곡을 대상으로 하고 CLI Top5/50~100/Proposed 100곡으로 임의 축소하지 않음.
- 호환 벡터 재사용·필요한 생성·처리 한도·실패/누락 표현을 정합화하고 전체 반환 검증.
- 아티스트 집계·후보 비교 문장을 생성하지 않음.
- Reliability·Risk Signal을 음악 유사도 순위에 합산하지 않음.
- 입력 표현·동점 처리·대량 결과 성능은 후속 계약/실측으로 확인.
- 화면·매칭 버튼은 Backend/Frontend 구현 책임이며 AI 완료와 구분.

당시 계획 이력: 2026-10-04~05에는 AI retrieval 50~100 → Backend Ranker Top10을 계획했다.
저장소 현행 작업 목표는 이번 사용자 결정으로 대체하며 Linear 승인 상태는 그대로다.

---

## Phase 7 — 곡별 추천 이유

관련 Issue: `NSUAI-10`, `NSUAI-11`.

목표:
- [Accepted 008](https://linear.app/nsu-capstone/document/008-추천-이유-생성-흐름-ae6cde7df2de)의 추가 AI 호출·템플릿 우선·실패 시 이유만 `null` 원칙 구현.
- 실제 곡 점수·필터 근거만 사용하고 순위를 재계산하지 않음.
- 전체 반환 흐름과 기존 Top10/신규 칸 설명 대상의 차이를 서버 협의에서 정합화.
- endpoint·DTO·timeout·대상 수는 [상세 계약](api/RECOMMENDATION_EXPLANATION_CONTRACT.md)에서 확정.
- 후보 간 비교·아티스트 집계 근거를 생성하지 않음. Proposed 012의 Spring 설명 책임으로 임의 변경하지 않음.

완료 기준:
- 곡과 설명 근거 일치, 실패해도 검색 결과 유지.
- 누락·오래된 결과·근거 없는 설명 검증.
- LLM 도입·성능 목표는 별도 결정/측정 전 미정.

---

## Phase 8 — 후보 간 비교 설명 (폐기 이력)

이전 계획은 상위 후보 항목 diff 계산과 비교 문장 생성이었다.
Accepted 008 및 2026-10-07 사용자 결정에 따라 현행 구현에서 제외한다.
확인 시 `NSUAI-3`·`NSUAI-5`는 Canceled, `NSUAI-6`은 Todo로 남아 있어 Issue 정합화가 필요하다.
이번에 Issue 상태를 변경하지 않는다. 이 Phase 번호를 재사용하지 않는다.

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
  ├── Item Score Normalization
  ├── Track Retrieval
  └── Explanation
  ↓
PostgreSQL + pgvector
```

곡 검색 API 응답의 개념 예시(확정 Schema가 아님; 설명 호출 계약은 별도 미정):

```json
{
  "tracks": [
    {
      "musicId": "example-music-id",
      "audioRevision": 2,
      "cosineSimilarity": 0.82,
      "scores": {
        "semantic": 95,
        "bpm": 92,
        "rhythm": 87
      }
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
→ 기존 v1 ACTIVE 벡터 유지·새 v2 생성/보관
→ Backend v2 ACTIVE 전환 커밋 확인
→ 유예/재검색 정책에 따라 이전 v1 정리

Sample 삭제
→ 검색 후보에서 제거·삭제 revision 기록
→ 과거 시도의 재등록 차단·연결 벡터 정리
```

완료 기준:
- 새 ACTIVE 전환 확인 전 기존 벡터 유지, 전환 후 이전 revision 정리
- 수정된 Sample의 Embedding 재생성
- 삭제 시 연결된 Embedding 제거
- 실패 상태 식별 및 재처리 가능

Phase 3의 저장·상태·ACTIVE 기반 위에서 이 Phase는 수정/삭제 lifecycle과 복구를 검증한다.

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
- 전체 통과 곡 처리·유사도 정렬·전체 반환 → Spring 곡 표시 → 별도 사용자 Artist 매칭 검증
- 항목별 Score 반환
- 추천 이유 반환
- Sample 등록/수정/삭제 후 Embedding 상태
- 실제 Audio/Text 데이터 기반 Matching 결과

---

# 2. 실제 구현 시작 순서

아래는 초기 구축부터의 의존 순서다. Phase 1 기반·Phase 2 PoC·현재 Audio 저장/검색 CLI는 이미 구현됐으며 서비스 전체 완료와 구분한다.

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
10. Accepted 항목 점수·누락 정책 검증
        ↓
11. 전체 통과 곡 유사도 정렬·전체 반환 → Spring 곡 표시
        ↓
12. 추천 이유
        ↓
13. Embedding revision 수정/삭제 lifecycle 검증 (비교 설명은 폐기)
        ↓
14. Python API Server
        ↓
15. Spring Boot 연동
        ↓
16. 별도 사용자 Artist 매칭 연동 검증
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
- 음악 유사도 = 현행 사용자 결정의 곡 정렬 기준
- 항목 점수 = Accepted 서버 정책의 값·누락 처리; 평균을 현행 순위 수식으로 사용하지 않음

## 설명은 실제 점수만 사용한다
곡별 추천 이유에 임의 평가를 추가하지 않는다. 후보 간 비교 설명은 제공하지 않는다.

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

# 5. 현재 다음 작업

MSCLAP PoC·Audio/Text 차원·실제 Similarity 측정과 Audio 저장/검색 CLI는 이미 수행한 단계다.
다음은 Phase 3의 다른 Dataset 입력 준비와 ADR-0007 생성 규칙·metadata 적용이다.
60~80초 적격 입력과 재생성 대상 매핑을 검증하기 전 기존 개발 벡터를 삭제하지 않는다.
길이 경계·8 Chunk·L2/Mean·재현성 검증 후 재생성·저장/검색 확인으로 진행한다.

## 2026-10-07 정합화 이력

이번 사용자 결정으로 전체 곡 반환·유사도 정렬·집계 없음·후보 비교 설명 폐기를 반영했다.
이전 순위/반환 제한 계획은 당시 이력이며 Linear Accepted 상태는 변경하지 않았다.
30초 FMA는 과거 PoC로 보존하고 새 검증은 다른 Dataset을 사용한다.
ADR-0007·코드·테스트·DB·데이터를 변경하지 않은 문서 작업이다.
