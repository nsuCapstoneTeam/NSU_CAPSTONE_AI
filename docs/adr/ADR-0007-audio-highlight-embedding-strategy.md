# ADR-0007. Audio Highlight의 다중 구간 대표 Embedding 전략

## Status

- **Accepted (사용자 승인, 2026-10-06); ADR-0007 generation policy 구현 완료**.
- 범위: Audio Highlight 권장 길이·최소/최대 길이 validation 정책, 분석 범위, Chunk 구성, 대표 벡터 집계, 개발/테스트 벡터 재생성 정책.
- 승인 근거: 2026-10-06 이 작업 대화의 사용자 최종 문서 작업 승인과 정책 변경 지시(R0).
- 이전 결정은 아래 변경 이력에 보존한다. 현행 정책은 권장 60초·허용 60~80초(양 경계 포함)·고정 8 non-overlap Chunk이며 기존 D5는 폐기한다.
- Accepted는 이 범위의 설계 승인을 뜻한다. 팀 전체 제품 요구사항 동기화나 구현 완료를 뜻하지 않는다.

구현 상태: 저장·검색에서 공통 AudioEmbeddingGenerator를 사용하며 60~80초 inclusive validation, 처음 56초의 고정 8개 7초 Chunk, Chunk별 L2 → Mean Pooling(N=8) → 최종 L2 및 대표 벡터 1개 생성, generation metadata/profile이 구현되었다. 관련 unit tests와 MSCLAP batch smoke validation도 수행했다. 권리 확인된 실제 60~80초 Dataset/fixture, 실제 음악 품질 평가, PostgreSQL 통합 검증, 개발/test Embedding 재생성, similarity 분포 검증 및 calibration은 아직 완료되지 않았다.

## 변경 이력

| 구분 | 당시 결정 또는 확인 | 현행 정책과의 관계 |
| --- | --- | --- |
| 초기 검토안 (미채택) | 60초 고정·9 Chunk·마지막 53~60초 overlap | 이전 대화의 검토안이며 채택하지 않음 |
| 2026-10-06 이전 사용자 승인 | 60~70초 권장, 별도 길이 상한 없음, 처음 최대 56초, 7초 이상 짧은 입력 허용, 마지막 end-aligned overlap, N=1~8, 7초 미만 처리 미결정 | 당시 결정으로 보존. 현행 정책에서 폐기 |
| 2026-10-06 Linear v1.10 정합화 | AI-033을 길이 정책의 주 기준으로 정리하고 AI-037/RIGHTS-023 및 AI-EMBED의 참조 책임 분리. Linear 저장 후 재조회 확인: 메인 2026-10-06T12:26:56.843Z, AI 2026-10-06T12:27:22.785Z | 당시 정합화 기록 유지. 길이·짧은 입력 정책은 v1.11로 대체 |
| 2026-10-06 최종 사용자 승인 / Linear v1.11 | 권장 60초, 허용 60~80초(60·80초 포함), 처음 56초, 고정 8 non-overlap Chunk, Mean Pooling(N=8) | 현행 정책. 최소/최대 validation 구현은 후속 작업. 기존 D5 폐기, 번호 재사용·다른 Decision 재번호 없음 |

## Context

Artist는 자신의 음악에서 대표 Highlight를 직접 선택해 업로드한다. 이 파일을 대표하는
Audio Embedding 하나를 PostgreSQL + pgvector에 저장하고 Text Embedding과 비교하는 것이
서비스 목표다. 현재 구현된 DB 검색은 Audio↔Audio이며 서비스용 Text 생성·검색 연결은 미구현이다.

ADR 결정 당시 `AudioEmbeddingGenerator`는 MSCLAP 2023 CPU 모델에 원본 파일을 전달하고
`resample=True`와 `base_seed + int(source_sha256[:8], 16)`으로 단일 crop을 재현했다(R7).
이것이 다중 Chunk와 pooling을 결정하게 된 기존 구현 배경이다. 현재는 아래 구현 상태처럼
고정 Chunk aggregation이 적용되며, 당시 구현과 현재 동작을 혼동하지 않는다.

