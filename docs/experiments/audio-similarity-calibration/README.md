# Audio Similarity Calibration Dataset 준비

## 목적과 상태

이 자료는 NSUAI-36 calibration cohort와 청취 평가의 계획·실행 evidence다. 후보 선정뿐 아니라 실제 50곡 acquisition/source validation, centered 60초 preparation, MSCLAP Audio Embedding, 16×50 raw cosine, 96쌍 청취 평가와 분석까지 완료했다. 이는 최종 표시 변환 확정이나 독립 validation 완료를 뜻하지 않는다.

Event query는 실제 사용자 데이터가 아니라 대표적인 합성 시나리오 benchmark다. 기존 draft inventory 20개를 모두 보존하며 engineering calibration v1의 ACTIVE는 16개, RESERVE는 2개, REPLACE 후보는 2개다. 16개는 통계적으로 최적이거나 충분하다고 검증된 수가 아니며 coverage와 청취 workload를 고려한 실용적 규모다.

## 현재 기준

- Accepted 서버 협의 012에 따라 순위는 raw cosine으로 결정한다. Spring은 순서를 다시 정렬하지 않는다.
- 사용자 표시용 음악 유사도는 후보 독립 고정 변환이다. calibration 분석은 완료했지만 최종 공식·threshold·breakpoint·parameter는 확정하지 않았다. provisional 후보와 독립 validation 상태는 아래에 기록한다.
- 이 calibration cohort는 당시 기록된 ADR-0007의 60–80초 조건 아래 준비했다. 준비된 중앙 정확히 60초 segment는 현재 AI 저장소의 56~60초 허용 범위에도 들어간다. 이 과거 실험 기록은 사용자 업로드/API 정책이 바뀌었다고 뜻하지 않는다.
- calibration 후보 선정: 완료, PASS 50곡
- Audio source acquisition/validation: completed, 50/50.
- Centered exact 60-second prepared audio: completed, 50/50.
- MSCLAP Audio Embedding: completed, shape [50,1024] float32.
- Raw cosine: completed, 16 ACTIVE queries x 50 songs = 800 values.
- Listening evaluation: completed, 96 pairs x 3 evaluators = 288 ratings; unable_to_judge = 0.
- Calibration analysis: completed; raw cosine vs human mean Pearson = 0.502 and Spearman = 0.524. Rank-group means (top/mid/bottom) = 2.854 / 2.375 / 1.448.
- Listening evaluation summary: 96 query/song pairs, 3 evaluators, 288 ratings, and 0 unable-to-judge responses. Mean of the 96 pair-level evaluator averages = 2.226/5 (median 2.0). Evaluator-pair agreement was variable (Pearson 0.297–0.515; Spearman 0.259–0.506).
- Fixed raw-cosine-bin human means were 1.406 (<0.10, n=23), 1.842 (0.10–<0.20, n=19), 2.417 (0.20–<0.30, n=16), 2.979 (0.30–<0.40, n=16), 2.769 (0.40–<0.50, n=13), and 2.667 (≥0.50, n=9; small sample). The upper bins are not monotonic.
- The temporary linear candidate had Pearson 0.558 and Spearman 0.535 against pair-level human means; these are calibration-cohort correlations, not independent validation.
- Final 0-100 display-score calibration: not finalized. Provisional candidate only: `clamp(100 * cosine / 0.4, 0, 100)`.
- Independent validation: not performed; this 50-song cohort and listening evaluation are calibration evidence only.

The completed listening evaluation was summarized here before removing evaluator-level CSVs, assignment/blinding files, the browser review page, derived intermediate reports, and 40 generated blinded playback WAVs plus their ZIP. Individual ratings and evaluator identifiers are no longer retained in the repository. The evaluation used 5-point Likert ratings; the 96 pairs were stratified from ranks 1/2, 25/26, and 49/50 over 16 ACTIVE queries and 50 candidate songs. The result is ordinal calibration evidence and does not establish recommendation accuracy or a final display-score mapping.

