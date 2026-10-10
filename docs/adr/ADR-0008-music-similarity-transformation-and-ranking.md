# ADR-0008. 음악 유사도의 원본 cosine 정렬과 고정 점수 변환·calibration 원칙

## Status

- **Accepted (AI 기술 원칙에 대한 사용자 승인, 2026-10-07)**.
- 최종 calibrated transformation·파라미터는 미확정이며, calibration 및 변환 버전 체계는 구현 전이다. 기존 cosine 정렬·임시 변환 구현과 구분한다.
- [ADR-0005](ADR-0005-audio-similarity-display-score.md)의 후속·확장이다. ADR-0005를 수정·삭제·Superseded 처리하지 않으며 당시 Decision/Status와 실험 근거를 보존한다.
- 승인 범위는 D1~D5의 AI 기술 원칙이다. 서버 간 계약·서비스 정책·Frontend UX의 승인을 뜻하지 않는다.
- 이번 작업은 문서 작성만 수행한다. 코드·테스트·DB·Embedding 데이터·Linear·NSU_CAPSTONE은 변경하지 않는다.

## Context

AI 검색은 cosine similarity와 표시/전달용 0~100 점수를 함께 다룬다. 변환의 clamp·saturation·rounding으로 다른 cosine이 같은 표시값을 가질 수 있으므로, 순위의 근거와 점수의 표현을 구분해야 한다.

ADR-0005는 개발용 임시 변환 구간과 초기 실험 근거를 기록했다. 현재 구현은 고정 구간 linear clamp이며 최종 calibration은 아니다. 요청마다 후보 집합으로 점수를 재정의하면 같은 cosine의 점수 의미가 달라진다. 향후 고정 변환을 선택할 때는 표본·생성 조건·검증 근거와 결과 의미의 버전 추적이 필요하다.

### 현재 구현에서 확인한 사실

- Audio↔Audio는 L2 정규화 내적, DB 검색은 pgvector cosine distance로 비교한다(R2, R3).
- 파일 검색은 변환값을 먼저 계산한 뒤 raw cosine으로 정렬한다. DB 검색은 거리로 정렬한 뒤 표시 점수를 붙인다. 모든 경로가 문자 그대로 ‘정렬 후 변환’ 순서로 실행되는 것은 아니다.
- 파일 검색의 raw cosine 동점은 `track_id` 오름차순, DB 거리 동점은 `music_id`의 C collation 순서로 처리한다. 이는 현재 개발 구현이며 서비스 전체 동점 계약을 확정한 것이 아니다.
- 현재 수식은 `clamp(100 * (cosine - lower) / (upper - lower), 0, 100)`이다. Audio↔Text 기본 구간은 0~0.4, Audio↔Audio는 0~1이다(R1, R4).
- FMA Audio↔Text 측정은 정규화 내적의 cosine과 MSCLAP 배율 적용 similarity를 별도로 기록한다(R5). 이 ADR의 raw cosine은 배율 적용 출력·softmax가 아니다.
- 생성 metadata와 `generation_profile`은 모델·checkpoint·전처리·패키지 등을 추적한다. 검색 출력의 `score_bounds`는 임시 구간을 기록하지만 전용 transformation/calibration 버전 체계는 구현되어 있지 않다(R3, R6).
- 서비스용 Text 검색·전체 결과 반환의 구현 완료를 이 ADR로 주장하지 않는다. 현재 CLI Top5와 실험 결과는 기존 범위로 유지한다.

## Decision / Rationale / Evidence / Alternatives / Trade-offs

근거를 [Current Implementation], [Project Experiment], [Existing ADR], [External Contract Record], [Engineering Decision]으로 구분한다. 이는 근거의 출처이며 모두 같은 수준의 검증을 뜻하지 않는다. R0~R10은 References와 연결된다.

### D1. AI ranking은 raw cosine에 의존한다

