# 공통 Audio 임베딩 생성

## 새 ADR-0007 개발/검증의 입력 선행조건

FMA Historical PoC의 핵심 실험 근거는 Markdown으로 보존하고, 원본·manifest·상세 결과는 2026-10-09 Cleanup에서 삭제한다.
새 개발/검증에는 **FMA와 다른 Dataset의 60~80초(양 경계 포함) 입력**을 사용한다.
2026-10-08 Phase A에서는 로컬 Kevin MacLeod 음원 6곡의 지정 구간으로 정확히 60초 WAV fixture를 준비했다.
기술 검증과 반복 재현성은 통과했다. 공식 곡의 CC BY 4.0 및 로컬 원본의 공식 Incompetech 사이트 직접 다운로드는 각각 confirmed_by_user다. Phase A 종합 verification_status=verified, rights_cleared=true는 로컬 MSCLAP 기술 검증용 Dataset의 출처·라이선스 확인 완료만 뜻한다. 공식 서버 파일과 SHA-256 비교는 not_performed이며 모든 향후 서비스/배포 용도의 권리 검토 완료를 뜻하지 않는다.
구간·manifest·실행 결과는 [Phase A 실험 기록](../experiments/audio-highlight-phase-a/README.md)을 참고한다.
2026-10-09 [실제 6곡 MSCLAP 검증](../experiments/audio-highlight-msclap-validation/README.md)에서 production generator의 24회 batch 추론·[8,1024]→[1,1024] 생성 경로·metadata 및 같은/별도 process exact 재현성을 확인했다. 이는 생성 경로 기술 검증이며 PostgreSQL 통합 검증·검색/음악 품질 평가·similarity 분포/calibration은 미완료다.
기존 FMA를 임의 반복·padding해서 새 검증 입력으로 바꾸지 않는다.

다른 Dataset의 권리·길이 확인 → 새 생성 규칙/metadata 검증 → 개발 벡터 대상·새 입력 매핑 확인 →
개발/테스트 벡터 삭제·재생성 → 저장/검색 검증 순서를 따른다.
적격 입력을 준비하기 전에 기존 벡터를 삭제하지 않는다.
세부 의존 순서는 [Roadmap Phase 3](../AI_DEVELOPMENT_ROADMAP.md)을 따른다.
ADR-0007의 정책·Decision은 그대로이며 Dataset 절차는 Roadmap/Guide에서 관리한다.


## 승인된 생성 기준 (ADR-0007, 구현 적용)

