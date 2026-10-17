"""Generate the ADR-0007 Audio vectors for the prepared calibration cohort."""

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.embedding.audio_embedding import (
    PREPROCESSING_VERSION,
    AudioEmbeddingGenerator,
    validate_audio_embedding,
)
from scripts.datasets.highlight_dataset import relative_path, sha256
from scripts.matching import prepare_calibration_audio as preparation
from scripts.matching.strict_json import parse_json_bytes
from scripts.matching.validate_calibration import CALIBRATION_DIR, _read_json, validate_calibration


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = CALIBRATION_DIR / 'manifest.json'
DEFAULT_ARTIFACT = CALIBRATION_DIR / 'artifacts' / 'calibration-v1-audio-embeddings.npz'
DEFAULT_EVIDENCE = CALIBRATION_DIR / 'audio-embedding-evidence.json'
TEXT_EVIDENCE = CALIBRATION_DIR / 'text-embedding-evidence.json'
ARTIFACT_CONTENT_DIGEST_ALGORITHM = 'sha256-framed-npz-arrays-v1'
ARTIFACT_CONTENT_DIGEST_PREFIX = b'NSU-CALIBRATION-AUDIO-NPZ-CONTENT\x00v1\x00'


class CalibrationAudioEmbeddingError(ValueError):
    """Calibration Audio generation failed a required validation gate."""


def _require(condition, message):
    if not condition:
        raise CalibrationAudioEmbeddingError(message)


def _git_value(root, *args):
    return subprocess.check_output(
        ['git', *args], cwd=root, text=True, encoding='utf-8'
    ).strip()


def _git_identity(root):
    commit_sha = _git_value(root, 'rev-parse', 'HEAD')
    _require(len(commit_sha) == 40 and all(c in '0123456789abcdef' for c in commit_sha.lower()),
             'could not determine full Git commit SHA')
    status = _git_value(root, 'status', '--porcelain', '--untracked-files=all')
    return commit_sha, not bool(status)


def _manifest_validator(manifest):
    schema = _read_json(CALIBRATION_DIR / 'manifest.schema.json', 'manifest schema')
    event_queries = _read_json(CALIBRATION_DIR / 'event-queries.json', 'event queries')
    event_schema = _read_json(
        CALIBRATION_DIR / 'event-queries.schema.json', 'event query schema'
    )
    errors = validate_calibration(manifest, schema, event_queries, event_schema)
    _require(not errors, 'calibration manifest validation failed:\n- ' + '\n- '.join(errors))


def _resolve_outputs(root, manifest_path, artifact_output, evidence_output, samples):
    root = Path(root).resolve()

    def resolve(path):
        candidate = Path(path)
        return (candidate if candidate.is_absolute() else root / candidate).resolve()

    artifact_path = resolve(artifact_output)
    evidence_path = resolve(evidence_output)
    inputs = [Path(manifest_path).resolve()]
    inputs.extend(item['source_path'].resolve() for item in samples)
    inputs.extend(item['prepared_path'].resolve() for item in samples)
    input_keys = {os.path.normcase(str(path)) for path in inputs}
    artifact_key = os.path.normcase(str(artifact_path))
    evidence_key = os.path.normcase(str(evidence_path))
    _require(artifact_key != evidence_key, 'artifact and evidence outputs resolve to the same path')
    _require(artifact_key not in input_keys, 'artifact output collides with an input file')
    _require(evidence_key not in input_keys, 'evidence output collides with an input file')
    _require(not artifact_path.exists(), f'artifact output already exists: {artifact_path}')
    _require(not evidence_path.exists(), f'evidence output already exists: {evidence_path}')
    return artifact_path, evidence_path