- **Decision:** AI의 음악 유사도 순위는 표시/전달용 transformed score가 아니라 원본 CLAP cosine similarity를 기준으로 결정한다. 표시값의 clamp·saturation·rounding으로 동점이 생겨도 그 표시값을 ranking 기준으로 사용하지 않는다.
- **Rationale:** 표현 과정에서 잃은 차이를 순위 계산에 반영하지 않고 원본 유사도 정보를 유지한다. `raw cosine → ranking 기준`, `raw cosine → 표시/전달용 transformation`은 의미적 의존관계이며 실행 순서를 강제하는 설명이 아니다.
- **Evidence:** [Current Implementation] R2의 raw cosine 정렬, R3의 거리 정렬, R7의 표시값 동점 테스트. [Existing ADR] R1의 원본 유사도 순위. [External Contract Record] R9 §4.3의 raw cosine 순위 기록. [Engineering Decision] R0의 AI ranking 원칙 승인.
- **Alternative / Trade-off:** transformed score로 정렬하면 포화·반올림으로 서로 다른 cosine을 구분하지 못한다. raw cosine을 보존하면 표시값이 같은 곡에도 순서가 생길 수 있다. raw cosine 자체의 동점 처리 계약·화면 설명은 별도이며 현재 CLI/DB tie-break를 서비스 계약으로 승격하지 않는다.

### D2. 동일 transformation version은 후보 집합에 독립적이다

- **Decision:** 동일 transformation version과 같은 cosine 입력에는 후보 집합이 달라도 같은 transformed score를 생성한다. 변환 버전은 적용하는 비교 유형·변환 규칙·파라미터를 식별할 수 있어야 하며 구체 식별 형식은 미정이다. 요청별 후보 1위=100·최하위=0, candidate min/max normalization, 후보 순위별 mapping 등 실행 시점의 candidate-relative 변환은 사용하지 않는다.
- **Rationale:** 주변 후보의 추가·제거가 동일 cosine의 표시값을 바꾸지 않게 하여 저장 결과의 의미와 요청 간 해석을 안정적으로 유지한다. 이는 서로 다른 모델·비교 유형·변환 버전의 점수가 자동으로 같은 의미라는 보장은 아니다.
- **Evidence:** [Current Implementation] R4의 함수는 후보 집합을 받지 않고 cosine과 고정 lower/upper만 사용한다. [External Contract Record] R9 §4.3의 후보 독립 고정 변환 기록. [Engineering Decision] R0의 후보 독립 원칙 승인.
- **Alternative / Trade-off:** 요청별 상대점수는 목록 내부의 차이를 강조하지만 후보 구성에 따라 같은 입력의 점수가 달라진다. 고정 변환은 일부 요청에서 표시값 범위가 좁거나 포화될 수 있어 calibration과 별도 검증이 필요하다.
- **Offline calibration과의 구분:** 고정 실험 표본의 분포·백분위를 분석해 변환 파라미터를 추정하고 이후 고정하여 사용하는 것은 허용한다. R8의 탐색 후보 B는 실험 표본의 백분위로 구간을 추정한 것이며, 매 요청의 후보 집합으로 점수를 재계산하는 방식과 다르다.

### D3. 현행 linear clamp는 최종 calibration이 아니다

- **Decision:** Audio↔Text 0~0.4, Audio↔Audio 0~1 및 현재 linear clamp 수식은 개발용 임시 기준으로 유지한다. 서비스의 최종 calibrated similarity 의미로 확정하지 않는다. ADR-0005와 당시 실험 자료는 historical decision/evidence로 보존한다.
- **Rationale:** 현재 기준은 작은 표본의 탐색·포화 완화 목적이며 검증된 음악 유사성 척도나 적합 확률을 제공하지 않는다.
- **Evidence:** [Existing ADR] R1의 개발용 Status와 최종 점수 미확정. [Current Implementation] R4의 임시 함수·R3의 provisional 출력. [Project Experiment] R8의 24곡 276쌍 중 215쌍이 cosine 0.4 이상인 결과와 소규모 평가 한계.
- **Alternative / Trade-off:** 현재 상한을 그대로 최종값으로 채택하면 구현은 단순하지만 검증되지 않은 해석을 고정한다. 임시 기준 유지에는 최종값과 현재값을 구분해 안내하고 후속 검증을 수행하는 비용이 있다. 선형 변환 자체는 ranking 오류나 모델 판별력을 개선하지 않는다.

