# Audio Similarity Calibration Dataset 준비

## 목적과 상태

이 자료는 NSUAI-36 “Calibration 표본 및 청취 평가 프로토콜 준비”를 위한 calibration 계획과 evidence다. calibration 후보 선정은 완료되어 PASS 후보 50곡이 확정됐다(Incompetech 2곡, 새 FMA 전체곡 20곡, Wikimedia Commons 22곡, ccMixter 6곡). 후보 선정 완료는 실제 Audio 취득이나 calibration 실험 완료를 뜻하지 않는다.

Event query는 실제 사용자 데이터가 아니라 대표적인 합성 시나리오 benchmark다. 기존 draft inventory 20개를 모두 보존하며 engineering calibration v1의 ACTIVE는 16개, RESERVE는 2개, REPLACE 후보는 2개다. 16개는 통계적으로 최적이거나 충분하다고 검증된 수가 아니며 coverage와 청취 workload를 고려한 실용적 규모다.

## 현재 기준

- Accepted 서버 협의 012에 따라 순위는 raw cosine으로 결정한다. Spring은 순서를 다시 정렬하지 않는다.
- 사용자 표시용 음악 유사도는 후보 독립 고정 변환이지만, 공식·threshold·breakpoint·parameter는 NSUAI-12 실험 전 확정하지 않는다.
- ADR-0007의 입력 길이 60–80초를 유지한다. 본 계획의 offline segment 준비는 중앙의 정확한 60초를 선택하는 것으로, 사용자 업로드 정책을 바꾸지 않는다.
- calibration 후보 선정: 완료, PASS 50곡
- Audio 다운로드: 아직 안 함
- source SHA-256 기록: 아직 없음
- 실제 decoder 기반 decode 검증: 아직 안 함
- deterministic 중앙 60초 prepared Audio 생성: 아직 안 함
- Audio MSCLAP Embedding 생성: 아직 안 함 (ACTIVE 16개 Text Embedding은 2026-10-15 생성, 아래 Event query 상태 참조)
- raw cosine 실험: 아직 안 함
- 청취평가: 아직 안 함
- 사용자 표시용 0~100 transformation 선정: 아직 안 함

따라서 candidate selection complete ≠ calibration experiment complete다. 후보 목록 확정과 Audio 준비·생성·평가 결과를 별도 단계로 관리한다. Audio/cosine/listening 실행 전에는 clean worktree의 Git commit SHA와 manifest/query/schema/protocol/실행 코드의 파일 bytes SHA-256을 기록하고, source·prepared·playback Audio도 각각 SHA-256으로 연결한다. 청취평가는 공통 AudioEmbeddingGenerator가 분석하는 동일한 전처리 파형의 `[0초, 56초)`만 대상으로 하며 prepared 60초 전체를 재생하지 않는다. 세부 기록 조건은 [청취 평가 프로토콜](./listening-protocol.md)을 따른다. Audio input 및 playback identity는 아직 생성되지 않았으며, Text Embedding identity는 [별도 evidence](./text-embedding-evidence.json)에 기록했다.

현재 PASS 50곡은 calibration cohort다. 이 cohort의 raw cosine 분포와 청취평가는 transformation 선정 자료이며 독립 validation 자료가 아니다. 최종 transformation 선택 후 별도로 구성한 독립 validation cohort에서 검증한다. 현재 50곡을 validation holdout으로 간주하지 않으며, 별도 validation cohort의 크기와 구성은 아직 정하지 않았다.

## Event query benchmark

Event query 자료는 다음 세 단계를 실험용으로 분리한다. 아래 구조의 이름은 calibration 자료의 의미 라벨이며 Spring API payload field 이름이나 API schema가 아니다.

