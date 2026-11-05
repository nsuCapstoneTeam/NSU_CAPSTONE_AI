# Git fixture와 source identity 후속 검증

## 범위와 기준

2026-11-05, Docker 1차 구현 `b8f0e8c`·검증 기록 `106e7a9` 이후 기존 실패 13개만 해결했다. 기존 [1차 검증 기록](DOCKER_DEV_RUNTIME_VALIDATION.md)은 당시 결과로 그대로 보존한다.

- 기준 HEAD: `106e7a9536f85a2be5bcb7d7021d90375badb23d`.
- 독립 Worker worktree/branch: `feat/docker-dev-runtime-cleanup`.
- Docker Desktop Linux Engine, CPython 3.11.18 / Linux x86-64.
- 기존 CPU package·Dockerfile·Compose·requirements·Audio 알고리즘·expected hash·generation/profile/version·기존 experiments/ADR는 변경하지 않았다.

## 실패 재현과 수정

수정 전 정상 Git clone에서 다음 targeted 검사를 실행해 **13 failed, 51 passed (6.33초)**를 재현했다.

```text
python -m pytest tests/embedding/test_audio_embedding_postgres_validation.py tests/embedding/test_text_embedding.py::test_installed_msclap_source_identity_matches_calibration -q -p no:cacheprovider --tb=short
```

### Git fixture 12개

기존 테스트는 production validation CLI의 ROOT를 Git repository 밖의 tmp_path로 바꿨다. CLI가 보고서 provenance용 `git rev-parse HEAD`를 먼저 호출해 exit 128이 발생했다.

해당 CLI 테스트에만 실제 임시 Git repository를 제공한다. fixture는 SHA-1 repository를 init하고 로컬 user/signing/empty hooks 설정, 작은 tracked file의 실제 initial commit을 만든다. 보고서의 repository_commit이 해당 실제 HEAD와 같은지 검증한다. invoking shell의 GIT_DIR/GIT_WORK_TREE 등 repository redirect 환경은 fixture에서 제거한다.

production CLI는 수정하지 않았다. non-Git ROOT에서는 여전히 예외가 나고 validation·보고서 생성으로 진행하지 않는 negative regression도 추가했다. 가짜 SHA, unknown fallback, 예외 무시, skip/xfail은 사용하지 않는다.

### Source identity 1개

기존 Path 정렬은 host flavor에 따라 달랐다. `app/embedding/source_identity.py`를 verifier와 calibration producer가 공유한다.

1. 기존 rglob/is_file 및 .py/.yml/.yaml 범위를 유지한다.
2. root-relative 경로의 component tuple을 casefold해서 비교하고 원문 component tuple로 동률을 구분한다. locale·host Path 비교 규칙을 사용하지 않는다.
3. digest에는 원문 case를 보존한 상대 POSIX 경로(UTF-8), NUL, 원본 file SHA-256의 binary digest, LF를 넣는다.
4. file bytes·CRLF/LF를 정규화하지 않는다. absolute path·drive·상위 traversal을 identity에 넣지 않는다.

component 비교는 `a/file.py`와 `a.py`를 단일 문자열 lexical 정렬하는 것과 다르며, 기록된 Windows component 순서를 보존한다. PureWindowsPath/PurePosixPath·모든 입력 순열·명시적 golden digest·casefold tie-break·case/newline 민감성·host path 거부를 순수 unit으로 검증했다. 기존 파일-symlink의 is_file 동작과 Python 3.11 rglob의 symlink-directory traversal 범위는 그대로다.

| 실제 installed MSCLAP 1.3.3 | 수정 후 결과 |
| --- | --- |
| Source/config 파일 수 | 13 |
| Source aggregate | `e867cdbb71f7bcee529afb92a096578faab46c69feb35d8192d4f220de56c181` |
| Config SHA-256 | `41fbc893997f75fe144d93bf2ec44d5ca27fe61beb8870dd815a53c064cb030f` |
| Calibration producer ↔ runtime verifier | 동일 |