def load_prepared_samples(manifest, root=REPOSITORY_ROOT, *, require_complete_cohort=True):
    """Validate the manifest, registered sources and prepared WAVs before inference."""
    root = Path(root).resolve()
    _manifest_validator(manifest)
    samples = manifest.get('samples')
    _require(isinstance(samples, list), 'manifest.samples must be a list')
    if require_complete_cohort:
        validate_canonical_cohort_gate(manifest)

    prepared_samples = []
    sample_ids = set()
    prepared_paths = set()
    for sample in samples:
        sample_id = sample.get('sample_id')
        _require(isinstance(sample_id, str) and sample_id.strip(), 'sample_id is missing or blank')
        _require(sample_id not in sample_ids, f'duplicate sample_id: {sample_id}')
        sample_ids.add(sample_id)
        if sample.get('prepared_local_path') is None:
            if require_complete_cohort:
                raise CalibrationAudioEmbeddingError(f'{sample_id} has no prepared audio')
            continue

        preparation._require_source_gate(sample, sample_id)
        source_relative, source_path, source_pcm, source_rate = preparation._inspect_registered_source(
            sample, sample_id, root
        )
        start = sample.get('segment_start_frame')
        end = sample.get('segment_end_frame_exclusive')
        target_frames = 60 * source_rate
        expected_start = (len(source_pcm) - target_frames) // 2
        _require(type(start) is int and type(end) is int,
                 f'{sample_id} prepared frame provenance is missing')
        _require(start == expected_start and end == start + target_frames,
                 f'{sample_id} does not use the centered exact 60-second frame range')
        _require(sample.get('prepared_duration') == 60,
                 f'{sample_id}.prepared_duration must equal 60')
        prepared_relative = sample.get('prepared_local_path')
        prepared_path = relative_path(root, prepared_relative)
        expected_prepared_prefix = f'data/calibration/audio/prepared/{sample_id}.wav'
        _require(prepared_relative == expected_prepared_prefix,
                 f'{sample_id}.prepared_local_path must equal {expected_prepared_prefix}')
        _require(prepared_path.is_file(), f'{sample_id} prepared WAV is missing: {prepared_relative}')
        key = os.path.normcase(str(prepared_path))
        _require(key not in prepared_paths, f'duplicate prepared path: {prepared_relative}')
        prepared_paths.add(key)

        expected_pcm = source_pcm[start:end]
        actual_sha, _ = preparation._validate_prepared_wav(
            prepared_path, expected_pcm, source_rate, sample_id
        )
        _require(actual_sha == sample.get('prepared_sha256'),
                 f'{sample_id} prepared file SHA-256 differs from manifest')
        prepared_samples.append({
            'sample_id': sample_id,
            'sample': sample,
            'source_path': source_path,
            'source_relative_path': source_relative,
            'source_sha256': sample['source_sha256'],
            'source_file_size': sample['source_file_size'],
            'decoded_frame_count': sample['decoded_frame_count'],
            'prepared_path': prepared_path,
            'prepared_relative_path': prepared_relative,
            'prepared_sha256': actual_sha,
            'segment_start_frame': start,
            'segment_end_frame_exclusive': end,
            'source_sample_rate': source_rate,
            'source_channels': sample['source_channels'],
        })
        # Release the full decoded source before checking the next cohort member.
        del source_pcm, expected_pcm

    _require(prepared_samples, 'no prepared cohort audio is available')
    if require_complete_cohort:
        _require(len(prepared_samples) == 50,
                 f'expected 50 prepared samples, found {len(prepared_samples)}')
    return prepared_samples