저장소 루트에서 `uv run --isolated --with jsonschema==4.26.0 python -m scripts.matching.validate_calibration` 한 명령으로 전체 calibration 검증을 실행한다. 고정된 `jsonschema` 버전을 격리된 uv 실행 환경에 준비하므로 새 checkout에서도 추가 설치 단계 없이 실행할 수 있다. `requirements-dev.txt`에도 같은 버전을 고정한다. 명령은 manifest/Event query JSON Schema, `sample_id`/`query_id` 고유성, complete cohort 내 credited artist 최대 2곡, `source_url` 및 `(provider, provider_track_id)` 고유성, query 간 정규화한 `(event_type, event_description_ko, desired_genre)` 조합 고유성, cohort/query 교차 규칙, Structured Interpretation의 non-blank 상태와 Raw evidence를 검사한다. 모든 query의 evidence가 해당 query의 현재 Raw에 포함되는지 확인하고, ACTIVE query의 `desired_genre` 참조 대상도 검증한다. 또한 complete cohort의 각 sample에서 non-blank `license_name`과 `license_url`, 명시적인 `attribution_required`, 필요한 경우 non-blank `attribution`을 검사한다. Raw 조합과 artist 표기는 공백을 정리하고 대소문자를 무시해 비교한다. ACTIVE query는 `review_status: reviewed_for_raw_support`여야 하며, 이 조건은 Event query schema가 검증한다. JSON Schema는 서로 다른 레코드 간 ID·실제 트랙 identity, artist 최대 개수나 Raw 문자열과 annotation evidence의 교차 필드 일치를 표현하지 못하므로 통합 validator가 추가로 검사한다.

각 Structured Interpretation 속성의 상태는 calibration 검수 근거를 나타낸다. `interpreted`는 null·빈 문자열·공백 문자열·빈 배열·빈 문자열 항목이 없는 해석값과 1개 이상의 non-blank 현재 Raw excerpt가 필요하고, `not_requested`는 null 값과 빈 evidence를 요구한다. `unable_to_interpret`는 요청 근거가 있으나 해석할 수 없는 상태이므로 null 값이면서 1개 이상의 non-blank 현재 Raw excerpt가 필요하다. 통합 validator는 제공된 excerpt가 동일 query의 현재 `raw_service_input`에 실제로 포함되는지 확인한다. `desired_genre`는 Raw 값이 존재할 때에만 고정 pointer로 참조한다.

통합 validator는 표준 JSON에서 허용되지 않는 `NaN`, `Infinity`, `-Infinity`뿐 아니라 유한 범위를 벗어나 Python에서 무한대로 변환되는 지수 표기도 입력 단계에서 거부한다. `source_catalog_duration`은 양수이며 complete 후보에서는 60초 이상이다. 성공적으로 decode한 source의 `decoded_duration`은 decoder가 반환한 정수 `decoded_frame_count / source_sample_rate`로 기록하고 두 값의 관계를 엄격히 검사한다. `source_sample_rate`와 `source_channels`는 null 또는 양의 정수, frame index는 null 또는 0 이상의 정수다. prepared hash·duration·시작/끝 frame 중 하나라도 채워지면 source hash·decode frame count·sample rate·channel·양 끝 frame·prepared hash·duration이 모두 있어야 하고, prepared duration은 정확히 60초여야 한다. 취득 전에는 decode/prepared metadata가 null이다. 취득 파일의 `source_file_size`(선택 기록)는 null 또는 0 이상의 정수다. `cohort_target`은 정확히 50이며 그 밖의 합리적 상한은 현재 정하지 않았다.

`source_url`, `license_url`, source metadata URL은 absolute HTTP(S) URL이어야 한다. URI 형식 검사와 함께 scheme·authority가 빠진 상대 경로 및 공백 포함 URL도 schema에서 거부한다.

`historical_raw_draft`는 최초 synthetic Raw draft 20개의 snapshot으로 calibration 문서 이력을 보존하며, 실제 사용자 입력 로그나 production revision history가 아니다. `raw_service_input`은 현재 calibration 단계에서 사용하는 Raw 입력이다. snapshot 생성 직후에는 두 값이 같았고, 현재는 ACTIVE 16개 중 15개에 검수한 Raw v1을 반영해 해당 항목에서 두 값이 다르다.