Candidate selection and calibration status are tracked separately. The 50-song source/prepared cohort, MSCLAP Audio Embedding, 16 x 50 raw cosine, 96-pair listening evaluation (3 evaluators, 288 ratings), and calibration analysis are complete. See [Audio Embedding evidence](./audio-embedding-evidence.json), [raw cosine artifact](./artifacts/calibration-v1-raw-cosine.json), and the aggregate listening results above. Final display-score calibration is not finalized; independent validation has not been performed.

현재 PASS 50곡은 calibration cohort다. 이 cohort의 raw cosine 분포와 청취평가는 transformation 선정 자료이며 독립 validation 자료가 아니다. 최종 transformation 선택 후 별도로 구성한 독립 validation cohort에서 검증한다. 현재 50곡을 validation holdout으로 간주하지 않으며, 별도 validation cohort의 크기와 구성은 아직 정하지 않았다.

## Event query benchmark

Event query 자료는 다음 세 단계를 실험용으로 분리한다. 아래 구조의 이름은 calibration 자료의 의미 라벨이며 Spring API payload field 이름이나 API schema가 아니다.

저장소 루트에서 `uv run --isolated --with jsonschema==4.26.0 python -m scripts.matching.validate_calibration` 한 명령으로 전체 calibration 검증을 실행한다. 고정된 `jsonschema` 버전을 격리된 uv 실행 환경에 준비하므로 새 checkout에서도 추가 설치 단계 없이 실행할 수 있다. `requirements-dev.txt`에도 같은 버전을 고정한다. 명령은 manifest/Event query JSON Schema, `sample_id`/`query_id` 고유성, complete cohort 내 credited artist 최대 2곡, `source_url` 및 `(provider, provider_track_id)` 고유성, query 간 정규화한 `(event_type, event_description_ko, desired_genre)` 조합 고유성, cohort/query 교차 규칙, Structured Interpretation의 non-blank 상태와 Raw evidence를 검사한다. 모든 query의 evidence가 해당 query의 현재 Raw에 포함되는지 확인하고, ACTIVE query의 `desired_genre` 참조 대상도 검증한다. 또한 complete cohort의 각 sample에서 non-blank `license_name`과 `license_url`, 명시적인 `attribution_required`, 필요한 경우 non-blank `attribution`을 검사한다. Raw 조합과 artist 표기는 공백을 정리하고 대소문자를 무시해 비교한다. ACTIVE query는 `review_status: reviewed_for_raw_support`여야 하며, 이 조건은 Event query schema가 검증한다. JSON Schema는 서로 다른 레코드 간 ID·실제 트랙 identity, artist 최대 개수나 Raw 문자열과 annotation evidence의 교차 필드 일치를 표현하지 못하므로 통합 validator가 추가로 검사한다.

각 Structured Interpretation 속성의 상태는 calibration 검수 근거를 나타낸다. `interpreted`는 null·빈 문자열·공백 문자열·빈 배열·빈 문자열 항목이 없는 해석값과 1개 이상의 non-blank 현재 Raw excerpt가 필요하고, `not_requested`는 null 값과 빈 evidence를 요구한다. `unable_to_interpret`는 요청 근거가 있으나 해석할 수 없는 상태이므로 null 값이면서 1개 이상의 non-blank 현재 Raw excerpt가 필요하다. 통합 validator는 제공된 excerpt가 동일 query의 현재 `raw_service_input`에 실제로 포함되는지 확인한다. `desired_genre`는 Raw 값이 존재할 때에만 고정 pointer로 참조한다.

