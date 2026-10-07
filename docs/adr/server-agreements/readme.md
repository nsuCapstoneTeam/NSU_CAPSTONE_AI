# Server Agreements — 과거 기록 보존 목록

현행 서버 협의와 작성 규칙의 관리 위치는 [Linear 서버 협의 목록](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3)이다.
공통 용어는 [Linear 용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105)을 우선 확인한다.
Linear는 2026-10-06 두 저장소의 로컬 server-agreements 관리 위치를 폐기했다.
여기 남은 문서의 Accepted/Proposed 표시는 **당시 기록**이며 현행 서버 협의의 승인 상태가 아니다.

## Linear로 이전된 중복 사본

2026-10-07 사용자 승인에 따라 본문·이력이 실질적으로 동일한 로컬 001~004 사본만 삭제했다.
링크 목적지·목록 기호 등 표시 차이를 제외한 본문은 Linear에 보존되어 있다.

| 이전 번호 | 현행 확인 위치 |
| --- | --- |
| 001 | [Audio revision·생성 버전 분리](https://linear.app/nsu-capstone/document/001-audio-revision과-생성-버전-분리-c5c95e36f3e2) |
| 002 | [revision 보관·ACTIVE 전환 후 정리](https://linear.app/nsu-capstone/document/002-revision별-벡터-보관과-active-전환-후-정리-e974a4620c8f) |
| 003 | [AI 처리 상태·Backend 활성 상태 분리](https://linear.app/nsu-capstone/document/003-ai-처리-상태와-backend-활성-상태-분리-3a0c0ca81f50) |
| 004 | [timeout·stale 재처리](https://linear.app/nsu-capstone/document/004-timeout-후-상태-확인과-stale-재처리-bc71a0dcdffd) |

## 이번에 보존한 파일

| 로컬 기록 | 보존 이유 / 현행 확인 위치 |
| --- | --- |
| [005](005-audio-retrieval-responsibilities.md) | Linear NSUAI-16 등 외부 참조가 남아 있으므로 사본을 유지. 현행 확인은 [Linear 005](https://linear.app/nsu-capstone/document/005-audio-후보-검색과-최종-추천-역할-분담-801efc93fbe3)와 후속 협의 및 사용자 결정 구분 |
| [007](007-recommendation-scoring-and-explanation-responsibilities.md) | 당시 점수·설명 책임의 고유 이력. Linear 007과 다른 내용; 관련 현행 원칙은 Linear 007·008·009 |
| [008](008-music-score-items-and-performance-format.md) | 당시 음악 항목·공연 형태 제안 이력. Linear 008과 다른 내용; 관련 Accepted 결정은 Linear 009 |

로컬 007·008을 Linear의 같은 번호로 단순 대응시키지 않는다. 과거 Decision·근거는 보존한다.
2026-10-07 사용자 결정의 전체 결과 반환·유사도 정렬·집계 없음·후보 비교 설명 폐기는
[AI 작업 기준](../../api/CLAP_RECOMMENDATION_DIRECTION.md)을 확인한다.
이 정리는 Linear의 Accepted/Proposed 상태나 다른 저장소를 변경하지 않는다.

## 문서 책임

- 서버 간 확정 처리 원칙·이유·승인 상태: Linear 서버 협의의 Accepted 문서.
- 상세 endpoint·DTO·파일 전달 제안: [Audio 연동 문서](../../api/AUDIO_SYNC_BACKEND_HANDOFF.md).
- AI 저장소 내부 기술 결정과 근거: [최상위 기술 ADR](../README.md).
- 현재 구현·미구현과 의존 순서: [Roadmap](../../AI_DEVELOPMENT_ROADMAP.md).

Accepted는 설계 합의를 뜻하며 구현 완료가 아니다. Proposed 내용을 확정 계약처럼 사용하지 않는다.