MSCLAP 2023 config는 `duration=7`, `sampling_rate=44100`, `d_proj=1024`다(R1).
wrapper는 긴 waveform에서 random crop하고 짧은 waveform은 반복한 뒤 절단한다(R2).
2023 모델 논문은 학습 시 7초 random truncation과 짧은 입력 padding을 설명한다(R4).
원 논문의 학습 입력은 5초이므로 현재 2023 모델의 7초 근거와 구분한다(R5).

다중 Chunk의 대표 벡터 집계는 프로젝트 자체 정책이다. 공식 모델 내부의 feature 처리와
이 ADR의 최종 Chunk Embedding aggregation을 동일한 장문 Audio 처리 방식으로 설명하지 않는다.
MSCLAP의 `compute_similarity()`는 학습된 배율을 곱하므로 순수 cosine과도 구분한다.

## Decision

| ID | 확정한 정책 |
| --- | --- |
| D1 | 사용자가 선택한 Highlight의 권장 길이는 60초다. 최소 60초·최대 80초 길이 validation을 적용하며 양 경계는 허용한다. |
| D2 | 허용된 입력의 처음 56초만 사용해 7초 × 8개의 non-overlap Chunk를 생성한다. 56초 이후는 사용하지 않는다. |
| D3 | MSCLAP 2023의 7초 처리 단위를 유지하고 `duration=60`으로 바꾸지 않는다. |
| D4 | 분석 범위에서 random 7초 하나만 선택하지 않고 결정적인 여러 Chunk를 반영한다. |
| D6 | 각 Chunk의 MSCLAP Audio Embedding을 먼저 L2 Normalize한다. |
| D7 | 정규화한 8개 Chunk 벡터를 동일 비중의 Mean Pooling(N=8)으로 집계한다. |
| D8 | 평균 결과를 다시 L2 Normalize해 대표 Audio Embedding 1개를 만든다. |
| D9 | 새 방식 적용 시 기존 개발/테스트 Audio Embedding은 삭제 후 재생성한다. 운영 데이터 전환 정책으로 일반화하지 않는다. |

### Chunk 구성과 처리 흐름

입력 길이를 L초라 할 때 L < 60 또는 L > 80은 길이 validation 실패다.
60 <= L <= 80은 길이 validation을 통과하며, 다른 파일 형식·크기·권리 조건은 별도로 충족해야 한다.
권장 길이는 60초다. 허용된 입력은 처음 56초에서 항상 8개의 겹치지 않는 Chunk를 생성한다.
구간은 시작 포함·끝 제외다. 구현은 decoded frame 수와 sample rate를 기준으로 길이를 판정하고
정확한 sample 경계로 Chunk를 자른다.

```text
[0,7), [7,14), [14,21), [21,28),
[28,35), [35,42), [42,49), [49,56)
56초 이후: Audio Embedding 생성에 사용하지 않음
```

| 입력 길이 | 길이 validation | Embedding 처리 |
| --- | --- | --- |
| L < 60초 (7·30·53·56초 포함) | 실패 | Embedding 생성 대상 아님 |
| L = 60초 | 통과, 권장 길이 | 처음 56초, 8 non-overlap Chunk |
| 60 < L < 80초 (70초 포함) | 통과 | 처음 56초, 8 non-overlap Chunk |
| L = 80초 | 통과, 최대 경계 | 처음 56초, 8 non-overlap Chunk |
| L > 80초 | 실패 | Embedding 생성 대상 아님 |

