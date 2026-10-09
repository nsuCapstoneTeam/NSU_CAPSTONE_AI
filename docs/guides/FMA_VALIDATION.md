# FMA Historical PoC 안내

FMA는 과거 모델·언어·점수 변환 탐색에 사용한 Historical PoC입니다.
2026-10-09 Cleanup에서 원본 30초 Audio·ZIP·metadata·manifest·상세 CSV/JSON·Embedding·청취 UI·로컬 평가 도구를 삭제합니다.
완전 재현은 지원하지 않으며 핵심 방법·조건·수치·한계와 ADR의 판단 근거만 보존합니다.

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
실제 MSCLAP real-music Embedding 검증과 새 정책 PostgreSQL 통합 검증은 아직 미완료입니다.
후속 순서는 [Roadmap](../AI_DEVELOPMENT_ROADMAP.md)을 따릅니다. 30초 FMA를 반복·padding하여 새 검증에 사용하지 않습니다.

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