1. `raw_service_input`: 대표 합성 시나리오의 행사 종류·한국어 행사 설명·희망 Genre 의미를 보존한다. 이는 실제 사용자 입력이나 실제 사용자 데이터가 아니다. ACTIVE v1은 16개이며 Raw 수정안은 15개에 반영했고 event-07은 유지했다. Genre 지정은 12개, 미지정은 4개다. 이 수와 비율은 통계적으로 최적이라고 검증된 값이 아니다.
2. `structured_interpretation`: calibration-only 의미 주석이며 production AI 결과나 Spring API 계약이 아니다. 속성은 mood, tempo, desired_genre, instrument_preference, vocal_preference, acoustic_electronic, dynamic_progression, usage_context, rhythmic_character, activity_character다. ACTIVE 16개는 Raw 근거 검수를 완료했고 RESERVE/REPLACE는 미검수 placeholder로 유지한다.
3. `msclap_model_input`: 사람이 작성한 영어 calibration 입력이다. ACTIVE 16개는 semantic fidelity 검수를 마쳤고, `approved_for_calibration_v1_experiment`로 calibration v1 Text Embedding/cosine 실험 입력으로 승인했다. 이는 모델 성능 검증이나 production query 확정이 아니다. RESERVE/REPLACE 4개는 `draft_not_confirmed_model_input` 및 `not_reviewed`를 유지한다.

현재 자료는 실제 사용자 데이터가 아닌 representative synthetic scenario benchmark다. ACTIVE 16개의 Structured Interpretation Raw 근거 검수, 영어 입력 semantic fidelity 검수 및 calibration v1 실험 입력 승인은 완료했다. 2026-10-15 ACTIVE 16개를 MSCLAP 2023 Text Encoder로 batch 생성했고, 결과와 실행 identity는 [Text Embedding evidence](./text-embedding-evidence.json)에 기록했다. 출력은 `[16, 1024]`, `float32`, CPU였으며 Text Encoder 출력에 L2 normalization을 적용하지 않았다. 같은 16-query batch의 반복 출력은 정확히 같았지만, batch와 single 입력은 bitwise 동일하지 않았다(상세 차이는 evidence 참조). 임의 허용 오차는 정하지 않았으므로 이후 cosine 실행은 이 evidence의 batch artifact를 입력으로 사용해야 한다. 임베딩 artifact는 ignored `tmp/calibration-v1-text-embeddings.npz`에만 저장했고 Git에 포함하지 않는다. Audio Embedding/acquisition, cosine 계산, 검색 성능 검증, 청취 평가와 transformation 선정은 미수행이며, 입력은 production query로 확정되지 않았다.

같은 Text Embedding 검증 경로는 저장소 루트에서 Python 3.11 및 프로젝트의 MSCLAP CPU 의존성이 설치된 환경에서 `python -m scripts.embedding.validate_calibration_text_embeddings`로 실행한다. 실행 전 통합 calibration validator를 수행하고, dirty worktree에서는 모델 추론을 시작하지 않는다.


Text Embedding evidence는 temporary harness가 아닌 저장소의 canonical runner에서 생성했으며, clean working tree의 implementation commit `d3fa00b130502e615ad9ed63fde8ce483321c90b`을 실행 identity로 기록한다.

## Dataset 구성

