# Phase 2 — FMA를 이용한 MSCLAP 단독 검증

관련 작업: [NSUAI-1](https://linear.app/nsu-capstone/issue/NSUAI-1),
[NSUAI-2](https://linear.app/nsu-capstone/issue/NSUAI-2).

참조 확인 (2026-10-02 KST): Linear NSUAI-1은 Todo, NSUAI-2는 Done이지만
두 이슈 본문에는 실제 similarity 측정 및 최종 정규화 기준 검증 요구가 남아 있다.
[GitHub #1](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/issues/1),
[GitHub #2](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI/issues/2)도 같은 요구를 명시한다.
[Notion Git & GitHub 실무 기초 정리](https://app.notion.com/p/3e6c1535250f801fbefcfdc775d3d5b4)는
CLAP Audio/Text Embedding 및 similarity와 대용량 음원·모델의 Git 제외 안내를 제공한다.
연결된 Notion에서 검색한 범위에는 Phase 2 전용 계획이 없으므로 검증 범위는 Linear와
저장소 로드맵을 기준으로 한다.

## 데이터 준비

현재 로컬 자료는 다음처럼 정리되어 있다. `datasets/fma/index.html`은 청취 페이지와
검증 결과를 연결하는 시작 페이지다. ZIP은 `archives/`, 입력 JSON은 `manifests/`,
측정 결과는 `results/`, 사람이 작성한 평가 JSON은 `evaluations/`에 보관한다.
음원·메타데이터·모델 캐시 경로는 그대로 유지한다.

최신 설명 검증 입력은 `datasets/fma/manifests/manifest-listening-aligned-docker.json`,
결과는 `datasets/fma/results/listening-aligned/`이며 청취 평가는
`datasets/fma/listening/evaluate-top3.html`에서 수행한다.

[FMA 공식 저장소](https://github.com/mdeff/fma)의 `fma_small.zip`과
`fma_metadata.zip`을 다운로드하고 공식 README의 SHA-1과 비교한 뒤 압축을 푼다.
`fma_small`은 8개 장르의 30초 MP3 8,000개이며 약 7.2 GiB이다.
Git clone만으로 음원을 받을 수는 없다. 오래된 FMA 프로젝트의 Python 환경은 설치하지 않아도 된다.

```text
datasets/fma/
  fma_metadata/tracks.csv
  fma_small/000/000002.mp3
  ...
```

메타데이터·음원·모델 가중치는 Git에 포함하지 않는다. 곡별 라이선스는 manifest에 기록된다.
음원 재배포·서비스 사용 전 해당 라이선스를 확인한다.

## 샘플 선정 (모델 설치 없이 실행 가능)

Windows에서 다운로드 재개, 공식 SHA-1 검사, 압축 해제를 한 번에 실행하려면:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_fma.ps1
```

ZIP 파일을 이미 다운로드했다면 `-ExtractOnly`를 추가한다. 메타데이터 ZIP은
bzip2 방식이므로 `Expand-Archive` 대신 Windows `tar.exe`를 사용한다.
다운로드 스크립트는 ZIP을 `datasets/fma/archives/`에 보관한다.

Docker Desktop 사용 시 프로젝트 루트에서 다음 순서로 실행한다. 기존 서비스와
같은 이미지에 datasets 볼륨을 추가하며, manifest 경로는 컨테이너 기준으로 생성한다.
Hugging Face 모델 캐시도 `datasets/fma/huggingface`에 보존된다.
공유 실험 입력을 사용하도록 `docs/`도 컨테이너에 읽기 전용으로 연결한다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.validate_fma prepare --metadata datasets/fma/fma_metadata/tracks.csv --audio-root datasets/fma/fma_small --per-genre 2 --seed 42 --manifest datasets/fma/manifests/manifest16-docker.json
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.validate_fma run --manifest datasets/fma/manifests/manifest16-docker.json --output datasets/fma/results/genre16
```

16곡 측정 결과를 검토한 뒤 `--per-genre 10`과 새로운 manifest/output 경로로
80곡 측정을 진행한다. 0~100 정규화 기준을 조정할 때는 `--split validation`으로
별도 표본을 만들고, 최종 평가용 test 결과에 맞추어 기준을 조정하지 않는다.

프로젝트 루트에서 Python으로 실행한다.

```powershell
python -m scripts.validate_fma prepare --metadata datasets/fma/fma_metadata/tracks.csv --audio-root datasets/fma/fma_small --per-genre 2 --seed 42 --manifest datasets/fma/manifest16.json
```

기본값은 공식 test split에서 장르별 2곡(총 16곡)이다. 동일 seed와 파일 집합이면
같은 곡을 선택한다. 각 장르에 충분한 로컬 음원이 없으면 오류로 종료한다.
`--per-genre 10`과 새 manifest 경로로 80곡까지 확대할 수 있다.
manifest에는 곡 ID, 장르, 제목, 라이선스, 절대 경로, 한국어·영어 장르 문장이 들어간다.
컴퓨터나 컨테이너를 바꾸면 그 환경에서 manifest를 다시 생성한다.

## 실제 모델 측정

Python 3.11의 MSCLAP 실행 환경에서 저장소 requirements를 설치한다.
CPU 패키지 호환성은 기존 모델 로딩 환경에 맞추며, 첫 로딩은 모델 다운로드가 필요할 수 있다.

```powershell
python -m scripts.validate_fma run --manifest datasets/fma/manifest16.json --output datasets/fma/results16
```

Docker 사용 시 기존 ai 컨테이너에 `datasets`를 별도로 연결해야 한다. 예를 들어
개발용 Compose override에 `./datasets:/workspace/datasets` 볼륨을 추가하고,
컨테이너 안에서 위 두 명령을 실행한다. 기존 compose 설정은 자동 변경하지 않는다.

출력 폴더는 새 경로여야 한다. 같은 결과를 덮어쓰지 않는다.

| 결과 | 내용 |
| --- | --- |
| similarities.csv | 각 곡 × 16개 문장의 순수 cosine similarity, MSCLAP 배율 적용 출력 |
| distributions.csv | 장르·언어·동일 장르 여부별 count/min/max/mean/stdev |
| report.json | 모델 버전·체크포인트 경로·패키지 버전·seed·입력 문장·파일 SHA-256·벡터 shape/norm·실패 내역 |

NaN/Inf, 영벡터, Audio/Text 차원 불일치를 검사한다. 손상 음원은 실패 내역에
남기고 나머지 곡을 측정하며, 실패가 있으면 종료 코드는 1이다.
텍스트 생성/모델 로딩 실패는 즉시 중단한다. 모델의 기본 crop/pad와 resampling을
사용하며 곡별 seed를 기록한다. 플랫폼·패키지 버전이 달라지면 완전히 같은 결과를 보장하지 않는다.

긴 문장은 MSCLAP의 `text_len`에 맞추어 명시적으로 토큰을 잘라 처리한다.
MSCLAP 1.3.3의 기본 전처리는 padding만 적용하여 긴 문장과 짧은 문장을 함께 넣으면
길이 불일치 오류가 발생할 수 있다. 검증 스크립트는 원래 문장을 manifest에 보존하고,
`report.json`의 `text_preprocessing`에 제한 길이, 문장별 원래/유지 토큰 수,
잘림 여부와 실제 입력 내용을 기록한다. 문장이 잘렸다면 전체 문장에 대한 검증으로
해석하지 않는다. 특히 한·영 비교는 같은 의미와 입력 길이를 확인한 뒤 진행한다.

## 결과 해석과 완료 범위

사용자 결정으로 MVP의 음악 요청은 한국어로 받되 영어로 변환한 뒤 MSCLAP에
입력한다. 근거·처리 조건·남은 번역 방식 결정은
[ADR 0004](adr/0004-korean-input-english-msclap.md)에 기록했다.
현재 영어 설명 비교는 자동 번역 경로를 검증한 결과가 아니므로 번역 연결 후
원문 의미와 추천 결과를 다시 확인한다.

MSCLAP `compute_similarity`는 학습된 배율을 곱하므로 순수 cosine과 구분한다.
[Microsoft 구현](https://github.com/microsoft/CLAP/blob/main/msclap/CLAPWrapper.py)을 기준으로
벡터를 정규화한 내적으로 cosine을 별도 계산한다. softmax나 0~100 변환은 하지 않는다.

동일 장르 문장의 값이 다른 장르보다 높은지, 한국어/영어 분포가 어떻게 다른지 확인한다.
다른 장르도 의미가 겹칠 수 있으므로 '다른 장르'를 '무관함'의 정답으로 간주하지 않는다.
장르 라벨은 행사 분위기 적합도의 정답이 아니다. 다음에는 실제 청취로 선정한 곡에
분위기·행사 설명 문장을 추가하고 사람이 기대한 순서와 비교해야 한다.

이 도구는 측정 수단을 구현한 것이다. 실제 FMA 추론 결과가 생성되고 검토되기 전에는
Phase 2 완료, 최종 모델 적합성, 실제 embedding dimension 또는 정규화 공식 확정으로 간주하지 않는다.

## 데이터 없이 확인

```powershell
python -m unittest tests.test_fma_validation -v
python -m scripts.validate_fma --help
```