통합 validator는 표준 JSON에서 허용되지 않는 `NaN`, `Infinity`, `-Infinity`뿐 아니라 유한 범위를 벗어나 Python에서 무한대로 변환되는 지수 표기도 입력 단계에서 거부한다. `source_catalog_duration`은 양수이며 complete 후보에서는 60초 이상이다. 성공적으로 decode한 source의 `decoded_duration`은 decoder가 반환한 정수 `decoded_frame_count / source_sample_rate`로 기록하고 두 값의 관계를 엄격히 검사한다. `source_sample_rate`와 `source_channels`는 null 또는 양의 정수, frame index는 null 또는 0 이상의 정수다. prepared hash·duration·시작/끝 frame 중 하나라도 채워지면 source hash·decode frame count·sample rate·channel·양 끝 frame·prepared hash·duration이 모두 있어야 하고, prepared duration은 정확히 60초여야 한다. 취득 전에는 decode/prepared metadata가 null이다. `source_file_size`는 `not_acquired`/`pending` 상태에서는 null이고, 취득 완료 상태부터 양의 정수가 필수다. `cohort_target`은 정확히 50이며 그 밖의 합리적 상한은 현재 정하지 않았다.

`source_url`, `license_url`, source metadata URL은 absolute HTTP(S) URL이어야 한다. URI 형식 검사와 함께 scheme·authority가 빠진 상대 경로 및 공백 포함 URL도 schema에서 거부한다.

`historical_raw_draft`는 최초 synthetic Raw draft 20개의 snapshot으로 calibration 문서 이력을 보존하며, 실제 사용자 입력 로그나 production revision history가 아니다. `raw_service_input`은 현재 calibration 단계에서 사용하는 Raw 입력이다. snapshot 생성 직후에는 두 값이 같았고, 현재는 ACTIVE 16개 중 15개에 검수한 Raw v1을 반영해 해당 항목에서 두 값이 다르다.

1. `raw_service_input`: 대표 합성 시나리오의 행사 종류·한국어 행사 설명·희망 Genre 의미를 보존한다. 이는 실제 사용자 입력이나 실제 사용자 데이터가 아니다. ACTIVE v1은 16개이며 Raw 수정안은 15개에 반영했고 event-07은 유지했다. Genre 지정은 12개, 미지정은 4개다. 이 수와 비율은 통계적으로 최적이라고 검증된 값이 아니다.
2. `structured_interpretation`: calibration-only 의미 주석이며 production AI 결과나 Spring API 계약이 아니다. 속성은 mood, tempo, desired_genre, instrument_preference, vocal_preference, acoustic_electronic, dynamic_progression, usage_context, rhythmic_character, activity_character다. ACTIVE 16개는 Raw 근거 검수를 완료했고 RESERVE/REPLACE는 미검수 placeholder로 유지한다.
3. `msclap_model_input`: 사람이 작성한 영어 calibration 입력이다. ACTIVE 16개는 semantic fidelity 검수를 마쳤고, `approved_for_calibration_v1_experiment`로 calibration v1 Text Embedding/cosine 실험 입력으로 승인했다. 이는 모델 성능 검증이나 production query 확정이 아니다. RESERVE/REPLACE 4개는 `draft_not_confirmed_model_input` 및 `not_reviewed`를 유지한다.

현재 자료는 실제 사용자 데이터가 아닌 representative synthetic scenario benchmark다. ACTIVE 16개의 Structured Interpretation Raw 근거 검수, 영어 입력 semantic fidelity 검수 및 calibration v1 실험 입력 승인은 완료했다. 2026-10-16 ACTIVE 16개를 MSCLAP 2023 Text Encoder로 batch 생성했고, 결과와 실행 identity는 [Text Embedding evidence](./text-embedding-evidence.json)에 기록했다. 출력은 `[16, 1024]`, `float32`, CPU였으며 Text Encoder 출력에 L2 normalization을 적용하지 않았다. 같은 16-query batch의 반복 출력은 정확히 같았지만, batch와 single 입력은 bitwise 동일하지 않았다(상세 차이는 evidence 참조). 임의 허용 오차는 정하지 않았으므로 기존 cosine 실행은 이 evidence의 batch artifact를 입력으로 사용했다. 이 canonical Text Embedding artifact는 61,228 bytes의 작은 calibration 산출물이므로 `docs/experiments/audio-similarity-calibration/artifacts/calibration-v1-text-embeddings.npz`에 Git으로 보존한다. cosine 실행 전 evidence SHA-256, query ID 순서, `[16, 1024]` shape, `float32`, finite 여부 및 execution identity를 대조한다. Audio Embedding/acquisition, raw cosine, 청취 평가와 calibration analysis는 완료했다. 이 benchmark 입력은 production query로 확정되지 않았고, production 검색 성능 검증은 수행하지 않았다.

