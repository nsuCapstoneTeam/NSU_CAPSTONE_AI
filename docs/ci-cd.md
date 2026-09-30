# PR 테스트와 main → GHCR 게시

## 실행 흐름

| 이벤트 | 테스트 | Docker 빌드 | GHCR Push |
| --- | --- | --- | --- |
| feature/* 등 작업 브랜치 push | PR이 없다면 실행 없음 | 없음 | 없음 |
| main 대상 PR 생성·업데이트 | Python 3.11 문법 검사·분류 단위 테스트 | 없음 | 없음 |
| main 반영 | 동일 테스트를 다시 실행 | 테스트 성공 후 실행 | 빌드 성공 후 실행 |

열린 PR의 작업 브랜치에 push하면 PR 테스트가 다시 실행된다.
main 직접 push도 게시 workflow를 실행하므로, PR 경유를 강제하려면 별도의 브랜치 보호 설정이 필요하다.

## 현재 제한 사항

**현재 저장소에는 Dockerfile과 HTTP 서버가 없다. 이번 변경은 CI와 GHCR 게시 workflow를 준비한다.**
Docker 게시 job은 루트의 Dockerfile이 없으면 설명과 함께 실패한다.
따라서 이 PR 병합만으로 실행 가능한 AI 서버 이미지가 게시되지는 않는다.
HTTP 서버 프레임워크, 포트, 시작 명령 및 CPU/GPU 실행 방식은 Dockerfile 구현 시 확정해야 한다.

CI는 실제 PyTorch CPU tensor로 분류 순서·Top K·상대점수를 검사한다.
CLAP 모델은 test double로 대체한다. 가중치·샘플 음원을 다운로드하지 않으며,
실제 임베딩 추론, msclap 전체 의존성 설치, Docker 이미지 실행은 검증 범위 밖이다.
수동 스크립트 scripts/test_embedding.py는 pytest 수집 대상에 포함하지 않는다.

## 권한

| 대상 | 권한 |
| --- | --- |
| 개발 팀원 | Repository Write |
| PR CI 및 main 테스트 | contents: read |
| main 게시 job | contents: read, packages: write |

GITHUB_TOKEN은 Actions에서 자동 제공된다. PAT Secret은 필요하지 않다.
packages: write는 Docker 게시 job의 YAML에만 선언한다.
워크플로 실행 이벤트는 이미지 게시 시점을 제어하며, main 보호 자체를 제공하지는 않는다.

Repository → Settings → Actions → General → Workflow permissions에서는
**Read repository contents and packages permissions**를 기본으로 유지한다.
Organization이 Actions 또는 사용 Action을 제한한다면 허용 정책도 확인한다.

기존 ai-server 패키지가 다른 저장소/PAT로 만들어졌다면:
Organization → Packages → ai-server → Package settings → Manage Actions access에서
NSU_CAPSTONE_AI에 Write 접근을 허용한다. OCI source label만으로 기존 접근 권한이 자동 해결된다고 가정하지 않는다.

main 보호 설정은 Settings → Rules → Rulesets 또는 Settings → Branches에서 적용한다.
PR 필수, 1명 승인, Python unit tests 체크 통과, force push/삭제 금지를 설정한다.
실제 상태 체크 이름은 첫 CI 실행 결과에서 선택한다.
이번 PR은 웹 설정, 팀원 권한, CODEOWNERS 및 보호 규칙을 변경하지 않는다.

## 이미지와 캐시

- 이미지: ghcr.io/nsucapstoneteam/ai-server
- 태그: latest, sha-<전체 커밋 SHA>
- 플랫폼: linux/amd64
- OCI source label: https://github.com/nsuCapstoneTeam/NSU_CAPSTONE_AI
- pip 및 BuildKit 캐시를 사용하며, 오래된 PR 테스트는 취소한다.
- 게시 작업은 동시 실행을 제한하고 진행 중인 게시를 취소하지 않는다.
- 배포 시 특정 sha 태그 또는 digest를 기록하여 사용한다. latest는 갱신된다.

게시 이후 패키지 공개 범위는 별도로 확인한다.
이 workflow는 GHCR 게시까지이며, 운영 서버 배포·PostgreSQL 이미지는 포함하지 않는다.

## 로컬 테스트

```bash
python -m pip install 'torch>=2.1,<3' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ci.txt
python -m compileall -q app scripts tests
python -m pytest -q tests
```

## 공식 문서

- [GITHUB_TOKEN 권한](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)
- [GHCR 인증과 Repository 연결](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [패키지 Actions 접근 설정](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)
