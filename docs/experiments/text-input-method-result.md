# 검색 입력 처리 방식 비교 실험

## 1. 실험 목적

한국어 행사 요청을 MSCLAP Text Embedding 입력으로 전달할 때 Korean Direct, OPUS-MT, M2M100,
Qwen/LLM 기반 변환의 실행 가능성과 의미 보존 문제를 조사했다. 별도의 AudioCaps Multilingual
실험으로 현재 MSCLAP 구성에서 텍스트 언어에 따른 일반 audio caption retrieval 차이도 확인했다.
두 실험은 서로 다른 질문을 다루며 하나의 점수로 합산하지 않는다.

## 2. 비교 대상

| 방식 | 실험에서의 역할 | 실험 여부 |
| --- | --- | --- |
| Korean Direct | 한국어 입력 feasibility control | 40-query 비교에서 실행 |
| OPUS-MT | 한국어→영어 일반 번역 | 3-query smoke 및 40-query 비교에서 실행 |
| M2M100 | 한국어→영어 일반 번역 후보 | 3-query runtime smoke; full comparison 미실행 |
| Qwen/LLM | 자유형/structured 영어 의미 변환 후보 | 여러 단계의 development·held-out·40-query 비교 실행 |
| Spring predefined mapping | 서비스용 결정적 입력 생성 후보 | 기존 실험의 직접 대상 아님. 실험 근거와 UI/서버 책임 결정을 바탕으로 선택 |

## 3. 실험 환경

### 고정 40-query 변환 비교

