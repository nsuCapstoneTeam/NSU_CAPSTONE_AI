import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import torch

from app.embedding.audio_embedding import PREPROCESSING_VERSION
from scripts.datasets.highlight_dataset import sha256
from scripts.embedding import generate_calibration_audio_embeddings as audio_runner
from scripts.matching import prepare_calibration_audio as preparation
from scripts.matching import register_calibration_audio as registration


SAMPLE_IDS = ['cal-incompetech-mandeville', 'cal-incompetech-lasting-hope']


def _base_manifest():
    return json.loads(registration.DEFAULT_MANIFEST.read_text(encoding='utf-8'))


def _register_and_prepare(root, sample_id, seed):
    relative = f'data/calibration/audio/source/{sample_id}/fixture.wav'
    source = root / Path(relative)
    source.parent.mkdir(parents=True, exist_ok=True)
    frames = 60 * 8000 + seed
    base = np.arange(frames * 2, dtype=np.float32).reshape(frames, 2)
    pcm = ((base + seed) % 2048) / 4096.0
    sf.write(source, pcm, 8000, subtype='FLOAT')
    return relative, source


def _prepared_fixture(root):
    manifest = _base_manifest()
    for seed, sample_id in enumerate(SAMPLE_IDS, start=1):
        relative, _ = _register_and_prepare(root, sample_id, seed)
        manifest, _ = registration.register_source_audio(
            manifest, sample_id, relative, 'official_direct_download', 'full_track', True,
            f'fixture source {seed} was verified as a full file', repository_root=root,
        )
        manifest, result, payload, _ = preparation.prepare_sample(
            manifest, sample_id, repository_root=root
        )
        output = root / result['prepared_local_path']
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    manifest_path = root / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    rows = audio_runner.load_prepared_samples(
        manifest, root, require_complete_cohort=False
    )
    return manifest, manifest_path, rows


class FakeGenerator:
    def __init__(self, checkpoint_path):
        self.checkpoint_path = str(checkpoint_path)
        self.calls = 0

    def generate(self, audio_path, *, expected_sha256):
        self.calls += 1
        assert sha256(audio_path) == expected_sha256
        seed = int(expected_sha256[:8], 16)
        values = torch.tensor([[float(seed % 7 + 1), float(seed % 5 + 2), 3.0]], dtype=torch.float32)
        vector = values / torch.linalg.vector_norm(values, dim=1, keepdim=True)
        metadata = {
            'source_sha256': expected_sha256,
            'model': 'MSCLAP',
            'model_version': '2023',
            'checkpoint_path': self.checkpoint_path,
            'checkpoint_revision': 'fixture-checkpoint-revision',
            'packages': {'msclap': '1.3.3', 'torch': '2.1.2+cpu', 'torchaudio': '2.1.2+cpu'},
            'device': 'cpu',
            'shape': [1, 3],
            'dimension': 3,
            'dtype': 'torch.float32',
            'norm': float(torch.linalg.vector_norm(vector)),
            'preprocessing_version': PREPROCESSING_VERSION,
            'preprocessing': {
                'analysis_duration_seconds': 56,
                'chunk_duration_seconds': 7,
                'chunk_count': 8,
                'chunk_overlap_seconds': 0,
                'chunk_normalization': 'l2',
                'aggregation': 'mean',
                'final_normalization': 'l2',
                'resample': True,
                'target_sample_rate': 44100,
                'channel_policy': 'arithmetic_mean_downmix_to_mono',
            },
        }
        return SimpleNamespace(vector=vector, metadata=metadata)


def _result(root, manifest, manifest_path, rows, tmp_path):
    checkpoint = tmp_path / 'CLAP_weights_2023.pth'
    checkpoint.write_bytes(b'fixture checkpoint identity')
    generator = FakeGenerator(checkpoint)
    vectors, ids, evidence = audio_runner.generate_embedding_result(
        rows, generator, root=root, manifest_path=manifest_path,
        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        git_commit_sha='a' * 40, working_tree_clean=False,
        expected_checkpoint_sha256=sha256(checkpoint),
        cohort_status=manifest.get('cohort_status'),
    )
    return vectors, ids, evidence, generator


def test_valid_prepared_files_generate_ordered_finite_float32_vectors(tmp_path):
    manifest, manifest_path, rows = _prepared_fixture(tmp_path)

    vectors, sample_ids, evidence, generator = _result(
        tmp_path, manifest, manifest_path, rows, tmp_path
    )

    assert sample_ids == SAMPLE_IDS
    assert vectors.shape == (2, 3)
    assert vectors.dtype == np.float32
    assert np.isfinite(vectors).all()
    assert np.all(np.linalg.norm(vectors.astype(np.float64), axis=1) > 0)
    assert evidence['embedding_output']['finite'] is True
    assert evidence['input_identity']['cohort_status'] == manifest['cohort_status']
    assert evidence['embedding_output']['zero_vector_count'] == 0
    assert len(evidence['embedding_output']['l2_norms']) == 2
    assert generator.calls == 4


