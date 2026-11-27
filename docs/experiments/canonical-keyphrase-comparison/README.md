# NSUAI-54 · MSCLAP 검색 표현 민감도

공통 후보군 32곡에서 5개 문맥의 영어 표현을 바꿔 검색 민감도를 측정했다. 같은 `grand → majestic` 교체로 단일 조건에서는 상위 10곡 중 4곡이 바뀌었고, 클래식·연주·콘서트 조건을 함께 둔 문장에서는 10곡 모두 유지됐다. 사람 평가는 생략했으며 독립 relevance label이 없어 검색 정확도와 추천 품질 우열은 **UNVERIFIED**다. Recall@10과 nDCG@10은 미측정이다.

## 입력과 측정 방법

동결한 `canonical-keyphrase-pool-v2`의 기존 복구곡 30곡과 보강곡 2곡에 대해 저장된 1024차원 오디오 벡터를 재사용했다. MSCLAP 2023 CPU 환경에서 12개 고유 질의의 텍스트 벡터를 생성해 raw cosine 384건을 얻었다. 각 문맥 안의 표현 비교는 총 9쌍이다. 정확한 문장, 패키지 버전, 체크포인트, 전처리 및 생성 프로필, 입력 파일과 원본 결과의 SHA-256을 기록했다. [재현성 정보](reproducibility.json)

순위는 반올림 전 float64 raw cosine 내림차순이다. 동점은 동결 후보 순서로 처리하도록 사전 지정했고 실제 동점은 없었다. Top10 중복률은 교집합 크기 / 10, Jaccard는 교집합 크기 / 합집합 크기다. 평균 절대 순위 변화와 두 상관계수는 32곡 전체를 사용한다. 마지막 열은 두 질의의 텍스트 벡터 사이 cosine이다. [원정밀도 수치와 진입·이탈 ID](comparison-metrics.csv)

| 문맥 | 표현 비교 | Top10 중복률 | Jaccard | 평균 절대 순위 변화 | Spearman | Kendall τ-b | 텍스트 cosine |
|---|---|---:|---:|---:|---:|---:|---:|
| G01 단일 | grand / epic | 70% | 0.538 | 5.25 | 0.710 | 0.536 | 0.806 |
| G01 단일 | grand / majestic | 60% | 0.429 | 5.00 | 0.749 | 0.560 | 0.850 |
| G01 단일 | epic / majestic | 70% | 0.538 | 6.25 | 0.610 | 0.427 | 0.751 |
| G02 복합 | grand / epic | 80% | 0.667 | 3.06 | 0.908 | 0.750 | 0.868 |
| G02 복합 | grand / majestic | 100% | 1.000 | 2.38 | 0.938 | 0.819 | 0.936 |
| G02 복합 | epic / majestic | 80% | 0.667 | 3.69 | 0.872 | 0.698 | 0.851 |
| V01 장소 | cafe / venue | 80% | 0.667 | 4.50 | 0.753 | 0.593 | 0.909 |
| J01 장르 | jazz 포함 / 생략 | 90% | 0.818 | 3.06 | 0.911 | 0.742 | 0.946 |
| O01 어순 | Mood 먼저 / Tempo 먼저 | 100% | 1.000 | 1.69 | 0.966 | 0.871 | 0.968 |

분포와 개별 곡의 변화를 함께 볼 수 있다. [질의별 raw cosine 분포](graphs/cosine-distribution.svg) · [Top10 중복률](graphs/top10-overlap.svg) · [전체 순위 상관](graphs/rank-spearman.svg) · [곡별 순위 변화](graphs/rank-changes.svg) · [텍스트 벡터 유사도](graphs/text-cosine.svg)

## Spring 인계 · NSU-159

**기존 mapping v1 및 `VERIFIED_MAPPING_VERSION = 0` 유지를 권고한다.** 관측은 이 후보군과 문맥에 한정된다. 한 요인만 바뀌었는지 확인한 문자열 검사 12/12는 PASS다. 기준 Spring 커밋에서 필요한 JDK 25 toolchain을 확보하지 못해 Spring runtime validation은 **BLOCKED**다. 실제 요청 validation과 `Keyphrase.of()` 출력 대조는 미완료이며, mapping v1 전체 품질도 미검증이다.

- **Grand** — 세 표현 쌍 모두 복합 조건에서 순위 이동이 줄었다. 어떤 표현이 ‘웅장한’ 음악을 더 잘 찾는지는 미확인이다. 현행 `grand` 유지를 권고한다.
- **SMALL_VENUE** — `cafe → venue`로 상위 2곡이 교체됐다. 제품 선택값은 카페와 일반 소규모 공연장을 포괄하므로 `for a small venue performance`를 **의미 범위 기준**으로 검토할 수 있다. 검색 품질 개선 근거는 없다.
- **장르** — 재즈 생략 시 Top10 평균 cosine은 0.27361에서 0.30285로 올랐다. 재즈 적합성은 미측정이므로 사용자 선택 장르를 포함하는 현행 방식을 권고한다.
- **어순** — Top10 구성은 같았고 순위와 점수는 달라졌다. 기존 Mood → Tempo 순서를 바꿀 필요성은 입증되지 않았다.

## 보류한 표현 비교

| 항목 | HOLD 사유 | 재개 조건 |
|---|---|---|
| Tempo 표현 | 독립 reference 후보가 SLOW 0곡, MEDIUM 3곡, FAST 0곡, UNSURE 27곡 | 세 속도별 비교가 가능한 독립 reference와 표본 확보 |
| Korean trot / trot | 적격 트로트 녹음물의 이용조건 및 AI-Hub 고정 모델 평가 용도 미확인 | 장르와 평가 용도 권리가 확인된 녹음물 확보 |
| R&B / R&B and soul | Positive 후보 3곡의 공식 취득이 HTTP 403으로 실패했고 보강한 2곡은 인접 장르 | R&B와 Soul을 포괄하는 묶음 장르의 대표 positive 표본 확보 |

이 세 표현 비교의 검색 성능은 미측정이다. O01은 동일 Tempo 토큰의 위치만 바꾼 어순 실험이다.