### D4. 최종 고정 transformation은 실험과 별도 검증으로 선정한다

- **Decision:** 최종 transformation 선정에는 현재 적용되는 모델/Embedding 생성 조건, 음악 샘플, 실제 cosine 분포, 청취 평가를 근거로 사용한다. calibration용 자료와 검증용 자료를 분리하고 표본·평가자·자료 재사용의 한계를 기록한다. 청취 평가는 근거 중 하나이며 개발팀 평가만으로 임의 threshold를 확정하지 않는다. 선정한 transformation에는 별도 검증 근거가 필요하다.
- **Rationale:** 이론적 cosine 전체 범위만으로 음악 유사성의 표시 의미를 정할 수 없다. 서로 다른 생성 조건·비교 유형의 실제 분포를 확인하고 탐색 자료에 대한 과적합을 줄인다. 여기서 calibration은 표시 척도와 평가 근거의 관계를 검증하는 것이며 확률 보정을 뜻하지 않는다.
- **Evidence:** [Project Experiment] R8의 Audio↔Text/Audio↔Audio 분포 차이, 청취 평가 그룹의 범위 중첩, 평가자 1명·표본 재사용 한계. [Existing ADR] R10의 새 aggregation 분포·청취 평가 필요. [Engineering Decision] R0의 실험·독립 검증 원칙 승인.
- **Alternative / Trade-off:** 이론 구간만 사용하거나 기존 표본에 최적화하면 간단하지만 실제 출력·청취 의미와 어긋날 수 있다. 별도 표본·평가는 비용이 들며 평가자 편향과 반복되는 음악 쌍을 독립 관측으로 오인하는 문제를 관리해야 한다.
- **미확정:** piecewise linear는 검토 가능한 방법일 뿐 채택하지 않는다. breakpoint·lower/upper·anchor score·최종 함수·최종 v1 parameter·Audio↔Audio와 Audio↔Text 변환 통합 여부는 실험 후 결정한다. 구체 threshold나 점수 예시를 Decision으로 두지 않는다.

### D5. 생성 기준과 변환 기준을 구분하여 버전을 추적한다

- **Decision:** 모델·checkpoint·preprocessing·transformation/calibration 등 결과 의미와 재현성에 영향을 주는 기준을 AI 내부에서 식별·추적할 수 있어야 한다. Embedding generation version과 score transformation/calibration version의 역할을 구분한다. 구체 버전 형식과 관리 구현은 후속 설계다.
- **Rationale:** 같은 원본이라도 생성 조건이 달라지면 cosine 분포가 달라질 수 있고, 같은 cosine도 변환 기준이 달라지면 표시 의미가 바뀐다. 결과가 어떤 생성·변환 조건에서 나온 것인지 확인할 수 있어야 한다.
- **Evidence:** [Current Implementation] R6의 생성 metadata, R3의 `generation_profile`과 호환성 검사. [External Contract Record] R9 §4.3의 결과 의미 변경·버전 추적 기록. [Engineering Decision] R0의 생성/변환 기준 분리 승인.
- **Alternative / Trade-off:** 별도 식별 없이 현재 설정만 보관하면 과거 결과를 해석·재현하기 어렵다. 추적에는 정의·보관·버전 간 검증 비용이 추가된다. 통합 외부 버전과 내부 구성요소 버전의 연결 방식은 이 ADR에서 확정하지 않는다.
- **변경 영향:** transformation만 변경되었다고 Embedding이 변경된 것으로 간주하지 않는다. preprocessing version 변경이나 전체 Embedding 재생성을 자동 결정하지 않는다. 모델/Embedding/preprocessing 조건 변경 시에는 기존 calibration의 유효성을 재검증해야 할 수 있다.

