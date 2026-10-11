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
- MSCLAP Embedding 생성: 아직 안 함
- raw cosine 실험: 아직 안 함
- 청취평가: 아직 안 함
- 사용자 표시용 0~100 transformation 선정: 아직 안 함

따라서 candidate selection complete ≠ calibration experiment complete다. 후보 목록 확정과 Audio 준비·생성·평가 결과를 별도 단계로 관리한다.

현재 PASS 50곡은 calibration cohort다. 이 cohort의 raw cosine 분포와 청취평가는 transformation 선정 자료이며 독립 validation 자료가 아니다. 최종 transformation 선택 후 별도로 구성한 독립 validation cohort에서 검증한다. 현재 50곡을 validation holdout으로 간주하지 않으며, 별도 validation cohort의 크기와 구성은 아직 정하지 않았다.

## Event query benchmark

Event query 자료는 다음 세 단계를 실험용으로 분리한다. 아래 구조의 이름은 calibration 자료의 의미 라벨이며 Spring API payload field 이름이나 API schema가 아니다.

저장소 루트에서 `uv run --isolated --with jsonschema==4.26.0 python -m scripts.matching.validate_calibration` 한 명령으로 전체 calibration 검증을 실행한다. 고정된 `jsonschema` 버전을 격리된 uv 실행 환경에 준비하므로 새 checkout에서도 추가 설치 단계 없이 실행할 수 있다. `requirements-dev.txt`에도 같은 버전을 고정한다. 명령은 manifest/Event query JSON Schema, `sample_id`/`query_id` 고유성, cohort/query 교차 규칙, ACTIVE 해석값의 Raw evidence와 `desired_genre` 참조 대상 일치를 검사한다. ACTIVE query는 `review_status: reviewed_for_raw_support`여야 하며, 이 조건은 Event query schema가 검증한다. JSON Schema는 query 간 ID 고유성이나 Raw 문자열과 annotation evidence의 교차 필드 일치를 표현하지 못하므로 통합 validator가 추가로 검사한다.

`historical_raw_draft`는 최초 synthetic Raw draft 20개의 snapshot으로 calibration 문서 이력을 보존하며, 실제 사용자 입력 로그나 production revision history가 아니다. `raw_service_input`은 현재 calibration 단계에서 사용하는 Raw 입력이다. snapshot 생성 직후에는 두 값이 같았고, 현재는 ACTIVE 16개 중 15개에 검수한 Raw v1을 반영해 해당 항목에서 두 값이 다르다.

1. `raw_service_input`: 대표 합성 시나리오의 행사 종류·한국어 행사 설명·희망 Genre 의미를 보존한다. 이는 실제 사용자 입력이나 실제 사용자 데이터가 아니다. ACTIVE v1은 16개이며 Raw 수정안은 15개에 반영했고 event-07은 유지했다. Genre 지정은 12개, 미지정은 4개다. 이 수와 비율은 통계적으로 최적이라고 검증된 값이 아니다.
2. `structured_interpretation`: calibration-only 의미 주석이며 production AI 결과나 Spring API 계약이 아니다. 속성은 mood, tempo, desired_genre, instrument_preference, vocal_preference, acoustic_electronic, dynamic_progression, usage_context, rhythmic_character, activity_character다. ACTIVE 16개는 Raw 근거 검수를 완료했고 RESERVE/REPLACE는 미검수 placeholder로 유지한다.
3. `msclap_model_input`: 기존 영어 문장을 그대로 보존한 사람이 작성한 번역 초안이다. 새 Raw와의 정합성 검수 전이며 `draft_not_confirmed_model_input` / `not_reviewed` 상태다. 확정된 MSCLAP 입력이 아니다.

현재 자료는 실제 사용자 데이터가 아닌 representative synthetic scenario benchmark다. ACTIVE 16개 Structured Interpretation의 Raw 근거 검수는 완료했지만, 영어 MSCLAP model input 검수는 미완료다. MSCLAP cosine calibration 실험도 시작하지 않았다.


## Dataset 구성

1차 목표는 50곡이다. 같은 아티스트는 가급적 1곡, 최대 2곡으로 제한한다. 장르·분위기, 보컬/인스트루멘탈, electronic/acoustic, 느림/중간/빠름 인상의 편중을 줄인다. 제공자 metadata와 사람이 붙인 label을 별도로 보존하고 출처가 불분명한 label은 unknown으로 둔다. Source metadata의 tempo는 표본 구성 설명으로만 쓸 수 있으며, BPM/Rhythm ranking 구현을 뜻하지 않는다.

정식 calibration 후보는 Incompetech 2곡, 새 FMA 전체곡 20곡, Wikimedia Commons 22곡, ccMixter 6곡으로 총 50곡이다. `candidate_selection_complete`는 정확히 50개이며 각 sample의 `source_catalog_duration`이 60초 이상, `commercial_use_status`가 `allowed`, `rights_status`가 `confirmed_from_official_metadata`이고 `sample_id`가 모두 고유한 현재 유효 후보 집합을 뜻한다. 위 통합 검증 명령은 schema의 개수·길이·권리 상태 조건과 객체 내 ID 고유성을 함께 검사한다. 재검증으로 sample이 길이·권리·상업 사용 기준에 부적격해지면 이 상태를 유지하지 않고 `candidate_selection_incomplete`로 바꾼다. 적격 대체 후보를 검증해 유효한 50곡을 다시 확보한 뒤에만 complete로 되돌린다. `source_catalog_duration`은 취득 전 catalog 기반 기준이며, Audio acquisition 후 실제 decode 및 `decoded_duration` 검증은 별도 단계에서 수행한다. ccMixter는 개별 트랙의 길이·라이선스·attribution·source dependency를 확인한 항목만 포함하며, sample/remix source chain이 불명확한 트랙은 포함하지 않는다. 기존 FMA 30초 Historical 자료는 사용하지 않고, Phase A 6곡은 기술 검증 fixture로만 유지하며 calibration cohort에서 제외한다. HOLD 판정된 The Wind that Shakes the Barley는 검토 이력에만 보존하고 PASS cohort 및 manifest에서는 제외했다. Audio 다운로드, source SHA 기록, decode 검증, prepared Audio 생성, MSCLAP Embedding, cosine 실험, 청취평가 및 transformation 선정은 아직 수행하지 않았다.

`candidate_selection_complete`는 취득 전 catalog 검증 단계에서도 사용할 수 있다. `acquisition_method`가 `not_acquired` 또는 `pending`이면 `decoded_duration`은 null이어야 하며 아직 decode를 요구하지 않는다. 취득 방법이 `official_direct_download` 또는 `other_confirmed_method`로 바뀌면 같은 complete cohort 검증에서 `decoded_duration`이 반드시 존재하고 60초 이상이어야 한다. 취득 후 decode 결과가 누락되거나 60초 미만이면 검증은 실패하며, 해당 sample을 교체해 적격 50곡을 확보하기 전까지 상태를 `candidate_selection_incomplete`로 낮춘다. Schema의 이 조건은 manifest 값 일관성을 검사하며, 실제 파일을 decode하거나 기록값의 진실성을 확인하는 검증은 후속 acquisition 절차의 책임이다.

## Segment 준비 규칙

이는 offline calibration Dataset 전용 규칙이다. 원본을 실제 decoder로 decode한 frame 수를 N, sample rate를 R이라 할 때 N ≥ 60R인지 확인하고 중앙의 정확히 60초를 선택한다.

- start_frame = floor((N - 60 * R) / 2)
- end_frame_exclusive = start_frame + 60 * R
- 선택 구간 = [start_frame, end_frame_exclusive)

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
