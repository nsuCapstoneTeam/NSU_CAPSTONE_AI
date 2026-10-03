# Phase 2 — FMA 실험 기록

실험일: 2026-10-02 KST. 관련 작업: NSUAI-1, NSUAI-2.
측정은 로컬 Docker에서 수행했고, 아래 공유 자료는 실제 결과에서 추출했다.
원음·가중치·개인 청취 평가 원문은 포함하지 않는다.

## 목적과 조건

MSCLAP 자체의 정상 동작, 장르·분위기 설명의 검색 결과, 한국어/영어 입력 차이를
확인해 후속 Text Embedding 구현 방향을 결정한다.

- 모델: Microsoft MSCLAP 2023, CPU, Audio/Text 1024차원.
- 체크포인트: microsoft/msclap, revision `c47d441165daa21986ead0850660917636a81775`.
- Python 3.11, msclap 1.3.3, torch/torchaudio 2.1.2+cpu, transformers 4.35.2.
- FMA small의 공식 test split, seed 42. crop/pad는 모델 기본값, 오디오 resample=True.
- 곡별 seed는 42 + track_id. 플랫폼·패키지가 달라지면 완전히 같은 값을 보장하지 않는다.
- ZIP의 공식 SHA-1 확인 후 8,000곡 추출.

## 수행한 실험

| 실험 | 성공 / 실패 곡 | 문장 | 유사도 수 | 입력 잘림 |
| --- | ---: | ---: | ---: | --- |
| 장르 진단 16곡 | 16 / 0 | 16 | 256 | 토큰 감사 기록 없음 |
| 장르 진단 80곡 | 80 / 0 | 16 | 1,280 | 토큰 감사 기록 없음 |
| 원문 분위기·행사 설명 | 16 / 0 | 32 | 512 | 한국어 16문장 |
| 한영 의미를 맞춘 짧은 설명 | 16 / 0 | 32 | 512 | 0문장, 최대 65토큰 |

원문 실행은 처음에 서로 다른 텍스트 토큰 길이로 stack 오류가 발생했다.
MSCLAP 1.3.3의 전처리는 max_length padding을 사용하지만 truncation을 명시하지 않아
긴 입력을 잘라 주지 않는다. 검증 스크립트는 tokenizer truncation을 명시하고 원래/유지
토큰 수와 실제 입력을 기록하도록 수정했다. 원문 측정의 0건 실패는 이 수정 후 실행 기준이다.

원문 10382번의 영어 설명은 한국어 포크 설명과 달리 힙합이었으므로 수정본에서 정정했다.
한국어·영어를 같은 의미의 짧은 설명으로 정리하고 원문·이전 결과는 로컬에 보존했다.

## 수정본 검색 결과

설명을 작성한 원곡을 target_track_id로 기록하고, 16곡 전체를 cosine 내림차순으로 정렬했다.

| 지표 | 한국어 | 영어 |
| --- | ---: | ---: |
| 원곡 1위 | 1/16 | 10/16 |
| 원곡 상위 3위 | 3/16 | 13/16 |
| 상위 후보에 등장한 서로 다른 곡 | 3 | 15 |

한국어 16개 설명 모두 84057, 111153, 145777 세 곡을 상위 후보로 선택했다.
각 설명의 전체 입력과 모델 출력은 `manifest16-descriptions.json`, `similarities.csv`,
`rankings.csv`로 확인한다. 원곡 1위 비율은 진단용 지표이며 음악 적합도의 정답률이 아니다.

## 사용자 청취 평가

점수·순위·장르·제목을 숨기고 상위 후보를 곡 ID 순서로 표시했다.
한 명의 사용자가 설명을 보면서 곡을 듣고 잘 맞음·애매함·안 맞음으로 평가했다.
미작성(null)은 평가 분모에서 제외했다.

| 항목 | 한국어 | 영어 |
| --- | ---: | ---: |
| 평가 완료 후보 | 3/48 | 48/48 |
| 잘 맞음 | 1 | 42 |
| 애매함 | 2 | 4 |
| 안 맞음 | 0 | 2 |
| 모델 1위 후보를 잘 맞음으로 평가 | 1/1 | 14/16 |

