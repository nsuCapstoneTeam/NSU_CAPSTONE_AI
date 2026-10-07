# Python AI 서버 API

> 2026-10-07 이 작업 대화의 사용자 결정, 구현 전. 전체 통과 곡 반환·유사도 정렬·아티스트 집계 없음·후보 간 비교 설명 폐기를 [AI 작업 기준](CLAP_RECOMMENDATION_DIRECTION.md)에 기록한다. 이 결정을 Linear Accepted 상태로 표시하지 않는다.


FastAPI 서버와 health API는 구현되어 있다.
임베딩 저장·DB 후보 검색은 동기 서비스와 CLI로 검증했으며 업무 HTTP API는 구현 전이다.
① AI에서 먼저 설계하고 백엔드가 검토하는 방식으로 진행한다.
등록·검색은 처리 완료 후 결과를 반환하는 동기 방식을 사용한다.
[초기 연동 제안 이력](AUDIO_JOB_CONTRACT.md)은 현행 개발 기준이 아니다. 당시 필드·엔드포인트·추천 경로 제안을 보존한 기록이다.
현행 개발 목표는 [AI 작업 기준](CLAP_RECOMMENDATION_DIRECTION.md)을 따른다.

2026-10-04 [백엔드 전달용 권장안](AUDIO_SYNC_BACKEND_HANDOFF.md)을 구체화했다.
파일 직접 전달(multipart), 등록·교체 통합 PUT, 버전·삭제 기록과 상태 조회를 권장한다.
동기 연동 설계·인터페이스 검토는 백엔드 전달용 권장안을 참고하며, Accepted 원칙과 미확정 상세 제안을 구분한다. 업무 API 구현은 다음 단계다.

백엔드 피드백으로 audioRevision·모델 버전 분리와 PROCESSING→ACTIVE 전환,
당시 최종 추천용 50~100개 retrieval 후보 방향을 반영했다. 이 반환 제한은 현행 사용자 결정의 전체 곡 반환 목표와 구분한다.
processing/ready/failed/deleted 조회, revision별 벡터 보관, ACTIVE revision 쌍 후보 제한을 반영했다.
v1·v2를 함께 보관하고 Backend v2 ACTIVE 커밋 확인 후 v1을 정리한다. 모두 구현 전이다.
활성 확인·정리 API, 정리 유예기간, stale 기준 및 세부 DTO는 추가 설계가 필요하다.

서버 정책·용어는 [Linear 서버 협의](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)의 Accepted 문서와 [용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 우선 확인한다.
로컬 서버 기록과 Proposed 011·012를 현행 확정 계약으로 사용하지 않는다.

## 책임 경계

Spring Hard Filter 이후 AI가 전체 통과 곡의 Embedding/유사도를 계산·정렬해 전체 결과를 반환한다.
Spring은 유사도 순 곡을 표시하고 사용자가 별도 버튼으로 해당 Artist와 매칭한다. 아티스트 집계·후보 비교 설명은 하지 않는다.
이 흐름의 출처는 이번 사용자 결정이며 기존 Linear Accepted 계약과 차이를 [작업 기준](CLAP_RECOMMENDATION_DIRECTION.md)에 명시한다.

곡별 추천 이유의 추가 AI 호출·템플릿 우선·실패 시 이유만 `null`은 [Accepted 서버 협의 008](https://linear.app/nsu-capstone/document/008-추천-이유-생성-흐름-ae6cde7df2de)을 참조한다.
[설명 상세 계약](RECOMMENDATION_EXPLANATION_CONTRACT.md)의 endpoint·DTO·timeout 및 전체 결과 흐름에 맞춘 설명 대상은 미정이다.
업무 API 구현이나 LLM 도입은 완료되지 않았다.

Spring Boot는 음악 ID·아티스트 소유 관계·인증/인가·서비스 화면 연결을 담당한다.
Python AI 서버는 전처리·임베딩·pgvector 저장·유사도 검색을 담당한다.

## 합의할 항목

| 항목 | 관련 이슈 | 상태 |
| --- | --- | --- |
| 동기 처리 방향 | NSUAI-17 | 사용자 동기 결정 반영 |
| Audio revision·수정/삭제·전환 후 정리 | NSUAI-25 / NSUAI-26 | 결정 반영, 구현 전 |
| 요청·응답·오류·타임아웃 | NSUAI-27 / NSU-63 | 초안 검토·업무 API 구현 필요 |

저장 책임은 [ADR 0001](../adr/ADR-0001-pgvector-adoption.md),
처리 방식은 [ADR 0006](../adr/ADR-0006-asynchronous-audio-processing.md)을 참고한다.
2026-10-04 Linear NSUAI-25·26·27, NSU-63과 연결 GitHub 이슈에 결정·미완료 기준을 반영했다.
음악 검색 표시 점수는 임시 유사도 지표이며 종합 적합도나 신뢰 확률이 아니다.
`AudioClassifier.classify()`의 `probability`는 비교 라벨 집합의 softmax 상대점수다.
