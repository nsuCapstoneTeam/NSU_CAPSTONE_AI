# Architecture Decision Records

Python AI/Matching Server 및 AI Matching 시스템에 영향을 주는
기술적 결정과 그 근거를 기록한다.

팀에서 확정된 결정은 개별 ADR 문서에 기록하며,
아직 확정되지 않은 사항은 확정된 결정과 구분하여 관리한다.

## 관련 결정

| ADR | 관련 이슈 | 결정 내용 | 상태 |
| --- | --- | --- | --- |
| [ADR-0001](./ADR-0001-pgvector-adoption.md) | NSUAI-19 | PostgreSQL + pgvector 채택 및 DB 운영 구조 | 승인 |
| [ADR-0002](./ADR-0002-ai-matching-server-architecture.md) | NSUAI-18, NSUAI-22 | Spring Boot ↔ Python AI Server 통신 및 Matching 처리 구조 | 승인 |
| [ADR-0003](./ADR-0003-embedding-and-scoring-policy.md) | NSUAI-17, NSUAI-20, NSUAI-21, NSUAI-2, NSUAI-12 | MSCLAP, Embedding 생성·저장 및 Matching Score 처리 방향 | 부분 승인 |
| [ADR-0004](./ADR-0004-korean-input-english-msclap.md) | NSUAI-1, NSUAI-2 | 한국어 음악 요청을 영어로 변환한 뒤 MSCLAP 입력 | 입력 정책 승인, 번역 방식 미정 |
| [ADR-0005](./ADR-0005-audio-similarity-display-score.md) | NSUAI-1, NSUAI-2 | 음악 파일 검색과 음악·텍스트별 임시 표시 점수 분리 | 개발용 기준 채택, 최종 점수 미정 |
| [ADR-0006](./ADR-0006-asynchronous-audio-processing.md) | NSUAI-17 관련, 외부 이슈 변경 전 | 음악 입력 동기 처리·AI 선설계 | 사용자 결정 반영, 업무 API 구현 전 |
| [ADR-0007](./ADR-0007-audio-highlight-embedding-strategy.md) | NSUAI-25 관련, 외부 이슈 변경 전 | Highlight 권장 60초·허용 60~80초(경계 포함)·처음 56초/고정 8 non-overlap Chunk·L2/Mean(N=8)·개발 벡터 재생성 | Accepted (사용자 승인), generation policy 및 실제 6곡 MSCLAP/전용 PostgreSQL 검증 완료; dev/test 벡터 재생성 미완료 |
| [ADR-0008](./ADR-0008-music-similarity-transformation-and-ranking.md) | 외부 이슈 변경 없음 | raw cosine ranking·후보 독립 transformation·calibration 및 버전 추적 원칙 | Accepted (AI 원칙 사용자 승인), 최종 calibration·버전 체계 구현 전 |

ADR-0005는 개발용 임시 표시 점수 기준과 초기 실험 근거를 보존한다.
ADR-0008은 그 후속·확장으로 원본 cosine ranking, 후보 독립 transformation, calibration·버전 추적 원칙을 정한다.
ADR-0005의 Decision/Status를 변경하거나 Superseded 처리하지 않으며, ADR-0008도 최종 변환 함수·파라미터를 확정하지 않는다.

## 최상위 기술 ADR 파일명

최상위 기술 ADR 전체는 `ADR-XXXX-kebab-case-topic.md` 형식을 사용한다.
`ADR-` prefix와 중복되지 않는 다음 4자리 번호, 영문 소문자 kebab-case topic을 사용한다.
이 번호는 최상위 기술 ADR의 번호이며 Linear 서버 협의 번호와 별도다.

2026-10-06 사용자 승인에 따라 기존 ADR-0001~0006의 번호와 topic을 유지하고 파일명에
`ADR-` prefix만 추가했다. 내부 참조 경로도 함께 정합화했다. ADR 본문의 제목·Status·Decision·근거는
재작성하지 않으며, 본문 안의 관련 ADR 링크는 목적지만 변경한다.
ADR-0006의 과거 "기존 파일 경로 유지" 기록은 보존하되 현재 파일명 운영 방침은 이 규칙을 따른다.
`server-agreements/`는 별도 체계이므로 이번 naming 정리 대상에서 제외한다.

## 서버 간 협의사항

서버별 책임·통신·장애 처리의 현행 합의와 작성 규칙은
[Linear 서버 협의 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)에서 관리한다. Proposed는 확정 정책으로 간주하지 않는다.
[로컬 보존 목록](server-agreements/readme.md)은 과거 기록이며 Linear의 같은 번호와 혼동하지 않는다.
API 상세 필드·요청/응답 명세는 [API 문서](../api/README.md)를 참고한다.

ADR-0002의 당시 TOP5와 ADR-0005의 아티스트 집계 후속 계획은 과거 기록으로 보존한다.
현행 추천 정책은 Accepted 012에 따른다. 전체 통과 ACTIVE 후보 쌍을 입력으로 받고 AI가 최대 100곡을 반환하는 기준은 [현재 AI 작업 기준](../api/CLAP_RECOMMENDATION_DIRECTION.md)에 정리되어 있다.
이 안내는 과거 ADR 본문이나 Linear 승인 상태를 변경하지 않는다.

기존 ADR의 실제 결정 내용과 변경 이력은 위 목록에서 계속 확인할 수 있다.
