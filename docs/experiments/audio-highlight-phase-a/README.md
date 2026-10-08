# ADR-0007 Phase A Audio Dataset

이번 Dataset은 실제 음악 검증의 입력을 준비하는 로컬 실험 fixture다. 원곡에서 Highlight를 추출하는 기능을 production application에 추가하지 않는다. 서비스는 Artist가 이미 60~80초 Highlight를 제공한다는 전제를 유지한다.

고정 정의는 [manifest.json](manifest.json), 권리 확인 근거는 [ATTRIBUTION.md](ATTRIBUTION.md), 실제 실행 결과는 [inspection-report.md](inspection-report.md)에 기록한다. manifest의 경로는 repository root 기준이다. `track_id`는 fixture 내부 식별자이며 Backend music ID가 아니다.

## 처리 방식

원본 SHA-256 검사 → 명시적 soundfile backend로 전체 decode → decoded frame/rate/channel 대조 → 시작 포함·끝 제외의 정확한 60초 slicing → 원본 rate와 stereo를 보존한 WAV/PCM_F/float32 저장 → 재decode → 형식·finite·frame/rate/channel·원본 구간 PCM 동일성 검사 순서로 처리한다.

MP3 정보 조회 frame 수와 실제 decoded frame 수가 달라 길이는 실제 decode 결과로 판단한다. 반복 검증은 원본을 별도로 다시 전체 decode하고 메모리에서 WAV를 재생성하여 PCM과 SHA-256을 비교한다. 기존 Highlight를 수정하지 않는다.

libsndfile FLOAT WAV writer의 PEAK chunk에는 생성 시각이 들어가 파일 해시가 달라지는 것을 synthetic 테스트에서 확인했다. 저장은 표준 little-endian IEEE float32 RIFF/WAV의 `fmt`, `fact`, `data` chunk만 명시적으로 기록한다. PCM을 변경하거나 추가 압축하지 않으며 생성 시각·경로를 오디오 header에 넣지 않는다. 생성물은 실제 torchaudio와 soundfile로 다시 읽어 검증한다.

## 실행

프로젝트 루트에서 실행한다. 이번 Windows 검증은 아래 기존 가상환경을 사용했다. 환경별 Python 실행 경로는 달라질 수 있다. 새 dependency를 설치하거나 requirements를 변경하지 않았다.

```powershell
& ./tmp/review-venv/Scripts/python.exe -B -m scripts.datasets.validate_audio_highlights --manifest docs/experiments/audio-highlight-phase-a/manifest.json --check source --report datasets/audio-highlight-validation/results/source-validation.json
& ./tmp/review-venv/Scripts/python.exe -B -m scripts.datasets.prepare_audio_highlights --manifest docs/experiments/audio-highlight-phase-a/manifest.json --report datasets/audio-highlight-validation/results/preparation.json
& ./tmp/review-venv/Scripts/python.exe -B -m scripts.datasets.validate_audio_highlights --manifest docs/experiments/audio-highlight-phase-a/manifest.json --check highlights --report datasets/audio-highlight-validation/results/highlight-validation.json
& ./tmp/review-venv/Scripts/python.exe -B -m scripts.datasets.validate_audio_highlights --manifest docs/experiments/audio-highlight-phase-a/manifest.json --check highlights --repeat --report datasets/audio-highlight-validation/results/reproducibility.json
```

`prepare`는 기존 출력이 있으면 실패하며 덮어쓰기 옵션을 제공하지 않는다. 이미 생성된 Dataset에서는 `validate`를 실행한다. `validate`는 기본적으로 파일을 수정하지 않는다. `--report`를 명시하면 새 JSON만 기록하며 기존 report도 덮어쓰지 않는다. 다른 실행의 결과를 보존하려면 새 report 이름을 사용한다. 출력 생성 중 실패한 파일도 임의 삭제하지 않으므로 오류 결과를 확인한 후 별도로 처리한다.

종료 코드: 전체 기술 검사 통과 `0`, 파일 검사·생성·report 쓰기 실패 `1`, manifest/인자 오류 또는 기존 report 경로 지정 `2`. 파일별 실패 사유는 stderr와 JSON에 표시한다. 프로그래밍 오류는 포괄적인 Exception 처리로 숨기지 않는다.

## 데이터와 권리

`datasets/audio-highlight-validation/source/`, `highlights/`, `results/`는 기존 `.gitignore`로 제외된다. 원본·생성 Audio를 Git fixture로 넣지 않는다. synthetic Audio는 테스트 임시 경로에서만 만든다.

공식 곡·CC BY 4.0과 현재 원본 MP3의 공식 Incompetech 사이트 직접 다운로드는 각각 사용자 확인 근거로 confirmed_by_user를 기록했다. 기존 SHA-256으로 파일을 식별하며 official_binary_verification=not_performed다. Phase A 종합 verification_status=verified, rights_cleared=true는 로컬 MSCLAP 기술 검증에 사용할 Dataset의 출처·라이선스 확인 완료만 뜻한다. 공식 서버 파일과 바이너리 동일성 검증 또는 모든 향후 서비스/배포 용도의 포괄적인 권리 검토 완료를 의미하지 않는다. source_url은 공식 곡 정보 페이지이며 실제 MP3 다운로드 URL이 아니다. 기술 상태는 별도로 관리하고 기존 실행 JSON의 rights_cleared=false는 당시 기록으로 보존한다. 상세 근거와 SHA별 연결은 [ATTRIBUTION.md](ATTRIBUTION.md)에 기록한다.

## 범위와 다음 단계

실제 MSCLAP Embedding, DB, 기존 벡터 삭제/재생성, 유사도 분포/calibration, 서비스의 MP3/M4A 지원 계약은 이번 단계에서 검증하지 않는다. Phase A의 출처·라이선스 확인과 fixture 준비는 완료됐으며, 다음 단계는 공통 AudioEmbeddingGenerator의 실제 음악 검증 범위를 별도로 승인받는 것이다. 기존 FMA PoC는 보존한다.
