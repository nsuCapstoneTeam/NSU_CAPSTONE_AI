# 청취 평가 프로토콜 초안

## 상태와 범위

이 문서는 NSUAI-36에서 사전 준비하는 프로토콜 초안이다. 실제 청취 평가는 NSUAI-38에서 수행한다. 이번 작업에서 평가 표본을 재생하거나 평가하지 않았다. Likert 응답을 사용자 표시 0–100 값으로 직접 변환하지 않는다.

평가 대상은 representative synthetic scenario benchmark의 ACTIVE v1 16개와 calibration cohort의 60초 segment 쌍이다. 현재 한국어 raw scenario는 사람 검수한 representative synthetic input이며 ACTIVE 16개 structured interpretation은 Raw 근거 검수를 마쳤다. 영어 model input은 `human_authored_draft_translation` / `not_reviewed` 상태다. 따라서 영어 문장은 평가에 확정된 입력이 아니며, 사람의 검수와 확정 뒤에만 사용한다. 이 자료는 실제 사용자 요청을 대표한다고 주장하지 않는다. 평가 화면에는 evaluator에게 raw cosine, rank, 점수 구간, 후보 선택 순위를 노출하지 않는다. 현재 50곡은 calibration cohort로만 사용하며, 그 분포와 이 청취 평가는 transformation 선정 자료다. 최종 transformation 선택 후에는 별도의 독립 validation cohort로 검증하고, 현재 calibration cohort를 독립 validation evidence로 재사용하지 않는다. 별도 cohort의 크기·구성 및 validation에서 재사용할 query/evaluation material은 결과 확인 전에 기록한다.

## 표본 추출

NSUAI-37이 각 query에 대한 cosine 결과를 생성한 뒤, raw cosine 내림차순 ranking의 rank를 기준으로 query별 다음 위치를 추출한다. 동일 raw cosine의 순서는 ranking을 생성한 기존 검색 경로의 tie-break 규칙을 그대로 사용하며, 표본 추출 단계에서 동점 순서를 다시 정렬하지 않는다. 이 프로토콜의 위치는 각 query ranking의 50개 후보를 전제로 하며 top은 rank 1·2, middle은 중앙에 인접한 rank 25·26, bottom은 rank 49·50이다. 따라서 같은 입력과 같은 ranking이면 항상 같은 stratified pair가 선택된다.

- Top: rank 1, 2
- Middle: rank 25, 26
- Bottom: rank 49, 50

ACTIVE v1 16개 기준 전체 cosine pair는 50곡 × 16 query = 800개다. query별 rank 1·2, rank 25·26, rank 49·50을 추출하면 최대 16 × 6 = 96쌍이다. 같은 query ranking에서는 각 rank가 서로 다른 sample 하나에 대응하므로 stratified 집합에서 중복 pair가 발생하면 이를 임의 대체하지 말고 입력/ranking 오류로 처리해 원인을 해결한 뒤 다시 추출한다. Stratified 집합을 먼저 확정하고, 추가 무작위 표본은 그 집합을 제외한 나머지 eligible pair 모집단에서 비복원 추출한다.

현재 문서의 무작위 표본 수 “20–40쌍”은 범위일 뿐이다. 저장소의 현재 protocol, ADR, Roadmap 또는 NSUAI-36 근거에서 이 범위의 선택 근거나 단일 count를 확인하지 못했다. 따라서 이는 실행 가능한 고정 표본 계획이 아니며, 20/30/40 중 어느 수도 임의로 선택하지 않는다. 실제 cosine/ranking 결과를 보기 전에 정확한 random count를 결정하고 승인된 protocol에 기록해야 한다. 그 결정 전까지 116–136 unique pairs와 348–408 ratings는 가능한 범위의 산술 예시일 뿐, 확정 workload가 아니다.

재현 가능한 실행을 위해 표본 추출 전 다음을 고정·기록한다: 50개 track ID와 16개 query ID의 입력 manifest/query version, 각 query의 50개 전체 ranking과 그 생성 코드/tie-break 버전, 중복이 없음을 확인한 stratified pair ID 목록, random eligible pair ID 전체 집합 및 canonical ordering 규칙, 정확한 표본 수, sampling algorithm 및 PRNG와 버전, seed. 결과에는 실제 선택된 pair ID 목록과 ordering을 보존한다. 이 정보가 없으면 seed만으로 추출을 재현한다고 간주하지 않는다. random pair 모집단의 canonical ordering은 ASCII query_id 오름차순, 각 query 안에서 ASCII sample_id 오름차순으로 정한다. 무작위 선택은 stratified pair와 겹치지 않는다.

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

각 rating row에는 최소 query_id, sample_id, evaluator_id, blinded presentation order, Likert/판단불가 응답, optional note, 평가 시각/환경 식별, 재생 완료 여부를 기록한다. Evaluator별 원자료를 덮어쓰거나 합산값만 남기지 않는다. Disagreement는 평가자별 값과 함께 보존하며 평균 하나로 숨기지 않는다. 평가자 간 일치도와 집계방법은 실제 표본을 본 뒤 명시하고, 결과가 없는 상태에서 수치를 미리 정하지 않는다.

## 저장과 한계

NSUAI-38 evidence는 각 evaluation sample을 query/sample ID로 연결하고 selection strata 및 추출 seed, evaluator pseudonym, 개별 rating, disagreement, 평가 환경, exclusions 및 제한사항을 machine-readable 형식과 Markdown 요약으로 보존한다. 전체 음악 vector는 Git에 넣지 않는다. Audio 원본과 prepared 파일은 local ignored 경로에만 둔다.

청취 평가는 소규모로 추출한 쌍의 사람 판단이다. 전체 운영 추천 품질, 모든 장르/행사 분포 또는 사용자 모집단을 대표한다고 주장하지 않는다. Likert 값은 표시 점수 변환식, threshold, breakpoint 또는 calibration parameter로 직접 복사하지 않는다. NSUAI-39에서 새 raw cosine 분포와 함께 검토할 evidence 중 하나로 사용한다.