같은 Text Embedding 검증 경로는 저장소 루트에서 Python 3.11 및 프로젝트의 MSCLAP CPU 의존성이 설치된 환경에서 실행한다. 기본 출력 경로는 canonical NPZ/evidence를 가리키며, 기존 canonical 결과가 이미 있으므로 보호를 위해 거부된다. 일반 검증 또는 재실행에서는 아래 예제처럼 `--embedding-output`과 `--evidence-output`에 임시/non-canonical 경로를 지정한다. `--overwrite`는 canonical 결과를 의도적으로 다시 게시할 때만 사용한다. 실행 전 통합 calibration validator를 수행하고, dirty worktree에서는 모델 추론을 시작하지 않는다. 동일한 16-query batch의 반복 출력은 bitwise identical이어야 성공하며, 불일치하면 canonical artifact/evidence를 확정하지 않고 실패한다. batch와 single 입력의 차이는 별도 진단으로만 기록하며 허용 오차는 정하지 않았다.


Text Embedding evidence는 임시 harness가 아니라 저장소의 canonical runner에서 clean worktree로 생성했다. 실행 commit은 `61790c4821aff6a4a6e6084f7c9f3457ee2a0320`이며, GPT-2 tokenizer snapshot `607a30d783dfa663caf39e06633721c8d4cfcd7e`, 실제 snapshot 파일 SHA-256, runtime tokenizer serialization hash, MSCLAP source/config hash와 checkpoint hash를 evidence에 기록했다. 이어서 Audio Embedding과 cosine을 생성하고 listening calibration analysis를 완료했다. production ranking 성능 검증은 수행하지 않았다. 이 SHA는 실제 runner를 실행한 execution/implementation commit이며, 최신 실행 결과를 기록한 evidence/document commit 2f46a94b137898a3b8a318234b0e5fa5d03bc58e과 구분한다.

### Text Encoder 자원 준비와 결과 보호

새 Python 환경에서는 저장소 루트에서 검증된 CPython 3.11 x86-64 Windows/Linux CPU 의존성을 설치한 뒤 tokenizer와 checkpoint를 먼저 준비한다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m scripts.embedding.validate_calibration_text_embeddings --prepare-resources
```

Bootstrap은 evidence에 고정된 GPT-2 tokenizer/config와 `model.safetensors`, `microsoft/msclap` checkpoint만 Hugging Face에서 준비하고 각 파일의 SHA-256을 확인한다. GPT-2 가중치는 MSCLAP 1.3.3의 TextEncoder.__init__()이 checkpoint 적용 전에 AutoModel.from_pretrained("gpt2")를 호출하므로 필요하다. 별도 cache 환경변수(`HF_HOME`, `HF_HUB_CACHE`, `TRANSFORMERS_CACHE`)가 설정되지 않으면 Hugging Face 기본 cache 위치를 사용한다. MSCLAP/Transformers 호출이 revision을 생략하므로 bootstrap은 두 모델 cache의 `refs/main` 포인터를 승인된 immutable revision으로 원자 갱신한다. 기존 snapshot 파일을 삭제하지 않는다. Bootstrap은 tokenizer/model/checkpoint를 `local_files_only` lookup으로 확인하고, 실제 MSCLAP TextEncoder 초기화는 offline 환경변수를 프로세스 시작 전에 설정한 별도 worker에서 검증한다. 일반 canonical 실행도 offline 환경에서 새 worker로 시작하므로 이미 import된 library의 online 상태를 뒤늦게 바꾸지 않는다. Worker는 Hugging Face와 Transformers의 내부 offline flag를 확인하고, 해당 cache의 `refs/main`, snapshot 파일 hash 및 local lookup을 검증한 뒤 모델을 읽는다. 비어 있거나 잘못된 cache에서는 추론 전에 실패하며 위 bootstrap 명령을 안내한다. 모든 실행은 저장소 루트에서 한다.

**일반 검증 또는 재실행**에서는 canonical 결과를 건드리지 않도록 두 출력에 별도의 임시 경로를 지정한다. 다음 예제는 Windows PowerShell용이며, 고유한 임시 파일명을 사용한다. pinned 자원이 준비되어 있고 runner의 clean-checkout 조건을 만족하는 상태에서 실행한다.

```powershell
$runId = [guid]::NewGuid().ToString("N")
$embeddingOutput = Join-Path $env:TEMP "calibration-v1-check-$runId.npz"
$evidenceOutput = Join-Path $env:TEMP "calibration-v1-check-$runId.json"
.\.venv\Scripts\python.exe -m scripts.embedding.validate_calibration_text_embeddings `
  --embedding-output $embeddingOutput `
  --evidence-output $evidenceOutput
