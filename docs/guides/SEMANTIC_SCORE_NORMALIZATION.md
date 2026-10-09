# 음악 의미 유사도 점수 — 임시 기준 A

## 음악 파일 검색: 별도 임시 기준

음악↔음악은 `normalize_audio_similarity_score`를 사용하며 기본 하한 0,
상한 1입니다. 음수는 0점으로 제한하고, 양수 유사도는 100을 곱해 표시합니다.
아래의 0~0.4 기준은 음악↔텍스트에만 적용합니다.

새 validation 음악 24곡의 서로 다른 276쌍에서 215쌍이 유사도 0.4 이상이었습니다.
음악↔텍스트 기준을 그대로 쓰면 약 78%가 100점에 몰립니다.
상한 1은 특정 표본 최댓값을 완벽한 적합으로 취급하지 않기 위한 임시 표시 기준입니다.
새 표본의 최댓값 0.93937은 약 93.94점이 됩니다.
이 변경은 모델 판별력 개선이나 사람 평가 기반 보정이 아닙니다.
청취 평가 24개에서 비슷함 5개 평균 72.75점, 애매함 8개 63.22점,
다름 11개 49.60점이었습니다. 범위가 겹치므로 최종 기준은 추가 표본 검증이 필요합니다.

```python
from app.matching.normalization import normalize_audio_similarity_score

normalize_audio_similarity_score(0.4)  # 40.0
normalize_audio_similarity_score(0.94)  # 94.0
```

## 음악↔텍스트: 임시 기준 A

`app.matching.normalization.normalize_semantic_score`는 원본 코사인 유사도를
고정 구간 선형 변환으로 0~100점에 매핑합니다.

```python
from app.matching.normalization import normalize_semantic_score

normalize_semantic_score(0.2)  # 50.0
normalize_semantic_score(0.2, lower=0.1, upper=0.3)  # 기준 변경 가능
```

- 기본 하한: 0.0, 상한: 0.4
- 수식: `clamp(100 * (cosine - lower) / (upper - lower), 0, 100)`
- 입력은 MSCLAP의 temperature-scaled similarity가 아닌 **원본 코사인 유사도**입니다.
- 결과는 반올림하지 않은 실수입니다. 화면 표시 반올림은 이후 응답 계층에서 처리합니다.
- NaN·무한대·코사인 범위 밖 입력·잘못된 하한/상한은 `ValueError`로 거부합니다.
- 순위는 원본 유사도로 계산합니다. 제한된 점수로 정렬하면 동점이 생깁니다.

## 선택 근거와 한계

MSCLAP 2023, 수작업 영어 설명 16개 × FMA 음악 16곡의 256개 조합에서
관측 최댓값은 약 0.3983입니다. 0.4는 이를 반올림한 탐색용 상한입니다.
평가자는 1명이고, 순위 1·2·3·6·10·14의 96개를 평가했습니다.

| 후보 | 하한 | 상한 | 256개 중 0점 | 256개 중 100점 |
|---|---:|---:|---:|---:|
| A | 0 | 0.4 | 23 | 0 |
| B: 전체 분포 10·90 백분위 | 0.007048 | 0.284672 | 26 | 26 |
| C: 부적합 중앙값·적합 90 백분위 | 0.073408 | 0.349893 | 74 | 8 |

A는 세 후보 중 제한된 극단 점수에 몰리는 개수가 가장 적어 개발용으로 채택했습니다.
그러나 A에서도 사람이 적합으로 평가한 77개 중 2개는 0점입니다.
적합·부적합 유사도는 겹치므로 이 변환은 모델의 판별력을 개선하지 않습니다.

**0점은 부적합 판정, 100점은 완벽한 적합, 80점은 적합 확률 80%라는 뜻이 아닙니다.**
현재 의미 적합도는 모델 유사도를 표시하는 지표이며 최종 종합 매칭 점수가 아닙니다.
같은 test 자료로 기준을 탐색했으므로 이를 독립 검증 자료로 재사용할 수 없습니다.
최종 기준은 새 설명·새 음악과 별도 평가로 검증해야 합니다.
자동 한국어→영어 번역 경로는 아직 검증되지 않았습니다.

[Historical 변환 탐색](../experiments/audio-search-phase2/README.md#음악텍스트-기준-탐색)과
[음악 간 측정·평가](../experiments/audio-search-phase2/README.md)에 핵심 근거를 보존했습니다. 상세 산출물은 삭제했습니다.
음악 파일 검색 CLI의 음악↔음악 변환과 Audio 임베딩 저장·DB 검색 CLI는 구현되어 있습니다.
업무 HTTP API·Text 저장·번역·곡별 설명은 후속 작업입니다.
여기 수식과 FMA 분포는 기존 단일 crop 개발용 기준입니다. ADR-0007 새 검증은 다른 Dataset의
Phase A에서 준비한 별도 60초 적격 입력을 사용하며 [Roadmap](../AI_DEVELOPMENT_ROADMAP.md)과 [입력 안내](FMA_VALIDATION.md)를 따릅니다.
서버 점수·누락 정책은 [Accepted Linear 협의 009](https://linear.app/nsu-capstone/document/009-종합-적합도의-항목-구성-85e281c843cd)를 확인합니다.
임시 CLI 수식을 서버의 최종 변환 수식으로 승격하지 않습니다.
외부 수치 전달·결과 버전은 Linear 011의 Superseded 상태와 012 §4.3의 AI 동의 기록을 참조하며, 012 전체 Status=Proposed와 부분 동의를 구분합니다. 상세 확인 위치는 [AI 작업 기준의 상태와 출처](../api/CLAP_RECOMMENDATION_DIRECTION.md#상태와-출처)입니다.
현재 CLI 수식·실측 결과와 향후 인터페이스 구현·검증은 별도로 관리합니다.

## 향후 transformation 설계 원칙

[ADR-0008](../adr/ADR-0008-music-similarity-transformation-and-ranking.md)은 ADR-0005의 후속·확장으로 raw cosine ranking과 후보 독립 transformation·실험 기반 calibration·버전 추적 원칙을 기록합니다.
순위는 transformed 표시/전달 점수가 아니라 raw cosine에 의존합니다. 이는 논리적 관계이며 현재 모든 코드 경로가 문자 그대로 정렬 후 변환한다는 뜻은 아닙니다.
동일 transformation version과 같은 cosine 입력의 점수는 현재 요청 후보 집합에 따라 달라지지 않아야 합니다. 오프라인 calibration 표본의 분포·백분위 분석과 요청별 candidate-relative normalization은 구분합니다.
위 CLI 수식·예제·실측은 기존 provisional 기준으로 유지하며 최종 calibrated transformation·파라미터는 미확정입니다. ADR-0008을 작성했다고 calibration이나 변환 버전 체계가 구현된 것은 아닙니다.
