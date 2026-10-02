# 음악 파일 검색 및 임시 점수 검증

2026-10-02 KST, MSCLAP 2023 CPU 실험입니다. 이 폴더에는 음원·가중치·벡터가
아닌 공유용 후보 목록, 측정값, 청취 평가, 집계를 보관합니다.

## 음악↔텍스트 기준 탐색

이전 실험의 수작업 영어 설명 16개 × 음악 16곡, 256개 조합을 사용했습니다.
순위 1·2·3·6·10·14의 96개를 한 명이 평가했으며 적합 77, 애매함 7, 부적합 12개입니다.
평균 코사인은 각각 0.21094, 0.22874, 0.08721입니다. 애매함 평균이 적합보다 높고
범위가 겹치므로 유사도만으로 적합 여부를 판정하지 않습니다.

| 후보 | 하한 / 상한 | 전체 0점 / 100점 |
|---|---|---|
| A | 0 / 0.4 | 23 / 0 |
| B | 전체 분포 10·90 백분위: 0.007048 / 0.284672 | 26 / 26 |
| C | 부적합 중앙값·적합 90 백분위: 0.073408 / 0.349893 | 74 / 8 |

A는 점수 제한이 상대적으로 적어 임시 표시 기준으로 선택했습니다.
하한 0과 상한 0.4가 실제 부적합·완벽한 적합의 경계라는 뜻은 아닙니다.
기존 test 자료를 기준 탐색에 사용했으므로 독립 검증으로 보고하지 않습니다.
세 후보의 상세 통계·입력 해시는 [비교 자료](text-normalization-comparison.json)에 있습니다.

## 새 음악 표본 및 쌍별 측정

FMA small의 공식 validation split에서 seed 43으로 장르별 3곡, 총 24곡을
선정했습니다. 기존 80곡과 중복은 없습니다. 같은 곡 비교를 제외한 276쌍을 측정했습니다.
임베딩 shape는 `(24, 1024)`이고 추론 seed는 `43 + track_id`입니다.

| 항목 | 결과 |
|---|---:|
| 최소 / 중앙 / 최대 코사인 | 0.04977 / 0.53068 / 0.93937 |
| 같은 장르 평균 | 0.65164 (24쌍) |
| 다른 장르 평균 | 0.50350 (252쌍) |
| 0.4 이상 | 215/276, 약 77.9% |

음악↔텍스트의 상한 0.4를 음악↔음악에 적용하면 대부분 100점이 됩니다.
음악↔음악은 별도 함수로 하한 0·상한 1을 사용하도록 분리했습니다.
이 기준에서 점수 범위는 약 4.98~93.94입니다. 판별력을 개선한 것이 아니라
표시 점수의 포화를 줄인 것입니다.

## 청취 평가

장르별 첫 기준 음악 8곡에 대해 각 23개 후보의 순위 1·11·21을 선택했습니다.
평가 화면은 점수·순위·제목·장르를 숨기고 후보 ID 오름차순으로 표시했습니다.
분위기·리듬·소리 질감의 핵심 특징이 비슷한지 평가했고, 한 명이 24개 모두 완료했습니다.

| 평가 | 개수 | 상한 1 기준 평균 점수 |
|---|---:|---:|
| 비슷함 | 5 | 72.75 |
| 애매함 | 8 | 63.22 |
| 다름 | 11 | 49.60 |

1위 후보는 비슷함 3, 애매함 4, 다름 1개입니다.
상대적인 평균 차이는 있지만 범위가 겹치며, 적합 확률이나 최종 서비스 품질을
보장하지 않습니다. 24개 평가는 같은 음악이 반복되는 소규모 표본입니다.
추가 기준 조정에 이 평가를 사용하면 별도 표본으로 다시 검증해야 합니다.

## 검색 실행 검증

`scripts.search_audio`는 SHA-256 기반 seed로 crop을 고정하고 매번 후보 임베딩을
생성합니다. 입력과 같은 바이트의 파일은 제외하며 원본 코사인 내림차순으로 정렬합니다.
점수가 같으면 정수 track ID 오름차순으로 순위를 안정화합니다.

- 공개 FMA 곡 `015770` 입력: 동일 곡 제외 후 23곡 비교, TOP 5 JSON 반환 성공.
- 사용자 `reference.mp3` 입력: 24곡 비교, TOP 5 JSON 반환 성공.
- 사용자 검색 1위 `136276`의 코사인 0.642706, 표시 점수 64.27.
  사용자는 다소 비슷하지만 애매하다고 판단했습니다. 정식 평가 표본에는 합산하지 않았습니다.
- 검색은 SHA-256 seed, 쌍별 실험은 곡 ID seed를 사용하므로 crop과 결과가 다를 수 있습니다.
  쌍별 실험의 청취 평가를 검색 CLI 자체의 정확도 평가로 취급하지 않습니다.

## 재현 방법

FMA 데이터 다운로드, Docker 및 `.env` 준비는 [기본 검증 안내](../../FMA_VALIDATION.md)를
따릅니다. 모델 추론은 DB 연결을 사용하지 않지만 Compose는 `DB_PASSWORD` 설정이 필요합니다.
프로젝트 루트에서 실행하고 기존 결과를 덮어쓰지 않는 새 output 이름을 사용합니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.validate_audio_similarity --manifest docs/experiments/audio-search-phase2/manifest24.json --output datasets/fma/results/audio-audio-reproduction --seed 43

docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.search_audio --audio datasets/fma/fma_small/015/015770.mp3 --manifest docs/experiments/audio-search-phase2/manifest24.json --output datasets/fma/results/search-public-example.json
```

전체 재측정 CSV는 현재 음악 간 점수 열을 추가하므로 이전 원본과 바이트 단위로
같지 않습니다. `track_id_a`, `track_id_b`, `cosine_similarity`를 대조합니다.
업로드 준비 시 공유 manifest와 새 측정 CLI로 다시 실행하여 276개 원본 코사인 값이
모두 정확히 일치하는 것을 확인했습니다. 전체 자동 테스트는 46개 통과했고,
Starlette TestClient deprecation 경고가 1개 있었습니다.
checkpoint는 `c47d441165daa21986ead0850660917636a81775`, msclap 1.3.3,
torch·torchaudio 2.1.2+cpu, transformers 4.35.2 기준입니다.

## 공유 파일

- [manifest24.json](manifest24.json): 이식 가능한 음원 경로·곡 ID·제목·라이선스
- [similarities.csv](similarities.csv): 실제 276쌍 원본 측정값, 상한 0.4 적용 진단 열 포함
- [measurement-report.json](measurement-report.json): 패키지·음원 해시·분포
- [listening-evaluation.json](listening-evaluation.json): 청취 평가 24개·집계, 자유 메모 제외
- [search-example.json](search-example.json): 사용자 검색 결과 예시, 입력 음원·경로 제외
- [provenance.json](provenance.json): 원본 및 공유 파일 해시; 공유 JSON·CSV는 LF 사용

원본 음원·ZIP·모델·벡터 캐시·개인 입력 음원·HTML 평가 페이지는 Git에 포함하지 않습니다.
장르 일치는 진단용이고 검색 계산에 사용하지 않습니다. BPM·리듬 특징은 별도 추출하지
않았으며 행사 적합도·아티스트별 TOP 5·종합 점수·LLM 설명 검증도 후속 작업입니다.
