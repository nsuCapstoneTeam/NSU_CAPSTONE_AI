# ADR-0007 실제 6곡 MSCLAP Audio Embedding 검증

## 목적과 완료 범위

2026-10-09, Phase A 실제 음악 Highlight 6곡을 production `AudioEmbeddingGenerator`에 입력하여 생성 경로와 같은 환경의 재현성을 검증했다. **6곡 모두 PASS**다. 입력은 정확히 60초 WAV/FLOAT·stereo이며 원본/Highlight SHA-256은 실행 전후 모두 Phase A 기록과 일치했다.

현재 실행 기준 repository commit은 `14d111df5cdd7ff658f16877bb855bdbfd172bad`다. 실행 당시 검증 도구는 미commit 상태였으므로 [validation-result.json](validation-result.json)의 `tool_sha256`와 `generator_sha256`도 코드 identity로 기록했다. 고정 입력 정의와 출처·라이선스 범위는 [Phase A](../audio-highlight-phase-a/README.md), 생성 정책은 [ADR-0007](../../adr/ADR-0007-audio-highlight-embedding-strategy.md)을 따른다.

이번 완료는 실제 입력에서의 **생성 경로 기술 검증**이다. 추천/행사 적합성·검색 품질·PostgreSQL 저장/검색·candidate similarity distribution·calibration·기존 dev/test 벡터 재생성은 수행하지 않았다. 다음 단계로 별도 PostgreSQL 통합 검증을 계획할 수 있으며 DB 데이터 삭제/재생성은 별도 승인 범위다.

## 실행 환경과 offline cache

Docker client 29.8.1은 있으나 Docker Desktop Linux engine pipe에 연결할 수 없어 로컬 Windows CPU에서 실행했다. `tmp/review-venv`는 이번 실행에서 사용 가능한 기존 환경이며 장기적인 공식 검증 환경으로 채택하지 않는다.

- Python 3.11.16; Windows 10.0.26200; CPU 6 threads / interop 6 threads, CUDA 사용 안 함.
- msclap 1.3.3; torch/torchaudio 2.1.2+cpu; numpy 1.26.4; soundfile 0.14.0; transformers 4.35.2; libsndfile 1.2.2.
- production torchaudio 기본 dispatcher를 그대로 사용했으며 당시 사용 가능한 backend는 soundfile 하나였다.
- `HF_HOME=datasets/fma/huggingface`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. 기존 cache만 사용했고 외부 모델 다운로드는 수행하지 않았다.
- MSCLAP checkpoint revision: `c47d441165daa21986ead0850660917636a81775`.
- checkpoint SHA-256: `2cef4016d47d00eb28d153d522f397222057f95000e9bad6b9583c631284a1e6` (689,950,036 bytes). 로컬 파일 식별이며 공식 서버와의 독립 바이너리 비교를 뜻하지 않는다.
- GPT-2 revision: `607a30d783dfa663caf39e06633721c8d4cfcd7e`. model/tokenizer/config 존재 및 hash를 evidence에 기록했고 두 process에서 offline model load가 성공했다.

## 실제 처리와 관측 방법

`AudioEmbeddingGenerator.generate()`를 그대로 호출한다. 검증 도구는 `msclap.CLAP` lazy factory를 감싸 원래 모델의 `get_audio_embeddings()`에 전달된 임시 WAV와 원래 반환 tensor의 복제본만 관측한다. 모델에 전달한 입력이나 반환값을 바꾸지 않으며 별도 알고리즘으로 대표 벡터를 생성하지 않는다. generator의 원래 model load/RNG 복원·집계·오류·임시 파일 정리 경로가 유지된다.

처리 순서:

```text
60초 Highlight decode·길이 validation
→ 원본 rate에서 [0,56)
→ 채널 산술 평균 mono
→ 연속 56초를 44.1 kHz로 resample
→ [0,7), [7,14), …, [49,56): 308,700 samples × 8
→ PCM_F/float32 임시 WAV
→ get_audio_embeddings(8 paths, resample=False) 1회
→ [8,D] → chunk별 L2 → Mean Pooling → final L2 → float32 [1,D]
```

각 임시 chunk PCM을 독립적으로 계산한 연속 56초 downmix/resample 기준과 정확히 비교했다. 시작 포함·끝 제외, overlap 0, mono·44.1 kHz·finite·nonzero를 확인했다. normalization norm은 관측한 raw vector에서 계산한 검사값이며 내부 local variable를 직접 읽은 값이 아니다. 이 raw vector에서 재계산한 집계가 production의 최종 반환 tensor와 정확히 일치함을 확인했다.

실제 출력 차원은 **D=1024**였다. 검증 도구는 D를 영구 상수로 고정하지 않으며 synthetic/mock 테스트에서 D=5도 처리한다.

## 곡별 결과

| 곡 | 실제 batch shape | 대표 shape | final L2 norm | 경로·metadata 검사 |
|---|---|---|---:|---|
| The Britons | `[8,1024]` | `[1,1024]` | 1.0000000000 | PASS |
| Dentaneosuchus Hunt | `[8,1024]` | `[1,1024]` | 0.9999999404 | PASS |
| Cretaceous Dawn | `[8,1024]` | `[1,1024]` | 1.0000000000 | PASS |
| That Zen Moment | `[8,1024]` | `[1,1024]` | 1.0000000000 | PASS |
| Boogie Party | `[8,1024]` | `[1,1024]` | 0.9999999404 | PASS |
| All This | `[8,1024]` | `[1,1024]` | 1.0000000000 | PASS |