```text
Artist가 직접 선택한 Highlight (권장 60초)
→ 길이 validation: 60초 ≤ L ≤ 80초 (구현 완료)
→ Audio 전처리 → 처음 56초의 7초 × 8 non-overlap Chunk
→ 동일 MSCLAP 2023으로 Chunk별 Audio Embedding
→ Chunk별 L2 Normalize → Mean Pooling(N=8) → 최종 L2 Normalize
→ 대표 Audio Embedding 1개 → PostgreSQL + pgvector 저장
→ 동일 모델 공간의 Text Embedding과 cosine 검색 (후속 구현)
```

## Rationale / Evidence

근거 유형은 출처의 종류를 구분한다. 기술적 판단이 공식 권장사항과 같은 수준의 검증을
받았다는 뜻이 아니다. R0~R10은 마지막 References와 연결된다.

### D1. 권장 60초와 허용 60~80초

#### D1-a. 권장 길이 60초

- **Decision:** Artist가 직접 선택한 대표 Highlight의 권장 업로드 길이는 60초다. 정확히 60초인 파일만 허용하는 것은 아니다.
- **Rationale:** 사용자에게 대표 구간 선택의 목표 길이를 안내하고, 권장 길이와 허용 범위를 구분한다.
- **Evidence:** [Project Requirement] R0의 최종 사용자 결정, R9의 메인 Linear v1.11 AI-033. 60초 권장은 MSCLAP 공식 요구사항이 아니다.
- **Alternative / Trade-off:** 이전 60~70초 권장은 폐기한다. 정확한 60초만 허용하는 대신 60~80초를 허용하지만, 56초 이후는 대표 벡터에 반영되지 않으므로 안내가 필요하다.

#### D1-b. 최소 허용 길이 60초

- **Decision:** L < 60초는 길이 validation 실패다. L = 60초는 통과한다.
- **Rationale:** 최소 60초를 서비스 입력 조건으로 확정한다. [Engineering Rationale] 모든 허용 입력에 실제 연속 Audio 56초가 존재하므로 짧은 입력 예외 없이 동일한 8 Chunk 분석을 적용할 수 있다. 60초 자체는 제품 정책이며 모델의 필수 최소 입력 길이로 주장하지 않는다.
- **Evidence:** [Project Requirement] R0와 R9의 AI-033. [Engineering Rationale] 허용 최소 60초가 분석 범위 56초 이상이라는 관계.
- **Alternative / Trade-off:** 짧은 입력 허용·end-aligned overlap·7초 미만 별도 처리 선택은 현행 정책에서 폐기한다. 60초 미만 파일은 대표 Highlight를 다시 선택하거나 편집해야 한다.

#### D1-c. 최대 허용 길이 80초

- **Decision:** L > 80초는 길이 validation 실패다. L = 80초는 통과한다. 길이 validation 통과가 다른 형식·크기·권리 조건 통과를 의미하지 않는다.
- **Rationale:** 업로드 대상을 전체 음악 파일이 아닌 Artist가 선택한 대표 Highlight로 유지한다. 최대 80초는 서비스 정책이며 MSCLAP의 최대 입력 길이로 주장하지 않는다.
- **Evidence:** [Project Requirement] R0의 최종 사용자 결정과 명시된 최대 길이 이유, R9의 AI-033.
- **Alternative / Trade-off:** 별도 상한 없음 및 70초 상한 대신 80초 상한을 선택한다. 80초를 넘는 파일은 편집해야 하며, 80초 파일의 마지막 24초는 Embedding에 반영되지 않는다. 업로드 최대 길이와 분석 길이는 별개다.

### D2. 처음 56초, 고정 8 non-overlap Chunk