```


canonical NPZ 또는 evidence JSON 중 하나라도 있으면 기본 출력 경로를 사용하는 실행은 거부된다. **의도적으로 canonical 결과를 다시 게시할 때만** 다음처럼 `--overwrite`를 지정한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.embedding.validate_calibration_text_embeddings --overwrite
```

`--overwrite`는 일반 확인용 옵션이 아니다. validation을 모두 통과한 뒤에도 기존 pair가 서로 일치하고 새 NPZ의 decoded content digest가 기존 artifact와 같을 때만 transactional 교체를 허용한다. ZIP timestamp 등 container metadata 차이로 file SHA-256이 달라도 decoded embeddings, dtype, shape, query ID와 순서가 같으면 동일 결과로 볼 수 있다. file SHA-256은 게시된 NPZ bytes의 무결성을 확인하고, content digest는 decode된 embedding 결과의 동일성을 확인한다. content digest가 다르거나 validation/write/replace에 실패하면 기존 pair를 유지하고 실패한다. 결과 한 쪽만 남은 불완전 pair도 자동 덮어쓰지 않는다.
## Dataset 구성

1차 목표는 50곡이다. 같은 아티스트는 가급적 1곡, 최대 2곡으로 제한한다. Complete 상태의 통합 validator는 manifest `artist` 표기를 공백 정리 및 대소문자 무시 후 세어 최대 2곡을 강제한다. artist alias와 여러 기여자 표기의 실체 식별은 자동 판정하지 않으므로 후보 선정 기록에서 사람이 검토한다. 장르·분위기, 보컬/인스트루멘탈, electronic/acoustic, 느림/중간/빠름 인상의 편중은 수치화된 완료 조건이 아니라 후보 구성 시 사람이 검토하는 다양성 기준이다. 제공자 metadata와 사람이 붙인 label을 별도로 보존하고 출처가 불분명한 label은 unknown으로 둔다. Source metadata의 tempo는 표본 구성 설명으로만 쓸 수 있으며, BPM/Rhythm ranking 구현을 뜻하지 않는다.

