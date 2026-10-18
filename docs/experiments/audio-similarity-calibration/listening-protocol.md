# Listening evaluation protocol

## 상태와 범위

Calibration listening evaluation is completed: 16 ACTIVE queries, six fixed ranks per query (1, 2, 25, 26, 49, 50), 96 pairs, three evaluators, 288 ratings, and zero unable_to_judge responses. Likert responses are not directly transformed into user-facing 0-100 values.

평가 대상은 representative synthetic scenario benchmark의 ACTIVE v1 16개와 calibration cohort의 60초 prepared segment 쌍이다. ACTIVE 16개 영어 입력은 Raw 및 Structured Interpretation과의 semantic fidelity review를 마쳤고 `approved_for_calibration_v1_experiment` 상태로 calibration v1 실험 입력에 고정했다. RESERVE/REPLACE 4개는 `not_reviewed` draft로 이번 승인 범위 밖이다. 2026-10-16 ACTIVE 16개의 MSCLAP 2023 Text Embedding 생성을 완료했으며 실행 identity·tokenizer preflight·출력 검사는 [Text Embedding evidence](./text-embedding-evidence.json)에 기록했다. 이는 cosine 검색 성능 검증이나 production query 확정을 뜻하지 않는다. 50-song acquisition/preparation, Audio Embedding, raw cosine 계산, 96-pair 청취 평가와 calibration analysis는 완료됐다. Pearson(raw cosine vs 3인 평균)=0.502, Spearman=0.524, top/mid/bottom mean human rating=2.854/2.375/1.448다. Final display-score calibration은 not finalized이며 provisional transform만 있고 independent validation은 수행하지 않았다. 이 자료는 실제 사용자 요청을 대표한다고 주장하지 않는다. 평가 화면에는 evaluator에게 raw cosine, rank, 점수 구간, 후보 선택 순위를 노출하지 않는다. 현재 50곡은 calibration cohort로만 사용하며, 그 분포와 이 청취 평가는 transformation 선정 자료다. 최종 transformation 선택 후에는 별도의 독립 validation cohort로 검증하고, 현재 calibration cohort를 독립 validation evidence로 재사용하지 않는다. 별도 cohort의 크기·구성 및 validation에서 재사용할 query/evaluation material은 결과 확인 전에 기록한다.

## 모델 입력과 재생 입력의 일치

Audio Embedding은 manifest의 중앙 60초 prepared 파일을 공통 `AudioEmbeddingGenerator`에 입력하지만, cosine에 반영되는 파형은 그 파일의 처음 56초뿐이다. generator는 그 구간을 산술 평균으로 mono downmix하고 44.1 kHz로 resample한 뒤 7초 PCM float32 WAV 8개로 나누어 MSCLAP에 전달한다. 따라서 evaluator는 prepared 60초 파일 전체를 재생하지 않는다. 마지막 4초는 Embedding에 포함되지 않으므로 사람 평가에도 포함하지 않는다.

각 평가 sample의 playback은 generator와 같은 decode/downmix/resample 경로에서 얻은 `[0초, 56초)` 파형이어야 한다. 가장 직접적인 재생 자료는 MSCLAP에 실제 전달한 8개 PCM chunk를 시간 순서대로 이어 붙인 56초 playback artifact다. 별도 loudness 처리, crop, resampling 또는 손실 재인코딩을 더하지 않는다. artifact는 local ignored 경로에 보관하고 SHA-256을 계산한다. 파일 생성 시 이 경로를 보존할 수 없다면, 기존 공통 generator의 동일한 전처리 결과를 보존하는 방법을 실험 실행 전에 마련해야 하며 원본 60초를 그대로 들은 결과를 같은 playback 조건으로 간주하지 않는다. 이는 ADR-0007의 Embedding 정책을 바꾸지 않고 사람에게 제시하는 파형을 모델의 실제 분석 파형과 맞추기 위한 기록 조건이다.

Raw cosine is computed by L2-normalizing each text vector and taking its dot product with the final L2-normalized Audio vectors. `compute_similarity()` and `ClapModel.similarity()` are not used because they return logit-scaled values. Raw cosine calculation is complete; retrieval-performance validation has not been performed, and the production query is not finalized.