전체 24회 batch 추론(6곡 × process 2개 × 각 2회)과 192개 chunk의 finite/nonzero/shape 검사가 통과했다.
chunk raw norm 범위는 `32.140950934~32.373598440`, L2 후 norm의 최대 1 편차는 `8.881784197001252e-16`이었다. mean norm 범위는 `0.961500611377~0.981441333951`이며 0인 평균은 없었다. final norm 최대 편차는 `5.960464477539063e-08`로 기존 unit test의 `abs=1e-6` 기준을 통과했다. 작은 norm에 새 epsilon/threshold를 도입하지 않았다.

generation version은 `msclap2023-audio-first56s-8x7s-nonoverlap-chunk-l2-mean-final-l2-v2`다. model/checkpoint revision/packages/device/dtype와 arithmetic mean downmix·44.1 kHz·first56·8×7·overlap0·chunk L2·mean·final L2 profile이 모두 일치했고 24개 generation profile도 동일했다.

## 재현성

- 첫 process/model의 같은 입력 2회: 6/6 representative exact equality·canonical float32 digest 일치.
- 별도 process에서 model reload 후 자체 반복: 6/6 일치.
- 첫 process의 baseline과 reload process의 두 반복: 12/12 일치.
- 위 비교에서 raw chunk Embedding도 모두 exact equality였다. representative max absolute/RMS/L2 difference는 모두 0이다.
- cosine difference 계산에는 최대 `1.5543122344752192e-15` 수준의 부동소수점 반올림이 있었다. vector 값 자체는 정확히 동일하며 allclose 허용 오차로 PASS 처리한 것이 아니다.

실제 MSCLAP의 approximate reproducibility 허용 오차 정책은 여전히 미정이다. 향후 exact mismatch가 발생하면 도구는 차이를 기록하고 `REVIEW_REQUIRED`/nonzero exit로 남긴다. 이번 환경에서의 exact PASS를 다른 OS·backend·패키지·CPU/GPU의 재현성 보장으로 확대하지 않는다.

## Evidence 보존과 한계

tracked JSON에는 입력 identity·checkpoint/cache hash·각 반복의 chunk 경계/PCM digest/raw norm/normalized norm·실제 shape·final norm·representative digest·차이 측정·generation metadata/profile·검사 상태가 남는다. 최초 process와 별도 process 결과 모두 포함한다. 절대 interpreter 경로는 실제 일회성 실행 환경 식별용이며 공식 환경 요구사항이 아니다.

전체 `[8,D]`/`[1,D]` vector는 Git과 Markdown에 포함하지 않는다. local ignored evidence는 다음에 보존했다.

- `datasets/audio-highlight-msclap-validation/results/run-02.json`
- `datasets/audio-highlight-msclap-validation/results/run-02-reload.json`
- `datasets/audio-highlight-msclap-validation/results/run-02.vectors.npz`
- `datasets/audio-highlight-msclap-validation/results/run-02-reload.vectors.npz`

**tracked JSON의 norm/hash만으로 전체 vector를 독립적으로 재계산하거나 모든 수치 검사를 재audit할 수는 없다.** 재실행에는 별도 보관된 동일 Audio·checkpoint/cache·실행 환경이 필요하며, 로컬 vector 파일이 있으면 기록된 digest와 비교할 수 있다. 해당 파일의 장기 보관은 Git으로 보장하지 않는다. 이 생성 경로 검증 evidence는 향후 similarity calibration의 raw distribution/evaluation evidence를 대체하지 않는다. 향후 calibration 근거는 ADR-0007 생성 조건으로 별도로 생성·보존해야 한다.

Phase A의 rights_cleared=true는 로컬 기술 검증용 Dataset 출처·라이선스 확인 범위이며 공식 바이너리 동일성이나 모든 향후 서비스/배포 용도의 권리 검토가 아니다. Audio·cache는 계속 Git 제외다.

## 실행과 테스트

이번 실제 실행 명령(도구가 offline 환경을 명시적으로 설정한다):

```powershell
& ./tmp/review-venv/Scripts/python.exe -X utf8 -B -m scripts.embedding.validate_audio_highlight_msclap --manifest docs/experiments/audio-highlight-phase-a/manifest.json --repeat 2 --report datasets/audio-highlight-msclap-validation/results/run-02.json
```

이미 결과가 있으므로 재실행에는 새 report 이름을 사용한다. 기존 JSON/vector를 덮어쓰지 않는다. report는 Git 제외 `datasets/` 아래에만 저장한다. CLI는 전체 6곡의 source/Highlight SHA와 길이/형식/권리 상태를 model load 전에 검사하고, 하나라도 실패하면 추론을 시작하지 않는다. 모델은 offline cache가 없거나 로드에 실패하면 네트워크 다운로드로 우회하지 않는다. 성공 `0`, 검사 실패/재현성 검토 필요 `1`, 잘못된 인자/기존 출력 `2`다.

최종 실제 추론 전에 새 도구 synthetic/mock 테스트 17개 및 기존 production generator 테스트 23개, 총 40개가 통과했다. 최초 도구 테스트의 CLI encoding 실패를 수정하여 재검증한 뒤 실제 추론을 실행했다.

```powershell
& ./tmp/review-venv/Scripts/python.exe -X utf8 -B -m pytest tests/embedding/test_audio_highlight_msclap_validation.py tests/embedding/test_audio_embedding.py --basetemp=tmp/msclap-tool-tests-run3 -q -p no:cacheprovider
```

## 남은 사항

- 현재 확인한 6곡 생성 경로 검증을 근거로 PostgreSQL 통합 검증을 별도 계획할 수 있다.
- 기존 dev/test vector 삭제·재생성, 검색 품질 평가, similarity 분포·calibration은 완료되지 않았다.
- Docker/다른 backend 환경 검증과 approximate reproducibility 기준은 미결정이다.