1차 목표는 50곡이다. 같은 아티스트는 가급적 1곡, 최대 2곡으로 제한한다. Complete 상태의 통합 validator는 manifest `artist` 표기를 공백 정리 및 대소문자 무시 후 세어 최대 2곡을 강제한다. artist alias와 여러 기여자 표기의 실체 식별은 자동 판정하지 않으므로 후보 선정 기록에서 사람이 검토한다. 장르·분위기, 보컬/인스트루멘탈, electronic/acoustic, 느림/중간/빠름 인상의 편중은 수치화된 완료 조건이 아니라 후보 구성 시 사람이 검토하는 다양성 기준이다. 제공자 metadata와 사람이 붙인 label을 별도로 보존하고 출처가 불분명한 label은 unknown으로 둔다. Source metadata의 tempo는 표본 구성 설명으로만 쓸 수 있으며, BPM/Rhythm ranking 구현을 뜻하지 않는다.

정식 calibration 후보는 Incompetech 2곡, 새 FMA 전체곡 20곡, Wikimedia Commons 22곡, ccMixter 6곡으로 총 50곡이다. `candidate_selection_complete`는 정확히 50개이며 각 sample의 `source_catalog_duration`이 60초 이상, `commercial_use_status`가 `allowed`, `rights_status`가 `confirmed_from_official_metadata`이고 `sample_id`, `source_url`, 그리고 값이 있는 경우 `(provider, provider_track_id)`가 모두 고유한 현재 유효 후보 집합을 뜻한다. 각 sample은 다시 확인 가능한 non-blank `license_name`과 `license_url`, 명시적인 boolean `attribution_required`를 가져야 하며, attribution이 필요한 경우에만 non-blank `attribution`을 요구한다. 현재 50개 모두 이 license URL 근거 구조를 사용한다. Validator는 해당 근거 필드의 존재·형식만 확인하며, URL 대상의 실제 라이선스 적용 범위나 페이지 내용까지 자동 판정하지 않는다. 이후 다른 provider에서 다른 라이선스 근거 모델을 쓸 필요가 생기면 complete 상태를 사용하기 전에 해당 근거 구조를 별도 검토해야 한다. 위 통합 검증 명령은 schema의 개수·길이·권리·라이선스 상태 조건과 논리 ID·실제 트랙 식별자 고유성을 함께 검사한다. `provider_track_id`가 없으면 이를 전역 고유값으로 강제하지 않고 `source_url` 고유성으로 fallback한다. 재검증으로 sample이 길이·권리·상업 사용 기준에 부적격해지면 이 상태를 유지하지 않고 `candidate_selection_incomplete`로 바꾼다. 적격 대체 후보를 검증해 유효한 50곡을 다시 확보한 뒤에만 complete로 되돌린다. `source_catalog_duration`은 취득 전 catalog 기반 기준이며, Audio acquisition 후 실제 decode 및 `decoded_duration` 검증은 별도 단계에서 수행한다. ccMixter는 개별 트랙의 길이·라이선스·attribution·source dependency를 확인한 항목만 포함하며, sample/remix source chain이 불명확한 트랙은 포함하지 않는다. 기존 FMA 30초 Historical 자료는 사용하지 않고, Phase A 6곡은 기술 검증 fixture로만 유지하며 calibration cohort에서 제외한다. HOLD 판정된 The Wind that Shakes the Barley는 검토 이력에만 보존하고 PASS cohort 및 manifest에서는 제외했다. Audio 다운로드, source SHA 기록, decode 검증, prepared Audio 생성, MSCLAP Embedding, cosine 실험, 청취평가 및 transformation 선정은 아직 수행하지 않았다.

`candidate_selection_complete`는 취득 전 catalog 검증 단계에서도 사용할 수 있다. 현재 `acquisition_method`는 `not_acquired` 50개이며 source SHA, decode 결과, prepared 결과는 모두 null이다. `not_acquired` sample에는 취득·decode·prepared 파일 metadata를 기록하지 않는다. 취득 방법이 `official_direct_download` 또는 `other_confirmed_method`이면 원본 `source_sha256`가 필요하다. decode 성공을 기록할 때는 `decoded_duration`, 정확한 정수 `decoded_frame_count`, decoder의 `source_sample_rate`, `source_channels`가 함께 있어야 하며 `decoded_duration == decoded_frame_count / source_sample_rate`를 만족해야 한다. complete cohort의 취득 sample은 실제 decode 길이도 60초 이상이어야 한다. 이미 취득한 sample의 decode가 실패했거나 아직 완료되지 않았다면 측정값을 만들지 않고 해당 manifest를 complete로 검증하지 않는다.