def test_repeatability_is_exact_and_content_digest_is_stable(tmp_path):
    manifest, manifest_path, rows = _prepared_fixture(tmp_path)
    first = _result(tmp_path, manifest, manifest_path, rows, tmp_path)
    second = _result(tmp_path, manifest, manifest_path, rows, tmp_path)

    assert np.array_equal(first[0], second[0])
    assert first[2]['reproducibility']['same_ordered_batch_repeated']['exact_equal'] is True
    assert audio_runner.artifact_content_digest(first[0], first[1]) == audio_runner.artifact_content_digest(second[0], second[1])


def test_deterministic_npz_and_evidence_publish_as_matching_pair(tmp_path):
    manifest, manifest_path, rows = _prepared_fixture(tmp_path)
    vectors, ids, evidence, _ = _result(tmp_path, manifest, manifest_path, rows, tmp_path)
    artifact_path = tmp_path / 'out' / 'calibration-audio.npz'
    evidence_path = tmp_path / 'out' / 'calibration-audio.json'
    artifact_path.parent.mkdir()
    artifact_temp, evidence_temp = audio_runner._write_temporary_outputs(
        artifact_path, evidence_path, vectors, ids, evidence
    )
    staged_sha = sha256(artifact_temp)
    audio_runner.publish_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path)

    with np.load(artifact_path, allow_pickle=False) as archive:
        assert archive['sample_ids'].tolist() == ids
        assert np.array_equal(archive['embeddings'], vectors)
    assert audio_runner.validate_artifact_evidence_pair(artifact_path, evidence_path, staged_sha) == staged_sha
    assert json.loads(evidence_path.read_text(encoding='utf-8'))['artifact']['content_digest'] == audio_runner.artifact_content_digest(vectors, ids)

    second_artifact = tmp_path / 'out' / 'same-content.npz'
    audio_runner.write_deterministic_npz(second_artifact, vectors, ids)
    assert second_artifact.read_bytes() == artifact_path.read_bytes()


def test_content_digest_includes_sample_order(tmp_path):
    embeddings = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    assert audio_runner.artifact_content_digest(embeddings, ['one', 'two']) != audio_runner.artifact_content_digest(embeddings, ['two', 'one'])


def test_artifact_shape_metadata_must_match_decoded_npz(tmp_path):
    manifest, manifest_path, rows = _prepared_fixture(tmp_path)
    vectors, ids, evidence, _ = _result(tmp_path, manifest, manifest_path, rows, tmp_path)
    artifact_path = tmp_path / 'shape.npz'
    evidence_path = tmp_path / 'shape.json'
    artifact_temp, evidence_temp = audio_runner._write_temporary_outputs(
        artifact_path, evidence_path, vectors, ids, evidence
    )
    staged_evidence = json.loads(evidence_temp.read_text(encoding='utf-8'))
    staged_evidence['artifact']['shape'] = [999, 999]
    evidence_temp.write_text(json.dumps(staged_evidence), encoding='utf-8')

    with pytest.raises(ValueError, match='artifact shape metadata'):
        audio_runner.validate_artifact_evidence_pair(artifact_temp, evidence_temp)


def test_missing_prepared_file_fails_before_generator(tmp_path):
    manifest, _, rows = _prepared_fixture(tmp_path)
    rows[0]['prepared_path'].unlink()
    manifest['samples'][0]['prepared_local_path'] = 'data/calibration/audio/prepared/missing.wav'
    manifest['samples'][0]['prepared_sha256'] = '0' * 64

    with pytest.raises((ValueError, FileNotFoundError)):
        audio_runner.load_prepared_samples(manifest, tmp_path, require_complete_cohort=False)


def test_prepared_sha_mismatch_fails(tmp_path):
    manifest, _, _ = _prepared_fixture(tmp_path)
    manifest['samples'][0]['prepared_sha256'] = '0' * 64

    with pytest.raises(ValueError, match='SHA-256'):
        audio_runner.load_prepared_samples(manifest, tmp_path, require_complete_cohort=False)


def test_wrong_duration_and_invalid_manifest_state_fail(tmp_path):
    manifest, _, _ = _prepared_fixture(tmp_path)
    manifest['samples'][0]['prepared_duration'] = 59
    with pytest.raises(ValueError, match='validation failed'):
        audio_runner.load_prepared_samples(manifest, tmp_path, require_complete_cohort=False)

    manifest, _, _ = _prepared_fixture(tmp_path / 'invalid')
    manifest['samples'][0]['full_track_verified'] = False
    with pytest.raises(ValueError):
        audio_runner.load_prepared_samples(manifest, tmp_path / 'invalid', require_complete_cohort=False)


