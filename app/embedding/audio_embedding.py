"""Audio Highlight를 ADR-0007 정책의 대표 벡터로 변환한다."""

import hashlib
import importlib.metadata
import random
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PREPROCESSING_VERSION = (
    'msclap2023-audio-first56s-8x7s-nonoverlap-chunk-l2-mean-final-l2-v2'
)
ANALYSIS_DURATION_SECONDS = 56
CHUNK_DURATION_SECONDS = 7
CHUNK_COUNT = 8
TARGET_SAMPLE_RATE = 44_100
MIN_AUDIO_DURATION_SECONDS = 60
MAX_AUDIO_DURATION_SECONDS = 80
_CHUNK_SAMPLE_COUNT = CHUNK_DURATION_SECONDS * TARGET_SAMPLE_RATE
_generation_lock = threading.Lock()


class AudioEmbeddingError(ValueError):
    """호출자가 실패 원인을 분류할 수 있도록 사유 코드와 원본 경로를 보존한다."""

    def __init__(self, reason, audio_path):
        self.reason = reason
        self.audio_path = str(audio_path)
        super().__init__(f'{reason}: {audio_path}')


@dataclass(frozen=True)
class AudioEmbeddingResult:
    """대표 벡터와 생성 조건을 함께 반환한다."""
    vector: Any
    metadata: dict


def audio_file_sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def validate_audio_embedding(vector, *, expected_dimension=None):
    """최종 단일 대표 벡터의 shape·값·차원을 검사한다."""
    import torch

    if not isinstance(vector, torch.Tensor) or vector.ndim != 2 or vector.shape[0] != 1 or vector.shape[1] < 1:
        raise ValueError('invalid_embedding_shape')
    if not vector.is_floating_point() or not torch.isfinite(vector).all():
        raise ValueError('non_finite_or_non_float_embedding')
    if vector.norm(dim=1).item() == 0:
        raise ValueError('zero_embedding')
    if expected_dimension is not None and vector.shape[1] != expected_dimension:
        raise ValueError('embedding_dimension_mismatch')


def validate_chunk_embeddings(vectors, *, expected_count=CHUNK_COUNT, expected_dimension=None):
    """8개 Chunk 출력 [N,D]를 각 행 단위로 검증한다."""
    import torch

    if (not isinstance(vectors, torch.Tensor) or vectors.ndim != 2
            or vectors.shape[0] != expected_count or vectors.shape[1] < 1):
        raise ValueError('invalid_chunk_embedding_shape')
    if not vectors.is_floating_point() or not torch.isfinite(vectors).all():
        raise ValueError('non_finite_or_non_float_chunk_embedding')
    # float64 norm은 낮은 dtype의 norm underflow/overflow를 피하면서 임의 epsilon 없이 0만 거른다.
    norms = torch.linalg.vector_norm(vectors.to(dtype=torch.float64), dim=1)
    if not torch.isfinite(norms).all():
        raise ValueError('non_finite_chunk_norm')
    if (norms == 0).any():
        raise ValueError('zero_chunk_embedding')
    if expected_dimension is not None and vectors.shape[1] != expected_dimension:
        raise ValueError('embedding_dimension_mismatch')


def _decode_and_chunk(path):
    """원본 길이를 decoded frame으로 검사하고 처음 56초를 8개 PCM WAV로 만든다."""
    import torchaudio

    waveform, sample_rate = torchaudio.load(str(path))
    if waveform.ndim != 2 or waveform.shape[0] < 1 or waveform.shape[1] < 1:
        raise ValueError('invalid_decoded_audio_shape')
    if type(sample_rate) is not int or sample_rate < 1:
        raise ValueError('invalid_audio_sample_rate')

    frame_count = waveform.shape[1]
    source_channels = waveform.shape[0]
    # 초 단위 float 비교 대신 decoded sample count와 rate로 경계를 정확히 판정한다.
    if frame_count < MIN_AUDIO_DURATION_SECONDS * sample_rate:
        raise ValueError('audio_duration_below_minimum')
    if frame_count > MAX_AUDIO_DURATION_SECONDS * sample_rate:
        raise ValueError('audio_duration_above_maximum')

    analysis_frame_count = ANALYSIS_DURATION_SECONDS * sample_rate
    waveform = waveform[:, :analysis_frame_count]
    # 프로젝트 전처리 정책: 채널을 시간축을 보존하며 산술 평균으로 mono downmix한다.
    waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != TARGET_SAMPLE_RATE:
        waveform = torchaudio.transforms.Resample(sample_rate, TARGET_SAMPLE_RATE)(waveform)

    expected_analysis_samples = ANALYSIS_DURATION_SECONDS * TARGET_SAMPLE_RATE
    if waveform.shape != (1, expected_analysis_samples):
        raise ValueError('resampled_analysis_length_mismatch')

    chunks = []
    chunk_paths = []
    for index in range(CHUNK_COUNT):
        start = index * _CHUNK_SAMPLE_COUNT
        end = start + _CHUNK_SAMPLE_COUNT
        chunk = waveform[:, start:end].contiguous()
        if chunk.shape != (1, _CHUNK_SAMPLE_COUNT):
            raise ValueError('invalid_audio_chunk_length')
        chunks.append(chunk)

    temporary_directory = tempfile.TemporaryDirectory(prefix='msclap-audio-chunks-')
    try:
        root = Path(temporary_directory.name)
        for index, chunk in enumerate(chunks):
            chunk_path = root / f'chunk-{index:02d}.wav'
            # PCM float WAV avoids lossy re-encoding between decode and MSCLAP inference.
            torchaudio.save(str(chunk_path), chunk, TARGET_SAMPLE_RATE,
                            format='wav', encoding='PCM_F', bits_per_sample=32)
            chunk_paths.append(str(chunk_path))
        return temporary_directory, chunk_paths, frame_count, sample_rate, source_channels
    except Exception:
        temporary_directory.cleanup()
        raise