Text Embedding evidence는 저장소의 canonical runner에서 clean worktree로 생성했고, 실행 당시 clean implementation commit은 `61790c4821aff6a4a6e6084f7c9f3457ee2a0320`이다. GPT-2 tokenizer snapshot은 `607a30d783dfa663caf39e06633721c8d4cfcd7e`로 고정했으며, 실제 snapshot 파일 및 runtime tokenizer serialization SHA-256, MSCLAP source/config와 checkpoint identity는 evidence에 기록한다. Audio Embedding과 raw cosine은 생성했으며 production ranking 성능 검증은 수행하지 않았다. 이 SHA는 실제 runner를 실행한 execution/implementation commit이며, 최신 실행 결과를 기록한 evidence/document commit 2f46a94b137898a3b8a318234b0e5fa5d03bc58e과 구분한다.

Text Encoder 자원은 README의 bootstrap 명령으로 evidence에 고정된 tokenizer/checkpoint revision과 file hash를 준비한다. Canonical runner는 Hugging Face offline 상태를 import 시점부터 적용한 별도 프로세스에서 cache snapshot identity를 확인한 뒤 실행하며, cache가 없거나 revision/hash가 다르면 추론 전에 중단한다. Tokenizer, GPT-2 weight, checkpoint lookup은 local-only 조건을 사용한다. 기본 실행은 기존 canonical NPZ/evidence pair를 덮어쓰지 않는다. `--overwrite`를 지정해도 이전 pair가 유효하고 새 NPZ의 decoded content digest가 기존 값과 같은 경우만 교체한다. NPZ file SHA-256은 저장 bytes 무결성을, content digest는 decoded embedding·dtype·shape·query ID 순서를 식별하며, ZIP timestamp 차이만으로 같은 결과를 거부하지 않는다. Content digest 차이 또는 validation 실패는 기존 결과를 보존하고 중단한다.

## 실험 입력의 불변 identity와 증거 연결

실제 실행 시 version label만으로 입력을 식별하지 않는다. 실험 시작 전에 추적 파일의 변경을 commit하고 calibration 입력·검증 코드가 있는 worktree를 clean 상태로 둔다. Evidence에는 repository 식별자와 full Git commit SHA, 그리고 아래 파일 각각의 **저장된 bytes 기준 SHA-256**을 기록한다. Git commit은 commit된 파일을 찾게 하고, 파일 hash는 실제 읽은 bytes를 직접 확인하게 한다.

- `manifest.json`, `event-queries.json`, 두 schema, `listening-protocol.md`, 통합 validator 및 ranking/sampling 실행 코드의 SHA-256
- sample별 원본 Audio SHA-256 (`manifest.source_sha256`), 중앙 60초 prepared Audio SHA-256 (`manifest.prepared_sha256`), 실제 playback artifact SHA-256 및 재생 구간 `[0, 56)`
- Embedding 입력은 prepared SHA와 일치하는지 확인하고 기록한다. `AudioEmbeddingGenerator`가 반환하는 `metadata.source_sha256`은 호출한 파일 bytes의 hash다. 따라서 prepared 파일을 넘겼다면 이는 원본 취득 파일의 `manifest.source_sha256`가 아니라 `manifest.prepared_sha256`와 일치해야 한다.
- generator의 `preprocessing_version`과 전체 `generation_profile`, MSCLAP model/version, checkpoint revision과 checkpoint 파일 SHA-256, 관련 package 버전
- Text tokenizer의 resolved snapshot revision, 실제 존재하는 tokenizer/model-config 파일별 SHA-256, runtime tokenizer serialization SHA-256, MSCLAP source/config SHA-256 및 text_len/EOS/padding/truncation 정책
- 기존 `query_set_version`과 `active_set_version`, 실험 당시 `event-queries.json` 저장 bytes의 SHA-256, full Git commit SHA 및 clean worktree 상태
- query별 실제 Text Encoder 입력 문자열, `query_id` 및 `draft_version`, query 파일 hash, Text model/checkpoint/profile identity, 생성된 Text Embedding을 보존한다면 그 artifact identity/hash
- cosine 결과의 query/sample ID, 두 Embedding identity, raw cosine; 각 query의 전체 ranking과 ranking/tie-break 코드 identity; stratified/random pair ID, sampling 규칙·PRNG·seed·입력 모집단 및 최종 순서표
- playback/rating row와 정확한 query/sample ID 및 playback artifact SHA-256의 연결. 원본·prepared/playback Audio와 대규모 embedding binary는 Git에 추가하지 않는다. 단, 16×1024 float32인 canonical calibration Text vector(61,228 bytes)는 후속 cosine 입력을 정확히 복원하기 위해 `docs/experiments/audio-similarity-calibration/artifacts/calibration-v1-text-embeddings.npz`에 예외적으로 Git 보존한다. cosine 전에 evidence의 SHA-256, query_id 순서, shape/dtype, finite 여부와 execution identity를 대조하며, 불일치하면 사용을 중단한다. 추가로 실험 입력 파일별 SHA-256과 manifest의 sample ID를 evidence에 남긴다. 실행 중 생성되는 ranking, 표본 목록, playback 순서와 rating의 실제 결과도 당시 값 그대로 보존한다. 설정 이름, manifest version 또는 seed만으로 파일 내용·실행 순서·결과를 재현했다고 간주하지 않는다. 현재 Audio acquisition/preparation, Audio Embedding, raw cosine, listening evaluation, and calibration analysis are completed. Final display-score calibration is not finalized; independent validation has not been performed.