정식 calibration 후보는 Incompetech 2곡, 새 FMA 전체곡 20곡, Wikimedia Commons 22곡, ccMixter 6곡으로 총 50곡이다. `candidate_selection_complete`는 정확히 50개이며 각 sample의 `source_catalog_duration`이 60초 이상, `commercial_use_status`가 `allowed`, `rights_status`가 `confirmed_from_official_metadata`이고 `sample_id`, `source_url`, 그리고 값이 있는 경우 `(provider, provider_track_id)`가 모두 고유한 현재 유효 후보 집합을 뜻한다. 각 sample은 다시 확인 가능한 non-blank `license_name`과 `license_url`, 명시적인 boolean `attribution_required`를 가져야 하며, attribution이 필요한 경우에만 non-blank `attribution`을 요구한다. 현재 50개 모두 이 license URL 근거 구조를 사용한다. Validator는 해당 근거 필드의 존재·형식만 확인하며, URL 대상의 실제 라이선스 적용 범위나 페이지 내용까지 자동 판정하지 않는다. 이후 다른 provider에서 다른 라이선스 근거 모델을 쓸 필요가 생기면 complete 상태를 사용하기 전에 해당 근거 구조를 별도 검토해야 한다. 위 통합 검증 명령은 schema의 개수·길이·권리·라이선스 상태 조건과 논리 ID·실제 트랙 식별자 고유성을 함께 검사한다. `provider_track_id`가 없으면 이를 전역 고유값으로 강제하지 않고 `source_url` 고유성으로 fallback한다. 재검증으로 sample이 길이·권리·상업 사용 기준에 부적격해지면 이 상태를 유지하지 않고 `candidate_selection_incomplete`로 바꾼다. 적격 대체 후보를 검증해 유효한 50곡을 다시 확보한 뒤에만 complete로 되돌린다. `source_catalog_duration`은 취득 전 catalog 기반 기준이며, Audio acquisition 후 실제 decode 및 `decoded_duration` 검증은 별도 단계에서 수행한다. ccMixter는 개별 트랙의 길이·라이선스·attribution·source dependency를 확인한 항목만 포함하며, sample/remix source chain이 불명확한 트랙은 포함하지 않는다. 기존 FMA 30초 Historical 자료는 사용하지 않고, Phase A 6곡은 기술 검증 fixture로만 유지하며 calibration cohort에서 제외한다. HOLD 판정된 The Wind that Shakes the Barley는 검토 이력에만 보존하고 PASS cohort 및 manifest에서는 제외했다. Audio acquisition/source validation and prepared audio are complete for 50/50 samples; Audio Embedding, raw cosine, listening evaluation, and calibration analysis are complete. Final display-score calibration is not finalized; independent validation has not been performed.

`candidate_selection_complete`는 취득 전 catalog 검증 단계에서도 사용할 수 있다. 현재 `acquisition_method`는 `not_acquired` 50개이며 source SHA, decode 결과, prepared 결과는 모두 null이다. 이 상태의 sample은 `source_local_path`와 `prepared_local_path`가 null, `source_file_kind`가 `unknown`, `full_track_verified`와 `full_track_evidence`가 null이어야 한다. 취득 방법이 `official_direct_download` 또는 `other_confirmed_method`이면 repository-root 기준 `source_local_path`와 원본 `source_sha256`가 필요하다. `data/calibration/audio/source/` 아래의 상대 POSIX 경로만 허용하며 절대경로, 빈 경로, `..` 경로 traversal은 거부한다. 경로 존재 여부는 manifest-only validator에서 검사하지 않는다. 이후 acquisition runner가 로컬 파일 존재·실제 경로·SHA를 확인해야 한다.

decode 성공을 기록할 때는 `decoded_duration`, 정확한 정수 `decoded_frame_count`, decoder의 `source_sample_rate`, `source_channels`가 함께 있어야 하며 `decoded_duration == decoded_frame_count / source_sample_rate`를 만족해야 한다. Acquisition은 실제 source의 상태와 decode metadata를 기록하는 단계이므로 길이가 60초 미만인 `preview`, `sample`, `unknown`도 등록할 수 있다. 다만 `full_track_verified=true`는 decoded duration이 60초 이상인 `full_track`에만 허용하며, preparation도 별도 60초 minimum을 강제한다. `source_file_kind`는 `full_track`, `preview`, `sample`, `unknown` 중 하나다. full-track 확인 근거는 `full_track_evidence`에 기록해야 한다. catalog duration이 60초 이상이라는 사실만으로 자동 verified 처리하지 않는다. `preview`, `sample`, `unknown`은 준비할 수 없다. 이미 취득한 sample의 decode가 실패했거나 아직 완료되지 않았다면 측정값을 만들지 않는다.

