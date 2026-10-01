FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
# Install the matching CPU wheels before resolving MSCLAP dependencies.
RUN pip install --no-cache-dir \
    torch==2.1.2+cpu \
    torchaudio==2.1.2+cpu \
    torchvision==0.16.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements-dev.txt \
    && pip check

# Catch binary/API incompatibilities without downloading model weights.
RUN python -c "import torch, torchaudio, torchvision; from msclap import CLAP; assert torch.version.cuda is None; print('MSCLAP CPU dependencies OK')"

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