class AudioEmbeddingGenerator:
    """MSCLAP 2023의 8개 Chunk를 집계해 단일 대표 Audio Embedding을 생성한다."""

    def __init__(self, model=None, *, expected_dimension=None):
        if expected_dimension is not None and (type(expected_dimension) is not int or expected_dimension < 1):
            raise ValueError('expected_dimension must be a positive integer')
        self._model = model
        self.dimension = expected_dimension

    def generate(self, audio_path, *, expected_sha256=None):
        """60~80초 파일의 처음 56초를 고정 8 Chunk로 변환해 하나의 벡터를 반환한다."""
        path = Path(audio_path).resolve()
        if not path.is_file():
            raise AudioEmbeddingError('audio_file_missing', path)
        try:
            if path.stat().st_size == 0:
                raise AudioEmbeddingError('audio_file_empty', path)
            file_hash = audio_file_sha256(path)
        except OSError as error:
            raise AudioEmbeddingError('audio_file_unreadable', path) from error
        if expected_sha256 is not None and file_hash != expected_sha256:
            raise AudioEmbeddingError('audio_source_changed', path)

        try:
            temporary_directory, chunk_paths, frame_count, source_sample_rate, source_channels = _decode_and_chunk(path)
        except ValueError as error:
            if str(error) in ('audio_duration_below_minimum', 'audio_duration_above_maximum'):
                raise AudioEmbeddingError(str(error), path) from error
            raise AudioEmbeddingError('audio_decode_or_preprocessing_failed', path) from error
        except Exception as error:
            raise AudioEmbeddingError('audio_decode_or_preprocessing_failed', path) from error

        try:
            import torch

            with _generation_lock:
                if self._model is None:
                    from msclap import CLAP
                    loading_state = random.getstate()
                    try:
                        with torch.random.fork_rng(devices=[]):
                            self._model = CLAP(version='2023', use_cuda=False)
                    except Exception as error:
                        raise AudioEmbeddingError('audio_model_load_failed', path) from error
                    finally:
                        random.setstate(loading_state)

                try:
                    with torch.inference_mode():
                        # 정확히 7초·44.1kHz WAV이므로 MSCLAP 공개 API의 random crop 분기를 타지 않는다.
                        chunk_vectors = self._model.get_audio_embeddings(chunk_paths, resample=False)
                except Exception as error:
                    raise AudioEmbeddingError('audio_embedding_failed', path) from error

                try:
                    validate_chunk_embeddings(chunk_vectors, expected_dimension=self.dimension)
                    # 정규화와 평균은 float64로 계산하고 저장/검색 인터페이스는 float32로 유지한다.
                    chunk_vectors = chunk_vectors.detach().cpu().to(dtype=torch.float64)
                    chunk_norms = torch.linalg.vector_norm(chunk_vectors, dim=1, keepdim=True)
                    normalized_chunks = chunk_vectors / chunk_norms
                    mean_vector = normalized_chunks.mean(dim=0, keepdim=True)
                    if not torch.isfinite(mean_vector).all():
                        raise ValueError('non_finite_mean_embedding')
                    mean_norm = torch.linalg.vector_norm(mean_vector, dim=1, keepdim=True)
                    if not torch.isfinite(mean_norm).all():
                        raise ValueError('non_finite_mean_norm')
                    if (mean_norm == 0).any():
                        raise ValueError('zero_mean_embedding')
                    vector = (mean_vector / mean_norm).to(dtype=torch.float32)
                    validate_audio_embedding(vector, expected_dimension=self.dimension)
                except ValueError as error:
                    raise AudioEmbeddingError(str(error), path) from error

            try:
                if audio_file_sha256(path) != file_hash:
                    raise AudioEmbeddingError('audio_source_changed', path)
            except OSError as error:
                raise AudioEmbeddingError('audio_source_changed', path) from error

            self.dimension = vector.shape[1]
            checkpoint = Path(getattr(self._model, 'model_fp', 'unavailable'))
            parts = checkpoint.parts
            revision = parts[parts.index('snapshots') + 1] if 'snapshots' in parts and parts.index('snapshots') + 1 < len(parts) else None
            preprocessing = {
                'resample': True,
                'target_sample_rate': TARGET_SAMPLE_RATE,
                'channel_policy': 'arithmetic_mean_downmix_to_mono',
                'analysis_duration_seconds': ANALYSIS_DURATION_SECONDS,
                'chunk_duration_seconds': CHUNK_DURATION_SECONDS,
                'chunk_count': CHUNK_COUNT,
                'chunk_overlap_seconds': 0,
                'chunk_normalization': 'l2',
                'aggregation': 'mean',
                'final_normalization': 'l2',
                'chunk_input': 'temporary_pcm_float32_wav',
            }
            metadata = {
                'source_path': str(path), 'source_sha256': file_hash,
                'source_duration_seconds': frame_count / source_sample_rate,
                'source_sample_rate': source_sample_rate,
                'source_channels': source_channels,
                'model': 'MSCLAP', 'model_version': '2023',
                'checkpoint_path': str(checkpoint), 'checkpoint_revision': revision,
                'packages': {name: importlib.metadata.version(name) for name in ('msclap', 'torch', 'torchaudio')},
                'device': 'cpu', 'shape': list(vector.shape), 'dimension': self.dimension,
                'dtype': str(vector.dtype), 'norm': float(vector.norm()),
                'preprocessing_version': PREPROCESSING_VERSION,
                'preprocessing': preprocessing,
            }
            return AudioEmbeddingResult(vector=vector, metadata=metadata)
        finally:
            temporary_directory.cleanup()