Manifest JSON Schema는 audio path의 POSIX 형태와 traversal 금지, 상태별 필수/null 필드를 검사한다. Schema만으로 record의 `sample_id`와 경로를 연결하지는 않는다. 통합 Python semantic validator가 source의 첫 디렉터리와 prepared 파일명을 `sample_id`에 묶고, repository-root resolve 및 symlink escape를 검사한다. `source_file_size`는 `not_acquired`/`pending`에서는 null이고, acquired 상태부터 양의 정수로 필수다. Manifest-only 검증은 실제 파일을 열지 않으며, acquisition/preparation/embedding runner는 등록된 크기와 실제 파일 크기를 다시 대조한다.

## Segment 준비 규칙

이는 offline calibration Dataset 전용 규칙이다. 원본을 실제 decoder로 decode한 frame 수를 N, decoder sample rate를 R이라 할 때 N ≥ 60R인지 확인하고 중앙의 정확히 60초를 선택한다. `decoded_duration`은 N/R로만 기록한다. frame index는 decoder가 반환한 원본 sample rate의 frame 좌표이며, prepared 추출은 이 sample rate/channel을 보존한다. catalog duration은 source page의 표기값이고 실제 decoded duration과 같은 정밀도를 가진다고 보장하지 않으므로 둘을 서로 대체하거나 같다고 강제하지 않는다.

- start_frame = floor((N - 60 * R) / 2)
- end_frame_exclusive = start_frame + 60 * R
- 선택 구간 = [start_frame, end_frame_exclusive)

prepared metadata가 존재하는 sample은 `prepared_frames = segment_end_frame_exclusive - segment_start_frame`이 `60 * R`과 정확히 같고 `prepared_duration`은 60이어야 한다. 시작 frame은 위 중앙 추출식과 같아야 하며 끝은 exclusive 경계로서 `decoded_frame_count` 이하이어야 한다. prepared path/hash/duration 또는 segment 시작/끝 frame 중 하나라도 있으면 전체 prepared metadata를 채워야 한다. 준비 전 acquisition method, source path/SHA, decode metadata, full-track 검증과 evidence가 모두 있어야 한다. `prepared_local_path`는 `data/calibration/audio/prepared/` 아래의 repository-root 기준 상대 POSIX 경로다. manifest에는 별도 prepared 상태 enum이 없으며, prepared 관련 필드가 모두 null이면 미준비, 하나라도 값이 있으면 완전한 prepared metadata로 검증한다.

사람이 듣고 “좋은 부분”을 고르지 않는다. 원본 sample rate와 channel을 준비 단계에서 보존한다. prepared 산출물은 float32 IEEE WAV (`PCM_F`, 32-bit)로 저장하며, decode된 float32 sample을 저장하는 것 외에 loudness normalization이나 lossy re-encoding을 하지 않는다. 재현 가능한 frame 수와 PCM WAV byte를 검증한다. 이후 공통 `AudioEmbeddingGenerator`가 ADR-0007 전처리를 적용한다. 선택된 segment가 곡 전체를 대표한다고 단정하지 않고 선택 규칙과 한계를 기록한다.

## 파일과 Audio 보관

Audio 원본은 `data/calibration/audio/source/<sample_id>/...`, prepared 파일은 `data/calibration/audio/prepared/<sample_id>.wav`에 local-only로 둔다. root `.gitignore`의 `data/` 규칙과 `*.wav` 규칙이 이를 무시하므로 Audio 보관을 위해 별도 ignore 규칙을 추가할 필요는 없다. 원본/prepared audio binary는 Git에 commit하지 않는다. manifest에는 상대경로, 각 파일 SHA-256, decoder metadata, full-track 근거, prepared frame provenance만 기록한다. 파일 경로와 SHA가 있어도 실제 local 파일의 존재·hash 일치는 별도 acquisition/preparation 실행에서 검사한다.

