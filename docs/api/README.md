# Python AI 서버 API

> 2026-10-05 현재 AI 측 방향: [CLAP 중심 곡 추천](CLAP_RECOMMENDATION_DIRECTION.md)을 우선 참고합니다. 아래 항목 평균·Spring Ranker·아티스트 집계·후보 비교 설명은 이전 계획이며, 이번 변경안은 팀 전체 합의 전입니다. BPM·리듬은 초기 순위에서 보류하고 추천 이유는 검증 가능한 근거로 유지합니다.


FastAPI 서버와 health API는 구현되어 있다.
임베딩 저장·DB 후보 검색은 동기 서비스와 CLI로 검증했으며 업무 HTTP API는 구현 전이다.
① AI에서 먼저 설계하고 백엔드가 검토하는 방식으로 진행한다.
등록·검색은 처리 완료 후 결과를 반환하는 동기 방식을 사용한다.
[연동 계약 초안](AUDIO_JOB_CONTRACT.md)의 필드·엔드포인트는 검토용 제안이다.

2026-10-04 [백엔드 전달용 권장안](AUDIO_SYNC_BACKEND_HANDOFF.md)을 구체화했다.
파일 직접 전달(multipart), 등록·교체 통합 PUT, 버전·삭제 기록과 상태 조회를 권장한다.
새 권장안의 경로와 규칙을 우선 검토하며 업무 API 구현은 다음 단계다.

백엔드 피드백으로 audioRevision·모델 버전 분리와 PROCESSING→ACTIVE 전환,
최종 추천용 50~100개 retrieval 후보 방향을 반영했다.
processing/ready/failed/deleted 조회, revision별 벡터 보관, ACTIVE revision 쌍 후보 제한을 반영했다.
v1·v2를 함께 보관하고 Backend v2 ACTIVE 커밋 확인 후 v1을 정리한다. 모두 구현 전이다.
활성 확인·정리 API, 정리 유예기간, stale 기준 및 세부 DTO는 추가 설계가 필요하다.

## 책임 경계

추천 이유·후보 비교 설명은 AI가 담당하며, 최종 순위 확정 후 추가 호출과 초기 템플릿 사용을
[설명 계약 제안](RECOMMENDATION_EXPLANATION_CONTRACT.md)으로 정리했다.
백엔드 합의 전이며 업무 API 구현이나 LLM 사용을 확정한 문서가 아니다.

Spring Boot는 음악 ID·아티스트 소유 관계·인증/인가·서비스 화면 연결을 담당한다.
Python AI 서버는 전처리·임베딩·pgvector 저장·유사도 검색을 담당한다.

## 합의할 항목

| 항목 | 관련 이슈 | 상태 |
| --- | --- | --- |
| 동기 처리 방향 | NSUAI-17 | 사용자 동기 결정 반영 |
| Audio revision·수정/삭제·전환 후 정리 | NSUAI-25 / NSUAI-26 | 결정 반영, 구현 전 |
| 요청·응답·오류·타임아웃 | NSUAI-27 / NSU-63 | 초안 검토·업무 API 구현 필요 |

저장 책임은 [ADR 0001](../adr/0001-pgvector-adoption.md),
처리 방식은 [ADR 0006](../adr/0006-asynchronous-audio-processing.md)을 참고한다.
2026-10-04 Linear NSUAI-25·26·27, NSU-63과 연결 GitHub 이슈에 결정·미완료 기준을 반영했다.
음악 검색 표시 점수는 임시 유사도 지표이며 종합 적합도나 신뢰 확률이 아니다.
`AudioClassifier.classify()`의 `probability`는 비교 라벨 집합의 softmax 상대점수다.
