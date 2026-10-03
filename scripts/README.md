# 개발 도구

프로젝트 루트에서 `python -m scripts.<기능>.<모듈>`로 실행합니다.
Docker 명령에서는 `ai` 다음에 같은 Python 명령을 붙입니다.
폴더 정리로 기존 `scripts.<모듈>` 실행 경로가 변경되었습니다.

| 폴더 | 파일 | 역할 |
| --- | --- | --- |
| database/ | check_database.py | DB 연결·pgvector 준비 상태 |
| database/ | inspect_embedding_database.py | 확장·테이블 읽기 전용 조회 |
| database/ | migrate_embeddings.py | 임베딩 테이블 마이그레이션 적용 |
| embedding/ | check_msclap.py | 모델 로딩 검사 |
| embedding/ | check_audio_embedding.py | samples/sample.wav 임베딩 검사 |
| embedding/ | store_audio_embedding.py | 외부 음악 ID·파일로 임베딩 생성·저장 |
| embedding/ | demo_classification.py | 모델·음원이 필요한 수동 장르 분류 예제 |
| matching/ | search_audio.py | 로컬 후보 목록의 Top5 음악 검색 |
| matching/ | search_database_audio.py | DB 저장 임베딩으로 Top5 음악 검색 |
| matching/ | validate_audio_similarity.py | 음악 간 쌍별 유사도 측정 |
| fma/ | download_fma.ps1 | FMA 다운로드·체크섬·압축 해제 |
| fma/ | validate_fma.py | 표본 선택·음악/텍스트 유사도 측정 |

```powershell
docker compose run --rm --no-deps ai python -m scripts.database.check_database
docker compose run --rm --no-deps ai python -m scripts.database.migrate_embeddings
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.embedding.store_audio_embedding --music-id dev-music-002 --audio samples/reference.mp3
```

상세 옵션과 데이터 준비 방법은 [문서 목록](../docs/README.md)을 참고하세요.
`demo_classification.py`는 자동 테스트가 아니며 `tests/`로 옮기지 않습니다.
