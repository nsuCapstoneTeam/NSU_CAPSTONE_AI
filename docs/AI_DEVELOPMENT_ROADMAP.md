# AI Development Roadmap

> 2026-10-10 현재 서버 간 추천 정책은 Accepted 012다. 구현 상태는 별도 추적하며, 이 Roadmap은 합의된 계약을 구현 완료로 표시하지 않는다.


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
- 서비스 검색 입력은 Spring이 predefined mapping으로 canonical English input을 생성하고 AI에 전달한다.
  영어 MSCLAP 입력 근거는 [ADR-0004](adr/ADR-0004-korean-input-english-msclap.md), 검색 입력 책임 결정은
  [ADR-0009](adr/ADR-0009-spring-canonical-search-input-mapping.md)를 따른다.
  Mapping과 AI 업무 API는 구현 전이며 AI는 검색 입력 번역/LLM 해석을 수행하지 않는다.

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
- raw cosine ranking·후보 독립 transformation·provisional 점수·calibration 원칙과 생성/변환 버전의 구분은
  [ADR-0008](adr/ADR-0008-music-similarity-transformation-and-ranking.md)을 따른다.
  calibration cohort 분석은 완료했지만 최종 transformation 선정 및 transformation/calibration 버전 체계의 production 구현·검증은 남아 있다.
- 후보 집합과 독립된 고정 0~100 음악 유사도 변환을 사용한다. raw cosine이 순위를 정하고 표시 점수는 순위를 바꾸지 않는다.
- 최종 formula·threshold·breakpoint·계수는 아직 확정하지 않았다. provisional 후보와 완료된 cohort 분석은 [calibration 기록](experiments/audio-similarity-calibration/README.md)을 참고한다. 독립 validation은 수행하지 않았다.
- 단, 아래 값은 실제 MSCLAP 결과와 평가 evidence를 바탕으로 결정한다.
  - similarity 유효 범위
  - threshold
  - min/max
  - clamp
  - 최종 변환 수식

### 현행 흐름과 서버 정책