- Run: `run-20261024-full`; 40개 query × 3개 방법 × 2회 = 240 method attempts.
- Query SHA-256: `60bc93b2fe1743d46264aedf8fae1ba3f2c0fb913472dcb140951958c1ab3a90`.
- Semantic Gold v2 SHA-256: `30a0d053bcf708088d970e3f82d6d8cb01a1264388aa69223b1c614011b21cab`.
- 실행 기준: 당시 repository HEAD `11860d9aa8d43c43cee253df05a311384d829965`.
- Korean Direct는 Event Type, Description, Genre 순서의 고정 입력, null Genre는 `미지정`, GPT-2 tokenizer 77-token 한도 및 truncation 금지 조건을 사용했다.
- OPUS-MT: `Helsinki-NLP/opus-mt-ko-en`, revision `242c8bc3d012792ae91e50ba1b6b3c7ffb932736`, weight SHA-256 `e5ea744d3e47499ebde92fb1e80a9645946afae3982d0744e19afedd547b2a68`; Event Type과 Description을 따로 번역했다.
- Qwen: `qwen3-4b-gguf-q4_k_m-structured-v3`, `music-intent-v3`, prompt SHA-256 `43e8fb320bafa975c9be433b37590b7c586ad7c0d50706c9f0ca41aa04e9e612`, model revision `bc640142c66e1fdd12af0bd68f40445458f3869b`, GGUF SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`, llama.cpp build 11835.
- Qwen stage 성공은 JSON parse 80/80, schema 44/80, evidence/normalization/serializer/token-limit 33/80이었다. Repeat 1은 17/40, repeat 2는 16/40, pooled 성공 attempt는 33/80, 두 번 모두 성공한 query는 16/40, 한 번 이상 성공한 unique query는 17/40이다.
- Semantic 수치는 frozen Gold에 대한 사후 Agent-coded baseline이며 human review pending이다. Qwen의 96/182 recall과 96/173 precision은 schema/evidence 실패 raw JSON fact도 포함한 해석 품질 aggregate이며 end-to-end usable query 점수가 아니다.
- Korean Direct는 semantic quality 0으로 평가되지 않았다. 80/80 입력이 77-token 한도를 넘어 최종 MSCLAP 입력 feasibility가 0/80이었다.

### 이전 개발·smoke 자료

- OPUS와 M2M100의 2026-10-23 runtime smoke는 각각 3개 query, 6개 field translation이었다. 세 입력 모두 고정 serializer에서 77 tokens 이내였지만, 사람의 전체 의미 평가·Text Embedding·검색은 수행하지 않았다.
- M2M100은 `facebook/m2m100_418M`, revision `e90186c7b91d549fb3222bb6a1b9e9a6be711e50`를 별도 환경에서 실행했다. 세 query smoke 외 full 40-query 비교는 수행하지 않았다.
- Qwen3-1.7B structured-v3 ACTIVE16은 32 generation에서 schema valid 0/32였다. 4B Q4_K_M structured-v1 ACTIVE16은 32 generation에서 JSON 32/32, schema/evidence/normalization/serializer/token-limit 22/32였다.
- Qwen3-4B structured-v3 Held-out24는 48 generation에서 JSON 46/48, schema 31/48, evidence·normalization·serializer·token-limit 25/48이었다. Human semantic review 및 MSCLAP retrieval은 수행하지 않았다.

## 4. 변환 방식 비교 결과

### 40-query, 2회 반복

| 방식 | 최종 입력 성공 | Semantic 결과 | 주요 실패 | 비고 |
| --- | ---: | --- | --- | --- |
| Korean Direct | 0/80 | 변환 품질 점수가 아님 | 80/80이 77 tokens 초과; min 97, median 162, mean 156.85, max 240 | 동일 고정 serializer의 입력 feasibility control |
| OPUS-MT | 80/80 | Recall 158/182 (86.8%); precision 174/188 (92.6%) | omission 24, hallucination 10, substitution 4 | Agent-coded baseline, human review pending |
| M2M100 | 해당 run에 없음 | N/A | 전체 40-query run은 실행하지 않음 | 별도 3-query smoke만 수행 |
| Qwen3-4B structured-v3 | 33/80 successful attempts | Raw semantic recall 96/182 (52.7%); precision 96/173 (55.5%) | omission 86, hallucination 41, substitution 36; schema 36건, evidence 11건 실패 | Agent-coded baseline, human review pending; invalid raw output도 semantic coding에 포함 |

성공 attempt의 tokenizer 길이는 OPUS min/median/mean/max 27/40.5/41.875/60, Qwen 15/18/18.91/29였다.
Qwen repeat 안정성은 raw output exact match 31/40 pairs, normalized intent 및 serializer exact match 각각
15/16 both-success pairs였다. OPUS field translation 및 최종 입력은 각각 40/40 pairs에서 반복 일치했다.
OPUS 의미 지표도 모델 결과를 보고 난 뒤 Agent가 코딩한 것이므로 사람 검수 전 확정 성능으로 취급하지 않는다.

3-query smoke의 OPUS/M2M100 결과에는 의미 이동 사례가 있었다. 예를 들어 OPUS는 acoustic 요청을
magical로 바꾸고 식전 맥락을 dinner로 옮긴 사례가 기록됐다. M2M100은 식전 의미를 dinner time으로
옮기거나 부정/강도 표현을 어색하게 바꾼 사례가 기록됐다. 이 소규모 smoke는 빈도나 전체 모델 품질을
추정하는 근거가 아니다.

## 5. 한국어/영어 MSCLAP Retrieval 비교

이는 번역 모델 비교가 아니라 같은 AudioCaps 오디오에 대해 영어 caption과 dataset의 한국어 AYA caption을
MSCLAP에 입력한 paired retrieval 실험이다.

| 지표 | English caption | Korean `kor_Hang_AYA` |
| --- | ---: | ---: |
| 후보 오디오 | 924 | 924 |
| paired query | 3,033 | 3,033 |
| Recall@1 | 11.34% | 0.13% |
| Recall@5 | 38.28% | 0.46% |
| Recall@10 | 55.52% | 1.09% |
| MRR | 0.2439 | 0.0081 |
| Median rank | 8 | 444 |
| Mean rank | 25.30 | 452.64 |

Paired target rank 기준 영어 우세 2,956, 한국어 우세 74, 동점 3이며 rank 차이(한국어−영어)의 median은
421, mean은 427.34였다. Korean−English 차이의 95% paired cluster bootstrap CI는 R@1 −11.21%p
[-13.02, -9.52], R@5 −37.82%p [-40.61, -34.97], R@10 −54.43%p [-57.23, -51.52],
MRR −0.2358 [-0.2537, -0.2186]이다. Bootstrap은 unique audio 기준 2,000회, seed 20261025였다.

전체 4,785 caption 기준 영어 77-token 초과는 0건, 한국어 초과는 1,734건(36.2%)이었다. paired retrieval cohort는
token limit을 통과한 항목으로 제한됐다. 한국어는 사람이 작성한 원문이 아닌 AYA 생성 번역이며 AudioCaps는
행사→음악 추천 데이터가 아니다.

## 6. 주요 관찰

- 일반 번역은 출력이 생성돼도 Event Type·시간 관계·polarity·강도 등 의미가 바뀔 수 있다.
- Qwen structured 출력은 JSON parse만으로 성공을 보장하지 않았다. schema, evidence, normalization,
  serializer 단계에서 추가 실패가 있었다.
- Qwen raw semantic coding에는 구조 검증 실패 output이 포함돼 있으므로 raw 해석 aggregate와 실제 사용 가능한
  query 성공률을 구분해야 한다.
- AudioCaps에서는 현재 MSCLAP 2023 구성과 GPT-2 tokenizer 입력 정책에서 영어 caption이 한국어 AYA caption보다
  높은 target retrieval을 보였다. 이 결과를 모든 CLAP 모델·한국어 문장·음악 추천에 일반화하지 않는다.

## 7. 최종 결정

서비스 검색 입력 처리에는 번역 API, OPUS-MT, M2M100, Qwen/LLM 또는 AI 서버 내부 원문 번역·해석을 사용하지 않는다.
Spring이 predefined mapping으로 canonical English input을 생성하고 AI는 전달받은 canonical text를
MSCLAP Text Embedding 입력으로 사용한다.

## 8. 선택 이유

- 고정 mapping은 동일 입력에 동일 결과를 내며 모델 생성 변동이 없다.
- 번역/LLM model loading, 추가 inference, 운영 자원 및 출력 검증 부담을 검색 입력 경로에서 제거한다.
- UI option의 의미와 사용자 입력을 이미 소유하는 Spring이 canonicalization 책임을 맡고, AI 입력 역할을 임베딩·검색으로 단순화한다.
- 기존 OPUS/M2M100/Qwen 실험은 결정 근거와 과거 연구 자료이며 서비스 경로로 채택하지 않는다.

## 9. 한계

- predefined mapping은 명시적으로 지원하는 선택값 범위에 적용된다. 자유로운 한국어 Description 전체를 포괄하도록 결정한 것이 아니다.
- Mapping 결과가 실제 음악 검색·추천 품질을 높이는지는 별도 평가가 필요하다.
- 변환 비교의 semantic 지표는 일부 Agent-coded이며 human review 전 baseline이다.
- AudioCaps의 한국어 caption은 AYA 생성 번역이고 token-limit 통과 cohort만 retrieval에 포함됐다.
- 이번 결과는 Qwen이 필수라는 결론, OPUS가 production에 적합하다는 결론, 실제 행사→음악 추천 품질을 보장하지 않는다.

## 10. 관련 ADR

- [ADR-0004: 한국어 요청과 영어 MSCLAP 입력 근거](../adr/ADR-0004-korean-input-english-msclap.md)
- [ADR-0009: Spring canonical 검색 입력 mapping](../adr/ADR-0009-spring-canonical-search-input-mapping.md)
