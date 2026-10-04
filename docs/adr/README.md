# Architecture Decision Records

Python AI/Matching Server 및 AI Matching 시스템에 영향을 주는
기술적 결정과 그 근거를 기록한다.

팀에서 확정된 결정은 개별 ADR 문서에 기록하며,
아직 확정되지 않은 사항은 확정된 결정과 구분하여 관리한다.

## 관련 결정

| ADR | 관련 이슈 | 결정 내용 | 상태 |
| --- | --- | --- | --- |
| [ADR-0001](./0001-pgvector-adoption.md) | NSUAI-19 | PostgreSQL + pgvector 채택 및 DB 운영 구조 | 승인 |
| [ADR-0002](./0002-ai-matching-server-architecture.md) | NSUAI-18, NSUAI-22 | Spring Boot ↔ Python AI Server 통신 및 Matching 처리 구조 | 승인 |
| [ADR-0003](./0003-embedding-and-scoring-policy.md) | NSUAI-17, NSUAI-20, NSUAI-21, NSUAI-2, NSUAI-12 | MSCLAP, Embedding 생성·저장 및 Matching Score 처리 방향 | 부분 승인 |
| [ADR-0004](./0004-korean-input-english-msclap.md) | NSUAI-1, NSUAI-2 | 한국어 음악 요청을 영어로 변환한 뒤 MSCLAP 입력 | 입력 정책 승인, 번역 방식 미정 |
| [ADR-0005](./0005-audio-similarity-display-score.md) | NSUAI-1, NSUAI-2 | 음악 파일 검색과 음악·텍스트별 임시 표시 점수 분리 | 개발용 기준 채택, 최종 점수 미정 |
| [ADR-0006](./0006-asynchronous-audio-processing.md) | NSUAI-17 관련, 외부 이슈 변경 전 | 음악 입력 동기 처리·AI 선설계 | 사용자 결정 반영, 업무 API 구현 전 |

## 서버 간 협의사항

서버별 책임·통신·장애 처리 결정의 관리 범위와 ADR 작성 양식은
[Server Agreements](server-agreements/readme.md)에서 관리한다.
API 상세 필드·요청/응답 명세는 [API 문서](../api/README.md)를 참고한다.

기존 ADR의 실제 결정 내용과 변경 이력은 위 목록에서 계속 확인할 수 있다.