def test_prepared_decode_failure_fails(tmp_path):
    manifest, _, rows = _prepared_fixture(tmp_path)
    rows[0]['prepared_path'].write_bytes(b'not a WAV')
    manifest['samples'][0]['prepared_sha256'] = sha256(rows[0]['prepared_path'])

    with pytest.raises(ValueError, match='re-decode failed'):
        audio_runner.load_prepared_samples(manifest, tmp_path, require_complete_cohort=False)


def test_duplicate_sample_id_and_incomplete_canonical_cohort_fail(tmp_path):
    manifest, _, _ = _prepared_fixture(tmp_path)
    manifest['samples'][1]['sample_id'] = manifest['samples'][0]['sample_id']
    with pytest.raises(ValueError):
        audio_runner.load_prepared_samples(manifest, tmp_path, require_complete_cohort=False)

    manifest, _, _ = _prepared_fixture(tmp_path / 'incomplete')
    with pytest.raises(ValueError, match='has no prepared audio'):
        audio_runner.load_prepared_samples(manifest, tmp_path / 'incomplete', require_complete_cohort=True)


def _canonical_ready_manifest():
    return {
        'cohort_status': 'candidate_selection_complete',
        'cohort_target': 50,
        'samples': [{
            'sample_id': f'cal-{index:02d}',
            'source_local_path': f'data/calibration/audio/source/cal-{index:02d}/source.wav',
            'source_sha256': 'a' * 64,
            'source_file_size': 100,
            'decoded_duration': 61,
            'decoded_frame_count': 61000,
            'source_sample_rate': 1000,
            'source_channels': 1,
            'source_file_kind': 'full_track',
            'full_track_verified': True,
            'full_track_evidence': 'verified full source',
            'prepared_local_path': f'data/calibration/audio/prepared/cal-{index:02d}.wav',
            'prepared_sha256': 'b' * 64,
            'prepared_duration': 60,
            'segment_start_frame': 500,
            'segment_end_frame_exclusive': 60500,
        } for index in range(50)],
    }


def test_canonical_gate_accepts_complete_ready_50_song_cohort():
    audio_runner.validate_canonical_cohort_gate(_canonical_ready_manifest())


def test_canonical_gate_rejects_incomplete_status_even_with_50_rows():
    manifest = _canonical_ready_manifest()
    manifest['cohort_status'] = 'candidate_selection_incomplete'
    with pytest.raises(ValueError, match='candidate_selection_complete'):
        audio_runner.validate_canonical_cohort_gate(manifest)


def test_canonical_gate_requires_exactly_50_rows():
    manifest = _canonical_ready_manifest()
    manifest['samples'].pop()
    with pytest.raises(ValueError, match='exactly 50'):
        audio_runner.validate_canonical_cohort_gate(manifest)


def test_canonical_gate_requires_target_50():
    manifest = _canonical_ready_manifest()
    manifest['cohort_target'] = 49
    with pytest.raises(ValueError, match='cohort_target=50'):
        audio_runner.validate_canonical_cohort_gate(manifest)


def test_canonical_gate_requires_every_sample_embedding_ready():
    manifest = _canonical_ready_manifest()
    manifest['samples'][17]['prepared_sha256'] = None
    with pytest.raises(ValueError, match='not embedding-ready'):
        audio_runner.validate_canonical_cohort_gate(manifest)


def test_output_collision_and_existing_output_are_rejected(tmp_path):
    manifest, manifest_path, rows = _prepared_fixture(tmp_path)
    source = rows[0]['source_path']
    with pytest.raises(ValueError, match='same path'):
        audio_runner._resolve_outputs(tmp_path, manifest_path, 'same.out', 'same.out', rows)
    with pytest.raises(ValueError, match='collides with an input'):
        audio_runner._resolve_outputs(tmp_path, manifest_path, source, 'different.out', rows)
    existing = tmp_path / 'already.npz'
    existing.write_bytes(b'preserve')
    with pytest.raises(ValueError, match='already exists'):
        audio_runner._resolve_outputs(tmp_path, manifest_path, existing, 'different.out', rows)
    assert existing.read_bytes() == b'preserve'