## Segment 준비 규칙

이는 offline calibration Dataset 전용 규칙이다. 원본을 실제 decoder로 decode한 frame 수를 N, decoder sample rate를 R이라 할 때 N ≥ 60R인지 확인하고 중앙의 정확히 60초를 선택한다. `decoded_duration`은 N/R로만 기록한다. frame index는 decoder가 반환한 원본 sample rate의 frame 좌표이며, prepared 추출은 이 sample rate/channel을 보존한다. catalog duration은 source page의 표기값이고 실제 decoded duration과 같은 정밀도를 가진다고 보장하지 않으므로 둘을 서로 대체하거나 같다고 강제하지 않는다.

- start_frame = floor((N - 60 * R) / 2)
- end_frame_exclusive = start_frame + 60 * R
- 선택 구간 = [start_frame, end_frame_exclusive)

prepared metadata가 존재하는 sample은 `prepared_frames = segment_end_frame_exclusive - segment_start_frame`이 `60 * R`과 정확히 같고 `prepared_duration`은 60이어야 한다. 시작 frame은 위 중앙 추출식과 같아야 하며 끝은 exclusive 경계로서 `decoded_frame_count` 이하이어야 한다. prepared hash/duration 또는 segment 시작/끝 frame 중 하나라도 있으면 전체 prepared metadata를 채워야 한다. manifest에는 별도 prepared 상태 enum이 없으며, prepared 관련 필드가 모두 null이면 미준비, 하나라도 값이 있으면 완전한 prepared metadata로 검증한다. 실제 50개 후보는 이번 작업에서 변경하지 않았다.

사람이 듣고 “좋은 부분”을 고르지 않는다. 원본 sample rate와 channel을 준비 단계에서 보존한다. 이후 production AudioEmbeddingGenerator가 ADR-0007 전처리를 적용한다. 선택된 segment가 곡 전체를 대표한다고 단정하지 않고 선택 규칙과 한계를 기록한다.

## 파일과 Audio 보관

Audio 원본과 준비본은 local-only 경로인 datasets/calibration/raw/ 및 datasets/calibration/prepared/에 둔다. 현재 root .gitignore의 /datasets/ 규칙이 두 경로를 포함해 무시한다. .gitignore는 수정하지 않는다. Manifest와 evidence는 Git 추적이 가능한 이 디렉터리 아래에 둔다. Audio 파일은 Git에 commit하지 않는다.

## 이후 단계

1. NSUAI-36: 곡별 source/license/길이 검증이 끝난 표본과 확정 프로토콜을 준비한다.
2. NSUAI-37: 새 표본과 generation/profile로 track/query raw cosine을 측정하고 개별 비교값과 분포 evidence를 보존한다.
3. NSUAI-38: 승인된 blind listening protocol에 따라 평가하고 평가자별 원자료와 disagreement를 보존한다.
4. NSUAI-39: 새 분포와 청취 evidence로 candidate-independent monotonic 변환 후보를 비교한다. 이 문서는 변환식을 선택하지 않는다.
5. NSUAI-40: 선정된 내부 변환 버전과 외부 resultVersion 대응 및 evidence를 정리한다.

과거 FMA 30초 표본과 삭제된 FMA raw evidence는 새 calibration 입력으로 사용하지 않는다. Phase A 6곡은 기술 검증 fixture로만 유지하고 cohort에서 제외한다. Calibration 단계에서도 전체 vector를 문서에 복사하지 않는다. 개별 pairwise score와 evaluation row는 sample/query identity 및 생성 환경과 연결된 machine-readable evidence로 별도 보존한다.
