# Python AI 서버 API

FastAPI 서버와 health API는 구현되어 있다.
임베딩 저장·DB 후보 검색은 동기 서비스와 CLI로 검증했으며 업무 HTTP API는 구현 전이다.
① AI에서 먼저 설계하고 백엔드가 검토하는 방식으로 진행한다.
등록·검색은 처리 완료 후 결과를 반환하는 동기 방식을 사용한다.
[연동 계약 초안](AUDIO_JOB_CONTRACT.md)의 필드·엔드포인트는 검토용 제안이다.

2026-10-04 [백엔드 전달용 권장안](AUDIO_SYNC_BACKEND_HANDOFF.md)을 구체화했다.
파일 직접 전달(multipart), 등록·교체 통합 PUT, 버전·삭제 기록과 상태 조회를 권장한다.
새 권장안의 경로와 규칙을 우선 검토하며 업무 API 구현은 다음 단계다.

## 책임 경계

Spring Boot는 음악 ID·아티스트 소유 관계·인증/인가·서비스 화면 연결을 담당한다.
Python AI 서버는 전처리·임베딩·pgvector 저장·유사도 검색을 담당한다.

## 합의할 항목

| 항목 | 관련 이슈 | 상태 |
| --- | --- | --- |
| 동기 처리 방향 | NSUAI-17 | 사용자 동기 결정 반영 |
| 원본 ID·파일 전달·수정/삭제 | NSUAI-25 | AI 초안, 백엔드 검토 필요 |
| 요청·응답·오류·타임아웃 | NSUAI-27 / NSU-63 | 초안 검토·업무 API 구현 필요 |

저장 책임은 [ADR 0001](../adr/0001-pgvector-adoption.md),
처리 방식은 [ADR 0006](../adr/0006-asynchronous-audio-processing.md)을 참고한다.
외부 이슈는 이번 작업에서 변경하지 않았다.
음악 검색 표시 점수는 임시 유사도 지표이며 종합 적합도나 신뢰 확률이 아니다.
`AudioClassifier.classify()`의 `probability`는 비교 라벨 집합의 softmax 상대점수다.