## 표본 추출

The calibration artifact records each query ranked by descending raw cosine. Ties use manifest `sample_id` ASCII order; the frozen mapping preserves stratified pairs at ranks 1/2, 25/26, and 49/50. These experiment ranks do not mean production query implementation or ranking-performance validation is complete.

- Top: rank 1, 2
- Middle: rank 25, 26
- Bottom: rank 49, 50

ACTIVE v1 16개 기준 전체 cosine pair는 50곡 × 16 query = 800개다. query별 rank 1·2, rank 25·26, rank 49·50을 추출하면 최대 16 × 6 = 96쌍이다. 같은 query ranking에서는 각 rank가 서로 다른 sample 하나에 대응하므로 stratified 집합에서 중복 pair가 발생하면 이를 임의 대체하지 말고 입력/ranking 오류로 처리해 원인을 해결한 뒤 다시 추출한다. Stratified 집합을 먼저 확정하고, 추가 무작위 표본은 그 집합을 제외한 나머지 eligible pair 모집단에서 비복원 추출한다.

현재 문서의 무작위 표본 수 “20–40쌍”은 범위일 뿐이다. 저장소의 현재 protocol, ADR, Roadmap 또는 NSUAI-36 근거에서 이 범위의 선택 근거나 단일 count를 확인하지 못했다. 따라서 이는 실행 가능한 고정 표본 계획이 아니며, 20/30/40 중 어느 수도 임의로 선택하지 않는다. 실제 cosine/ranking 결과를 보기 전에 정확한 random count를 결정하고 승인된 protocol에 기록해야 한다. 그 결정 전까지 116–136 unique pairs와 348–408 ratings는 가능한 범위의 산술 예시일 뿐, 확정 workload가 아니다.

재현 가능한 실행을 위해 표본 추출 전 다음을 고정·기록한다: 위 입력 파일 hash와 commit, 50개 track ID와 16개 query ID, 각 query의 50개 전체 ranking과 그 생성 코드/tie-break 버전, 중복이 없음을 확인한 stratified pair ID 목록, random eligible pair ID 전체 집합 및 canonical ordering 규칙, 정확한 표본 수, sampling algorithm 및 PRNG와 버전, seed. 결과에는 실제 선택된 pair ID 목록과 ordering을 보존한다. 이 정보가 없으면 seed만으로 추출을 재현한다고 간주하지 않는다. random pair 모집단의 canonical ordering은 ASCII query_id 오름차순, 각 query 안에서 ASCII sample_id 오름차순으로 정한다. 무작위 선택은 stratified pair와 겹치지 않는다.

3명의 evaluator가 모든 고유 쌍을 각각 평가한다면 확정된 pair 수의 3배가 rating 수다. 현재 random count가 결정되지 않았으므로 348–408건은 workload 범위 예시로만 남긴다. 실행 전 확정 pair 수, evaluator 수, pair별 evaluator 배정표를 기록한다.