기존 expected aggregate를 그대로 재현하므로 저장된 Text/Audio profile identity와 기존 evidence hash를 바꿀 필요가 없다. package·expected constants·checkpoint·기존 evidence를 수정하지 않았다. 이는 source identity portability 수정이며 Embedding 생성/검색 정책 변경이 아니다.

## 검증 결과

Main이 정상 임시 clone HEAD106e7a9에 최종 변경 6개 파일만 복사해 전체 회귀를 독립 실행했다. 해당 source/test snapshot은 최종 구현과 일치한다.

| 검사 | 결과 |
| --- | --- |
| Main targeted regression: validation module + pure identity + installed verifier + producer parity | 79 passed, 6.26초 |
| Main 전체 pytest: embedding/matching/database/config/전체 기존 범위 | **717 passed, 0 failed, 25 skipped**, Starlette deprecation warning 1개, 137.20초 |
| 실제 Compose CLI base/dev 병합·DB_HOST 필수 | Main 독립 PASS |
| `docker build --target runtime --tag nsu-capstone-ai:identity-runtime-check .` | Worker PASS |
| `docker build --target dev --tag nsu-capstone-ai:identity-dev-check .` | Worker PASS |
| 두 이미지 `python -m pip check` | Worker PASS |
| CPU torch/torchaudio/torchvision/MSCLAP·FastAPI·DB CLI imports | Worker PASS |
| runtime 실제 installed source verifier | 기존 aggregate/config/file-count 일치, Worker PASS |
| runtime dev package/scripts 경계 | pytest/httpx/jsonschema/imageio-ffmpeg 없음, 최소 DB CLI만 존재, Worker PASS |
| runtime Uvicorn startup + `/health/live` | HTTP 200, Worker PASS |
| dev producer/verifier identity parity | Worker PASS |
| `git diff --check` | PASS |

25 skipped는 기존 명시적 DB/Hugging Face integration opt-in 22개와 Docker CLI 없는 dev 환경의 Compose CLI 검사 3개다. 기존 실패 13개를 skip으로 바꾸지 않았다. Compose의 실제 CLI 동작은 별도로 검증했다.

## 이미지와 한계

| 로컬 검증 tag | Image ID |
| --- | --- |
| `nsu-capstone-ai:identity-runtime-check` | `sha256:f47d4bd4e435e8681746b037c24b7978b0ee76a321ea75d32f816099cc03cb13` |
| `nsu-capstone-ai:identity-dev-check` | `sha256:4fd93056118b2ab8a17c93bd65e49a2693752f894cbdbca0eedf2f76fa80cc8c` |

이 결과 기록·링크만 build 이후 추가했다. 실행 코드·테스트·dependency는 검증 snapshot과 동일하다.

- Windows host Python이 없어 Windows 네이티브 전체 실행은 못했다. PureWindowsPath/PurePosixPath 논리 경로 계약은 Linux에서 모두 검증했으며 Windows 실제 파일시스템 실행과 구분한다.
- 실제 DB integration·migration 실행·모델 가중치 다운로드/inference·Spring E2E·원격 GitHub Actions·GHCR push는 미실행이다.
- 전체 unit regression과 source verifier가 통과했지만 실제 모델 inference/추천 품질 완료로 표현하지 않는다. 기존 provenance/hash 정책은 유지한다.
- Git metadata 없는 standalone dev image에서는 checkout을 요구하는 다른 validation CLI에 실행 환경 제약이 남는다. CI는 실제 checkout metadata를 읽기 전용 제공하며 전역 GIT_DIR/GIT_WORK_TREE로 우회하지 않는다.
- dependency lock·model preparation·startup preload·model readiness·production hardening은 별도 후속 작업이다.
- 기존 container/image/tag/volume·cache·evidence는 삭제하지 않았다. 새 검증 컨테이너만 `--rm`으로 정리했다. push·PR·merge·Main 수정은 하지 않았다.