취득한 source를 등록할 때는 `data/calibration/audio/source/<sample_id>/` 아래에 파일을 둔 뒤 저장소 루트에서 `python -m scripts.matching.register_calibration_audio`를 실행한다. 기본 실행은 decode·finite PCM·duration/frame metadata·SHA 및 manifest 조건을 검사하고 변경 예정 metadata만 출력한다. 길이가 60초 미만인 preview/sample/unknown은 상태와 source metadata를 기록할 수 있지만 preparation-ready가 되지 않는다. 60초 미만 `full_track`도 검토 전 metadata로 등록할 수 있으나 `full_track_verified=true`로 승인할 수 없다. `--write`를 지정한 경우에만 검증 후 manifest를 atomic하게 갱신한다. `--source-file-kind`와 acquisition method는 명시해야 하며 `--full-track-verified`는 full-track 근거를 `--full-track-evidence`로 제공하고 decode duration이 60초 이상인 경우에만 허용된다. catalog/source 길이만으로 full-track을 판정하지 않는다. 이 runner는 source 등록/검증만 수행하며 centered 60초 prepared WAV는 생성하지 않는다.

등록된 source를 준비할 때는 저장소 루트에서 `python -m scripts.matching.prepare_calibration_audio --sample-id <sample_id>`를 실행한다. 기본 dry-run과 `--write` 모두 source SHA/크기/decode metadata, full-track 조건 및 `commercial_use_status=allowed`, `rights_status=confirmed_from_official_metadata`, 비어 있지 않은 license name/URL을 재검증한다. 이 sample-level rights gate는 `cohort_status`와 무관하게 적용되므로 cohort가 incomplete여도 부적격 source는 준비할 수 없다. dry-run은 중앙 60초의 frame 범위, 출력 경로, SHA 및 manifest 변경안을 출력하지만 WAV나 manifest를 만들지 않는다. 검증된 결과를 함께 게시하려면 `--write`를 지정한다. prepared WAV는 decoded frame 수 기준 `start = floor((N - 60R) / 2)`, `end = start + 60R`의 `[start, end)` 구간으로 만들며 홀수 leftover frame은 뒤쪽에 하나 더 남긴다. WAV는 원본 sample rate와 channel 수를 유지하는 little-endian IEEE float32다. 준비 단계에서는 resampling, mono downmix, loudness normalization, lossy re-encode를 하지 않는다. 이 변환은 이후 Audio Embedding generator 단계와 구분한다. 기존 prepared 파일 또는 manifest metadata가 있으면 덮어쓰지 않고 실패한다.

The existing canonical runner consumes all 50 validated prepared files, creates embeddings in manifest order, and publishes the NPZ/evidence pair only after bitwise-repeatability and provenance checks. Acquisition/preparation, canonical Audio Embedding, and raw cosine generation are complete; refer to the linked experiment evidence for recorded outputs.

The canonical Audio Embedding artifact `artifacts/calibration-v1-audio-embeddings.npz` and machine-readable evidence were generated from the completed 50-song cohort and are preserved as experiment outputs. Source, prepared, and playback audio remain outside Git.

## 이후 단계

1. NSUAI-36: 곡별 source/license/길이 검증이 끝난 표본과 확정 프로토콜을 준비한다.
2. NSUAI-37: 새 표본과 generation/profile로 track/query raw cosine을 측정하고 개별 비교값과 분포 evidence를 보존한다.
3. NSUAI-38: 승인된 blind listening protocol에 따라 평가하고 평가자별 원자료와 disagreement를 보존한다.
4. NSUAI-39: 새 분포와 청취 evidence로 candidate-independent monotonic 변환 후보를 비교한다. 이 문서는 변환식을 선택하지 않는다.
5. NSUAI-40: 선정된 내부 변환 버전과 외부 resultVersion 대응 및 evidence를 정리한다.

과거 FMA 30초 표본과 삭제된 FMA raw evidence는 새 calibration 입력으로 사용하지 않는다. Phase A 6곡은 기술 검증 fixture로만 유지하고 cohort에서 제외한다. Calibration 단계에서도 전체 vector를 문서에 복사하지 않는다. 개별 pairwise score와 evaluation row는 sample/query identity 및 생성 환경과 연결된 machine-readable evidence로 별도 보존한다.
