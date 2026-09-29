# Python Embedding Server — CLAP Audio Analysis Service

아티스트–행사 매칭 플랫폼의 Python AI·오디오 분석 저장소입니다.
CLAP 기반 Audio/Text Embedding 생성, 오디오 분석, 유사도 및 점수 계산을 다룹니다.

[NSU_CAPSTONE](https://github.com/nsuCapstoneTeam/NSU_CAPSTONE)의 협업 문서 구조를 바탕으로
Python 서버에 필요한 설정·PR 템플릿·기술 문서만 구성했습니다.
현재는 로컬 추론 코드 단계이며 HTTP 서버와 Spring Boot 연동은 구현 전입니다.

## 현재 코드

| 경로 | 역할 |
| --- | --- |
| `app/inference/clap_model.py` | Microsoft CLAP 2023 로딩, 오디오·텍스트 임베딩, 유사도 계산 |
| `app/classification/classifier.py` | 라벨 유사도 비교, softmax 상대점수, Top K 정렬 |
| `app/classification/labels.py` | 장르·분위기·사운드 등 분류 라벨 |
| `scripts/test_embedding.py` | 샘플 오디오의 장르 Top 3 수동 실행 스크립트 |

라벨 정의가 있다는 것과 해당 특징 추출 기능이 완성되었다는 것은 다릅니다.
현재 분류 상대점수는 행사 매칭용 0–100 정규화 점수와 구분합니다.
실제 모델 추론 검증은 샘플 음원과 모델 가중치가 필요합니다.

## 관련 Linear 작업

2026-09-29에 확인한 관련 작업입니다. 최신 범위와 Acceptance Criteria는 각 이슈를 확인합니다.
요구사항 원문은 [Linear Requirements](https://linear.app/nsu-capstone/document/ssot-아티스트-행사-매칭-플랫폼-mvp-요구사항-e38bb23f87b1)입니다.

| 이슈 | 이 저장소와의 관계 |
| --- | --- |
| [NSU-10](https://linear.app/nsu-capstone/issue/NSU-10), [NSU-45](https://linear.app/nsu-capstone/issue/NSU-45) | CLAP 의미 유사도, 입력 전처리, 0–100 점수 정규화 |
| [NSU-8](https://linear.app/nsu-capstone/issue/NSU-8), [NSU-42](https://linear.app/nsu-capstone/issue/NSU-42) | BPM·리듬 특징 추출 및 적합도 계산 — 구현 전 |
| [NSU-22](https://linear.app/nsu-capstone/issue/NSU-22), [NSU-47](https://linear.app/nsu-capstone/issue/NSU-47) | 분석 결과를 사용하는 공통 점수 계약·종합 점수 연계 |
| [NSU-60](https://linear.app/nsu-capstone/issue/NSU-60) | 임베딩 비동기 처리 방식 — 팀 결정 대기 |
| [NSU-61](https://linear.app/nsu-capstone/issue/NSU-61) | 2-서버 상위 책임 확정, 유사도 세부 위치·API 계약 결정 대기 |
| [NSU-62](https://linear.app/nsu-capstone/issue/NSU-62) | pgvector 채택·저장 책임 — 팀 결정 대기 |
| [NSU-63](https://linear.app/nsu-capstone/issue/NSU-63) | Spring Boot 연동 시 API 계약 협의; Java 구현은 메인 저장소 범위 |

현재 사용 기술은 Python 3.11, Microsoft CLAP(`msclap`), PyTorch입니다.
HTTP 프레임워크, 비동기 큐, pgvector는 이 구조 정리에서 도입하지 않습니다.
Frontend, 회원가입·프로필·게시판, Spring Boot DTO/Service는 이 저장소 범위에 포함하지 않습니다.

## Project Structure

```text
clap-audio-analysis-service/
├── .github/
│   └── PULL_REQUEST_TEMPLATE/
│       ├── 구현_PR.md
│       └── 문서_PR.md
├── app/
│   ├── __init__.py
│   ├── inference/
│   │   ├── __init__.py
│   │   └── clap_model.py
│   └── classification/
│       ├── classifier.py
│       └── labels.py
├── docs/
│   ├── api/README.md
│   ├── adr/README.md
│   └── 협업-가이드/README.md
├── scripts/
│   └── test_embedding.py
├── .editorconfig
├── .gitattributes
├── .gitignore
├── requirements.txt
└── README.md
```

## 협업 및 기술 문서

- [협업 가이드](docs/협업-가이드/README.md): GitHub Flow, Linear, PR 및 검증 규칙
- [API 문서](docs/api/README.md): Python–Spring Boot 책임 경계와 계약 정의 항목
- [ADR 안내](docs/adr/README.md): 비동기·계산 위치·저장소 결정 대기 목록

리뷰 담당자가 확정되지 않은 `CODEOWNERS`, 빈 서비스 모듈, 배포·CI 설정은 추가하지 않았습니다.
실제 구현과 운영 결정에 맞춰 필요한 파일을 추가합니다.

## 설치 및 실행

Python 3.11을 권장합니다. 프로젝트 루트에서 실행하세요.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.test_embedding
```

실행 전에 `samples/sample.wav`를 준비하세요. 첫 모델 실행 시 가중치가 자동으로 다운로드됩니다.
기존 가상환경의 Python 경로가 없다는 오류가 나면 Python 3.11을 설치하거나 복구한 뒤 가상환경을 다시 생성해야 합니다.

현재 코드는 Microsoft의 `msclap`을 사용합니다. `requirements.txt`는 전체 환경의
설치 목록 대신 프로젝트의 직접 의존성을 선언하며, 하위 의존성은 pip가 설치합니다.
전체 버전을 고정한 lock 파일은 아닙니다.

현재 실행 스크립트는 모델을 직접 로드하는 수동 확인용이며 자동 단위 테스트가 아닙니다.
이 문서의 실행 안내는 기존 코드 기준이고, 이번 저장소 구조 정리가 추론 성공을 보증하지는 않습니다.