def validate_canonical_cohort_gate(manifest):
    """Require a finalized 50-song cohort with all rows structurally embedding-ready."""
    samples = manifest.get('samples') if isinstance(manifest, dict) else None
    _require(isinstance(manifest, dict)
             and manifest.get('cohort_status') == 'candidate_selection_complete',
             'canonical Audio embedding requires cohort_status=candidate_selection_complete')
    _require(manifest.get('cohort_target') == 50,
             'canonical Audio embedding requires cohort_target=50')
    _require(isinstance(samples, list) and len(samples) == 50,
             'canonical Audio embedding requires exactly 50 sample rows')
    required = (
        'source_local_path', 'source_sha256', 'source_file_size', 'decoded_duration',
        'decoded_frame_count', 'source_sample_rate', 'source_channels', 'full_track_evidence',
        'prepared_local_path', 'prepared_sha256', 'prepared_duration',
        'segment_start_frame', 'segment_end_frame_exclusive',
    )
    for index, sample in enumerate(samples):
        sample_id = sample.get('sample_id', f'samples[{index}]') if isinstance(sample, dict) else f'samples[{index}]'
        _require(isinstance(sample, dict), f'{sample_id} must be an object')
        _require(sample.get('prepared_local_path') is not None,
                 f'{sample_id} has no prepared audio')
        _require(sample.get('source_file_kind') == 'full_track'
                 and sample.get('full_track_verified') is True,
                 f'{sample_id} is not a verified full-track source')
        missing = [field for field in required if sample.get(field) is None]
        _require(not missing,
                 f'{sample_id} is not embedding-ready; missing: {", ".join(missing)}')
        for field in ('source_local_path', 'source_sha256', 'full_track_evidence',
                      'prepared_local_path', 'prepared_sha256'):
            _require(isinstance(sample.get(field), str) and bool(sample[field].strip()),
                     f'{sample_id}.{field} is blank')
        for field in ('source_file_size', 'decoded_frame_count', 'source_sample_rate',
                      'source_channels', 'segment_start_frame', 'segment_end_frame_exclusive'):
            _require(type(sample.get(field)) is int and sample[field] >= 0,
                     f'{sample_id}.{field} must be a non-negative integer')
        _require(sample['source_file_size'] > 0 and sample['decoded_frame_count'] > 0
                 and sample['source_sample_rate'] > 0 and sample['source_channels'] > 0,
                 f'{sample_id} has invalid source/decode dimensions')
        _require(sample.get('decoded_duration', 0) >= 60,
                 f'{sample_id} decoded audio is shorter than 60 seconds')
        _require(sample.get('prepared_duration') == 60,
                 f'{sample_id}.prepared_duration must equal 60')
        frame_span = sample['segment_end_frame_exclusive'] - sample['segment_start_frame']
        _require(frame_span == 60 * sample['source_sample_rate']
                 and sample['segment_end_frame_exclusive'] <= sample['decoded_frame_count'],
                 f'{sample_id} prepared frame provenance is invalid')