분포 전체의 상·중·하위 표본을 확보하면서 query별 차이도 놓치지 않도록 두 sampling 방식을 함께 사용한다. 무작위 표본의 query별 최소/최대 배분 규칙은 아직 확정되지 않았다. 적용할 경우 표본 추출 전에 규칙을 고정하고 기록하며, 규칙이 확정되기 전에는 결과를 임의로 query 간 재배분하지 않는다. 변환 후보 간 경계 주변 sampling은 후보 변환이 NSUAI-39에서 구체화된 후 별도 라운드로만 검토한다. ACTIVE 16개는 coverage와 listening workload를 고려한 engineering v1의 실용적 규모이며 통계적으로 최적이거나 충분하다는 검증 결과는 없다.

## Blind 제시와 재생 순서

- 화면에는 Event 원문과 오디오를 제시하되 cosine, rank, raw score stratum, genre/mood annotation은 제시하지 않는다.
- 오디오 재생 순서는 evaluator와 session별로 무작위화한다. 재현을 위해 실제 생성된 evaluator/session별 순서표를 local/private evaluation record에 보존한다. seed만 보존하는 경우에는 PRNG 및 구현 버전도 함께 기록한다. Event query 순서와 query 안의 sample 순서도 해당 순서표에 포함한다.
- 평가자는 곡 제목·artist 및 다른 evaluator의 응답을 보지 않는다.
- Audio 문제, query 모호함, 판단 불가 사유를 별도 메모로 기록할 수 있다.
- 같은 query에 여러 sample을 듣는 경우 순서 효과를 줄이도록 query/sample 순서를 무작위화한다.

## 평가 항목

5점 Likert scale을 사용한다. 기준은 Event 요청과 음악이 얼마나 잘 어울리는지를 판단하는 ordinal label이며 확률이나 정밀한 수치 효용으로 해석하지 않는다.

1. 전혀 어울리지 않음
2. 대체로 어울리지 않음
3. 애매하거나 일부만 어울림
4. 대체로 잘 어울림
5. 매우 잘 어울림

별도 선택값으로 “판단 불가”를 제공한다. 선택 이유는 선택적으로 짧은 자유 메모로 남긴다. 요청에 없는 정밀 BPM이나 새 속성을 evaluator에게 유도하지 않는다. Label은 음악-요청 적합성 판단을 위한 실험 관측이며 raw cosine 순위를 변경하는 직접 규칙이 아니다.

## Evaluator와 원자료

가능하면 3명의 evaluator가 독립적으로 평가한다. 한 명만 참여하면 exploratory 한계로 기록한다. 두 명인 경우 불일치 사례를 제3자 없이 임의 다수결 처리하지 않는다. Evaluator ID는 공개 문서에서 pseudonym 처리한다. “가능하면 3명”은 고정 cardinality가 아니므로 실제 evaluator 수와 pair별 배정을 평가 시작 전에 기록하고, 해당 수를 기준으로 rating workload를 계산한다.

각 rating row에는 최소 query_id, sample_id, evaluator_id, blinded presentation order, Likert/판단불가 응답, optional note, 평가 시각/환경 식별, 재생 완료 여부, playback artifact SHA-256 및 `[0초, 56초)` 범위를 기록한다. 평가자가 들은 artifact hash가 cosine pair의 sample 및 manifest `prepared_sha256`와 연결되는지 확인한다. Evaluator별 원자료를 덮어쓰거나 합산값만 남기지 않는다. Disagreement는 평가자별 값과 함께 보존하며 평균 하나로 숨기지 않는다. 평가자 간 일치도와 집계방법은 실제 표본을 본 뒤 명시하고, 결과가 없는 상태에서 수치를 미리 정하지 않는다.

## 저장과 한계

NSUAI-38 evidence는 각 evaluation sample을 query/sample ID, 정확한 model text, source/prepared/playback artifact hash 및 입력 commit으로 연결하고 selection strata 및 추출 seed, evaluator pseudonym, 개별 rating, disagreement, 평가 환경, exclusions 및 제한사항을 machine-readable 형식과 Markdown 요약으로 보존한다. 전체 음악 vector는 Git에 넣지 않는다. Audio 원본과 prepared/playback 파일은 local ignored 경로에만 둔다.

청취 평가는 소규모로 추출한 쌍의 사람 판단이다. 전체 운영 추천 품질, 모든 장르/행사 분포 또는 사용자 모집단을 대표한다고 주장하지 않는다. Likert 값은 표시 점수 변환식, threshold, breakpoint 또는 calibration parameter로 직접 복사하지 않는다. NSUAI-39에서 새 raw cosine 분포와 함께 검토할 evidence 중 하나로 사용한다.
