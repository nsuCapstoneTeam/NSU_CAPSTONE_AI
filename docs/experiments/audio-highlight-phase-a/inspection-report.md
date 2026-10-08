# Phase A 실제 파일 검증 기록

2026-10-08 실행. 실제 MP3 6곡에서 지정된 60초 WAV를 생성했다. **기술 검사 6/6 통과, 권리 확인 6/6 pending. Dataset은 rights-cleared가 아니다.**

## 실행 환경

- Python 3.11.16; Windows.
- torch 2.1.2+cpu
- torchaudio 2.1.2+cpu
- soundfile 0.14.0
- libsndfile 1.2.2; explicit backend: soundfile.
- 새 패키지 설치 및 requirements 변경 없음. Docker 엔진 연결 불가로 기존 Windows 가상환경에서 실행.
- 반복 검사 시각(UTC): 2026-10-08T11:00:19.024527+00:00

## 실행 결과

source validation → Highlight 생성 → Highlight validation → 별도 전체 decode 및 메모리 WAV 재생성 순서로 실행했다. 네 CLI 실행 모두 종료 코드 0이며 technical_passed=true, rights_cleared=false다. 실행 시각과 전체 관측값은 다음 로컬 JSON에 보존한다.

- `datasets/audio-highlight-validation/results/source-validation.json`
- `datasets/audio-highlight-validation/results/preparation.json`
- `datasets/audio-highlight-validation/results/highlight-validation.json`
- `datasets/audio-highlight-validation/results/reproducibility.json`

## 생성물

출력: `datasets/audio-highlight-validation/highlights/`. 모두 WAV / IEEE PCM_F / float32.

| 곡 | 파일 | 시작초 | 실제 초 | Frames | Rate | Channels | PCM 동일 | 반복 SHA 동일 |
|---|---|---:|---:|---:|---:|---:|---|---|
| The Britons | `the-britons.wav` | 0 | 60.0 | 2646000 | 44100 | 2 | 예 | 예 |
| Dentaneosuchus Hunt | `dentaneosuchus-hunt.wav` | 120 | 60.0 | 2880000 | 48000 | 2 | 예 | 예 |
| Cretaceous Dawn | `cretaceous-dawn.wav` | 60 | 60.0 | 2880000 | 48000 | 2 | 예 | 예 |
| That Zen Moment | `that-zen-moment.wav` | 270 | 60.0 | 2646000 | 44100 | 2 | 예 | 예 |
| Boogie Party | `boogie-party.wav` | 90 | 60.0 | 2646000 | 44100 | 2 | 예 | 예 |
| All This | `all-this.wav` | 90 | 60.0 | 2880000 | 48000 | 2 | 예 | 예 |

6곡 모두 finite이며 정확히 60 × 원본 sample rate frames다. 원본 stereo와 rate를 유지하고 반복/padding, resampling, downmix, 음량 정규화를 적용하지 않았다. 원본 decoded 지정 구간과 출력 PCM이 정확히 동일하다. 원본을 별도로 다시 전체 decode해 생성한 WAV의 PCM과 SHA-256도 동일하다. 기존 출력은 덮어쓰지 않았다. 다른 OS/decoder 환경의 bit 단위 재현성은 검증하지 않았다.

## 원본 검사

| 곡 | Bytes | Decoded frames | Decoded seconds | Info frames |
|---|---:|---:|---:|---:|
| The Britons | 12271315 | 13526784 | 306.729795918 | 13527803 |
| Dentaneosuchus Hunt | 4932317 | 11832192 | 246.504000000 | 11837560 |
| Cretaceous Dawn | 4903512 | 11763072 | 245.064000000 | 11768428 |
| That Zen Moment | 12038401 | 26539776 | 601.808979592 | 26567505 |
| Boogie Party | 5437265 | 11984256 | 271.751836735 | 11999481 |
| All This | 9158674 | 10987776 | 228.912000000 | 10990408 |

SoundFile은 원본 전체를 MP3 / MPEG_LAYER_III로 인식했다. 사전조사 TorchAudio info는 encoding=UNKNOWN, bits_per_sample=0을 반환했으나 전체 decode는 성공했다. Info frame과 decoded frame 차이 때문에 구간 판정에는 실제 decoded frame을 사용한다.