def artifact_content_digest(embeddings, sample_ids):
    """Hash decoded arrays with framing so ZIP timestamps do not define identity."""
    vectors = np.ascontiguousarray(embeddings)
    ids = [str(value) for value in sample_ids]
    digest = hashlib.sha256(ARTIFACT_CONTENT_DIGEST_PREFIX)

    def add(name, payload):
        key = name.encode('ascii')
        digest.update(len(key).to_bytes(4, 'big'))
        digest.update(key)
        digest.update(len(payload).to_bytes(8, 'big'))
        digest.update(payload)

    add('dtype', vectors.dtype.str.encode('ascii'))
    add('shape', json.dumps(list(vectors.shape), separators=(',', ':')).encode('ascii'))
    add('embeddings_c_order', vectors.tobytes(order='C'))
    add('sample_ids_json', json.dumps(ids, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    return digest.hexdigest()


def _npy_bytes(array):
    stream = io.BytesIO()
    np.lib.format.write_array(stream, array, allow_pickle=False)
    return stream.getvalue()


def write_deterministic_npz(path, embeddings, sample_ids):
    """Write a stable NPZ container with fixed ZIP timestamps and member order."""
    arrays = {
        'embeddings': np.ascontiguousarray(embeddings, dtype=np.float32),
        'sample_ids': np.asarray(sample_ids, dtype=np.str_),
    }
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, array in arrays.items():
            info = zipfile.ZipInfo(f'{name}.npy', date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            info.flag_bits = 0
            archive.writestr(info, _npy_bytes(array), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)


def validate_artifact_evidence_pair(artifact_path, evidence_path, expected_artifact_sha=None):
    actual_file_sha = sha256(artifact_path)
    with np.load(artifact_path, allow_pickle=False) as archive:
        embeddings = np.ascontiguousarray(archive['embeddings'])
        sample_ids = archive['sample_ids'].tolist()
    evidence = parse_json_bytes(Path(evidence_path).read_bytes(), 'Audio embedding evidence', evidence_path)
    artifact = evidence['artifact']
    _require(sample_ids == evidence['input_identity']['sample_ids'],
             'artifact sample_id order differs from evidence')
    _require(list(embeddings.shape) == evidence['embedding_output']['shape'],
             'artifact shape differs from evidence')
    _require(str(embeddings.dtype) == evidence['embedding_output']['dtype'],
             'artifact dtype differs from evidence')
    _require(list(embeddings.shape) == artifact['shape'],
             'artifact shape metadata differs from decoded NPZ')
    _require(str(embeddings.dtype) == artifact['dtype'],
             'artifact dtype metadata differs from decoded NPZ')
    _require(bool(np.isfinite(embeddings).all()), 'artifact contains non-finite values')
    norms = np.linalg.norm(embeddings.astype(np.float64), axis=1)
    _require(np.isfinite(norms).all() and np.all(norms != 0),
             'artifact contains a zero or non-finite vector')
    _require(evidence['embedding_output']['zero_vector_count'] == 0,
             'evidence reports invalid zero vectors')
    _require(evidence['embedding_output']['finite'] is True,
             'evidence does not confirm finite vectors')
    _require(evidence['embedding_output']['l2_norms'] == [float(value) for value in norms],
             'evidence L2 norms differ from decoded vectors')
    _require(artifact['sha256'] == actual_file_sha,
             'evidence artifact file SHA-256 differs from NPZ bytes')
    _require(artifact['content_digest'] == artifact_content_digest(embeddings, sample_ids),
             'evidence artifact content digest differs from decoded NPZ')
    if expected_artifact_sha is not None:
        _require(actual_file_sha == expected_artifact_sha, 'published artifact SHA changed')
    return actual_file_sha


def _generate_pass(prepared_samples, generator):
    vectors = []
    metadata = []
    for item in prepared_samples:
        result = generator.generate(item['prepared_path'], expected_sha256=item['prepared_sha256'])
        validate_audio_embedding(result.vector)
        vector = result.vector.detach().cpu().numpy()
        _require(vector.shape[0] == 1, f"{item['sample_id']} generator must return one vector")
        _require(vector.dtype == np.float32,
                 f"{item['sample_id']} generator returned {vector.dtype}, expected float32")
        _require(np.isfinite(vector).all(), f"{item['sample_id']} vector contains non-finite values")
        vectors.append(vector[0].copy())
        metadata.append(result.metadata)
        _require(result.metadata.get('source_sha256') == item['prepared_sha256'],
                 f"{item['sample_id']} generator input SHA differs from prepared SHA")
    matrix = np.ascontiguousarray(np.stack(vectors), dtype=np.float32)
    return matrix, metadata


def _model_identity(metadata, expected_checkpoint_sha256, expected_checkpoint_revision=None):
    first = metadata[0]
    _require(first.get('model') == 'MSCLAP' and first.get('model_version') == '2023',
             'AudioEmbeddingGenerator did not report MSCLAP 2023')
    _require(first.get('preprocessing_version') == PREPROCESSING_VERSION,
             'AudioEmbeddingGenerator preprocessing version differs from the approved generator')
    for item in metadata[1:]:
        for key in ('model', 'model_version', 'preprocessing_version', 'preprocessing', 'dimension', 'dtype', 'device'):
            _require(item.get(key) == first.get(key), f'generator metadata differs between samples: {key}')
    checkpoint_path = Path(first.get('checkpoint_path', '')).resolve()
    _require(checkpoint_path.is_file(), 'MSCLAP checkpoint path is missing or unavailable')
    checkpoint_sha256 = sha256(checkpoint_path)
    _require(checkpoint_sha256 == expected_checkpoint_sha256,
             'MSCLAP checkpoint SHA-256 differs from canonical Text Embedding evidence')
    if expected_checkpoint_revision is not None:
        _require(first.get('checkpoint_revision') == expected_checkpoint_revision,
                 'MSCLAP checkpoint snapshot revision differs from canonical Text Embedding evidence')
    packages = first.get('packages')
    _require(isinstance(packages, dict), 'AudioEmbeddingGenerator package identity is missing')
    for name in ('msclap', 'torch', 'torchaudio'):
        value = packages.get(name)
        _require(isinstance(value, str) and bool(value.strip()),
                 f'AudioEmbeddingGenerator package identity is missing: {name}')
    preprocessing = first.get('preprocessing')
    _require(isinstance(preprocessing, dict) and bool(preprocessing),
             'AudioEmbeddingGenerator preprocessing identity is missing')
    return {
        'model': first['model'],
        'model_version': first['model_version'],
        'checkpoint_file': checkpoint_path.name,
        'checkpoint_revision': first.get('checkpoint_revision'),
        'checkpoint_sha256': checkpoint_sha256,
        'preprocessing_version': first['preprocessing_version'],
        'preprocessing': preprocessing,
        'packages': packages,
        'device': first['device'],
        'embedding_dimension': first['dimension'],
        'embedding_dtype': first['dtype'],
    }


def generate_embedding_result(
    prepared_samples,
    generator,
    *,
    root,
    manifest_path,
    manifest_sha256,
    git_commit_sha,
    working_tree_clean,
    expected_checkpoint_sha256,
    expected_checkpoint_revision=None,
    cohort_status=None,
):
    """Run two fixed-order passes and return arrays plus auditable evidence."""
    sample_ids = [item['sample_id'] for item in prepared_samples]
    _require(len(sample_ids) == len(set(sample_ids)), 'duplicate sample_id in prepared input')
    first_vectors, first_metadata = _generate_pass(prepared_samples, generator)
    repeated_vectors, repeated_metadata = _generate_pass(prepared_samples, generator)
    _require(first_vectors.shape == repeated_vectors.shape,
             'repeated batch output shape changed')
    exact_equal = np.array_equal(first_vectors, repeated_vectors)
    _require(exact_equal, 'same ordered prepared batch did not reproduce bitwise-identical embeddings')
    _require(first_vectors.ndim == 2 and first_vectors.shape[0] == len(prepared_samples)
             and first_vectors.shape[1] > 0, 'embedding matrix has invalid shape')
    _require(np.isfinite(first_vectors).all(), 'embedding matrix contains NaN or Infinity')
    norms = np.linalg.norm(first_vectors.astype(np.float64), axis=1)
    _require(np.isfinite(norms).all() and np.all(norms != 0),
             'embedding matrix contains a zero or non-finite vector norm')
    model = _model_identity(
        first_metadata, expected_checkpoint_sha256, expected_checkpoint_revision
    )
    repeated_model = _model_identity(
        repeated_metadata, expected_checkpoint_sha256, expected_checkpoint_revision
    )
    _require(model == repeated_model, 'model/runtime identity changed between repeated passes')
    _require(model['embedding_dimension'] == first_vectors.shape[1],
             'generator embedding dimension differs from output shape')
    _require(model['embedding_dtype'] == 'torch.float32',
             'generator metadata must report torch.float32 embeddings')
    generated_at = datetime.now(timezone.utc).isoformat()
    evidence = {
        'schema_version': 1,
        'experiment': 'NSUAI-36 calibration v1 Audio Embedding',
        'result_status': 'PASS',
        'generated_at_utc': generated_at,
        'scope_limitations': [
            'Audio vector generation does not validate Text/Audio similarity or recommendation quality',
            'No cosine calculation or ranking was performed',
            'Calibration vectors are not production validation',
        ],
        'input_identity': {
            'git_commit_sha': git_commit_sha,
            'working_tree_clean_before_and_after_inference': working_tree_clean,
            'manifest_path': _display_path(root, manifest_path),
            'manifest_bytes_sha256': manifest_sha256,
            'cohort_target': 50,
            'cohort_status': cohort_status,
            'sample_count': len(sample_ids),
            'sample_ids': sample_ids,
            'samples': [{
                'sample_id': item['sample_id'],
                'source_sha256': item['source_sha256'],
                'source_local_path': item['source_relative_path'],
                'source_file_size': item['source_file_size'],
                'decoded_frame_count': item['decoded_frame_count'],
                'prepared_local_path': item['prepared_relative_path'],
                'prepared_sha256': item['prepared_sha256'],
                'prepared_duration': 60,
                'segment_start_frame': item['segment_start_frame'],
                'segment_end_frame_exclusive': item['segment_end_frame_exclusive'],
                'source_sample_rate': item['source_sample_rate'],
                'source_channels': item['source_channels'],
            } for item in prepared_samples],
        },
        'model_runtime': {
            **model,
            'runner_path': 'scripts/embedding/generate_calibration_audio_embeddings.py',
            'runner_sha256': sha256(Path(__file__).resolve()),
            'python_version': sys.version.split()[0],
            'runtime_packages': {
                name: importlib.metadata.version(name)
                for name in ('numpy', 'torch', 'torchaudio', 'transformers', 'msclap')
            },
            'repeatability_contract': 'same ordered sample batch must be bitwise identical on repeated generation',
        },
        'reproducibility': {
            'same_ordered_batch_repeated': {
                'exact_equal': exact_equal,
                'max_absolute_difference': 0.0,
                'rms_difference': 0.0,
            },
        },
        'embedding_output': {
            'shape': list(first_vectors.shape),
            'dtype': str(first_vectors.dtype),
            'device': model['device'],
            'finite': True,
            'nan_count': 0,
            'positive_infinity_count': 0,
            'negative_infinity_count': 0,
            'zero_vector_count': 0,
            'l2_norms': [float(value) for value in norms],
        },
        'artifact': {
            'path': None,
            'sha256': None,
            'content_digest': None,
            'content_digest_algorithm': ARTIFACT_CONTENT_DIGEST_ALGORITHM,
            'sample_ids_key': 'sample_ids',
            'embeddings_key': 'embeddings',
            'shape': list(first_vectors.shape),
            'dtype': str(first_vectors.dtype),
        },
    }
    return first_vectors, sample_ids, evidence


def _display_path(root, path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _write_temporary_outputs(artifact_path, evidence_path, embeddings, sample_ids, evidence):
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_fd, artifact_name = tempfile.mkstemp(
        prefix=f'.{artifact_path.name}.', suffix='.tmp', dir=artifact_path.parent
    )
    os.close(artifact_fd)
    artifact_temp = Path(artifact_name)
    evidence_temp = None
    try:
        evidence_fd, evidence_name = tempfile.mkstemp(
            prefix=f'.{evidence_path.name}.', suffix='.tmp', dir=evidence_path.parent
        )
        os.close(evidence_fd)
        evidence_temp = Path(evidence_name)
        with artifact_temp.open('wb') as stream:
            write_deterministic_npz(stream, embeddings, sample_ids)
            stream.flush()
            os.fsync(stream.fileno())
        evidence['artifact']['path'] = _display_path(REPOSITORY_ROOT, artifact_path)
        evidence['artifact']['sha256'] = sha256(artifact_temp)
        evidence['artifact']['content_digest'] = artifact_content_digest(embeddings, sample_ids)
        with evidence_temp.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(evidence, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        validate_artifact_evidence_pair(
            artifact_temp, evidence_temp, expected_artifact_sha=evidence['artifact']['sha256']
        )
        return artifact_temp, evidence_temp
    except BaseException:
        artifact_temp.unlink(missing_ok=True)
        if evidence_temp is not None:
            evidence_temp.unlink(missing_ok=True)
        raise


def publish_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path):
    """Publish two previously validated new files without replacing existing outputs."""
    published = []
    try:
        os.link(artifact_temp, artifact_path)
        published.append(artifact_path)
        os.link(evidence_temp, evidence_path)
        published.append(evidence_path)
        validate_artifact_evidence_pair(artifact_path, evidence_path)
    except Exception as publish_error:
        rollback_errors = []
        for path in reversed(published):
            try:
                path.unlink()
            except OSError as rollback_error:
                rollback_errors.append(f'{path}: {rollback_error}')
        if rollback_errors:
            raise RuntimeError(
                f'FATAL: artifact/evidence publish failed ({publish_error}); '
                f'rollback failed: {"; ".join(rollback_errors)}'
            ) from publish_error
        raise
    finally:
        artifact_temp.unlink(missing_ok=True)
        evidence_temp.unlink(missing_ok=True)


def _expected_checkpoint_identity(root):
    evidence_path = Path(root) / TEXT_EVIDENCE.relative_to(REPOSITORY_ROOT)
    evidence = _read_json(evidence_path, 'canonical Text Embedding evidence')
    value = evidence.get('model_runtime', {}).get('checkpoint_sha256')
    _require(isinstance(value, str) and len(value) == 64
             and all(character in '0123456789abcdef' for character in value.lower()),
             'canonical Text Embedding evidence has no checkpoint SHA-256')
    revision = evidence.get('model_runtime', {}).get('checkpoint_snapshot_revision')
    _require(isinstance(revision, str) and bool(revision.strip()),
             'canonical Text Embedding evidence has no checkpoint snapshot revision')
    return value, revision


def run(
    *, manifest_path=DEFAULT_MANIFEST, artifact_output=DEFAULT_ARTIFACT,
    evidence_output=DEFAULT_EVIDENCE, root=REPOSITORY_ROOT, generator=None,
    require_complete_cohort=True,
):
    root = Path(root).resolve()
    manifest_path = Path(manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    manifest_path = manifest_path.resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = parse_json_bytes(manifest_bytes, 'calibration manifest', manifest_path)
    prepared_samples = load_prepared_samples(
        manifest, root, require_complete_cohort=require_complete_cohort
    )
    artifact_path, evidence_path = _resolve_outputs(
        root, manifest_path, artifact_output, evidence_output, prepared_samples
    )
    canonical_outputs = canonical_output_pair_mode(
        root, manifest_path, artifact_path, evidence_path
    )
    commit_sha, clean_before = _git_identity(root)
    _require(not canonical_outputs or clean_before,
             'canonical Audio Embedding requires a clean Git working tree')
    generator = generator or AudioEmbeddingGenerator()
    expected_checkpoint_sha256, expected_checkpoint_revision = _expected_checkpoint_identity(
        REPOSITORY_ROOT
    )
    vectors, sample_ids, evidence = generate_embedding_result(
        prepared_samples, generator, root=root, manifest_path=manifest_path,
        manifest_sha256=manifest_sha256, git_commit_sha=commit_sha,
        working_tree_clean=clean_before,
        expected_checkpoint_sha256=expected_checkpoint_sha256,
        expected_checkpoint_revision=expected_checkpoint_revision,
        cohort_status=manifest.get('cohort_status'),
    )
    _require(hashlib.sha256(manifest_path.read_bytes()).hexdigest() == manifest_sha256,
             'manifest bytes changed during Audio Embedding execution')
    for item in prepared_samples:
        _require(sha256(item['prepared_path']) == item['prepared_sha256'],
                 f"{item['sample_id']} prepared audio changed during inference")
        _require(sha256(item['source_path']) == item['source_sha256'],
                 f"{item['sample_id']} source audio changed during inference")
    _, clean_after = _git_identity(root)
    _require(clean_before == clean_after, 'Git working tree changed during Audio Embedding execution')
    _require(not canonical_outputs or clean_after,
             'canonical Audio Embedding requires a clean Git working tree after inference')
    evidence['input_identity']['working_tree_clean_before_and_after_inference'] = clean_before and clean_after
    artifact_temp, evidence_temp = _write_temporary_outputs(
        artifact_path, evidence_path, vectors, sample_ids, evidence
    )
    publish_output_pair(artifact_temp, artifact_path, evidence_temp, evidence_path)
    return parse_json_bytes(evidence_path.read_bytes(), 'Audio embedding evidence', evidence_path)


def canonical_output_pair_mode(root, manifest_path, artifact_path, evidence_path):
    """Require canonical outputs to use the official canonical manifest."""
    root = Path(root).resolve()

    def resolve(path):
        candidate = Path(path)
        return (candidate if candidate.is_absolute() else root / candidate).resolve()

    canonical_artifact = (root / DEFAULT_ARTIFACT.relative_to(REPOSITORY_ROOT)).resolve()
    canonical_evidence = (root / DEFAULT_EVIDENCE.relative_to(REPOSITORY_ROOT)).resolve()
    canonical_manifest = (root / DEFAULT_MANIFEST.relative_to(REPOSITORY_ROOT)).resolve()
    artifact_is_canonical = os.path.normcase(str(resolve(artifact_path))) == os.path.normcase(
        str(canonical_artifact)
    )
    evidence_is_canonical = os.path.normcase(str(resolve(evidence_path))) == os.path.normcase(
        str(canonical_evidence)
    )
    _require(
        artifact_is_canonical == evidence_is_canonical,
        'canonical Audio Embedding artifact and evidence outputs must be selected as a pair',
    )
    manifest_is_canonical = os.path.normcase(str(resolve(manifest_path))) == os.path.normcase(
        str(canonical_manifest)
    )
    _require(
        not artifact_is_canonical or manifest_is_canonical,
        'canonical Audio Embedding outputs require the canonical calibration manifest',
    )
    return artifact_is_canonical


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--artifact-output', type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument('--evidence-output', type=Path, default=DEFAULT_EVIDENCE)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        evidence = run(
            manifest_path=args.manifest,
            artifact_output=args.artifact_output,
            evidence_output=args.evidence_output,
        )
        print(json.dumps({
            'result_status': evidence['result_status'],
            'artifact': evidence['artifact'],
            'sample_count': evidence['input_identity']['sample_count'],
            'shape': evidence['embedding_output']['shape'],
            'dtype': evidence['embedding_output']['dtype'],
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f'Calibration Audio Embedding failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
