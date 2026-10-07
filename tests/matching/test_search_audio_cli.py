import json

import torch

from app.embedding.audio_embedding import AudioEmbeddingError, AudioEmbeddingResult
from scripts.matching import search_audio


def _inputs(tmp_path):
    query = tmp_path / 'query.wav'
    query.write_bytes(b'query audio')
    first = tmp_path / 'first.wav'
    first.write_bytes(b'first candidate')
    invalid = tmp_path / 'invalid.wav'
    invalid.write_bytes(b'invalid candidate')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'tracks': [
        {'track_id': 10, 'audio_path': str(first)},
        {'track_id': 20, 'audio_path': str(invalid)},
    ]}), encoding='utf-8')
    output = tmp_path / 'results.json'
    return query, manifest, output, first, invalid


def _argv(query, manifest, output):
    return [
        'search_audio', '--audio', str(query), '--manifest', str(manifest),
        '--output', str(output),
    ]


def test_invalid_query_embedding_prints_reason_and_returns_nonzero(tmp_path, monkeypatch, capsys):
    query, manifest, output, _, _ = _inputs(tmp_path)

    class InvalidQueryGenerator:
        def __init__(self):
            pass

        def generate(self, path, *, expected_sha256=None):
            raise AudioEmbeddingError('audio_duration_below_minimum', path)

    monkeypatch.setattr(search_audio, 'AudioEmbeddingGenerator', InvalidQueryGenerator)
    monkeypatch.setattr('sys.argv', _argv(query, manifest, output))

    assert search_audio.main() == 1
    captured = capsys.readouterr()
    assert 'query audio embedding failed' in captured.err
    assert 'audio_duration_below_minimum' in captured.err
    assert 'Traceback' not in captured.err
    assert not output.exists()


def test_invalid_manifest_candidate_is_identified_without_traceback(
        tmp_path, monkeypatch, capsys):
    query, manifest, output, first, invalid = _inputs(tmp_path)

    class InvalidCandidateGenerator:
        def __init__(self):
            pass

        def generate(self, path, *, expected_sha256=None):
            if str(path) == str(invalid.resolve()):
                raise AudioEmbeddingError('audio_duration_above_maximum', path)
            return AudioEmbeddingResult(
                torch.tensor([[1.0, 0.0]]),
                {'checkpoint_path': 'test-checkpoint', 'preprocessing_version': 'test-v1',
                 'preprocessing': {}},
            )

    monkeypatch.setattr(search_audio, 'AudioEmbeddingGenerator', InvalidCandidateGenerator)
    monkeypatch.setattr('sys.argv', _argv(query, manifest, output))

    assert search_audio.main() == 1
    captured = capsys.readouterr()
    assert 'candidate track_id=20' in captured.err
    assert str(invalid.resolve()) in captured.err
    assert 'audio_duration_above_maximum' in captured.err
    assert 'Traceback' not in captured.err
    assert not output.exists()


def test_valid_query_and_candidates_keep_search_output(tmp_path, monkeypatch, capsys):
    query, manifest, output, _, _ = _inputs(tmp_path)

    class ValidGenerator:
        def __init__(self):
            pass

        def generate(self, path, *, expected_sha256=None):
            return AudioEmbeddingResult(
                torch.tensor([[1.0, 0.0]]),
                {'checkpoint_path': 'test-checkpoint', 'preprocessing_version': 'test-v1',
                 'preprocessing': {}},
            )

    monkeypatch.setattr(search_audio, 'AudioEmbeddingGenerator', ValidGenerator)
    monkeypatch.setattr('sys.argv', _argv(query, manifest, output))

    assert search_audio.main() == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert [item['track_id'] for item in result['results']] == [10, 20]
    assert output.is_file()