- **Decision:** 허용된 60~80초 Highlight의 처음 56초만 7초 × 8개의 겹치지 않는 Chunk로 분석한다. 56초 이후는 사용하지 않는다.
- **Rationale:** 7초로 나누어떨어지는 분석 범위와 고정 추론 작업량을 사용한다. 모든 허용 입력에서 같은 구간 경계를 적용하고 잔여·overlap·가변 Chunk 처리가 필요하지 않게 한다. 저장·Audio 검색은 같은 생성 규칙을 사용한다.
- **Evidence:** [Project Requirement] R0와 R9의 AI-033. [Engineering Rationale] 7 × 8 = 56, 허용 최소 60초. 56초와 8개 선택은 공식 자료가 아닌 프로젝트 정책이다.
- **Alternative / Trade-off:** 60초·9 Chunk·마지막 overlap 또는 전체 파일 분석 대신 처음 56초만 사용한다. 60초 입력의 마지막 4초, 80초 입력의 마지막 24초는 반영되지 않는다. 고정 Chunk 수가 실제 처리시간의 동일성을 보장하지 않으며 처리시간은 아직 측정하지 않았다.

### D3. MSCLAP 2023의 7초 유지

- **Decision:** `duration=7`을 유지하며 `duration=60`으로 변경하지 않는다.
- **Rationale:** pretrained 모델이 사용한 입력 조건에서 불필요하게 벗어나지 않는다.
- **Evidence:** [Official Implementation] R1의 7초 config를 R2의 `preprocess_audio()`가 사용하고 긴 waveform은 `load_audio_into_tensor()`에서 random crop한다. [Paper] R4의 학습 전처리는 연속 7초 random truncation이다. R5의 원 논문은 5초로 서로 구분한다.
- **Alternative / Trade-off:** `duration=60`은 입력 조건 변경과 별도 검증이 필요하다. 7초 유지에는 구간별 추론·집계 비용이 따른다. 공식 근거 없이 60초 입력의 성능이 나쁘다고 단정하지 않는다.

### D4. Random Chunk 하나 대신 결정적인 다중 구간

- **Decision:** 분석 범위에서 임의의 7초 하나만 대표 벡터로 사용하지 않는다.
- **Rationale:** 사용자가 고른 대표 Highlight 중 분석 대상으로 정한 범위를 여러 구간으로 반영하고 crop 선택의 우연성을 제거한다.
- **Evidence:** [Official Implementation] R2의 긴 입력 random crop. [Project Requirement] R0의 대표 Highlight·재현성 요구. [Engineering Rationale] 다중 구간 선택 자체는 프로젝트 판단이다. ADR 작성 당시의 R7 코드는 해시 seed로 단일 crop을 재현했으므로 매 호출 결과가 무작위로 바뀐다고 설명하지 않는다.
- **Alternative / Trade-off:** random 1개나 고정 1개는 저비용이지만 다른 구간을 반영하지 못한다. 다중 구간은 추론 작업이 늘고 후속 pooling에서 시간 순서를 잃는다. 품질 개선은 별도 실험이 필요하다.

### D6. Chunk Embedding별 L2 Normalize

- **Decision:** 유효한 각 Chunk 벡터 E_i를 E_i / ||E_i||_2로 바꾼다.
- **Rationale:** 원본 magnitude가 다를 수 있으므로 그대로 평균하면 큰 norm의 Chunk가 대표 방향에 더 큰 영향을 준다. 방향을 유지하고 norm을 1로 맞춰 Chunk마다 동일 비중으로 집계한다.
- **Evidence:** [Official Implementation] R2의 `get_audio_embeddings()`는 encoder 결과를 반환하며 R3의 AudioEncoder 투영 결과에도 최종 L2 정규화가 없다. `compute_similarity()`는 Audio/Text를 norm으로 나눈 후 내적과 학습된 배율을 적용한다. [Paper] R4는 공통 embedding space의 contrastive similarity와 cosine 평가를 설명한다. [Engineering Rationale] 이를 참고한 Chunk별 정규화·집계는 프로젝트 선택이다.
- **Alternative / Trade-off:** raw vector 평균은 magnitude를 보존하지만 암묵적인 norm 가중치가 생긴다. 정규화는 magnitude 정보를 버린다. 실제 Chunk norm 분포는 아직 측정하지 않았다. 공식이 다중 Chunk의 L2 후 pooling을 권장했다고 쓰지 않는다.

