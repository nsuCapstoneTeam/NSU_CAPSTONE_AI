"""검색과 향후 저장에서 전처리 차이로 벡터가 달라지지 않도록 공통 생성 경로를 제공한다."""

import hashlib
import importlib.metadata
import random
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PREPROCESSING_VERSION = 'msclap2023-audio-resample-sha256-seed-v1'
# MSCLAP의 구간 자르기는 프로세스 전체의 Python/Torch 난수 상태를 사용합니다.
# 호출을 순차 처리한 뒤 상태를 복원합니다. 잠금을 공유하려면 이 생성기를 사용해야 합니다.
_generation_lock = threading.Lock()


class AudioEmbeddingError(ValueError):
    """호출자가 실패 원인을 분류할 수 있도록 사유 코드와 원본 경로를 보존한다."""

    def __init__(self, reason, audio_path):
        self.reason = reason
        self.audio_path = str(audio_path)
        super().__init__(f'{reason}: {audio_path}')


@dataclass(frozen=True)
class AudioEmbeddingResult:
    """벡터와 생성 조건을 함께 전달해 저장 시 원본·모델 정보를 잃지 않도록 한다."""
    vector: Any
    metadata: dict


def audio_file_sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def validate_audio_embedding(vector, *, expected_dimension=None):
    """잘못된 벡터가 검색·저장에 전달되지 않도록 단일 곡 출력과 차원을 검증한다.

    Raises:
        ValueError: 형태·값·차원이 유효하지 않거나 벡터가 모두 0인 경우.
    """
    import torch

    if not isinstance(vector, torch.Tensor) or vector.ndim != 2 or vector.shape[0] != 1 or vector.shape[1] < 1:
        raise ValueError('invalid_embedding_shape')
    if not vector.is_floating_point() or not torch.isfinite(vector).all():
        raise ValueError('non_finite_or_non_float_embedding')
    if vector.norm(dim=1).item() == 0:
        raise ValueError('zero_embedding')
    if expected_dimension is not None and vector.shape[1] != expected_dimension:
        raise ValueError('embedding_dimension_mismatch')


class AudioEmbeddingGenerator:
    """모델을 지연 로딩해 재사용하고, 검증된 벡터와 생성 조건을 반환한다.

    차원은 임의로 고정하지 않고 첫 성공 결과를 기준으로 이후 출력을 검사한다.
    생성기 인스턴스를 재사용해야 모델 재로딩과 전처리 정책 불일치를 피할 수 있다.
    """

    def __init__(self, model=None, *, seed=43, expected_dimension=None):
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError('seed must be an integer between 0 and 2**32 - 1')
        if expected_dimension is not None and (type(expected_dimension) is not int or expected_dimension < 1):
            raise ValueError('expected_dimension must be a positive integer')
        self._model = model
        self.seed = seed
        self.dimension = expected_dimension

    def generate(self, audio_path, *, expected_sha256=None):
        """음악 파일을 기존 검색과 동일한 전처리로 임베딩한다.

        Args:
            audio_path: 현재 실행 환경에서 읽을 수 있는 음악 파일 경로.
            expected_sha256: 사전 확인한 원본 해시. 전달하면 파일 변경도 검사한다.
        Returns:
            AudioEmbeddingResult: 검증된 CPU 벡터와 원본·모델·전처리 메타데이터.
        Raises:
            AudioEmbeddingError: 파일·모델·추론·벡터 검증에 실패한 경우.
        """
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
        # 파일 이름이나 검색 역할이 달라도 같은 내용이면 같은 구간을 선택한다.
        crop_seed = self.seed + int(file_hash[:8], 16)
        import torch

        with _generation_lock:
            if self._model is None:
                from msclap import CLAP
                loading_state = random.getstate()
                try:
                    # 모델 초기화가 다른 처리의 난수 흐름에 영향을 남기지 않도록 복원한다.
                    with torch.random.fork_rng(devices=[]):
                        self._model = CLAP(version='2023', use_cuda=False)
                except Exception as error:
                    raise AudioEmbeddingError('audio_model_load_failed', path) from error
                finally:
                    random.setstate(loading_state)
            state = random.getstate()
            try:
                # 학습 그래프는 필요 없으며, 실패한 경우에도 외부 난수 상태를 복원한다.
                with torch.random.fork_rng(devices=[]), torch.inference_mode():
                    random.seed(crop_seed)
                    torch.random.default_generator.manual_seed(crop_seed)
                    try:
                        vector = self._model.get_audio_embeddings([str(path)], resample=True)
                    except Exception as error:
                        # 디코딩·전처리·모델 실행 실패를 포함하므로 모든 오류를
                        # 지원하지 않는 오디오 형식으로 분류하지 않습니다.
                        raise AudioEmbeddingError('audio_embedding_failed', path) from error
                    try:
                        validate_audio_embedding(vector, expected_dimension=self.dimension)
                    except ValueError as error:
                        raise AudioEmbeddingError(str(error), path) from error
                    vector = vector.detach().cpu().clone()
            finally:
                random.setstate(state)
            try:
                # 생성 도중 바뀐 원본의 벡터에 이전 해시가 연결되는 것을 방지한다.
                if audio_file_sha256(path) != file_hash:
                    raise AudioEmbeddingError('audio_source_changed', path)
            except OSError as error:
                raise AudioEmbeddingError('audio_source_changed', path) from error
            self.dimension = vector.shape[1]
            checkpoint = Path(getattr(self._model, 'model_fp', 'unavailable'))
            parts = checkpoint.parts
            # 캐시 경로에서 확인되는 revision만 기록하며 임의의 버전을 추정하지 않는다.
            revision = parts[parts.index('snapshots') + 1] if 'snapshots' in parts and parts.index('snapshots') + 1 < len(parts) else None
            metadata = {
                'source_path': str(path), 'source_sha256': file_hash,
                'model': 'MSCLAP', 'model_version': '2023',
                'checkpoint_path': str(checkpoint), 'checkpoint_revision': revision,
                'packages': {name: importlib.metadata.version(name) for name in ('msclap', 'torch', 'torchaudio')},
                'device': 'cpu', 'shape': list(vector.shape), 'dimension': self.dimension,
                'dtype': str(vector.dtype), 'norm': float(vector.norm()),
                'preprocessing_version': PREPROCESSING_VERSION,
                'preprocessing': {'resample': True, 'crop_pad': 'MSCLAP default',
                                  'base_seed': self.seed, 'crop_seed': crop_seed,
                                  'seed_policy': 'base_seed + int(source_sha256[:8], 16)'},
            }
        return AudioEmbeddingResult(vector=vector, metadata=metadata)
