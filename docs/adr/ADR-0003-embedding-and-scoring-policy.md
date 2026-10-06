# 0003. MSCLAP Embedding 및 Matching Score 처리 방향

## 상태

부분 승인

## 관련 근거

- Linear Issue: NSUAI-17
- Linear Issue: NSUAI-20
- Linear Issue: NSUAI-21
- Linear Issue: NSUAI-2
- Linear Issue: NSUAI-12
- 팀 AI Matching 기술 결정 회의 결과

## 배경

AI Matching을 구현하기 위해 사용할 CLAP 모델,
Audio/Text Embedding의 생성 및 저장 방식,
Matching 항목의 0~100 점수 정규화 방향을 정의할 필요가 있다.

일부 사항은 확정되었으며,
실제 모델 실행 결과가 필요한 세부 사항은 미확정 상태로 유지한다.

## 1. CLAP 모델

### 확정

AI Matching의 Audio/Text Embedding 생성에는
MSCLAP을 사용한다.

### 미확정

다음 내용은 실제 구현 환경에서 MSCLAP을 검증한 후 확정한다.

- 실제 사용할 model/checkpoint
- 실제 Embedding dimension

Embedding dimension을 임의의 값으로 결정하지 않는다.

현재 로컬 PostgreSQL + pgvector 테스트에서 사용하는
`VECTOR(3)`은 pgvector 기능 확인을 위한 테스트 값이며
실제 MSCLAP Embedding dimension이 아니다.

## 2. Embedding 저장

### 확정

Audio Embedding과 Text Embedding 모두
PostgreSQL + pgvector에 저장한다.

Python AI/Matching Server에서 AI Matching에 필요한
Embedding 생성 및 관련 처리를 수행한다.

저장된 Embedding은 Vector Similarity Search 및
AI Matching 과정에서 사용한다.

## 3. Embedding 생성 방식

2026-10-03 확인: 사용자 후속 결정에 따라 동기 생성 원칙을 유지한다.
AI 선설계 진행 방식과 결정 이력은 [ADR 0006](ADR-0006-asynchronous-audio-processing.md)을 참고한다.

### MVP 확정

MVP에서는 Audio/Text Embedding을
등록/수정 시 동기 방식으로 생성 및 갱신한다.

```text
Audio/Text 등록 또는 수정
        ↓
MSCLAP Embedding 생성
        ↓
PostgreSQL + pgvector 저장/갱신
        ↓
처리 완료