### D7. Mean Pooling

- **Decision:** 8개 단위 Chunk 벡터를 m = (1/8) × sum(E_i / ||E_i||_2), i=1..8로 평균한다. N=8로 고정한다.
- **Rationale:** 현재 음악당 단일 벡터 저장·검색 구조에 맞고, 임의 가중치 없이 Chunk를 동일 비중으로 집계할 수 있다.
- **Evidence:** [Project Requirement] R0의 단일 대표 벡터·Mean Pooling 승인. [Engineering Rationale] R7의 단일 벡터 구조와 구현 단순성을 근거로 한 집계 선택. MSCLAP 공식 장문 Audio 처리 표준이 아니다.
- **Alternative / Trade-off:** Chunk 하나, Max/Top-K similarity, Chunk별 DB 저장, Weighted Pooling과 비교는 아래 표를 따른다. 평균은 시간 순서를 보존하지 않고 특징 상쇄·국소 특징 희석이 가능하다. 대표 벡터의 cosine은 Chunk별 cosine 평균과 일반적으로 같지 않다.

### D8. 최종 L2 Normalize와 대표 벡터 1개

- **Decision:** 평균 m을 m / ||m||_2로 정규화해 대표 Audio Embedding 1개를 저장한다.
- **Rationale:** 단위 벡터들의 평균 norm은 일반적으로 1이 아니므로 저장 표현을 통일한다.
- **Evidence:** [Official Implementation] R2의 similarity 정규화, R6의 pgvector cosine 내부 norm 계산. [Engineering Rationale] R7의 PyTorch 정규화 내적·pgvector cosine 검색과 일관된 표현을 선택한다.
- **Alternative / Trade-off:** 비영 평균을 그대로 저장해도 cosine은 크기를 제거하므로 사전 정규화는 검색 수학상 필수가 아니다. 최종 L2는 저장 표현 정책이며 평균 norm에 담긴 방향 일치 정도를 제거한다. 0벡터는 정규화할 수 없고 거의 0인 평균은 수치적으로 불안정할 수 있어 후속 실패·허용오차 기준이 필요하다.

### D9. 개발/테스트 벡터 삭제 후 재생성

- **Decision:** 새 방식 적용 시 기존 방식으로 생성한 개발/테스트 Audio Embedding은 보존하지 않고 삭제 후 재생성한다. 실제 데이터 삭제·재생성은 아직 수행하지 않았다.
- **Rationale:** 운영 데이터가 아니며 생성 정책 혼재와 동일 music_id 충돌을 피한다. 현 단계에 복잡한 generation 전환 구조를 도입할 실익이 적다.
- **Evidence:** [Project Requirement] R0의 개발 데이터 재생성 승인. [Engineering Rationale] R7 repository는 동일 ID의 다른 결과를 `EmbeddingConflict`로 거부한다. R8은 생성 조건이 다르면 재생성하도록 하는 합의 원칙이다.
- **Alternative / Trade-off:** 이전·신규 generation 병행은 rollback에 유리하지만 키·활성 generation·전환 설계가 추가된다. 삭제·재생성은 재추론 비용과 이전 DB 벡터의 비교·복구 불가를 감수한다. 원본 음원·모델·과거 실험 결과·다른 업무 데이터는 삭제 대상이 아니다. 향후 운영 migration/version transition은 별도 설계다.

## Alternatives Considered

