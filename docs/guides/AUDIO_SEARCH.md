# 음악 파일로 후보 음악 검색

음악 파일을 MSCLAP Audio 임베딩으로 변환하고, 후보 음악들의 임베딩과 코사인
유사도를 비교합니다. 원본 유사도로 정렬하여 기본 상위 5곡을 반환합니다.
표시 점수는 임시 하한 0·상한 1 기준입니다. 아티스트별 집계·행사 적합도·BPM·리듬·
종합 점수·번역·HTTP API는 포함되지 않습니다. 이 문서는 로컬 manifest 검색을 설명합니다.
후보를 미리 저장해 사용하는 검색은 [DB 음악 검색](DATABASE_AUDIO_SEARCH.md)을 참고하세요.

프로젝트 루트에서 `samples`에 검색할 음악을 넣은 뒤 실행합니다.
FMA 데이터는 별도로 다운로드합니다. [FMA 안내](FMA_VALIDATION.md)를 참고하세요.
아래는 저장소에 공유한 24곡 validation 목록을 사용하는 예시입니다.
Compose 설정을 위해 `.env`의 `DB_PASSWORD`가 필요하지만 검색은 DB에 접속하지 않습니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.matching.search_audio --audio samples/reference.mp3 --manifest docs/experiments/audio-search-phase2/manifest24.json --output datasets/fma/results/search-reference-new.json
```

결과 JSON의 `results`에 `track_id`, `audio_path`, `cosine_similarity`,
`audio_similarity_score`, `rank`가 기록됩니다. 출력 파일은 덮어쓰지 않습니다.
동일 파일은 이름이 달라도 SHA-256으로 제외합니다. 누락·디코딩 실패 등은 오류로
중단하며 불완전한 결과를 정상 검색 결과로 저장하지 않습니다.

`--top-k` 기본값은 5이며 후보가 적으면 남은 후보 수만 반환합니다.
`--seed` 기본값은 43입니다. 기존 출력 파일이 있으면 새 파일명을 사용하세요.
입력 포맷은 torchaudio가 디코딩할 수 있는 MP3·WAV 등을 사용합니다.
Docker에서는 `samples`가 읽기 전용으로 연결되므로 입력 음원을 변경하지 않습니다.

입력 음악이 없는 상태에서 먼저 검색을 시험하려면 공개 FMA 곡으로 실행할 수 있습니다.

```powershell
docker compose -f compose.yaml -f compose.fma.yaml run --rm --no-deps ai python -m scripts.matching.search_audio --audio datasets/fma/fma_small/015/015770.mp3 --manifest docs/experiments/audio-search-phase2/manifest24.json --output datasets/fma/results/search-public-new.json
```

위 예시는 동일 곡을 제외한 23곡 중 상위 5곡을 반환합니다.
검색 결과의 정확성은 청취 평가가 필요하며, 현재 점수는 사용자용 최종 적합도 기준이 아닙니다.
[실험 근거와 한계](../experiments/audio-search-phase2/README.md)를 함께 참고하세요.

사용자 후보 목록도 아래 형식으로 만들 수 있습니다. 상대 경로는 실행 디렉터리
기준이고, Docker에서 접근 가능한 경로를 사용해야 합니다.

```json
{"tracks": [{"track_id": 1, "audio_path": "samples/candidate.mp3"}]}
```

MSCLAP의 crop/pad는 전체 음원 분석이 아닙니다. 입력 파일의 SHA-256과 seed로
crop을 고정합니다. 이전 쌍별 검증은 곡 ID 기반 seed이므로 결과가 정확히 같지는
않을 수 있습니다. 이 manifest 검색 도구는 후보 임베딩을 매 실행마다 생성합니다.
DB 검색 도구는 저장된 후보 벡터를 재사용합니다. 점수는 비슷함의 확률을 나타내지 않습니다.

검색은 [공통 Audio 생성기](AUDIO_EMBEDDING.md)를 사용합니다. 각 파일의 임베딩을
생성 직후 검증하고, 결과 JSON에 원본·모델·전처리 메타데이터를 함께 기록합니다.
