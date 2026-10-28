# ADR-0009. Spring canonical 검색 입력 mapping

## Status

- Accepted — Spring canonical mapping 방향에 대한 사용자 결정 반영 (2026-10-28).
- Linear 서버 협의 012의 검색 입력 처리 책임을 대체하는 새 협의가 승인된 것을 전제로 한다. 012의 다른 검색·랭킹·서버 책임은 이 ADR의 범위에서 변경하지 않는다.
- Spring Mapping 및 AI 업무 HTTP API 구현은 아직 완료된 것으로 간주하지 않는다.

## Context

[ADR-0004](ADR-0004-korean-input-english-msclap.md)는 현재 MSCLAP 2023 구성에서 영어 입력 경로를 검토할 근거를 기록한다. 그 결정은 영어 입력 경로의 적합성을 다루며, 한국어 요청을 어떤 구성요소가 변환할지는 별도 문제로 남았다.

후속 후보로 Korean Direct, OPUS-MT, M2M100, Qwen/LLM 및 AI 서버 내부 자연어 해석을 조사했다. AudioCaps Multilingual paired 실험에서는 영어 원문 caption이 dataset의 한국어 AYA caption보다 target retrieval이 높았으나, 일반 audio caption 실험이며 언어 효과와 번역 표현 품질을 분리하지 못한다. 변환 방식 비교에서는 번역·structured interpretation에서 의미 이동과 단계별 실행 실패가 확인됐다. 비교 상세와 한계는 [검색 입력 처리 방식 비교 실험](../experiments/text-input-method-result.md)에 기록한다.

실제 서비스 UI와 요청값의 의미는 Spring이 소유한다. 이를 AI에서 다시 번역·분류하면 동일 의미를 두 번 해석하고 모델별 오류와 운영 의존성을 추가한다.

## Alternatives

- **Korean Direct:** 한국어 원문을 MSCLAP에 직접 전달. 별도 변환은 없지만 현재 MSCLAP 구성의 paired AudioCaps 결과 및 고정 serializer token feasibility가 불리했다. 한국어 의미 품질 점수로 해석하지 않는다.
- **OPUS-MT:** 한국어→영어 범용 번역. 40-query Agent-coded baseline에서 결과가 생성됐지만 의미 누락·추가·치환이 남았고 사람 검수 전이다.
- **M2M100:** 별도 번역 모델 후보. 3-query runtime smoke만 수행했으며 품질 비교 근거는 충분하지 않다.
- **Qwen/LLM:** 자유형 또는 structured 의미 변환 후보. structured 실험에서 parse 이후 schema/evidence 등 추가 실패가 있었고 40-query 비교의 의미 지표는 Agent-coded baseline이다.
- **Spring predefined mapping:** Spring이 사용자 선택값을 사전 정의 mapping으로 canonical English input으로 변환하고 AI에 전달한다. 이번 기존 변환 실험에서 직접 평가한 후보는 아니다.

## Evidence

- AudioCaps Multilingual test split: revision `6d74f0a52927fb4c776fb344de0b01db851b07d9`, CC-BY-NC-4.0, 924 usable audio, 3,033 paired query. English/Korean R@1은 11.34%/0.13%, R@5는 38.28%/0.46%, R@10은 55.52%/1.09%, MRR은 0.2439/0.0081이었다. 한국어는 AYA 생성 번역이며 한국어 token 초과 1,734/4,785(36.2%)를 paired retrieval cohort에서 제외했다.
- 40-query 변환 비교: 총 240 attempts. Korean Direct 최종 입력 0/80 token-feasible, OPUS 80/80, Qwen-v3 33/80이었다. OPUS semantic recall 158/182 및 precision 174/188, Qwen raw-output recall 96/182 및 precision 96/173은 Agent-coded baseline이며 human review pending이다. Qwen 의미 집계에는 schema/evidence 실패 raw output이 포함돼 end-to-end 품질로 해석하지 않는다.
- M2M100은 3개 입력 runtime smoke였고 semantic scoring·retrieval 비교가 아니었다.
- 상세 조건, 실패 유형, 분모, 한계는 [실험 요약](../experiments/text-input-method-result.md)을 참조한다.

## Decision

서비스 검색 입력 처리에는 번역 API, OPUS-MT, M2M100, Qwen/LLM 또는 AI 내부 원문 해석을 사용하지 않는다.

Spring이 predefined mapping으로 canonical English input을 생성하고 AI가 이를 MSCLAP Text Embedding 입력으로 사용한다.

## Spring Responsibility

- UI/요청 입력값 검증
- 승인된 선택값의 predefined mapping
- canonical value 및 canonical query 구성
- canonical input이 포함된 AI request DTO 생성
- 입력 option과 mapping 정의의 동기화

## AI Responsibility

- canonical input의 계약·형식 검증
- 전달받은 canonical text를 MSCLAP Text Embedding에 사용
- 기존 승인된 후보·revision 조건에 따른 Audio Embedding similarity 검색 및 랭킹
- 번역이나 자연어 의미 재해석을 수행하지 않음

정확한 DTO 필드명과 세부 version/error contract는 새 서버 협의 및 API 설계에서 확정한다. 현재 AI 저장소에 health endpoint 외 업무 API가 구현되어 있지 않으므로 이 ADR은 업무 API 구현 완료를 의미하지 않는다.

## Consequences

- 동일 입력의 canonicalization은 결정적이어야 한다.
- Spring은 mapping의 의미 정확성과 UI option 변경 시 갱신 책임을 가진다.
- AI 검색 입력 경로에서 번역/LLM model runtime과 출력 안정성 검증이 필요하지 않다.
- 기존 OPUS/M2M100/Qwen 실험 코드는 서비스 코드가 아니며, 이 ADR의 근거를 요약한 실험 문서는 보존한다.
- Mapping 기반 입력의 실제 retrieval 품질은 별도 평가가 필요하다.

## Limitations

- 이 결정은 서비스 검색 입력 처리 방식에 한정한다. 추천 이유 생성 등 별도 기능의 미래 LLM 가능성을 결정하지 않는다.
- Mapping은 정의된 선택값 범위에 한정되며 모든 자유 자연어를 표현한다고 보장하지 않는다.
- AudioCaps는 일반 audio caption retrieval 데이터이고 한국어 caption은 AYA 번역이다. 실험은 실제 행사→음악 추천을 검증하지 않았다.
- 변환 비교 semantic metric은 human-reviewed final score가 아니다.

## Related ADRs

- [ADR-0004](ADR-0004-korean-input-english-msclap.md) — 영어 MSCLAP 입력 근거 및 과거 정책 기록
- [ADR-0002](ADR-0002-ai-matching-server-architecture.md) — AI matching 서버 구조
- Linear 서버 협의 012 및 이를 입력 책임 범위에서 대체하는 신규 서버 협의

## Related Experiments

- [검색 입력 처리 방식 비교 실험](../experiments/text-input-method-result.md)
- 보존된 실험 script: `scripts/experiments/msclap_korean_vs_english_retrieval.py` (AudioCaps 언어 효과 검증 코드; OPUS/Qwen 비교가 아님)