| 방식 | 장점 | 선택하지 않은 이유 / Trade-off | 관련 Decision |
| --- | --- | --- | --- |
| 정확한 60초·9 Chunk·마지막 53~60초 | 60초 전체 포함 | 미채택 검토안. 현행 허용 60~80초·처음 56초 고정 분석과 다름 | D1, D2 |
| 전체 파일 또는 duration=60 | 구간 집계가 없거나 전체 범위 처리 | 길이·비용 증가 또는 pretrained 입력 조건 변경, 별도 검증 필요 | D2, D3 |
| Chunk 하나 선택 | 적은 추론·저장 비용 | 다른 분석 구간을 반영하지 못함 | D4, D7 |
| 짧은 입력 허용·end-aligned overlap (이전 정책) | 짧은 파일도 처리 가능 | 최소 60초 validation 결정으로 현행 정책에서 폐기. short-audio·잔여 처리 예외를 두지 않음 | D1, D2 |
| Max/Top-K similarity | 요청과 맞는 국소 구간 선택 가능 | 요청별 점수·집계 정책 및 구간 벡터 접근이 필요하며 단일 대표 벡터 방식과 다름 | D7 |
| Chunk별 DB 저장 | 구간 보존·부분 검색 | 곡별 여러 벡터와 검색 결과 집계·중복 처리 필요 | D7 |
| Weighted Pooling | 중요한 구간의 비중 조절 | 가중치 산정·근거·검증이 필요, 현재 동일 Chunk 비중 정책과 다름 | D7 |
| Mean Pooling (채택) | 동일 비중·단일 벡터·단순 집계 | 시간 순서 소실, 특징 상쇄·국소 정보 희석 | D7 |
| raw vector 평균 / 평균 그대로 저장 | magnitude 또는 평균 norm 보존 | 각각 norm에 의한 암묵적 가중치 또는 저장 표현 차이 | D6, D8 |
| 개발 벡터 generation 병행 | 이전 결과 비교·rollback | 현 단계에 추가 저장·전환 복잡도 | D9 |

## Consequences / Trade-offs

- 모든 허용 입력은 처음 56초에서 실제 7초 구간 8개를 겹침 없이 분석한다. 길이 validation 실패 입력은 Embedding 생성 대상이 아니며, 56초 이후는 사용하지 않는다.
- N=8이며 각 Chunk의 길이와 pooling 비중은 동일하다. 겹치는 시간 구간은 없지만 모델이 각 시점의 특징을 동일하게 반영한다는 뜻은 아니다.
- 대표 벡터 1개로 저장·검색 구조를 유지하지만 시간 순서·구간별 검색 근거를 보존하지 못한다.
- 기존 실험의 단일 crop 결과는 새 전략의 품질 검증 결과가 아니다. 새 Text↔Audio·Audio↔Audio 분포와 청취 평가가 필요하다.

### 구현 단계의 Future Work

- 개발/테스트 벡터 대상·재생성 원본 목록을 확인하고 실행 단계에서만 삭제·재생성한다. 이 정책을 Backend ACTIVE revision 보존·전환에 적용하지 않는다.
- 실제 권리 확인 Dataset을 이용한 음악 품질과 PostgreSQL 통합 검증을 수행한다. 현재 unit tests와 smoke validation은 해당 실제 음악/DB 평가를 대체하지 않는다.
- 실제 처리시간·동시성·메모리·검색 품질을 측정한다. API·timeout·generation 형식은 별도 협의하고 운영 데이터 migration/version transition을 후속 설계한다.

### 기준 문서와 현재 구현의 차이

