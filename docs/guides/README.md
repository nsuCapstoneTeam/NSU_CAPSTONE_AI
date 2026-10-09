# 기능 사용·검증 가이드

서비스 기능 실행 방법과 개발 검증 절차를 모았습니다.
현재 구현과 향후 계약은 각 문서에서 구분합니다.

| 관심 기능 | 문서 |
| --- | --- |
| 공통 Audio 임베딩·전처리 | [Audio 생성](AUDIO_EMBEDDING.md) |
| 테이블 생성·음악 ID별 저장 | [임베딩 저장](EMBEDDING_STORAGE.md) |
| 파일 목록을 이용한 후보 검색 | [Audio 검색](AUDIO_SEARCH.md) |
| DB 저장 벡터를 이용한 후보 검색 | [DB 검색](DATABASE_AUDIO_SEARCH.md) |
| 유사도 점수의 변환·해석 | [점수 정규화](SEMANTIC_SCORE_NORMALIZATION.md) |
| FMA Historical PoC 안내 | [FMA 검증](FMA_VALIDATION.md) |

프로젝트 루트에서 명령을 실행합니다. 문서 폴더 이동은 CLI 실행 위치를 바꾸지 않습니다.
설계 이유는 [ADR](../adr/README.md), 상세 연동 계약은 [API](../api/README.md),
실험 결과는 [전체 문서 목록](../README.md)의 experiments 항목을 참고하세요.