def test_canonical_output_pair_mode_accepts_canonical_and_custom_pairs(tmp_path):
    canonical_manifest = tmp_path / audio_runner.DEFAULT_MANIFEST.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    canonical_artifact = tmp_path / audio_runner.DEFAULT_ARTIFACT.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    canonical_evidence = tmp_path / audio_runner.DEFAULT_EVIDENCE.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    custom_artifact = tmp_path / 'temporary' / 'vectors.npz'
    custom_evidence = tmp_path / 'temporary' / 'evidence.json'

    assert audio_runner.canonical_output_pair_mode(
        tmp_path, canonical_manifest, canonical_artifact, canonical_evidence
    ) is True
    assert audio_runner.canonical_output_pair_mode(
        tmp_path, tmp_path / 'custom-manifest.json', custom_artifact, custom_evidence
    ) is False
    with pytest.raises(ValueError, match='require the canonical calibration manifest'):
        audio_runner.canonical_output_pair_mode(
            tmp_path, tmp_path / 'custom-manifest.json', canonical_artifact, canonical_evidence
        )


@pytest.mark.parametrize('canonical_side', ['artifact', 'evidence'])
def test_partial_canonical_output_pair_is_rejected_before_clean_tree_check(
    tmp_path, monkeypatch, canonical_side,
):
    _, manifest_path, _ = _prepared_fixture(tmp_path)
    canonical_artifact = audio_runner.DEFAULT_ARTIFACT.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    canonical_evidence = audio_runner.DEFAULT_EVIDENCE.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    custom_artifact = tmp_path / 'temporary' / 'vectors.npz'
    custom_evidence = tmp_path / 'temporary' / 'evidence.json'
    artifact_path = canonical_artifact if canonical_side == 'artifact' else custom_artifact
    evidence_path = custom_evidence if canonical_side == 'artifact' else canonical_evidence
    monkeypatch.setattr(
        audio_runner, '_git_identity',
        lambda root: pytest.fail('partial canonical pair reached clean-tree gate'),
    )

    with pytest.raises(ValueError, match='must be selected as a pair'):
        audio_runner.run(
            manifest_path=manifest_path,
            artifact_output=artifact_path,
            evidence_output=evidence_path,
            root=tmp_path,
            generator=object(),
            require_complete_cohort=False,
        )


def test_resolved_canonical_path_aliases_are_canonical(tmp_path):
    canonical_manifest = tmp_path / audio_runner.DEFAULT_MANIFEST.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    canonical_artifact = tmp_path / audio_runner.DEFAULT_ARTIFACT.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    canonical_evidence = tmp_path / audio_runner.DEFAULT_EVIDENCE.relative_to(
        audio_runner.REPOSITORY_ROOT
    )
    artifact_alias = tmp_path / 'alias' / '..' / canonical_artifact.relative_to(tmp_path)
    manifest_alias = tmp_path / 'alias' / '..' / canonical_manifest.relative_to(tmp_path)
    if os.name == 'nt':
        evidence_alias = Path(str(canonical_evidence).replace('/', '\\'))
    else:
        evidence_alias = canonical_evidence.parent / '.' / canonical_evidence.name

    assert audio_runner.canonical_output_pair_mode(
        tmp_path, manifest_alias, artifact_alias, evidence_alias
    ) is True


@pytest.mark.parametrize('field', [
    'source_catalog_duration', 'decoded_duration', 'prepared_duration',
])
@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity'])
def test_run_rejects_nonstandard_numeric_manifest_json(tmp_path, field, token):
    manifest = _base_manifest()
    serialized = json.dumps(manifest, ensure_ascii=False)
    marker = f'"{field}": '
    start = serialized.index(marker) + len(marker)
    end = start
    while end < len(serialized) and serialized[end] not in ',}':
        end += 1
    path = tmp_path / 'manifest.json'
    path.write_text(serialized[:start] + token + serialized[end:], encoding='utf-8')

    with pytest.raises(ValueError, match='Non-finite JSON'):
        audio_runner.run(
            manifest_path=path,
            artifact_output=tmp_path / 'vectors.npz',
            evidence_output=tmp_path / 'evidence.json',
            root=tmp_path,
        )


def test_artifact_evidence_publish_failure_rolls_back_first_file(tmp_path, monkeypatch):
    manifest, manifest_path, rows = _prepared_fixture(tmp_path)
    vectors, ids, evidence, _ = _result(tmp_path, manifest, manifest_path, rows, tmp_path)
    artifact_path = tmp_path / 'publish' / 'out.npz'
    evidence_path = tmp_path / 'publish' / 'out.json'
    artifact_path.parent.mkdir()
    artifact_temp, evidence_temp = audio_runner._write_temporary_outputs(
        artifact_path, evidence_path, vectors, ids, evidence
    )
    original_link = audio_runner.os.link

    def fail_evidence_link(source, destination):
        if Path(destination) == evidence_path:
            raise OSError('injected evidence publish failure')
        return original_link(source, destination)

    monkeypatch.setattr(audio_runner.os, 'link', fail_evidence_link)
    with pytest.raises(OSError, match='injected evidence publish failure'):
        audio_runner.publish_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path)
    assert not artifact_path.exists()
    assert not evidence_path.exists()