- R9의 메인 Linear Requirements v1.11을 실제 저장 후 재조회로 확인했다. AI-033은 권장 60초·허용 60~80초(경계 포함)·처음 56초의 주 기준이다. AI-037/RIGHTS-023은 기존 AI-033 참조와 권리·원본 저장 정책을 유지하며 수정하지 않았다. AI-EMBED는 길이 정책을 AI-033, 고정 Chunk/aggregation을 이 ADR로 참조한다. 이는 Audio 정책 한정 승인이고 v1.11 문서 전체는 승인 전이다. v1.9의 추천/신규 아티스트 미승인 정책, 최종 전체 승인 revision v1.8 및 구현 Baseline v1.1은 유지한다.
- R8에 따라 서버 협의는 Linear가 관리 위치다. 저장소에 남은 server-agreements 문서와 번호 정합화는 이번 범위 밖이다. 서버 협의 012는 Proposed이며 이번 ADR로 승인하지 않는다.
- 기존 ADR 0003의 MSCLAP·pgvector 방향과 0006의 동기 처리는 유지한다. D9는 개발/테스트 데이터 한정이며 운영 ACTIVE revision 보존 결정을 폐기하지 않는다.
- ADR 작성 당시 구현은 해시 seed의 단일 crop이었다. 이후 ADR-0007 생성 정책과 generation metadata/profile을 구현했으며 관련 unit tests와 MSCLAP batch smoke validation을 수행했다. 실제 권리 확인 Dataset·품질 평가·PostgreSQL 통합 검증·개발/test 벡터 재생성과 similarity calibration은 아직 완료되지 않았다. 현재 동작은 [공통 생성 기준 문서](../guides/AUDIO_EMBEDDING.md), 완료·잔여 구현 작업은 [Roadmap Phase 3](../AI_DEVELOPMENT_ROADMAP.md)에서 확인한다.

### 미결정 사항

- 검증 실패의 서버/API 오류 표현과 사용자 안내는 관련 외부 계약에서 정한다. 입력 길이 허용 범위와 AI generator의 validation은 구현되어 있다.
- 실제 음악 데이터에서의 집계 품질과 매우 작은 비영 평균 벡터의 안정성은 실제 Dataset 검증 단계에서 평가한다. 현재 구현은 float64로 정규화/평균을 계산하고 finite 및 정확한 0 norm만 검사하며 임의 epsilon을 적용하지 않는다.
- 향후 운영 generation 보관·migration/version transition·rollback 및 서버 간 세부 계약.

## References

