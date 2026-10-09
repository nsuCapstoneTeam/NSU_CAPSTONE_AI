# 음악 파일로 후보 음악 검색

## 새 ADR-0007 개발/검증의 입력 선행조건

FMA Historical PoC의 핵심 실험 근거는 Markdown으로 보존하고, 원본·manifest·상세 결과는 2026-10-09 Cleanup에서 삭제한다.
새 개발/검증에는 **FMA와 다른 Dataset의 60~80초(양 경계 포함) 입력**을 사용한다.
[Phase A](../experiments/audio-highlight-phase-a/README.md)의 6곡·60초 fixture와 Phase A 범위 출처·라이선스 확인은 완료됐다. 실제 MSCLAP real-music 검증과 새 정책 PostgreSQL 통합 검증은 아직 미완료다.
기존 FMA를 임의 반복·padding해서 새 검증 입력으로 바꾸지 않는다.

다른 Dataset의 권리·길이 확인 → 새 생성 규칙/metadata 검증 → 개발 벡터 대상·새 입력 매핑 확인 →
개발/테스트 벡터 삭제·재생성 → 저장/검색 검증 순서를 따른다.
적격 입력을 준비하기 전에 기존 벡터를 삭제하지 않는다.
세부 의존 순서는 [Roadmap Phase 3](../AI_DEVELOPMENT_ROADMAP.md)을 따른다.
ADR-0007의 정책·Decision은 그대로이며 Dataset 절차는 Roadmap/Guide에서 관리한다.


음악 파일을 MSCLAP Audio 임베딩으로 변환하고, 후보 음악들의 임베딩과 코사인
유사도를 비교합니다. 원본 유사도로 정렬하여 기본 상위 5곡을 반환합니다.
표시 점수는 임시 하한 0·상한 1 기준입니다. 아티스트별 집계·행사 적합도·BPM·리듬·
종합 점수·번역·HTTP API는 포함되지 않습니다. 이 문서는 로컬 manifest 검색을 설명합니다.
후보를 미리 저장해 사용하는 검색은 [DB 음악 검색](DATABASE_AUDIO_SEARCH.md)을 참고하세요.

## Historical PoC / 과거 검증

당시 30초 FMA·단일 crop 검색의 [조건·결과·한계](../experiments/audio-search-phase2/README.md)를 Markdown으로 보존합니다.
원본·manifest·상세 결과는 삭제했으며 완전 재현 명령은 제공하지 않습니다. 이를 현재 8-Chunk 정책 검증으로 간주하지 않습니다.

## Current Usage / 현재 실행

현재 `search_audio.py`는 `AudioEmbeddingGenerator`의 generation policy를 사용합니다.
입력은 60~80초(양 경계 포함)여야 하며, 처음 56초에서 7초 × 8개 Chunk를 생성해
하나의 대표 벡터로 집계합니다. Phase A fixture 준비는 완료됐고 실제 MSCLAP 음악 품질 평가는 후속 단계입니다. Phase A manifest는 이 검색 CLI의 후보 manifest와 형식이 다르므로 직접 전달하지 않습니다.
적격 query Audio와 각 후보 Audio를 준비해야 합니다. manifest의 모든 후보도 현재 60~80초
validation을 통과해야 합니다. Dataset/fixture 준비 후 아래 placeholder 경로를 실제 경로로 바꿔 실행합니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.matching.search_audio --audio samples/eligible-highlight.wav --manifest samples/eligible-candidates.json --output /workspace/datasets/audio-search-results/search-eligible-new.json
```

이 예제의 `compose.fma.yaml`은 host의 `./datasets`를 `/workspace/datasets`에 쓰기 가능하게 mount합니다.
결과는 host의 `datasets/audio-search-results/`에 저장되어 `run --rm` 종료 후에도 남습니다.
CLI가 결과 폴더를 생성하며, 이 로컬 결과 디렉터리는 Git에서 제외됩니다.

`--top-k` 기본값은 5이며 후보가 적으면 남은 후보 수만 반환합니다.
검색 생성은 고정 8 chunk 방식이며 random crop seed를 사용하지 않습니다. 기존 출력 파일이 있으면 새 파일명을 사용하세요.
입력은 현재 실행환경의 torchaudio decoder가 읽을 수 있어야 합니다. 압축 형식별 공식 지원 범위는
별도 검증 전까지 확정하지 않습니다.
Docker에서는 `samples`가 읽기 전용으로 연결되므로 입력 음원을 변경하지 않습니다.

검색 결과의 정확성은 청취 평가가 필요하며, 현재 점수는 사용자용 최종 적합도 기준이 아닙니다.
[과거 실험 근거와 한계](../experiments/audio-search-phase2/README.md)를 참고하세요.

사용자 후보 목록도 아래 형식으로 만들 수 있습니다. 상대 경로는 실행 디렉터리
기준이고, Docker에서 접근 가능한 경로를 사용해야 합니다.

```json
{"tracks": [{"track_id": 1, "audio_path": "samples/candidate.mp3"}]}
```

Audio Highlight 길이와 첫 56초 분석 범위는 [공통 생성 기준](AUDIO_EMBEDDING.md)을 따릅니다.
이 manifest 검색 도구는 후보 임베딩을 매 실행마다 생성합니다.
DB 검색 도구는 저장된 후보 벡터를 재사용합니다. 점수는 비슷함의 확률을 나타내지 않습니다.

검색은 [공통 Audio 생성기](AUDIO_EMBEDDING.md)를 사용합니다. 각 파일의 임베딩을
생성 직후 검증하고, 결과 JSON에 원본·모델·전처리 메타데이터를 함께 기록합니다.