- 서비스 흐름은 행사 등록 후 발급된 `eventId`로 본문 없는 추천 요청을 보내는 방식이다. Spring이 등록자·상태를 확인하고 한 행사 snapshot에서 Eligibility와 AI 입력을 구성한다. 세부 흐름과 내부 DTO 경계는 [현재 AI 작업 기준](api/CLAP_RECOMMENDATION_DIRECTION.md)을 따른다.
- Spring은 입력 ACTIVE 후보를 임의로 자르지 않는다. 숫자 입력 최대치는 NSUAI-15의 성능·메모리·동시성 실측 후 결정하며, 결과 반환 상한 100곡과 구분한다. 상한 초과 시 503/경보를 사용하며 임의 분할 호출을 하지 않는다.
- Spring은 rank/order 연속성, 중복, 후보 범위, 결과 개수, 0~100 점수 및 표시 점수 단조성을 확인한다. raw cosine은 Spring 계약에 포함하지 않으므로 raw cosine 순위 검증은 AI 쪽이 담당한다.
- 외부 결과 의미는 단일 `resultVersion`으로 식별한다. model/checkpoint, generation/preprocessing, transformation/calibration, 상세 분석, 요청 해석 버전은 AI 내부에서 나눠 추적한다.
- 정책·용어는 [Linear 서버 협의](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 Accepted 문서와 [용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 먼저 확인한다.
- [Accepted 009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd)는 평균 순위 범위에서 Superseded다. BPM/Rhythm은 추출·요청 비교 상세 정보로 유지되며 음악 순위 점수가 아니다. 공연 형태 Hard Filter는 유지한다.
- [Accepted 012](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba)는 005의 retrieval 50~100/Backend Top10과 008의 별도 AI Explanation API 범위도 대체한다. 005의 ACTIVE 후보 쌍·revision 비교·Trust/Risk 분리 원칙은 유지한다. 010은 유지한다. 011은 Superseded 상태를 유지하고, 013은 Proposed 별도 협의로 남는다.
- Spring은 AI의 구조화된 근거로 템플릿 추천 이유를 생성한다. 별도 AI Explanation API 및 필수 LLM은 현행 흐름이 아니다.
- 검색 입력의 의미와 canonical mapping은 Spring 책임이다. AI 업무 요청은 canonical English input을 받는 방향이며 정확한 DTO·입력 최대치·resource/timeout은 계약 및 실측 과제로 남는다. AI는 원문 Event Description에서 음악 의미를 재추출하지 않는다.

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
Phase 9 HTTP API 완료가 아니다. FMA16 한국어/영어 비교는 소규모 예비 실험이며,
후속 [대규모 AudioCaps paired retrieval 실험](experiments/text-input-method-result.md)은
현재 MSCLAP 2023에서 영어 caption 입력 우세를 확인했다. AudioCaps는 일반 audio caption
검색이며 행사→음악 추천 검증은 아니다. 검색 입력 처리 방식은 Spring predefined mapping으로
결정됐으나 mapping 및 canonical AI 업무 API는 구현 전이다. 자유 자연어 검색은 별도 후속
협의·ADR로 재검토한다.

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
Audio 공통 생성기는 승인된 [ADR-0007](adr/ADR-0007-audio-highlight-embedding-strategy.md)의
56~60초 inclusive validation 및 고정 8 chunk 대표 벡터 생성 정책을 적용합니다.
실제 권리 확인 Phase A 6곡의 MSCLAP 생성 경로 기술 검증과 [전용 PostgreSQL/pgvector 통합 검증](experiments/audio-embedding-postgres-validation/README.md)은 완료했습니다. 별도의 50곡 calibration cohort Audio/Text Embedding·raw cosine·청취 분석도 완료했으며 자세한 결과는 [calibration 기록](experiments/audio-similarity-calibration/README.md)에 있습니다.
음악 입력은 동기로 처리합니다. Spring 업무 API 구현은 Accepted 012/014 정책을 기준으로 후속 진행하며, 내부 DTO의 미정 계약을 이 Roadmap에서 새로 확정하지 않습니다.
[저장 안내](guides/EMBEDDING_STORAGE.md), [DB 검색 검증](guides/DATABASE_AUDIO_SEARCH.md)을 참고합니다.
Text Embedding 생성(NSUAI-41)과 저장/profile 호환성(NSUAI-42)은 구현 완료했습니다. 영어 입력 경로의 근거와 Spring predefined mapping 결정은 확보했지만 mapping 및 AI 업무 API는 구현 전입니다. 과거 Held-out24는 한국어 사용자 입력을 Qwen structured pipeline이 MSCLAP용 영어 의미로 해석한 개발 평가이며 서비스 경로나 한국어/영어 직접 입력 비교가 아닙니다. Spring 업무 API 연결, 백엔드 ID/FK·revision lifecycle과 오류 기록·자동 재처리는 별도 미완료 범위입니다.
Phase 3 전체 완료를 의미하지 않습니다.

남은 작업:
- [x] 기존 30초 FMA와 다른 Phase A Dataset의 로컬 MSCLAP 기술 검증용 출처·라이선스 확인(사용자 확인 근거) 및 60초 적격 fixture 준비·길이 검증
- [ ] 개발 벡터 재생성 대상과 새 입력 매핑 확인: 같은 FMA 원본으로 재생성하지 않음
- [x] 최신 Audio 입력 기준에 따른 decoded sample frame 기준 56~60초 inclusive 길이 validation 구현
- [x] ADR-0007 D2·D3·D4에 따른 처음 56초 사용 및 7초 × 8개 non-overlap Chunk 생성
- [x] ADR-0007 D6·D7·D8에 따른 Chunk별 L2 → Mean Pooling(N=8) → 최종 L2 및 대표 벡터 1개 생성
- [x] 저장·검색의 공통 생성 경로와 preprocessing/generation metadata 정합화
- [ ] 적격 새 입력·대상 매핑·새 생성 방식 검증 완료 후 ADR-0007 D9의 개발/테스트 벡터 삭제·재생성
- [ ] revision별 벡터 보관·처리 상태·attempt 소유권·삭제 기록 추가
- [ ] Backend ACTIVE 전환 커밋 확인 후 이전 revision 정리와 실패 복구
- [ ] ACTIVE (music_id, audioRevision) 후보 쌍 필터와 검색 결과 revision 반환
- [ ] 백엔드 연동 계약 확정: 음악 ID·파일 전달·버전·오류·타임아웃
- [ ] 음악 수정·삭제 처리와 오래된 요청의 덮어쓰기·재등록 방지
- [ ] Spring predefined mapping 및 canonical English input 생성 구현
- [ ] canonical input 업무 DTO/API를 확정·구현하고 Text Embedding에 연결
- [ ] 동기 업무 HTTP API 구현: 등록·검색·수정·삭제
- [ ] 실패 기록·재시도·중복 요청·시간 초과 후 재요청 정책
- [ ] 실제 백엔드 음악 ID를 사용한 등록→검색→수정→삭제 통합 검증

관련 Issue:
- `NSUAI-25` Audio/Text Embedding 생성 및 저장 구현

Audio 정책 적용 순서:
완료: ADR-0007 generator·generation metadata 구현, synthetic Audio 단위 검증, MSCLAP batch smoke validation.
완료 단계: Phase A Dataset 준비·60초 입력 기술 검증·Phase A 로컬 MSCLAP 기술 검증용 출처·라이선스 확인.
완료 단계: 2026-10-09 [실제 6곡 MSCLAP 생성 경로 검증](experiments/audio-highlight-msclap-validation/README.md). 같은 process 반복과 별도 process/model reload에서 [8,1024]→[1,1024] 및 exact 재현성 확인.
완료: 2026-10-09 전용 PostgreSQL/pgvector 통합 검증. 저장 round-trip, cosine 수치 parity(`abs=1e-6`, `rtol=0`), 정확한 ranking parity 및 격리/rollback 결과는 [실험 기록](experiments/audio-embedding-postgres-validation/README.md)을 참고한다. Text Embedding 생성·저장도 구현했다. 별도의 50곡 calibration cohort similarity·청취 평가 분석은 [실험 기록](experiments/audio-similarity-calibration/README.md)에 완료 상태로 보존했다. 기존 dev/test Embedding은 이번 단계에서 삭제하거나 재생성하지 않았다. 최종 display calibration, 독립 validation, production 검색 품질 평가는 남아 있다.
기존 30초 FMA의 핵심 조건·결과·한계는 Historical Markdown으로 보존하고 원본·상세 산출물은 삭제하며 임의 반복/padding으로 FMA를 새 fixture로 바꾸지 않는다.
2026-10-08 [Phase A](experiments/audio-highlight-phase-a/README.md)에서 Kevin MacLeod 음원 6곡의 지정 60초 WAV 생성·기술 검증·반복 재현성을 완료했다. 공식 곡의 CC BY 4.0과 원본 MP3의 공식 Incompetech 직접 다운로드는 각각 confirmed_by_user다. Phase A 종합 verification_status=verified, rights_cleared=true로 로컬 MSCLAP 기술 검증용 출처·라이선스 확인을 완료했다. 공식 서버 파일과 SHA-256 비교는 not_performed이며 모든 향후 서비스/배포 용도의 포괄적인 권리 검토 완료를 뜻하지 않는다. 실제 MSCLAP/DB 평가·벡터 삭제/재생성은 수행하지 않았다.
Dataset 선행조건은 Roadmap과 [FMA 안내](guides/FMA_VALIDATION.md)·[DB 검증 안내](guides/DATABASE_AUDIO_SEARCH.md)에서 관리하고 ADR-0007은 변경하지 않는다.
운영 ACTIVE revision 보관·전환 정책과 구분합니다. 생성기는 float64로 norm과 pooling을
계산하고 정확한 0 및 non-finite만 거부합니다. 실제 모델 생성 경로와 calibration cohort 분석은 각각 해당 실험에서 완료했으며, 운영 검색 품질과 독립 validation은 별도 미수행입니다.

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
- Text Embedding 생성 경로 구현 완료 (`NSUAI-41`); Spring predefined mapping과 canonical 입력 업무 API는 후속 구현이며, AI 검색 입력 번역/LLM 해석은 현재 경로에서 사용하지 않음
- 모델 버전 저장
- Embedding dimension 관리
- Audio/Text pgvector 저장과 Text↔Audio profile 호환성 구현 완료 (`NSUAI-42`)
- 중복 생성 정책
- 실패 시 재처리 가능한 오류 정보

완료 기준:
- Audio 입력으로 Embedding 생성 가능
- Text 입력으로 Embedding 생성 가능
- 생성된 벡터 저장 가능
- 저장된 Embedding을 Similarity 계산에 사용 가능
- ADR-0007의 길이 경계·분석 범위·고정 Chunk·aggregation·재현성을 검증하고 저장·검색에 동일 규칙이 적용됨을 확인
- 과거 개발/검증 Dataset 입력·대상 매핑 및 새 방식 벡터 생성은 당시 60~80초 기준으로 완료했다. 현재 56~60초 AI 입력 범위에도 포함되는 정확한 60초 fixture는 그대로 유효하며, 운영 ACTIVE revision 정책과 구분한다. Linear AI-033 / NSU-89의 60~80초 문구는 최신 사용자 결정과 불일치하므로 후속 동기화 대상이다.

---

## Phase 4 — BPM / Rhythm 상세 정보

관련 Issue:
- `NSUAI-8` BPM 및 리듬 측정·요청 비교 검증
- `NSUAI-9` BPM·리듬 feature 상세 정보 생성

목표:
- CLAP 순위와 분리된 BPM/Rhythm 측정값과 요청 비교 상세 정보를 검증·구현한다.

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
- 분석 불가와 요청 조건 없음의 구분 및 `null`+reason을 확인
- BPM/Rhythm은 음악 순위 점수로 사용하지 않음

---

## Phase 5 — 고정 음악 유사도 변환 calibration

관련 Issue: `NSUAI-12`. `NSUAI-13`은 NSUAI-16에 통합된 Duplicate이며 재활성화하지 않는다.

상태: 50곡 cohort, 16×50 raw cosine, 96쌍×3명 청취 평가 및 분석을 완료했다([결과](experiments/audio-similarity-calibration/README.md)). 분석에서 raw cosine과 사람 평균의 Pearson 0.502, Spearman 0.524 및 rank 상/중/하 평균 2.854/2.375/1.448을 관찰했다.

남은 작업:
- 최종 표시 변환은 미확정이다. `clamp(100 * cosine / 0.4, 0, 100)`는 provisional 후보일 뿐이다.
- 독립 validation cohort는 아직 수행하지 않았다. calibration 자료를 일반화 성능 검증으로 재사용하지 않는다.
- 표시 변환의 production 적용과 `resultVersion` 연결은 별도 구현·검증 대상으로 남아 있다.

---

## Phase 6 — 후보 쌍 검색·최대 100곡 반환

출처: Accepted Linear 서버 협의 012. 정책은 승인됐으며 HTTP 업무 흐름은 구현 전이다.
관련 Issue: `NSUAI-15`, `NSUAI-16`. 입력 최대치는 NSUAI-15에서 실측 후 정한다.

```text
저장 행사 등록 → eventId로 본문 없는 추천 요청
→ Spring 권한·상태 확인 및 단일 snapshot 고정
→ 같은 snapshot의 Eligibility, Spring이 생성한 canonical English 검색 입력 + eligible ACTIVE 후보 쌍을 AI에 전달
→ AI canonical input/후보 호환성 확인·raw cosine 정렬
→ 최대 100곡·구조화된 상세 정보 반환
→ Spring 순서/구조 검증 후 순위를 유지하고 결과 구성
→ 사용자가 별도 버튼으로 해당 Artist와 매칭
```

사용자→Spring endpoint와 행사 입력 규칙은 Spring 소유 계약이다. AI 내부 요청의 구체 DTO는 별도 계약 확정 전까지 미정으로 유지한다([현재 AI 작업 기준](api/CLAP_RECOMMENDATION_DIRECTION.md)).

완료 기준:
- ACTIVE 후보 쌍을 계산 전에 정확히 제한하고 결과 revision 반환.
- Spring이 입력 ACTIVE 후보를 임의로 자르지 않음. 측정한 입력 maximum을 초과하면 503·경보 처리.
- 결과 상한 최대 100곡. 반환 개수 상한과 입력 후보 상한을 구분.
- Spring은 raw cosine을 받지 않고 순서를 재정렬하지 않음. Spring 구조 검사와 AI raw cosine 정렬 검증을 분리.
- 호환 벡터 재사용·필요한 생성·처리 한도·실패/누락 표현을 정합화하고, AI가 최대 100곡을 반환하며 상한 미만 후보는 가능한 결과를 모두 반환하는지 검증.
- 아티스트 집계·후보 비교 문장을 생성하지 않음.
- Reliability·Risk Signal을 음악 유사도 순위에 합산하지 않음.
- 입력 표현·동점 처리·대량 결과 성능은 후속 계약/실측으로 확인.
- 화면·매칭 버튼은 Backend/Frontend 구현 책임이며 AI 완료와 구분.

당시 계획 이력: 2026-10-04~05에는 AI retrieval 50~100 → Backend Ranker Top10을 계획했다.
2026-10-10 Accepted 012에서 해당 과거 흐름의 적용 범위를 대체했다. 과거 계획과 Decision 이력은 보존한다.

---

## Phase 7 — Spring 템플릿 추천 이유

역사적 관련 Issue: `NSUAI-10`, `NSUAI-11` (현재 Canceled).

012에서 별도 AI Explanation API 호출은 현행 흐름에서 제외했다. `NSUAI-10`/`NSUAI-11`은 Canceled 상태를 유지한다.

목표:
- Spring이 AI 구조화 상세 정보, Spring이 확정한 canonical 요청 의미 및 실제 통과 조건으로 템플릿 추천 이유를 만든다.
- 실제 근거만 사용하고 AI/Spring에서 순위를 다시 계산하지 않는다.
- 구체 evidence field/schema를 API 계약에서 구현 시 정합화한다.
- 후보 간 비교 문장이나 아티스트 집계 점수를 생성하지 않는다. LLM은 필수가 아니다.

완료 기준:
- Spring template 설명과 AI 상세 근거의 일치 검증.
- 누락·오래된 결과·근거 없는 설명을 검증.
- LLM은 선택 사항이며 필수 구현이 아니다.

---

## Phase 8 — 후보 간 비교 설명 (폐기 이력)

이전 계획은 상위 후보 항목 diff 계산과 비교 문장 생성이었다.
Accepted 012가 008의 별도 AI Explanation API 범위를 대체했으며 후보 비교 설명은 현행 흐름에서 제외한다.
`NSUAI-3`·`NSUAI-5`·`NSUAI-6`의 기록은 이 과거 Phase의 이력이며 이번 동기화 범위에서 상태를 변경하지 않는다.
이 Phase 번호를 재사용하지 않는다.

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
  ├── Fixed 0–100 Music Similarity
  ├── Track Retrieval
  └── Structured recommendation details for Spring templates
  ↓
PostgreSQL + pgvector
```

곡 검색 API 응답의 과거 개념 예시(확정 Schema가 아님; 별도 설명 API 호출은 현행 정책이 아님):

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
- 전체 통과 ACTIVE 후보 쌍 입력 → AI 유사도 정렬·최대 100곡 반환 → Spring 순서 유지·곡 표시 → 별도 사용자 Artist 매칭 검증
- 곡별 `rank`와 응답 순서, 후보 독립 0~100 음악 유사도 반환; raw cosine은 AI 내부 정렬 기준이며 Spring 계약 필드에 포함하지 않음
- BPM/Rhythm 등 구조화된 상세 정보 반환; 순위 점수로 사용하지 않음
- AI의 구조화된 곡 정보, Spring이 확정한 canonical 요청 의미 및 통과 조건을 사용한 Spring 템플릿 추천 이유 구성
- Sample 등록/수정/삭제 후 Embedding 상태
- 실제 Audio/Text 데이터 기반 Matching 결과

---

# 2. 실제 구현 시작 순서

아래는 초기 구축 때 정리한 의존 순서의 이력이다. 초기 환경·MSCLAP·Embedding·DB 기반 및 CLI는 구현됐고, 실제 6곡 MSCLAP 생성 경로와 전용 PostgreSQL 통합 검증도 완료됐다. 이 초기 순서는 현재 남은 작업의 우선순위를 나타내지 않으므로, 이어지는 현행 순서를 따른다.

```text
초기 설정·생성·DB 기반 및 CLI                         ✅
ADR-0007 실제 음악 생성 경로 검증                    ✅
전용 PostgreSQL/pgvector 통합 검증                    ✅
기존 dev/test Embedding 대상·소유권·입력 mapping 확인 ⏳ NEXT
별도 승인 후 ADR-0007 generation으로 재생성            ⏳
새 generation 저장·검색 확인                          ⏳
새 similarity 분포·음악 품질 평가                     ⏳
후보 독립 0~100 음악 유사도 calibration               ⏳
Accepted 012 업무 API / Spring 연동·E2E               ⏳
```

Accepted 012 응답에서는 곡별 `rank`, 후보 독립 0~100 음악 유사도, BPM/Rhythm 등 구조화된 상세 정보를 다룬다. API 문서에서 세부 DTO/schema는 구현 시 확정 대상으로 남아 있으므로 여기서 추가 field 이름을 정하지 않는다. raw cosine은 AI 내부 정렬 기준이며 Spring 응답 계약에 노출하지 않는다. Spring은 AI 순서를 유지하고 AI의 구조화 근거와 실제 통과 조건으로 템플릿 추천 이유를 만든다. BPM/Rhythm은 음악 순위 점수나 legacy 종합 Score가 아니다.

---

# 3. 개발 시 주의사항

## API부터 만들지 않는다
Python 내부의 Matching Pipeline을 먼저 함수 수준에서 완성한 뒤 HTTP API 계층을 연결한다.

## 정규화 수식을 임의로 확정하지 않는다
`cosine_similarity * 100` 등 임의 공식으로 최종 확정하지 않는다.

실제 MSCLAP similarity 분포를 측정한 후 결정한다.

## Embedding Dimension을 하드코딩하지 않는다
과거 pgvector 기능 확인에 사용한 `VECTOR(3)`은 테스트 값이며 MSCLAP의 실제 차원이 아니다.
현재 Phase 2에서 MSCLAP 2023 CPU의 Audio/Text Embedding을 1024차원으로 실측했다.
저장·검색에 사용하는 차원은 실제 모델/환경의 출력으로 검증하며, 모델·checkpoint·환경 변경 시 재검증한다.

## Hard Filter와 음악 유사도 정렬을 분리한다
- Hard Filter = 후보 포함 여부
- 음악 유사도 = 현행 사용자 결정의 곡 정렬 기준
- BPM/Rhythm 등 구조화 상세 정보는 순위 점수로 사용하지 않으며 legacy 항목 점수·종합 점수 평균을 현행 순위에 사용하지 않음

## 설명은 실제 근거만 사용한다
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
- `NSUAI-12`
- `NSUAI-15`
- `NSUAI-16`
- `NSUAI-25`
- `NSUAI-26`
- `NSUAI-27`

Canceled/Duplicate 이력은 현행 구현 backlog가 아니다: `NSUAI-10`, `NSUAI-11`, `NSUAI-13`, `NSUAI-28`.

---

# 5. 현재 다음 작업

MSCLAP PoC·Audio/Text 생성 및 저장 경로, Phase A 기술 검증과 전용 PostgreSQL/pgvector 통합 검증을 완료했다. 별도 50곡 calibration cohort의 raw cosine·청취 분석도 완료했으며 결과는 [calibration 기록](experiments/audio-similarity-calibration/README.md)에 있다. 최종 display calibration과 독립 validation, 운영 검색 품질의 일반화는 미완료다.
다음 서비스 구현은 새 검색 입력 협의와 Accepted 012/014의 유지 범위에 따른 Spring 추천 API 연동(NSU-63)이다. Spring mapping과 canonical input DTO/API는 후속 구현이며, 기존 개발 벡터의 삭제·재생성은 소유권·mapping 확인과 별도 승인 후에만 수행한다.

## 2026-10-07~10 정합화 이력

2026-10-07 당시 계획에는 전체 결과 반환·유사도 정렬·집계 없음·후보 비교 설명 폐기가 포함됐다.
2026-10-10 Linear 012가 Accepted로 동기화되며 반환 상한은 최대 100곡으로 확정됐다. 전체 통과 ACTIVE 후보 입력과 결과 상한을 구분하고, 005/008/009의 대체 범위와 유지 원칙을 기록했다. 구현 상태는 별도로 추적한다.
30초 FMA는 핵심 근거만 Historical Markdown으로 보존하고 새 검증은 다른 Dataset을 사용한다.
ADR-0007·코드·테스트·DB·데이터를 변경하지 않은 문서 작업이다.