이 절은 현재 구현에 적용된 Audio 생성 규칙이다. 결정 이유·공식 근거·대안과
trade-off 및 이전 정책의 변경 이력은 [ADR-0007](../adr/ADR-0007-audio-highlight-embedding-strategy.md)에 기록한다.
제품 길이 정책의 주 기준은 [Linear AI-033](https://linear.app/nsu-capstone/document/ssot-아티스트-행사-매칭-플랫폼-mvp-요구사항-e38bb23f87b1)의 v1.11이다.
현재 공통 생성기 구현은 아래 정책을 적용한다. 실제 MSCLAP 통합 검증과 새 Dataset 평가 상태는
구현 단위 테스트 통과 여부와 구분해 관리한다.

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

길이는 decoder가 반환한 sample frame 수와 sample rate의 정수 경계로 검사한다. 입력을 decode한 뒤
처음 56초만 남기고 mono downmix 및 44.1kHz resampling을 적용한다. 고정된 8개 구간을
PCM float 임시 WAV로 만들며 MSCLAP 공개 API가 각 입력을 random crop하지 않도록 정확히 7초로 전달한다.
다채널은 시간축을 보존하는 채널 산술 평균으로 downmix한다. 이는 프로젝트 전처리 정책이며
공식 MSCLAP wrapper의 기존 채널 flatten 동작과 다르다.

Chunk는 각각 L2 정규화하고 float64 계산으로 평균 및 최종 L2 정규화를 수행한다. norm 검사에는
임의 epsilon을 적용하지 않고 finite 여부와 정확한 0만 검사한다. 0에 가까운 비영 norm은 임계값으로
거부하지 않는다. decoder별 압축 형식의 경계 정밀도와 실제 음원에서의 품질은 별도 통합 검증 대상이다.

## 현재 구현

`app.embedding.audio_embedding.AudioEmbeddingGenerator`는 음악 파일을 받아 검증한
벡터와 메타데이터를 반환합니다. 검색 CLI에서 사용하며 Phase 3 DB 저장에서도
재사용합니다. 테이블과 저장 흐름은 [임베딩 저장 안내](EMBEDDING_STORAGE.md)에 있습니다.
Text 생성 구현은 포함하지 않습니다. 현재 생성기는 60~80초 길이 validation과 고정 8 Chunk aggregation을 적용합니다.

```python
from app.embedding.audio_embedding import AudioEmbeddingGenerator

generator = AudioEmbeddingGenerator()
result = generator.generate('samples/reference.mp3')
vector = result.vector        # CPU Tensor, shape (1, 실제 모델 차원)
metadata = result.metadata    # 원본 해시·길이, 모델·체크포인트·전처리 profile·차원
```

생성기는 파일 존재·비어 있음·SHA-256과 기대 해시를 확인한 뒤 오디오를 decode하고
60~80초 길이를 검증합니다. 최초 요청에서 MSCLAP 2023 CPU 모델을 불러오고 이후 재사용합니다.
처음 56초를 7초 단위 8개 chunk로 만들어 한 번의 공개 `get_audio_embeddings(paths, resample=False)`
호출로 처리합니다. 각 chunk 임베딩을 정규화해 평균하고, 최종 벡터 하나를 다시 정규화합니다.

Chunk batch는 `[8, D]`, 최종 대표 벡터는 `[1, D]` shape로 각각 검증합니다.
실수형·finite·nonzero·차원 일치를 확인합니다. norm은 float64로 계산해 dtype에 따른
norm underflow/overflow를 줄이고, 임의의 작은 norm 임계값은 두지 않습니다.
원본 해시를 생성 전후 비교하며 `expected_sha256`으로 후보 검사 이후 파일 변경도 확인합니다.

metadata에는 모델·체크포인트 revision·패키지·차원·dtype·norm·원본 SHA-256과 원본
decode 길이·sample rate·channel 수를 기록합니다. generation profile에는 고정 분석 시간,
chunk 길이·수·overlap, pooling/normalization, resampling과 channel 정책을 포함합니다.
새 preprocessing version은 `msclap2023-audio-first56s-8x7s-nonoverlap-chunk-l2-mean-final-l2-v2`입니다.
체크포인트 경로만으로 임의의 로컬 가중치 파일 무결성을 보장하지는 않습니다.

고정 길이 chunk 입력에서는 seed 기반 crop이 필요하지 않습니다. 공통 모델 호출은 잠금으로
직렬화하며 임시 chunk 디렉터리는 추론의 성공·실패와 관계없이 정리합니다.

`AudioEmbeddingError`의 `reason`은 파일 누락·빈 파일·읽기 실패·원본 변경·모델 로딩
실패·생성 실패·벡터 검증 실패를 구분합니다. 디코딩 오류를 포함한 생성 실패는
`audio_embedding_failed`이며 decode/전처리 실패는 `audio_decode_or_preprocessing_failed`로
분류하고 원본 예외를 보존합니다. 오류를 DB에 기록하고 재처리하는
부분은 저장 계층 구현에서 연결합니다.

기존 FMA 측정 스크립트와 공용으로 import되는 helper는 별도 코드 퇴역 전까지 유지합니다. 상세 산출물 삭제 후 과거 실험의 완전 재현은 지원하지 않습니다.
검색 출력에는 `query_embedding_metadata`, `candidate_embedding_metadata`가 추가됩니다.
기존 유사도·점수·순위 필드는 유지합니다.

## 기존 단일 crop 검증 결과 (새 정책의 검증 결과가 아님)

2026-10-03, Docker CPU 환경에서 자동 테스트 55개 통과, 기존 Starlette
deprecation 경고 1개를 확인했습니다. 입력 복사·벡터 오류·차원 변화·예외 발생 시
난수 상태 복원·생성 중 원본 변경 처리를 검사했습니다.
실제 `reference.mp3`와 후보 24곡으로 실행한 TOP 5 ID·원본 유사도·점수는
기존 검색 결과와 모두 정확히 같았습니다. 실제 출력 차원은 1024이며 메타데이터는
입력 1개와 후보 24개 모두 기록되었습니다.
[Historical 공통 생성기 검증 요약](../experiments/audio-search-phase2/README.md#당시-공통-생성기db-경로-검증)에 근거를 보존하며 상세 JSON은 삭제했습니다.
