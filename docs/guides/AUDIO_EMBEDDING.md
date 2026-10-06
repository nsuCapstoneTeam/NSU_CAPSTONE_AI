# 공통 Audio 임베딩 생성

## 승인된 생성 기준 (2026-10-06, 구현 전)

이 절은 앞으로 구현할 Audio 생성 규칙의 기준이다. 결정 이유·공식 근거·대안과
trade-off 및 이전 정책의 변경 이력은 [ADR-0007](../adr/ADR-0007-audio-highlight-embedding-strategy.md)에 기록한다.
제품 길이 정책의 주 기준은 [Linear AI-033](https://linear.app/nsu-capstone/document/ssot-아티스트-행사-매칭-플랫폼-mvp-요구사항-e38bb23f87b1)의 v1.11이다.
아래 현재 구현과 과거 검증 기록이 이 정책의 구현 완료를 뜻하지는 않는다.
이번에는 Linear 및 문서만 정합화하며 서버 협의 승인 상태와 코드는 변경하지 않는다.

- Artist가 직접 선택한 대표 Highlight의 **권장 길이는 60초**다.
- **최소 60초·최대 80초**를 길이 validation 조건으로 적용한다. L < 60초 또는 L > 80초는 실패하고, **60초 ≤ L ≤ 80초는 통과**한다. 양 경계인 60초와 80초도 허용한다.
- 길이 validation 통과는 형식·크기·권리 등 다른 조건 통과를 의미하지 않는다. 최대 80초는 업로드 대상을 전체 음악 파일이 아닌 대표 Highlight로 유지하기 위한 서비스 정책이다.
- 허용된 입력의 **처음 56초만** 사용해 **7초 × 8개의 non-overlap Chunk**를 생성한다. 56초 이후 구간은 Audio Embedding 생성에 사용하지 않는다.
- 각 Chunk는 같은 MSCLAP 2023으로 생성하고 **Chunk별 L2 Normalize → Mean Pooling(N=8) → 최종 L2 Normalize**하여 대표 Audio Embedding 1개를 만든다.
- 대표 벡터를 PostgreSQL + pgvector에 저장한다. Text Embedding과의 서비스 검색 연결은 후속 구현이다.
- 새 방식 적용 시 기존 개발/테스트 Audio Embedding은 **삭제 후 재생성**한다. 이번에는 데이터를 삭제하거나 생성하지 않는다. 운영 generation 전환은 별도 후속 설계다.

구간은 시작 포함·끝 제외로 표기한다. 모든 허용 입력에 동일한 구간을 사용한다.

```text
[0,7), [7,14), [14,21), [21,28),
[28,35), [35,42), [42,49), [49,56)
```

| 입력 길이 | 길이 validation | Chunk 처리 |
| --- | --- | --- |
| L < 60초 | 실패 | Embedding 생성 대상 아님 |
| L = 60초 | 통과, 권장 길이 | 처음 56초, 8 Chunk |
| 60 < L < 80초 | 통과 | 처음 56초, 8 Chunk |
| L = 80초 | 통과, 최대 경계 | 처음 56초, 8 Chunk |
| L > 80초 | 실패 | Embedding 생성 대상 아님 |

### 정책 변경 이력

- 2026-10-06 이전 승인 기준: 60~70초 권장, 짧은 입력 허용·end-aligned overlap, 가변 Chunk 수, 7초 미만 처리 미결정.
- 2026-10-06 최종 사용자 승인: 위 정책과 별도 길이 상한을 두지 않던 설명을 현행 정책에서 폐기하고 권장 60초·허용 60~80초·고정 8 non-overlap Chunk로 대체했다. 이전 결정의 이유와 근거는 ADR-0007 변경 이력에서 확인한다.

MSCLAP 공식은 2023의 7초 전처리와 similarity 정규화를 제공하지만,
권장 60초·허용 60~80초·56초 분석·고정 Chunk 구성·두 단계 L2와 Mean Pooling은 **프로젝트 자체 정책**이다.
최종 L2는 저장 표현을 통일하는 정책이며, 내부에서 norm을 제거하는
pgvector cosine 검색의 수학적 필수조건은 아니다.

길이 validation·다중 Chunk 생성·aggregation·전처리 버전·generation metadata·테스트와 공통 생성기 변경은 후속 구현 과제다.
길이 측정과 60/80초 경계 판정, 검증 담당 계층·오류 응답/화면 안내, sample 경계·채널 처리·구간 실패·0/거의 0 norm의 수치 안정성 기준도 후속 결정·검증이 필요하다.

## 현재 구현 (길이 validation·승인된 다중 Chunk 정책 미적용)

`app.embedding.audio_embedding.AudioEmbeddingGenerator`는 음악 파일을 받아 검증한
벡터와 메타데이터를 반환합니다. 검색 CLI에서 사용하며 Phase 3 DB 저장에서도
재사용합니다. 테이블과 저장 흐름은 [임베딩 저장 안내](EMBEDDING_STORAGE.md)에 있습니다.
Text 생성 구현은 포함하지 않습니다. 현재 생성기는 60~80초 길이 validation 및 고정 8 Chunk aggregation을 구현하지 않았습니다.

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

## 기존 단일 crop 검증 결과 (새 정책의 검증 결과가 아님)

2026-10-03, Docker CPU 환경에서 자동 테스트 55개 통과, 기존 Starlette
deprecation 경고 1개를 확인했습니다. 입력 복사·벡터 오류·차원 변화·예외 발생 시
난수 상태 복원·생성 중 원본 변경 처리를 검사했습니다.
실제 `reference.mp3`와 후보 24곡으로 실행한 TOP 5 ID·원본 유사도·점수는
기존 검색 결과와 모두 정확히 같았습니다. 실제 출력 차원은 1024이며 메타데이터는
입력 1개와 후보 24개 모두 기록되었습니다.
로컬 재측정 결과: `datasets/fma/results/search-reference-common-embedding.json`.