## Historical evidence의 보존 수준

R8은 당시 의사결정을 설명하는 보존된 Historical 집계 요약이며 현재 재계산 가능한 raw evidence가 아니다. D3의 historical evidence 보존은 이 Markdown 요약으로 유지한다. 상세 track 목록·pairwise raw cosine·파일 hash·개별 rating·과거 Embedding은 의도적으로 제거했으며 현재 checkout에서 개별 데이터 수준의 재계산/audit이나 완전 재현을 지원하지 않는다. 과거 Git history 자체를 삭제했다는 의미는 아니다.

## Consequences / Future Work

- ADR-0005의 임시 기준·초기 근거는 유지하고 이 ADR은 향후 설계·검증 원칙을 확장한다. 최종 변환을 실제 채택할 때 대체하는 임시 기준과 검증 근거를 명시해야 한다.
- 현재 수식·CLI Top5·코드·테스트·DB 결과는 변경하지 않는다. D1·후보 독립 임시 변환은 기존 구현에서 확인했지만, 최종 calibration과 전용 변환 버전 체계 구현 완료를 뜻하지 않는다.
- ADR-0007 적용 후 새 Embedding 생성 조건으로 cosine 분포를 다시 측정한다. 기존 단일 crop·30초 FMA PoC를 새 생성 정책의 calibration 검증으로 간주하지 않는다. 새 검증 입력 선행조건은 Roadmap/Guide를 따른다.
- 향후 calibration은 삭제된 FMA raw evidence나 Historical 집계를 입력으로 사용하지 않는다. ADR-0007 generation policy에 따라 새로 생성한 Embedding·새 similarity distribution·새 evaluation evidence를 기반으로 수행하고, 해당 evidence는 별도로 생성·보존한다.
- 비교 유형별 calibration 표본과 별도 검증 표본, 음악 중복·평가자 구성·평가 기준·검증 통과 기준을 설계하고 기록한다. 이번 ADR은 구체 표본 수·threshold를 확정하지 않는다.
- 후보 집합 변경에도 동일 입력·변환 버전의 점수가 유지되는지, 표시 점수 동점에서도 raw cosine 순위를 유지하는지, 버전별 결과를 추적할 수 있는지 후속 구현에서 검증한다.
- 모델·preprocessing 변경 시 기존 변환의 유효성을 재검증하고 변환 변경 시에는 과거 표시값 해석과 재현 조건을 구분한다. 과거 결과 재계산·저장·migration은 별도 계약/설계다.
- 실제 사용자 피드백을 근거로 한 향후 recalibration은 후속 후보로만 둔다. 수집 방식·UI·재학습·주기·threshold를 결정하지 않는다.

## 외부 계약과 결정하지 않는 사항

2026-10-10 기준 Linear 011은 **Superseded**, 서버 협의 012는 **Accepted**다. 외부 수치·단일 resultVersion·AI 내부 세부 버전 분리는 012 §4.3을 참조한다(R9). 이는 이 ADR의 D1~D5 Decision을 변경하지 않으며, 이 ADR은 서버 간 계약·API 구현 완료를 주장하지 않는다.

다음은 이 ADR의 Decision이 아니다. 필요한 인터페이스는 외부 authoritative source를 참조하고 별도 협의한다.

- `resultVersion`의 JSON 타입/형식과 전달 소수점 자리수.
- Spring DB 저장 타입·정밀도·결과 보관 정책, Frontend 반올림·정수 표시·화면 UX.
- 입력 후보 최대치의 실측 값, API의 구체 DTO/schema, 처리 자원·timeout, 저장 형식과 Frontend 표시 세부사항.
- 사용자 피드백 수집 UX와 운영 정책.