## SHA-256

| 곡 | Source SHA-256 | Output SHA-256 |
|---|---|---|
| The Britons | `00e766ef7a2635b1e7c116bfff794cb3485c17730ec26c114a9b3fb21d7a837d` | `cfb5182628e687dc344d1162c87752f581dfec5659cc59e304fdecd987a7b231` |
| Dentaneosuchus Hunt | `9db6b36ce1f47769a4f3b5c36c4a06981dea0e7a8fa9d44d7d30ddf180760ace` | `9a67f675eb6557384c58b43ca114d66843b2eb7dce37b42e781badaf027068bf` |
| Cretaceous Dawn | `a3f7bc1b0e0947d9b2a00c4faaeec55c73458b13b97d7fcb5d20e830da6e9226` | `4db8aa72bbf406df859f689005a3f7e7a6834e02b2186d0733b9fd01577ab050` |
| That Zen Moment | `d796b819607ebb2b9c04a5b5a838d0e167ed66b765ecacf9423fb6c0953853dc` | `7d1c0c856e31fedc00853ac2aca281baab642a3f7ab468764e3dad88735ddc93` |
| Boogie Party | `738c7cf5b142bca6f249f731d1f7c5a5025d17b7a05ba649319b0c512c229643` | `1c1b837a394c5306653d65c35e1e8d2a7dcdf30b7980d91ed4712a8938b88b01` |
| All This | `15aa40f76bf114748e23452e4659fed30cfb88745efa5d13c7279ea2fc370f12` | `ae86a8582210f8585e457bf2a4eb369e75819da1bc12b8749cb501fa61726418` |

최종 재확인에서도 source/output 해시는 6/6 일치했다. 원본 SHA는 사전조사 때와 동일하다.

## 권리

[ATTRIBUTION.md](ATTRIBUTION.md)에 공식 목록과 로컬 ID3v2.2 title/artist 대조를 기록했다. 제목과 Kevin MacLeod는 일치하지만 로컬 ISRC/copyright 태그와 실제 다운로드 증거는 없다. 곡별 license/license_url은 null, verification은 pending이다.

## 검증

- Dataset synthetic unit/CLI tests: 18 passed (33.50s). 44.1kHz/48kHz, 정확히 60초, 시작 포함/끝 제외, stereo, PCM 보존, 누락/해시/길이 실패, 기존 출력 보호, malformed manifest, CLI 종료 코드, 별도 파일 재생성 검사.
- 기본 pytest 임시 경로는 PermissionError로 실패해 새 repository 내부 basetemp로 재실행했다.
- 수정 전 15 passed / 3 failed: libsndfile FLOAT WAV PEAK chunk의 생성 시각 때문에 파일 해시가 달랐다. 시간 metadata 없는 표준 fmt/fact/data writer 적용 후 18개 통과.
- 기존 공통 생성기 non-DB unit tests: 23 passed (18.56s). 모델은 mock이며 실제 MSCLAP 평가나 DB 테스트가 아니다.
- py_compile: Dataset Python 도구 5개와 테스트 1개 성공. 캐시는 Git 제외 tmp/에 기록.
- 전체 원본/생성물 최종 SHA 확인 및 PCM_F/32bit/60초/stereo 정보 조회 검사: 6/6 통과.
- git diff --check 통과. 신규 도구/테스트/문서 10개 파일의 trailing whitespace 검사도 통과했다.

## Git 및 범위

기존 datasets/ ignore 패턴이 scripts/datasets/도 제외하므로 /datasets/로 root 범위만 한정했다. 원본·Highlight·로컬 results와 Audio 확장자는 계속 Git 제외다. 고정 manifest와 문서/도구/테스트만 추적 가능한 위치에 둔다.

app/, 공통 생성기 알고리즘, requirements는 변경하지 않았다. 실제 Embedding, DB, 벡터 삭제/재생성, calibration, 외부 프로젝트 변경과 git add/commit/push/PR은 수행하지 않았다.