영어의 잘 맞음 비율은 42/48=87.5%이다. 전체 16개 영어 설명에서 상위 후보 중
잘 맞음인 곡이 하나 이상 있었다. 크리스마스 설명의 1위 곡 111153과 3위 곡 10382는
안 맞음으로 평가됐다. 실험 음악 설명의 1위는 애매함이었다.

한국어는 첫 설명만 평가했으므로 청취 평가 결과로 언어 간 직접 비교를 하지 않는다.
평가자는 설명을 작성한 사용자이기도 하며 독립적인 다수 평가자 검증이 아니다.

## 결정과 후속 검증

사용자 결정: **한국어로 요청을 받고 영어로 변환한 뒤 MSCLAP에 입력**한다.
[ADR 0004](../../adr/0004-korean-input-english-msclap.md)에 반영했다.

영어 설명은 사람이 작성·수정했다. 따라서 자동 번역 품질, 새로운 음악·요청에 대한
추천 성능, 서비스 전체 적합성 또는 최종 0–100 수식이 검증됐다고 볼 수 없다.
후속 작업은 번역 모델/API 선택, 의미·부정 조건 보존, 77토큰 제한 처리 및 실패 처리다.
정규화 조정에는 validation split을 사용하고 test 결과에 수식을 맞추지 않는다.

## 공유 파일과 재현

| 파일 | 내용 |
| --- | --- |
| manifest16-descriptions.json | 16곡 ID·라이선스·상대 음원 경로와 한영 32문장 |
| similarities.csv | 수정본의 실제 512개 cosine 및 MSCLAP 배율 적용 출력 |
| rankings.csv | 설명별 원곡 순위·상위 3곡 |
| summary.json | 실험별 집계, 패키지, 로컬 원본 SHA-256, 청취 평가 집계 |

프로젝트 루트에서 FMA 다운로드·추출을 먼저 수행한다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fma/download_fma.ps1
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.fma.validate_fma run --manifest docs/experiments/fma-phase2/manifest16-descriptions.json --output datasets/fma/results/listening-reproduced
```

report.json의 SHA-256은 해당 로컬 실행 원본을 식별한다. report에는 절대 경로 등이
포함되므로 재실행 시 파일 SHA-256이 같아야 한다는 의미는 아니다.
현재 스크립트는 similarities/distributions/report를 생성한다. 공유용 rankings는
similarities를 prompt_genre·language별로 묶고 cosine으로 내림차순 정렬해 원곡 순위와
상위 3곡을 추출했다. `same_genre`와 장르별 distributions는 사용자 설명 평가 지표로 쓰지 않는다.

80곡 장르 검증 재현은 [FMA 실행 가이드](../../FMA_VALIDATION.md)의 prepare에서
`--per-genre 10`을 사용한다. 다운로드한 데이터와 로컬 페이지·개인 평가는 datasets/에
보관되어 Git에서 제외된다.

## 업로드 전 확인

- 최신 main `bc5665b`를 반영해 CPU 의존성 고정과 Docker 검사 코드를 유지했다.
- 자동 테스트 13개 통과, Starlette TestClient deprecation warning 1건.
- 위 공유 상대경로 manifest로 16곡·32문장을 재측정해 512개 비교, 오류 0건·잘림 0건 확인.
- 재측정 similarities.csv의 SHA-256이 로컬 실행 원본과 정확히 일치했다:
  `e6a3f93d024c413714d8f2477e517f86afcb2cc5f93a2c5f3e9d9714a6925a84`.
- Git 공유 파일은 LF 줄바꿈으로 정규화했다. 따라서 위 원시 실행 파일과 바이트 해시는
  다를 수 있으며 공유 파일의 해시는 summary.json의 published_artifacts_sha256에 별도 기록했다.
- 실제 DB 연결·서버 endpoint와 전체 Docker 이미지 빌드는 이번 준비 단계에서 재검증하지 않았다.