Accepted 012는 결과 최대 100곡과 Spring 템플릿 설명 등 외부 흐름을 정했지만, 이 ADR의 D1~D5를 변경하지 않는다. 구체 API schema와 미구현 사항은 [AI 작업 기준](../api/CLAP_RECOMMENDATION_DIRECTION.md)에서 별도 관리한다.

## References

| ID | 자료 | 뒷받침하는 사실·Decision |
| --- | --- | --- |
| R0 | 2026-10-07 이 작업 대화의 사용자 승인: ADR-0008 D1~D5 AI 원칙·문서 3개 범위, 최종 calibration 미확정, 외부 계약 제외 | D1~D5의 프로젝트 승인. 외부 permalink는 없으며 Status와 Decision에 승인 범위 기록 |
| R1 | [ADR-0005](ADR-0005-audio-similarity-display-score.md) | D1·D3: raw cosine 순위·임시 구간·실험 한계, 후속 관계 |
| R2 | [Audio cosine·파일 검색 순위](../../app/matching/audio_search.py), [파일 검색 CLI](../../scripts/matching/search_audio.py) | D1: L2 내적·raw cosine 정렬·현재 tie-break와 변환 실행 순서 |
| R3 | [DB repository](../../app/repository/embedding_repository.py), [DB 검색 서비스](../../app/matching/database_audio_search.py) | D1·D3·D5: cosine 거리 정렬·표시 변환·provisional 출력·생성 profile |
| R4 | [점수 변환 함수](../../app/matching/normalization.py), [변환 Guide](../guides/SEMANTIC_SCORE_NORMALIZATION.md) | D2·D3: 후보 독립 함수·고정 lower/upper·linear clamp·현재 용도 |
| R5 | [FMA 측정](../../scripts/fma/validate_fma.py), [쌍별 측정](../../scripts/matching/validate_audio_similarity.py) | Context·D3: raw cosine과 배율 출력 구분, 임시 변환 사용 위치 |
| R6 | [공통 Audio 생성기](../../app/embedding/audio_embedding.py) | D5: 모델·checkpoint·preprocessing·seed·패키지 metadata |
| R7 | [검색 테스트](../../tests/matching/test_audio_search.py), [변환 테스트](../../tests/matching/test_normalization.py) | D1·D3: 표시값 동점의 raw 순위·임시 구간 검사. 이번 문서 작업에서 테스트를 실행하지 않음 |
| R8 | [변환 탐색](../experiments/audio-search-phase2/README.md#음악텍스트-기준-탐색), [쌍별 분포](../experiments/audio-search-phase2/README.md#새-음악-표본-및-쌍별-측정), [청취 평가](../experiments/audio-search-phase2/README.md#청취-평가), [실험 조건](../experiments/audio-search-phase2/README.md#공통-실험-조건) | D2~D4: Historical 집계 요약에 남은 오프라인 표본 분석·분포 차이·215/276 포화 진단·평가/표본 재사용 한계. 현재 재계산/audit 가능한 raw evidence가 아님 |
| R9 | [Linear 011](https://linear.app/nsu-capstone/document/011-ai-항목-점수의-전달-형식-43fcf42521b7), [Linear 012 §4.3](https://linear.app/nsu-capstone/document/012-clap-음악-유사도-기반-곡-추천-흐름-c7c809f92cba), [서버 협의 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3) | D1·D2·D5 외부 수치·버전 reference, 011 Superseded·012 Accepted 상태. 이 외부 참조 갱신은 D1~D5 Decision을 변경하지 않음 |
| R10 | [ADR-0007](ADR-0007-audio-highlight-embedding-strategy.md), [Roadmap](../AI_DEVELOPMENT_ROADMAP.md), [입력 검증 Guide](../guides/FMA_VALIDATION.md) | D4·Future Work: 새 생성 조건 분포·검증 필요, 과거 FMA와 새 적격 Dataset 구분 |

0~100 변환·candidate-independent transformation·청취 기반 calibration·piecewise linear 검토는 프로젝트의 engineering decision이다. MSCLAP 공식 점수 변환·calibration 방식이라고 인용하지 않는다.