## 다음 단계

곡별 다운로드 출처·녹음 버전·license/attribution 증거 확인 후 실제 공통 생성기 음악 검증 범위를 별도로 승인받는다. 다른 decoder 환경 재현성과 서비스 업로드 형식 계약은 미결정이다.

## 후속 라이선스 확인 기록 (2026-10-08)

사용자가 6곡 모두 Incompetech 공식 곡 페이지에서 CC BY 4.0을 확인했다고 통보했다. 이 후속 근거를 현재 manifest 및 ATTRIBUTION.md에 반영했다. 위 본문의 license/license_url=null 설명과 기존 실행 JSON의 권리 상태는 당시 기록으로 보존한다.

공식 곡 정보 URL·ISRC·저작자·CC BY 4.0 URL·60초 발췌 및 WAV 변환 표시를 기록했다. 공식 정보 URL은 실제 MP3 다운로드 URL이 아니다. source SHA-256은 기존 값을 유지하며 로컬 출처 확인 객체에 연결했다.

공식 라이선스 상태는 confirmed_by_user, 로컬 source 확인과 종합 verification_status는 pending이다. rights_cleared=false를 유지한다. 원본/Highlight와 기존 Phase A 기술 결과는 변경하지 않았다. 로컬 파일의 공식 취득 경로를 확인한 것으로 간주하지 않는다.

## 후속 원본 취득 확인 및 Phase A 권리 상태 (2026-10-08)

사용자는 현재 원본 MP3 6곡을 모두 Incompetech 공식 사이트에서 직접 다운로드했다고 추가 확인했다. 기존 source SHA-256으로 식별되는 파일별 local_source_verification을 confirmed_by_user로 기록했다. 공식 곡·CC BY 4.0도 confirmed_by_user이며 공식 URL은 곡 정보 페이지로 유지한다. 실제 다운로드 URL·날짜를 임의로 기록하지 않는다.

official_binary_verification=not_performed: 공식 서버 파일을 별도 취득하여 SHA-256 비교를 수행하지 않았다. 종합 verification_status=verified, rights_cleared=true는 Phase A 로컬 MSCLAP 기술 검증에 사용할 Dataset의 출처·라이선스 확인이 완료됐다는 의미로 한정한다. 공식 서버 파일과의 바이너리 동일성 검증 또는 모든 향후 서비스/배포 용도의 포괄적인 권리 검토 완료를 뜻하지 않는다.

위의 pending/rights_cleared=false 및 기존 실행 결과 JSON은 당시 기록으로 그대로 보존한다. 현재 상태는 수정된 manifest를 사용한 새 검증 결과에서만 반영한다. 원본 SHA, Highlight 및 기존 기술 검증 결과는 변경하지 않았으며 실제 MP3/WAV는 계속 Git 제외다. 실제 MSCLAP Embedding 평가는 수행하지 않았다.

### 현재 manifest의 후속 검증 결과

- 새 읽기 전용 Highlight 검증 시각(UTC): 2026-10-08T11:22:43.210205+00:00. 결과는 메모리에서 확인하여 기존 JSON을 수정하거나 새 결과 파일을 생성하지 않았다.
- manifest loader 호환성 및 6곡 ISRC/공식 곡 URL/CC BY 4.0/저작자/attribution/Highlight 구간 정합성: 통과.
- 공식 라이선스와 로컬 취득 확인 confirmed_by_user, 공식 바이너리 비교 not_performed, Phase A 종합 verified 상태: 6/6 일치.
- 새 결과: technical_passed=true, rights_cleared=true, 지정 구간과 출력 PCM 동일성 6/6 통과. 실제 MSCLAP Embedding 추론은 실행하지 않았다.
- 기존 결과 JSON 4개의 rights_cleared=false 및 파일 바이트, 원본/Highlight SHA-256, Dataset 코드/requirements: 불변.
- 기존 Dataset unit/CLI tests: 18 passed (33.88s). 테스트 코드는 수정하지 않았다.
- git diff --check 통과. MP3/WAV는 계속 Git 제외이며 이번 변경은 승인된 문서 6개로 한정한다.
