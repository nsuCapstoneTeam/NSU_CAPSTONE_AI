# FMA Historical PoC 안내

FMA는 과거 모델·언어·점수 변환 탐색에 사용한 Historical PoC입니다.
2026-10-09 Cleanup에서 원본 30초 Audio·ZIP·metadata·manifest·상세 CSV/JSON·Embedding·청취 UI·로컬 평가 도구를 삭제했습니다.
완전 재현은 지원하지 않으며 핵심 방법·조건·수치·한계와 ADR의 판단 근거만 보존합니다.

FMA 상세 track 목록·pairwise raw cosine·파일 hash·개별 rating·과거 Embedding은 Cleanup에서 의도적으로 제거했습니다. 현재 checkout에는 핵심 실험 조건·집계 결과·결론·한계의 Historical Markdown 요약만 남아 있어 개별 데이터 수준의 재계산/audit이나 완전 재현을 지원하지 않습니다. 이는 현재 checkout의 보존 범위이며 과거 Git history 자체를 삭제했다는 의미는 아닙니다.

## 보존한 실험 근거

- [FMA 표본·모델·전처리 조건](../experiments/fma-phase2/README.md#목적과-조건)
- [한국어/영어 검색 결과](../experiments/fma-phase2/README.md#수정본-검색-결과)
- [청취 평가와 영어 입력 결정](../experiments/fma-phase2/README.md#사용자-청취-평가)
- [96개 점수 변환 탐색](../experiments/audio-search-phase2/README.md#음악텍스트-기준-탐색)
- [276쌍 분포·포화 진단](../experiments/audio-search-phase2/README.md#새-음악-표본-및-쌍별-측정)
- [24개 Audio 청취 평가](../experiments/audio-search-phase2/README.md#청취-평가)

[ADR-0004](../adr/ADR-0004-korean-input-english-msclap.md)와 [ADR-0008](../adr/ADR-0008-music-similarity-transformation-and-ranking.md)의 Decision은 변경하지 않습니다.

## 현재 검증 경로

현재 기준은 [ADR-0007](../adr/ADR-0007-audio-highlight-embedding-strategy.md)과 [Phase A](../experiments/audio-highlight-phase-a/README.md)입니다.
별도 음악 6곡의 정확히 60초 fixture·PCM 동일성·재현성 및 Phase A 범위 출처·라이선스 확인은 완료됐습니다.
실제 6곡의 production MSCLAP 생성 경로 검증과 전용 PostgreSQL/pgvector 통합 검증도 완료됐습니다. 두 검증은 음악 검색 품질·similarity 분포·calibration의 평가를 대신하지 않습니다.
현재 후속 순서는 [Roadmap](../AI_DEVELOPMENT_ROADMAP.md)을 따릅니다. 검색 품질 평가와 dev/test 벡터 대상·입력 mapping 확인은 남아 있으며, 30초 FMA를 반복·padding해 새 검증 입력으로 사용하지 않습니다.

FMA Historical 집계는 과거 의사결정 설명용이며 향후 calibration input으로 사용하지 않습니다. 향후 calibration은 ADR-0007 generation policy에 따라 새로 생성한 Embedding·새 similarity distribution·새 evaluation evidence를 기반으로 수행하고, 해당 evidence는 별도로 생성·보존합니다.

## 유지하는 코드와 공유 캐시

`datasets/fma/huggingface/`는 공유 MSCLAP/GPT-2 캐시이므로 유지합니다.
`scripts/fma/validate_fma.py`와 helper, `scripts/matching/validate_audio_similarity.py`, 관련 synthetic tests는 유지합니다.
`scripts/fma/download_fma.ps1`와 `compose.fma.yaml`도 이번 단계에서는 유지합니다. 코드 퇴역·공용 helper 분리는 별도 작업입니다.
삭제한 입력·상세 결과를 사용하는 재현 명령은 제공하지 않습니다.

데이터·모델 다운로드 없이 확인할 수 있는 명령:

```powershell
python -m unittest discover -s tests/fma -p 'test_fma_validation.py' -v
python -m scripts.fma.validate_fma --help
```
