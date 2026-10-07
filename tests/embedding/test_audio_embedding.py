import array
import wave
from pathlib import Path
from unittest.mock import Mock

import pytest
import torch

from app.embedding.audio_embedding import (
    ANALYSIS_DURATION_SECONDS,
    CHUNK_COUNT,
    CHUNK_DURATION_SECONDS,
    PREPROCESSING_VERSION,
    TARGET_SAMPLE_RATE,
    AudioEmbeddingError,
    AudioEmbeddingGenerator,
    audio_file_sha256,
    validate_audio_embedding,
    validate_chunk_embeddings,
)


SAMPLE_RATE = TARGET_SAMPLE_RATE


def write_audio(path, duration, *, channels=1, tail_value=20_000, sample_rate=SAMPLE_RATE):
    frame_count = round(duration * sample_rate)
    channel_data = [array.array('h') for _ in range(channels)]
    chunk_frames = CHUNK_DURATION_SECONDS * sample_rate
    for start in range(0, frame_count, chunk_frames):
        end = min(start + chunk_frames, frame_count)
        value = tail_value if start >= ANALYSIS_DURATION_SECONDS * SAMPLE_RATE else (start // chunk_frames + 1) * 1000
        for channel, values in enumerate(channel_data):
            # Different stereo channels make the chosen deterministic downmix observable.
            channel_value = value if channel == 0 else -value // 3
            values.extend(array.array('h', [channel_value]) * (end - start))
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        interleaved = array.array('h')
        for frame in range(frame_count):
            for channel in range(channels):
                interleaved.append(channel_data[channel][frame])
        output.writeframes(interleaved.tobytes())
    return path


@pytest.fixture(autouse=True)
def package_metadata(monkeypatch):
    monkeypatch.setattr('app.embedding.audio_embedding.importlib.metadata.version', lambda name: 'test')


def audio_reading_model(*, vectors=None, mutate=None):
    import torchaudio

    observed = {'calls': [], 'paths': [], 'chunks': []}
    model = Mock(model_fp='/cache/snapshots/revision123/CLAP_weights_2023.pth')

    def encode(paths, *, resample):
        observed['calls'].append((list(paths), resample))
        observed['paths'].extend(paths)
        rows = []
        for index, path in enumerate(paths):
            chunk, sample_rate = torchaudio.load(path)
            observed['chunks'].append((chunk.clone(), sample_rate))
            rows.append(torch.tensor([chunk.mean().item(), 1.0 + index / 10, 0.5]))
        if mutate is not None:
            mutate()
        return torch.stack(rows) if vectors is None else vectors

    model.get_audio_embeddings.side_effect = encode
    return model, observed


@pytest.mark.parametrize(('duration', 'accepted'), [
    (59.9, False), (60, True), (70, True), (80, True), (80.1, False),
])
def test_decoded_frame_duration_boundaries(tmp_path, duration, accepted):
    path = write_audio(tmp_path / f'{duration}.wav', duration)
    model, observed = audio_reading_model()
    generator = AudioEmbeddingGenerator(model)
    if accepted:
        result = generator.generate(path)
        assert result.vector.shape == (1, 3)
        assert len(observed['calls']) == 1
    else:
        expected = 'audio_duration_below_minimum' if duration < 60 else 'audio_duration_above_maximum'
        with pytest.raises(AudioEmbeddingError, match=expected):
            generator.generate(path)
        model.get_audio_embeddings.assert_not_called()


def test_exact_chunk_count_boundaries_and_non_overlap(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, observed = audio_reading_model()
    result = AudioEmbeddingGenerator(model).generate(path)

    assert len(observed['calls']) == 1
    paths, resample = observed['calls'][0]
    assert len(paths) == CHUNK_COUNT == 8
    assert resample is False
    assert len(observed['chunks']) == 8
    assert all(rate == TARGET_SAMPLE_RATE for _, rate in observed['chunks'])
    assert all(chunk.shape == (1, CHUNK_DURATION_SECONDS * TARGET_SAMPLE_RATE)
               for chunk, _ in observed['chunks'])
    expected_means = [index * 1000 / 32768 for index in range(1, 9)]
    assert [float(chunk.mean()) for chunk, _ in observed['chunks']] == pytest.approx(expected_means, abs=2e-5)
    assert result.metadata['preprocessing']['chunk_count'] == 8
    assert result.metadata['preprocessing']['chunk_overlap_seconds'] == 0


def test_stereo_is_deterministically_downmixed_without_time_flattening(tmp_path):
    path = write_audio(tmp_path / 'stereo.wav', 60, channels=2)
    model, observed = audio_reading_model()
    result = AudioEmbeddingGenerator(model).generate(path)

    expected = (1000 + (-1000 // 3)) / 2 / 32768
    assert float(observed['chunks'][0][0].mean()) == pytest.approx(expected, abs=2e-5)
    assert result.metadata['source_channels'] == 2
    assert result.metadata['preprocessing']['channel_policy'] == 'arithmetic_mean_downmix_to_mono'


def test_non_target_sample_rate_is_resampled_before_exact_chunking(tmp_path):
    source_rate = 22_050
    path = write_audio(tmp_path / 'resampled.wav', 60, sample_rate=source_rate)
    model, observed = audio_reading_model()

    result = AudioEmbeddingGenerator(model).generate(path)

    assert result.metadata['source_sample_rate'] == source_rate
    assert all(rate == TARGET_SAMPLE_RATE for _, rate in observed['chunks'])
    assert all(chunk.shape == (1, CHUNK_DURATION_SECONDS * TARGET_SAMPLE_RATE)
               for chunk, _ in observed['chunks'])
    assert len(observed['chunks']) == CHUNK_COUNT


@pytest.mark.parametrize('kind', ['missing', 'empty', 'decode_error'])
def test_invalid_source_files_fail_before_model_inference(tmp_path, kind):
    path = tmp_path / 'source.wav'
    if kind == 'empty':
        path.write_bytes(b'')
    elif kind == 'decode_error':
        path.write_bytes(b'not a wav file')
    model, _ = audio_reading_model()

    if kind == 'missing':
        with pytest.raises(AudioEmbeddingError, match='audio_file_missing'):
            AudioEmbeddingGenerator(model).generate(path)
    elif kind == 'empty':
        with pytest.raises(AudioEmbeddingError, match='audio_file_empty'):
            AudioEmbeddingGenerator(model).generate(path)
    else:
        with pytest.raises(AudioEmbeddingError, match='audio_decode_or_preprocessing_failed'):
            AudioEmbeddingGenerator(model).generate(path)
    model.get_audio_embeddings.assert_not_called()


def test_first_56_seconds_only_and_same_input_are_reproducible(tmp_path):
    first = write_audio(tmp_path / 'first.wav', 60, tail_value=20_000)
    second = write_audio(tmp_path / 'second.wav', 80, tail_value=-20_000)
    model1, _ = audio_reading_model()
    model2, _ = audio_reading_model()
    first_result = AudioEmbeddingGenerator(model1).generate(first)
    first_repeat = AudioEmbeddingGenerator(model1).generate(first)
    changed_tail = AudioEmbeddingGenerator(model2).generate(second)

    assert torch.equal(first_result.vector, first_repeat.vector)
    assert torch.equal(first_result.vector, changed_tail.vector)
    assert first_result.metadata['source_sha256'] != changed_tail.metadata['source_sha256']


def test_chunk_l2_mean_pooling_and_final_l2_normalization(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    chunk_vectors = torch.tensor([
        [3.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 5.0],
        [3.0, 4.0, 0.0], [0.0, 4.0, 3.0], [4.0, 0.0, 3.0],
        [2.0, 2.0, 2.0], [1.0, 2.0, 3.0],
    ])
    model, _ = audio_reading_model(vectors=chunk_vectors)
    result = AudioEmbeddingGenerator(model).generate(path)

    normalized = chunk_vectors.double() / torch.linalg.vector_norm(chunk_vectors.double(), dim=1, keepdim=True)
    expected_mean = normalized.mean(dim=0, keepdim=True)
    expected = (expected_mean / torch.linalg.vector_norm(expected_mean, dim=1, keepdim=True)).float()
    assert result.vector == pytest.approx(expected, abs=1e-6)
    assert result.vector.norm().item() == pytest.approx(1.0, abs=1e-6)
    assert result.vector.shape == (1, 3)
    assert torch.isfinite(result.vector).all()


@pytest.mark.parametrize(('vectors', 'reason'), [
    (torch.ones(7, 3), 'invalid_chunk_embedding_shape'),
    (torch.tensor([[0.0, 0.0, 0.0]] + [[1.0, 0.0, 0.0]] * 7), 'zero_chunk_embedding'),
    (torch.tensor([[float('nan'), 0.0, 0.0]] + [[1.0, 0.0, 0.0]] * 7),
     'non_finite_or_non_float_chunk_embedding'),
])
def test_invalid_chunk_outputs_rejected(tmp_path, vectors, reason):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, _ = audio_reading_model(vectors=vectors)
    with pytest.raises(AudioEmbeddingError, match=reason):
        AudioEmbeddingGenerator(model).generate(path)


def test_embedding_dimension_mismatch_rejected(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, _ = audio_reading_model(vectors=torch.ones(8, 4))
    with pytest.raises(AudioEmbeddingError, match='embedding_dimension_mismatch'):
        AudioEmbeddingGenerator(model, expected_dimension=3).generate(path)


def test_zero_mean_vector_rejected_without_epsilon_threshold(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    vectors = torch.tensor([[1.0, 0.0]] * 4 + [[-1.0, 0.0]] * 4)
    model, _ = audio_reading_model(vectors=vectors)
    with pytest.raises(AudioEmbeddingError, match='zero_mean_embedding'):
        AudioEmbeddingGenerator(model).generate(path)


def test_temporary_chunks_are_outside_source_and_always_cleaned(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, observed = audio_reading_model()
    AudioEmbeddingGenerator(model).generate(path)
    temporary_paths = [Path(value) for value in observed['paths']]
    assert all(value.parent != path.parent for value in temporary_paths)
    assert all(not value.exists() for value in temporary_paths)


def test_temporary_chunks_cleaned_when_model_fails(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, observed = audio_reading_model()
    def fail(paths, *, resample):
        observed['paths'].extend(paths)
        raise RuntimeError('inference failed')
    model.get_audio_embeddings.side_effect = fail
    with pytest.raises(AudioEmbeddingError, match='audio_embedding_failed'):
        AudioEmbeddingGenerator(model).generate(path)
    assert len(observed['paths']) == 8
    assert all(not Path(value).exists() for value in observed['paths'])


def test_source_sha256_validation_and_change_detection(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, _ = audio_reading_model()
    with pytest.raises(AudioEmbeddingError, match='audio_source_changed'):
        AudioEmbeddingGenerator(model).generate(path, expected_sha256='0' * 64)
    model.get_audio_embeddings.assert_not_called()

    def mutate():
        path.write_bytes(b'changed after model input was created')

    model, _ = audio_reading_model(mutate=mutate)
    with pytest.raises(AudioEmbeddingError, match='audio_source_changed'):
        AudioEmbeddingGenerator(model).generate(path)


def test_metadata_has_stable_generation_profile_without_crop_seed(tmp_path):
    path = write_audio(tmp_path / 'sixty.wav', 60)
    model, _ = audio_reading_model()
    result = AudioEmbeddingGenerator(model).generate(path)
    metadata = result.metadata
    preprocessing = metadata['preprocessing']

    assert metadata['preprocessing_version'] == PREPROCESSING_VERSION
    assert preprocessing == {
        'resample': True,
        'target_sample_rate': TARGET_SAMPLE_RATE,
        'channel_policy': 'arithmetic_mean_downmix_to_mono',
        'analysis_duration_seconds': 56,
        'chunk_duration_seconds': 7,
        'chunk_count': 8,
        'chunk_overlap_seconds': 0,
        'chunk_normalization': 'l2',
        'aggregation': 'mean',
        'final_normalization': 'l2',
        'chunk_input': 'temporary_pcm_float32_wav',
    }
    assert metadata['source_duration_seconds'] == 60
    assert 'source_duration_seconds' not in preprocessing
    assert not any('seed' in key for key in preprocessing)


def test_audio_validators_keep_single_and_batch_responsibilities_separate():
    validate_audio_embedding(torch.tensor([[1.0, 0.0]]), expected_dimension=2)
    validate_chunk_embeddings(torch.ones(8, 2), expected_dimension=2)
    with pytest.raises(ValueError, match='invalid_embedding_shape'):
        validate_audio_embedding(torch.ones(8, 2))
    with pytest.raises(ValueError, match='invalid_chunk_embedding_shape'):
        validate_chunk_embeddings(torch.ones(1, 2))