| ID | 자료 | 지원하는 결정 또는 사실 |
| --- | --- | --- |
| R0 | 2026-10-06 이 작업 대화의 사용자 최종 승인: 권장 60초·허용 60~80초(양 경계 포함)·대표 Highlight 유지 목적의 80초 상한·처음 56초/고정 8 non-overlap Chunk·두 단계 L2/Mean(N=8)·기존 개발 벡터 재생성 정책 유지·문서만 작업 | D1~D4·D6~D9의 프로젝트 정책 출처. 이전 정책 및 D5 폐기는 변경 이력 참조. 외부 permalink는 없으며 Decision에 승인 내용을 기록 |
| R1 | [Microsoft config_2023.yml](https://github.com/microsoft/CLAP/blob/e8a6467b87cd85716e20c6a008126150d9740be0/msclap/configs/config_2023.yml) | D3의 duration=7, wrapper 44100Hz, d_proj=1024 |
| R2 | [Microsoft CLAPWrapper.py](https://github.com/microsoft/CLAP/blob/e8a6467b87cd85716e20c6a008126150d9740be0/msclap/CLAPWrapper.py) | D3·D4·D6·D8의 preprocess_audio/load_audio_into_tensor/get_audio_embeddings/compute_similarity 사실, short-audio 반복·다채널 flatten |
| R3 | [Microsoft models/clap.py](https://github.com/microsoft/CLAP/blob/e8a6467b87cd85716e20c6a008126150d9740be0/msclap/models/clap.py) | D6의 AudioEncoder·Projection 반환 경로: 최종 L2 없음 |
| R4 | [Natural Language Supervision for General-Purpose Audio Representations, arXiv:2309.05767v2](https://arxiv.org/pdf/2309.05767v2) | D3의 7초 학습 전처리(§3), D6·D8의 공통 공간·contrastive similarity·cosine 평가(§2). 프로젝트 Chunk aggregation의 권장 근거가 아님 |
| R5 | [CLAP: Learning Audio Concepts From Natural Language Supervision, arXiv:2206.04769v1](https://arxiv.org/pdf/2206.04769v1) | D3의 버전 구분: 원 논문 §3.2는 5초·44100Hz·1024차원 |
| R6 | [pgvector v0.8.6 vector.c](https://github.com/pgvector/pgvector/blob/v0.8.6/src/vector.c) | D8: VectorCosineSimilarity/cosine_distance가 내부 norm으로 나눔. 사전 L2는 cosine 수학상 필수가 아님 |
| R7 | [공통 생성기](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/blob/bd186987a72183c03a15806a1bc7a8c1307a9206/app/embedding/audio_embedding.py), [repository](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/blob/bd186987a72183c03a15806a1bc7a8c1307a9206/app/repository/embedding_repository.py), [Audio cosine](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/blob/bd186987a72183c03a15806a1bc7a8c1307a9206/app/matching/audio_search.py), [저장 안내](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/blob/bd186987a72183c03a15806a1bc7a8c1307a9206/docs/guides/EMBEDDING_STORAGE.md) | ADR 작성 당시 코드의 D4 해시 seed 단일 crop, D7 단일 벡터, D8 cosine 및 D9 동일 ID 충돌 근거. 당시 구현 상태의 immutable historical snapshot |
| R8 | [Linear 서버 협의 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3), [001 생성 버전 분리](https://linear.app/nsu-capstone/document/001-audio-revision과-생성-버전-분리-c5c95e36f3e2), [002 revision 보관](https://linear.app/nsu-capstone/document/002-revision별-벡터-보관과-active-전환-후-정리-e974a4620c8f), [NSUAI-25](https://linear.app/nsu-capstone/issue/NSUAI-25) | D9·Future Work: 생성 조건 변경 시 재생성, 운영 revision 보존과 개발 초기화 구분, 서버 협의 관리 위치 |
| R9 | [메인 Linear Requirements](https://linear.app/nsu-capstone/document/ssot-아티스트-행사-매칭-플랫폼-mvp-요구사항-e38bb23f87b1), [AI Linear Requirements](https://linear.app/nsu-capstone/document/ssot-ai-clap-기반-아티스트-추천-요구사항-5997d668913b), [메인 협업 가이드](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE/blob/23d3b5b804a91ce4730b6089b720d0cc28c1cd3b/docs/협업-가이드/README.md), [관련 ADR 0003](ADR-0003-embedding-and-scoring-policy.md), [관련 ADR 0006](ADR-0006-asynchronous-audio-processing.md) | D1·D2의 제품 기준: 메인 v1.11 AI-033(Audio 정책 한정 승인), AI-037/RIGHTS-023 기존 참조 유지, AI-EMBED의 기술 기준 참조. 2026-10-06 실제 저장 후 재조회 확인(메인 2026-10-06T12:47:20.537Z, AI 2026-10-06T12:47:50.286Z). 문서 전체 승인·구현 완료를 뜻하지 않음. 협업 가이드·ADR 0003/0006은 문서 책임·동기화·동기 처리 유지 근거 |
| R10 | [Microsoft HTSATWrapper](https://github.com/microsoft/CLAP/blob/e8a6467b87cd85716e20c6a008126150d9740be0/msclap/models/htsat.py), [내부 config](https://github.com/microsoft/CLAP/blob/e8a6467b87cd85716e20c6a008126150d9740be0/msclap/models/config.py) | Future Work: wrapper 설정과 HTSAT 내부 sample_rate 등이 다름. 실제 config 감사 대상이며 이번에 공식 소스를 변경하지 않음 |

공식 소스는 commit e8a6467에 고정했다. 프로젝트 requirements는 msclap==1.3.3,
모델 선택은 2023 CPU다. 이번 문서 작업은 설치 패키지·배포 wheel·checkpoint·실제 모델 실행을
재검증한 작업이 아니며 References의 코드 사실과 실행 환경 확인을 구분한다.
