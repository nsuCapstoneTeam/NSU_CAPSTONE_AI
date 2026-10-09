# 프로젝트 문서 목록

## 큰 범위별 구성

| 위치 | 용도 |
| --- | --- |
| AI_DEVELOPMENT_ROADMAP.md | 개발 순서·진행 상태·완료 기준 |
| guides/ | 개발자가 기능을 실행하고 검증하는 사용법 |
| api/ | 서버 연동의 상세 인터페이스·계약 제안 |
| adr/ | 아키텍처 결정·선택 이유·변경 이력 |
| adr/server-agreements/ | 보존된 과거 서버 협의 기록; 현행 관리는 Linear |
| experiments/ | 실험 입력·결과·평가 근거 |
| 협업-가이드/ | 팀 도구·협업 절차 |

## 문서 찾기

| 관심 기능 | 문서 |
| --- | --- |
| 개발 순서·완료 기준 | [개발 로드맵](AI_DEVELOPMENT_ROADMAP.md) |
| 공통 임베딩 생성·전처리·메타데이터 | [Audio 임베딩](guides/AUDIO_EMBEDDING.md) |
| 테이블 생성·임베딩 저장·중복 처리 | [임베딩 저장](guides/EMBEDDING_STORAGE.md) |
| 음악 파일로 Top5 검색 | [Audio 검색](guides/AUDIO_SEARCH.md) |
| DB 저장 후보로 Top5 검색 | [DB 음악 검색](guides/DATABASE_AUDIO_SEARCH.md) |
| 유사도 표시 점수 | [점수 정규화](guides/SEMANTIC_SCORE_NORMALIZATION.md) |
| FMA Historical PoC 안내 | [FMA 검증](guides/FMA_VALIDATION.md) |
| 음악·텍스트 검증 근거 | [Phase 2 실험](experiments/fma-phase2/README.md) |
| 음악·음악 검증 근거 | [음악 검색 실험](experiments/audio-search-phase2/README.md) |
| 기술 결정 | [ADR](adr/README.md) |
| 현행 서버 협의·용어 | [Linear 서버 협의](https://linear.app/nsu-capstone/document/000-server-agreements-목록-7e0bf3793fd3) · [용어집](https://linear.app/nsu-capstone/document/용어집-context-475370673105) |
| 과거 서버 협의 기록 | [보존 목록](adr/server-agreements/readme.md) |
| API 책임 경계 | [API](api/README.md) |
| 현재 사용자 결정·AI 작업 기준 | [전체 곡 유사도 정렬·반환](api/CLAP_RECOMMENDATION_DIRECTION.md) |
| AI 선설계·동기 연동 | [동기 연동 설계 및 인터페이스 참고](api/AUDIO_SYNC_BACKEND_HANDOFF.md) — Accepted 원칙과 미확정 상세 인터페이스 제안을 구분 |
| 팀 협업 | [협업 가이드](협업-가이드/README.md) |

사용법 문서는 guides/로 모았고 실험 데이터·API·ADR의 기존 경로는 유지했습니다.
개발 로드맵은 프로젝트 지침에서 참조하는 루트 경로를 유지합니다.
실행 파일 목록은 [개발 도구](../scripts/README.md), 테스트 목록은
[자동 테스트](../tests/README.md)에 있습니다.
