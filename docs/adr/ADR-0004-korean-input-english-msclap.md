# 0004. 한국어 요청을 영어로 변환한 뒤 MSCLAP에 입력

- 상태: Accepted (사용자 결정, 2026-10-02)
- 범위: 행사 관계자의 음악 느낌·분위기 요청과 Text Embedding 생성

## 결정

사용자는 한국어로 음악 요청을 입력한다. 음악 요청 전처리 단계에서 의미를 유지한
영어 음악 설명으로 변환한 뒤 MSCLAP Text Embedding을 생성한다.
사용자가 영어를 직접 입력하도록 요구하지 않는다.

```text
한국어 요청 → 영어 음악 설명 → MSCLAP Text Embedding
                                   ↓
                    Audio Embedding과 유사도 계산
```

영어로 이미 입력된 요청은 번역 없이 모델 입력 길이를 확인한 뒤 사용한다.
화면·응답용 원문은 유지하며 사용자에게 영어 설명으로 대체된 요청을 보여줄 필요는 없다.

## 근거와 한계

### A. Historical Pilot — FMA16

동일한 의미로 정리한 16곡·한영 32문장의 비교에서 문장 잘림은 없었다.
원곡 1위는 한국어 1/16, 영어 10/16이었고 Top3 원곡 적중은 각각 3/16, 13/16이었다.
단일 평가자의 영어 후보 청취 평가에서는 48개 중 42개를 잘 맞음으로 평가했지만,
한국어 청취 평가는 48개 중 3개만 작성되어 양쪽을 직접 비교할 수 없다.
영어 문장은 사람이 작성·수정한 것이며, 이 결과는 소규모 예비 실험이다.

### B. 대규모 보강 실험 (supporting experiment) — AudioCaps Multilingual

CC-BY-NC-4.0으로 배포된 AudioCaps Multilingual test split의 고정 revision
`6d74f0a52927fb4c776fb344de0b01db851b07d9`에서 924개 오디오와 3,033개 동일 paired
query를 비교했다. 영어 원문 대비 한국어 `kor_Hang_AYA`의 검색 결과는 다음과 같다.

| 지표 | English | Korean AYA | Korean − English |
| --- | ---: | ---: | ---: |
| Recall@1 | 11.34% | 0.13% | −11.21%p (95% CI −13.02~−9.52%p) |
| Recall@5 | 38.28% | 0.46% | −37.82%p (95% CI −40.61~−34.97%p) |
| Recall@10 | 55.52% | 1.09% | −54.43%p (95% CI −57.23~−51.52%p) |
| MRR | 0.2439 | 0.0081 | −0.2358 (95% CI −0.2537~−0.2186) |
| Median rank | 8 | 444 | — |

한국어 caption 중 1,734/4,785개(약 36.2%)가 현재 MSCLAP GPT-2 tokenizer의 77-token
제한을 초과해 paired cohort에서 제외됐다. 전체 방법·코호트·runtime·제외 조건은
[대규모 paired 한국어/영어 MSCLAP retrieval 실험](../experiments/text-input-method-result.md)에
기록했다.

### C. 해석

현재 프로젝트에서 사용하는 MSCLAP 2023 구성에서는 동일 오디오를 대상으로 영어 caption이
한국어 caption보다 텍스트→오디오 검색에서 현저히 높은 성능을 보였다.

따라서 한국어 사용자 입력을 그대로 MSCLAP에 전달하는 것보다 영어 표현을 사용하는 입력 경로를
검토·유지할 강한 실험적 근거가 확보되었다.

### D. 한계

AudioCaps의 한국어는 사람이 작성한 원문이 아니라 AYA 생성 번역이므로 언어 차이와 번역 표현
품질을 분리할 수 없다. AudioCaps는 일반 audio caption retrieval 데이터이며 행사→음악 추천
데이터가 아니고, 실제 서비스 추천 품질을 직접 검증한 실험도 아니다. 77-token 초과 쌍을 제외한
결과는 token 제한을 통과한 cohort에 한정되며, token 결과도 현재 GPT-2 tokenizer/MSCLAP 입력
구성에 대한 결과다. 이 결과는 모든 CLAP 모델이나 모든 음악 추천으로 일반화하지 않는다.

## 구현 조건

- 음악 특징·분위기·강도·템포·장르·부정 조건을 보존하고 원문에 없는 특징을 추가하지 않는다.
- 원문과 영어 입력, 번역 방식/버전, 모델 버전 및 실제 입력 토큰 수를 추적 가능하게 남긴다.
- 현재 MSCLAP 2023의 77토큰 제한을 실제 토크나이저로 검사한다.
  길면 의미를 보존해 짧게 다시 변환하고, 끝부분을 임의로 버린 것을 전체 요청 처리로 간주하지 않는다.
- 번역 실패·빈 결과·길이 초과 시 실패를 명시한다. 한국어 직접 입력으로 조용히 우회하지 않는다.
- 원문 또는 번역 결과가 바뀌면 해당 Text Embedding을 재생성한다.

## 남은 결정

번역 공급자·모델·인증·호출 위치·timeout 등은 아직 선택하지 않았다.
이 ADR은 입력 언어 처리 정책을 확정하며 자동 번역 기능 구현 완료를 뜻하지 않는다.
행사 조건 구조화에 사용하는 기존 LLM을 재사용할지, Python에서 번역 모델/API를
호출할지 결정한 뒤 구현한다. Qwen은 영어 변환 후보 중 하나이며, Qwen·OPUS·번역 API
중 어떤 방식도 현재 채택되지 않았다. 영어 입력 경로의 필요성 근거 확보와 변환 방식 선정은
서로 다른 결정이다.

## Historical FMA Pilot 근거

- [실험 조건](../experiments/fma-phase2/README.md#목적과-조건)
- [수정본 검색 결과](../experiments/fma-phase2/README.md#수정본-검색-결과)
- [사용자 청취 평가와 한계](../experiments/fma-phase2/README.md#사용자-청취-평가)
- 원본·상세 산출물은 Cleanup으로 삭제했으며 핵심 근거는 위 Markdown에 보존한다.
- 관련 작업: NSUAI-1, NSUAI-2 및 Phase 3 Text Embedding 생성

## 후속 결정

[ADR-0009](ADR-0009-spring-canonical-search-input-mapping.md)는 영어 MSCLAP 입력 근거를 유지하면서 서비스 검색 입력을 Spring predefined mapping으로 생성하도록 정한다. 이 후속 결정은 ADR-0004의 역사적 근거를 덮어쓰지 않는다.
