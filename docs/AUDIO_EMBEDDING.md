# 공통 Audio 임베딩 생성

`app.embedding.audio_embedding.AudioEmbeddingGenerator`는 음악 파일을 받아 검증한
벡터와 메타데이터를 반환합니다. 검색 CLI에서 사용하며 Phase 3 DB 저장에서도
재사용합니다. 테이블과 저장 흐름은 [임베딩 저장 안내](EMBEDDING_STORAGE.md)에 있습니다.
Text 생성 구현은 포함하지 않습니다.

```python
from app.embedding.audio_embedding import AudioEmbeddingGenerator

generator = AudioEmbeddingGenerator(seed=43)
result = generator.generate('samples/reference.mp3')
vector = result.vector        # CPU Tensor, shape (1, 실제 모델 차원)
metadata = result.metadata    # 원본 해시, 모델·체크포인트·전처리·차원
```

생성기는 최초 요청에서 MSCLAP 2023 CPU 모델을 불러오고 이후 재사용합니다.
파일 검사와 해시 확인은 모델 로딩 전에 수행합니다. 리샘플링을 명시적으로 켜고,
`base_seed + int(SHA256[:8], 16)`으로 모델 기본 crop/pad를 고정합니다.
기존 검색과 같은 방식이며 파일 이름이나 요청/후보 역할이 바뀌어도 같은 바이트는
같은 seed를 사용합니다. 전체 음악을 분석하는 다중 구간 방식은 아닙니다.

벡터를 반환하기 전에 shape·실수형·유한값·0벡터·차원을 검사합니다.
차원은 하드코딩하지 않고 첫 성공 결과로 측정합니다. 이후 호출의 차원은 일치해야
하며 저장 정책이 확정되면 `expected_dimension`을 전달할 수도 있습니다.
원본 해시를 생성 전후 비교해 변경된 파일에 잘못된 메타데이터를 붙이지 않습니다.
`expected_sha256`으로 후보 목록 검사 이후 파일 변경도 확인합니다.

메타데이터는 모델 버전, 실제 체크포인트 경로·확인 가능한 revision, 패키지 버전,
shape·차원·dtype·norm, 원본 경로·SHA-256, 전처리 버전·seed를 포함합니다.
체크포인트 경로만으로 임의의 로컬 가중치 파일 무결성을 보장하지는 않습니다.

모델 초기화와 추론의 Python/Torch CPU 난수 상태는 복원합니다. 공통 함수끼리의
호출은 잠금으로 직렬화하여 crop seed 간섭을 방지합니다. 공통 함수를 사용하지 않는
외부 코드의 난수 소비나 서로 다른 하드웨어·패키지 버전까지 통제하지는 않습니다.

`AudioEmbeddingError`의 `reason`은 파일 누락·빈 파일·읽기 실패·원본 변경·모델 로딩
실패·생성 실패·벡터 검증 실패를 구분합니다. 디코딩 오류를 포함한 생성 실패는
`audio_embedding_failed`이고 원본 예외를 보존합니다. 오류를 DB에 기록하고 재처리하는
부분은 저장 계층 구현에서 연결합니다.

기존 FMA 측정 스크립트는 과거 실험 재현을 위해 변경하지 않았습니다.
검색 출력에는 `query_embedding_metadata`, `candidate_embedding_metadata`가 추가됩니다.
기존 유사도·점수·순위 필드는 유지합니다.

## 검증 결과

2026-10-03, Docker CPU 환경에서 자동 테스트 55개 통과, 기존 Starlette
deprecation 경고 1개를 확인했습니다. 입력 복사·벡터 오류·차원 변화·예외 발생 시
난수 상태 복원·생성 중 원본 변경 처리를 검사했습니다.
실제 `reference.mp3`와 후보 24곡으로 실행한 TOP 5 ID·원본 유사도·점수는
기존 검색 결과와 모두 정확히 같았습니다. 실제 출력 차원은 1024이며 메타데이터는
입력 1개와 후보 24개 모두 기록되었습니다.
로컬 재측정 결과: `datasets/fma/results/search-reference-common-embedding.json`.
