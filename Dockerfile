FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS runtime-deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip check

# 큰 모델 가중치 다운로드 없이도 바이너리·API 호환성 문제를 빌드 단계에서 발견한다.
RUN python -c "import torch, torchaudio, torchvision; from msclap import CLAP; assert torch.version.cuda is None; print('MSCLAP CPU dependencies OK')"

FROM runtime-deps AS dev
# 검증 CLI가 repository commit을 조회할 때 사용하는 개발 전용 도구다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt \
    && pip check
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs
COPY pytest.ini AGENTS.md ./
COPY compose.yaml compose.dev.yaml ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 기본 build 결과는 개발 도구를 포함하지 않는 runtime이다.
FROM runtime-deps AS runtime
COPY app ./app
COPY scripts/__init__.py ./scripts/__init__.py
COPY scripts/database/__init__.py \
     scripts/database/check_database.py \
     scripts/database/inspect_embedding_database.py \
     scripts/database/migrate_embeddings.py ./scripts/database/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
