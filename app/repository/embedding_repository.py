"""음악 ID별 최초 저장과 동일 결과의 재요청만 허용하는 임시 저장 계약이다."""

import hashlib
import json
import math
import re
from dataclasses import dataclass

from psycopg.types.json import Jsonb

from app.embedding.audio_embedding import PREPROCESSING_VERSION, validate_audio_embedding
from app.embedding.text_embedding import (
    CALIBRATION_CHECKPOINT_REVISION,
    CALIBRATION_CHECKPOINT_SHA256,
    CALIBRATION_MSCLAP_CONFIG_SHA256,
    CALIBRATION_MSCLAP_PACKAGE_VERSION,
    CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
    CALIBRATION_MSCLAP_SOURCE_SHA256,
    GENERATION_PROFILE as TEXT_GENERATION_PROFILE,
    GENERATION_VERSION as TEXT_GENERATION_VERSION,
    MODEL_VERSION as TEXT_MODEL_VERSION,
    TEXT_EMBEDDING_DIMENSION,
    TEXT_ENCODER_MODEL_ID,
    TEXT_ENCODER_MODEL_SHA256,
    TEXT_ENCODER_REVISION,
    TEXT_ENCODER_TOKENIZER_FILE_SHA256,
    TextEmbeddingError,
    validate_text_embedding,
)


class EmbeddingConflict(ValueError):
    """협의되지 않은 수정 요청으로 기존 임베딩이 교체되는 것을 방지한다."""


@dataclass(frozen=True)
class EmbeddingSaveResult:
    music_id: str
    created: bool
    source_sha256: str
    dimension: int


def validate_music_id(music_id):
    if not isinstance(music_id, str) or not music_id.strip() or len(music_id) > 200 or music_id != music_id.strip():
        raise ValueError('music_id must be a nonblank string of at most 200 characters without surrounding whitespace')


def prepare_embedding(result):
    """DB 전달 직전에도 벡터와 생성 정보의 정합성을 검사한다."""
    import torch
    metadata = result.metadata
    dimension = metadata.get('dimension')
    if type(dimension) is not int or not 1 <= dimension <= 16000:
        raise ValueError('invalid_embedding_dimension')
    validate_audio_embedding(result.vector, expected_dimension=dimension)
    if metadata.get('shape') != [1, dimension]:
        raise ValueError('embedding_metadata_shape_mismatch')
    if not isinstance(metadata.get('source_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', metadata['source_sha256']):
        raise ValueError('invalid_source_sha256')
    for key in ('model', 'model_version', 'preprocessing_version'):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f'invalid_{key}')
    packages = metadata.get('packages')
    implementation = metadata.get('msclap_implementation')
    if not isinstance(packages, dict) or not isinstance(metadata.get('preprocessing'), dict):
        raise ValueError('missing_generation_profile')
    if not isinstance(packages.get('msclap'), str) or not packages['msclap'].strip():
        raise ValueError('missing_msclap_package_identity')
    checkpoint_revision = metadata.get('checkpoint_revision')
    checkpoint_sha256 = metadata.get('checkpoint_sha256')
    if not isinstance(checkpoint_revision, str) or not re.fullmatch('[0-9a-f]{40}', checkpoint_revision):
        raise ValueError('invalid_checkpoint_revision')
    if not isinstance(checkpoint_sha256, str) or not re.fullmatch('[0-9a-f]{64}', checkpoint_sha256):
        raise ValueError('invalid_checkpoint_sha256')
    if (
        not isinstance(implementation, dict)
        or implementation.get('package_version') != packages['msclap']
        or type(implementation.get('source_file_count')) is not int
        or implementation['source_file_count'] < 1
        or not re.fullmatch('[0-9a-f]{64}', str(implementation.get('source_sha256', '')))
        or implementation.get('config_file') != 'configs/config_2023.yml'
        or not re.fullmatch('[0-9a-f]{64}', str(implementation.get('config_sha256', '')))
    ):
        raise ValueError('missing_msclap_implementation_identity')
    # 경로가 바뀌어도 내용과 생성 조건은 같을 수 있으므로 경로는 동일성 판단에서 제외한다.
    profile = {key: metadata.get(key) for key in (
        'model', 'model_version', 'checkpoint_revision', 'checkpoint_sha256',
        'msclap_implementation', 'packages',
        'preprocessing_version', 'preprocessing', 'dimension', 'dtype', 'device',
    )}
    json.dumps(metadata, allow_nan=False)
    # pgvector의 단정밀도 값으로 비교하고, ID·메타데이터는 SQL에 직접 삽입하지 않는다.
    stored_vector = result.vector.detach().cpu().to(dtype=torch.float32)
    validate_audio_embedding(stored_vector, expected_dimension=dimension)
    vector = json.dumps(stored_vector[0].tolist(), allow_nan=False)
    return metadata, profile, vector


class AudioEmbeddingRepository:
    def search(self, connection, query_result, *, top_k=5):
        """호환되는 저장 벡터만 pgvector 코사인 거리로 비교하고 동일 파일은 제외한다."""
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError('top_k must be an integer between 1 and 100')
        metadata, profile, vector = prepare_embedding(query_result)
        with connection.cursor() as cursor:
            # 차원 혼합 테이블에서 거리 계산이 필터보다 먼저 실행되지 않도록 후보를 먼저 확정한다.
            # 후보 수와 TopK도 한 SQL 스냅샷에서 계산해 동시 등록 중 서로 다른 목록을 보고하지 않는다.
            cursor.execute('''WITH eligible AS MATERIALIZED (
                SELECT music_id, embedding FROM ai_embeddings.audio_embeddings
                WHERE dimension = %s
                  AND generation_profile = %s
                  AND source_sha256 <> %s
            )
            SELECT totals.candidate_count, matches.music_id, matches.cosine_similarity
            FROM (SELECT count(*) AS candidate_count FROM eligible) totals
            LEFT JOIN LATERAL (
                SELECT music_id, 1 - (embedding <=> %s::vector) AS cosine_similarity
                FROM eligible ORDER BY embedding <=> %s::vector, music_id COLLATE "C"
                LIMIT %s
            ) matches ON true''',
                (metadata['dimension'], Jsonb(profile), metadata['source_sha256'], vector, vector, top_k))
            rows = cursor.fetchall()
        results = []
        for _, music_id, value in rows:
            if music_id is None:
                continue
            cosine = float(value)
            if not math.isfinite(cosine):
                raise ValueError('invalid_database_cosine')
            results.append({'music_id': music_id, 'cosine_similarity': max(-1.0, min(1.0, cosine))})
        return {
            'candidate_count': rows[0][0],
            'results': results,
        }

    def save(self, connection, music_id, result):
        """같은 ID의 동시 등록을 DB 제약으로 처리하고 동일한 결과만 재사용한다.

        호출자가 트랜잭션을 관리하며 충돌이나 SQL 실패 시 전체를 롤백해야 한다.
        """
        validate_music_id(music_id)
        metadata, profile, vector = prepare_embedding(result)
        with connection.cursor() as cursor:
            # 사전 조회만으로 동시 등록을 막을 수 없어 기본키 제약을 최종 판단에 사용한다.
            cursor.execute('''INSERT INTO ai_embeddings.audio_embeddings
                (music_id, source_sha256, model, model_version, preprocessing_version,
                 dimension, embedding, generation_profile, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s)
                ON CONFLICT (music_id) DO NOTHING RETURNING music_id''',
                (music_id, metadata['source_sha256'], metadata['model'], metadata['model_version'],
                 metadata['preprocessing_version'], metadata['dimension'], vector, Jsonb(profile), Jsonb(metadata)))
            created = cursor.fetchone() is not None
            if not created:
                cursor.execute('''SELECT source_sha256 = %s AND generation_profile = %s
                    AND embedding = %s::vector FROM ai_embeddings.audio_embeddings
                    WHERE music_id = %s FOR UPDATE''',
                    (metadata['source_sha256'], Jsonb(profile), vector, music_id))
                row = cursor.fetchone()
                if row is None or not row[0]:
                    raise EmbeddingConflict('music_id_already_has_different_embedding')
        return EmbeddingSaveResult(music_id, created, metadata['source_sha256'], metadata['dimension'])


@dataclass(frozen=True)
class TextEmbeddingSaveResult:
    query_text_sha256: str
    generation_profile_sha256: str
    created: bool
    dimension: int


def prepare_text_embedding(result):
    """Validate and identify a Text Embedding before it crosses the DB boundary."""
    try:
        metadata = result.metadata
        dimension = metadata.get('dimension')
        if type(dimension) is not int or dimension != TEXT_EMBEDDING_DIMENSION:
            raise ValueError('invalid_embedding_dimension')
        vector_tensor = validate_text_embedding(result.vector, expected_count=1, expected_dimension=dimension)
        if metadata.get('shape') != [1, dimension]:
            raise ValueError('embedding_metadata_shape_mismatch')
        input_sha = metadata.get('query_text_sha256')
        if not isinstance(input_sha, str) or not re.fullmatch('[0-9a-f]{64}', input_sha):
            raise ValueError('invalid_query_text_sha256')
        generation_version = metadata.get('generation_version')
        generation_profile = metadata.get('embedding_generation_profile')
        if not isinstance(generation_version, str) or not generation_version.strip():
            raise ValueError('invalid_generation_version')
        if not isinstance(generation_profile, str) or not generation_profile.strip():
            raise ValueError('invalid_generation_profile')
        for key in ('model', 'model_version', 'checkpoint_revision', 'checkpoint_sha256'):
            if not isinstance(metadata.get(key), str) or not metadata[key].strip():
                raise ValueError(f'invalid_{key}')
        if not re.fullmatch('[0-9a-f]{40}', metadata['checkpoint_revision']):
            raise ValueError('invalid_checkpoint_revision')
        if not re.fullmatch('[0-9a-f]{64}', metadata['checkpoint_sha256']):
            raise ValueError('invalid_checkpoint_sha256')
        packages = metadata.get('packages')
        implementation = metadata.get('msclap_implementation')
        if not isinstance(packages, dict) or not isinstance(packages.get('msclap'), str) or not packages['msclap'].strip():
            raise ValueError('missing_msclap_package_identity')
        if (
            not isinstance(implementation, dict)
            or implementation.get('package_version') != packages.get('msclap')
            or type(implementation.get('source_file_count')) is not int
            or implementation['source_file_count'] < 1
            or not re.fullmatch('[0-9a-f]{64}', str(implementation.get('source_sha256', '')))
            or implementation.get('config_file') != 'configs/config_2023.yml'
            or not re.fullmatch('[0-9a-f]{64}', str(implementation.get('config_sha256', '')))
        ):
            raise ValueError('missing_msclap_implementation_identity')
        text_encoder = metadata.get('text_encoder')
        if (
            not isinstance(text_encoder, dict)
            or not isinstance(text_encoder.get('model_id'), str)
            or not text_encoder['model_id'].strip()
            or not re.fullmatch('[0-9a-f]{40}', str(text_encoder.get('revision', '')))
            or not re.fullmatch('[0-9a-f]{64}', str(text_encoder.get('config_sha256', '')))
            or not isinstance(text_encoder.get('model_file'), str)
            or not re.fullmatch('[0-9a-f]{64}', str(text_encoder.get('model_file_sha256', '')))
            or text_encoder.get('tokenizer_id') != text_encoder.get('model_id')
            or text_encoder.get('tokenizer_revision') != text_encoder.get('revision')
            or not isinstance(text_encoder.get('tokenizer_files_sha256'), dict)
            or any(not re.fullmatch('[0-9a-f]{64}', str(value))
                   for value in text_encoder['tokenizer_files_sha256'].values())
            or not re.fullmatch('[0-9a-f]{64}', str(text_encoder.get('tokenizer_runtime_sha256', '')))
        ):
            raise ValueError('unsupported_text_encoder_identity')
        if metadata.get('dtype') != str(vector_tensor.dtype):
            raise ValueError('embedding_metadata_dtype_mismatch')
        if not isinstance(metadata.get('device'), str) or not metadata['device'].strip():
            raise ValueError('invalid_embedding_device')

        # Token counts and query hash describe the input, not the generation profile.
        preprocessing = metadata.get('text_preprocessing')
        if not isinstance(preprocessing, dict):
            raise ValueError('missing_text_generation_profile')
        input_independent_preprocessing = {
            key: preprocessing[key] for key in (
                'encoder_api', 'text_model', 'text_model_revision', 'token_limit',
                'truncation', 'normalization',
            ) if key in preprocessing
        }
        if set(input_independent_preprocessing) != {
            'encoder_api', 'text_model', 'text_model_revision', 'token_limit', 'truncation', 'normalization'
        }:
            raise ValueError('missing_text_generation_profile')
        profile = {
            key: metadata[key] for key in (
                'model', 'model_version', 'checkpoint_revision', 'checkpoint_sha256',
                'msclap_implementation', 'text_encoder', 'packages', 'dimension', 'dtype',
                'generation_version', 'embedding_generation_profile',
            ) if key in metadata
        }
        profile['text_preprocessing'] = input_independent_preprocessing
        profile_json = json.dumps(profile, sort_keys=True, separators=(',', ':'), allow_nan=False)
        json.dumps(metadata, sort_keys=True, separators=(',', ':'), allow_nan=False)
        import torch
        vector = vector_tensor.detach().cpu().to(dtype=torch.float32)
        validate_text_embedding(vector, expected_count=1, expected_dimension=dimension)
        vector_json = json.dumps(vector[0].tolist(), allow_nan=False)
    except TextEmbeddingError as exc:
        raise ValueError('invalid_text_embedding_vector') from exc
    except (AttributeError, TypeError) as exc:
        raise ValueError('invalid_text_embedding_result') from exc
    profile_sha256 = hashlib.sha256(profile_json.encode('utf-8')).hexdigest()
    return metadata, profile, profile_sha256, vector_json


def text_audio_profiles_compatible(text_profile, audio_profile):
    """Require supported modality profiles and the same calibrated joint CLAP space."""
    if not isinstance(text_profile, dict) or not isinstance(audio_profile, dict):
        return False
    text_packages = text_profile.get('packages')
    audio_packages = audio_profile.get('packages')
    expected_implementation = {
        'package_version': CALIBRATION_MSCLAP_PACKAGE_VERSION,
        'source_file_count': CALIBRATION_MSCLAP_SOURCE_FILE_COUNT,
        'source_sha256': CALIBRATION_MSCLAP_SOURCE_SHA256,
        'config_file': 'configs/config_2023.yml',
        'config_sha256': CALIBRATION_MSCLAP_CONFIG_SHA256,
    }
    text_implementation = text_profile.get('msclap_implementation')
    audio_implementation = audio_profile.get('msclap_implementation')
    expected_text_preprocessing = {
        'encoder_api': 'CLAP.get_text_embeddings',
        'text_model': TEXT_ENCODER_MODEL_ID,
        'text_model_revision': TEXT_ENCODER_REVISION,
        'token_limit': 77,
        'truncation': 'rejected',
        'normalization': 'none; raw MSCLAP Text Embedding',
    }
    return all((
        text_profile.get('generation_version') == TEXT_GENERATION_VERSION,
        text_profile.get('embedding_generation_profile') == TEXT_GENERATION_PROFILE,
        audio_profile.get('preprocessing_version') == PREPROCESSING_VERSION,
        text_profile.get('model') == 'MSCLAP',
        text_profile.get('model') == audio_profile.get('model'),
        text_profile.get('model_version') == TEXT_MODEL_VERSION,
        text_profile.get('model_version') == audio_profile.get('model_version'),
        text_profile.get('checkpoint_revision') == CALIBRATION_CHECKPOINT_REVISION,
        text_profile.get('checkpoint_revision') == audio_profile.get('checkpoint_revision'),
        text_profile.get('checkpoint_sha256') == CALIBRATION_CHECKPOINT_SHA256,
        text_profile.get('dtype') == 'torch.float32',
        text_profile.get('text_preprocessing') == expected_text_preprocessing,
        isinstance(text_profile.get('text_encoder'), dict)
        and text_profile['text_encoder'].get('model_id') == TEXT_ENCODER_MODEL_ID
        and text_profile['text_encoder'].get('revision') == TEXT_ENCODER_REVISION
        and text_profile['text_encoder'].get('config_sha256') == TEXT_ENCODER_TOKENIZER_FILE_SHA256['config.json']
        and text_profile['text_encoder'].get('model_file') == 'model.safetensors'
        and text_profile['text_encoder'].get('model_file_sha256') == TEXT_ENCODER_MODEL_SHA256
        and text_profile['text_encoder'].get('tokenizer_id') == TEXT_ENCODER_MODEL_ID
        and text_profile['text_encoder'].get('tokenizer_revision') == TEXT_ENCODER_REVISION
        and text_profile['text_encoder'].get('tokenizer_files_sha256') == TEXT_ENCODER_TOKENIZER_FILE_SHA256
        and isinstance(text_profile['text_encoder'].get('tokenizer_runtime_sha256'), str)
        and re.fullmatch('[0-9a-f]{64}', text_profile['text_encoder']['tokenizer_runtime_sha256']) is not None,
        text_profile.get('checkpoint_sha256') == audio_profile.get('checkpoint_sha256'),
        text_implementation == expected_implementation,
        audio_implementation == expected_implementation,
        text_implementation == audio_implementation,
        text_profile.get('dimension') == TEXT_EMBEDDING_DIMENSION
        and type(audio_profile.get('dimension')) is int
        and text_profile.get('dimension') == audio_profile.get('dimension'),
        isinstance(text_packages, dict) and isinstance(audio_packages, dict)
        and text_packages.get('msclap') == CALIBRATION_MSCLAP_PACKAGE_VERSION
        and text_packages.get('msclap') == audio_packages.get('msclap'),
    ))


class TextEmbeddingRepository:
    """Store exact query/profile identities separately from music-keyed Audio rows."""

    def save(self, connection, result):
        metadata, profile, profile_sha, vector = prepare_text_embedding(result)
        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO ai_embeddings.text_embeddings
                (query_text_sha256, generation_version, generation_profile_sha256,
                 dimension, embedding, generation_profile, metadata)
                VALUES (%s, %s, %s, %s, %s::vector, %s, %s)
                ON CONFLICT (query_text_sha256, generation_profile_sha256) DO NOTHING
                RETURNING query_text_sha256''',
                (metadata['query_text_sha256'], metadata['generation_version'], profile_sha,
                 metadata['dimension'], vector, Jsonb(profile), Jsonb(metadata)))
            created = cursor.fetchone() is not None
            if not created:
                cursor.execute('''SELECT dimension = %s AND generation_version = %s
                    AND generation_profile = %s AND embedding = %s::vector
                    FROM ai_embeddings.text_embeddings
                    WHERE query_text_sha256 = %s AND generation_profile_sha256 = %s FOR UPDATE''',
                    (metadata['dimension'], metadata['generation_version'], Jsonb(profile), vector,
                     metadata['query_text_sha256'], profile_sha))
                row = cursor.fetchone()
                if row is None or not row[0]:
                    raise EmbeddingConflict('text_embedding_identity_has_different_vector_or_profile')
        return TextEmbeddingSaveResult(metadata['query_text_sha256'], profile_sha, created, metadata['dimension'])

    def get(self, connection, query_text_sha256, generation_profile_sha256):
        if not re.fullmatch('[0-9a-f]{64}', str(query_text_sha256)) or not re.fullmatch(
            '[0-9a-f]{64}', str(generation_profile_sha256)
        ):
            raise ValueError('invalid_text_embedding_identity')
        with connection.cursor() as cursor:
            cursor.execute('''SELECT embedding::text, dimension, generation_version,
                generation_profile_sha256, generation_profile, metadata
                FROM ai_embeddings.text_embeddings
                WHERE query_text_sha256 = %s AND generation_profile_sha256 = %s''',
                (query_text_sha256, generation_profile_sha256))
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            'embedding': row[0], 'dimension': row[1], 'generation_version': row[2],
            'generation_profile_sha256': row[3], 'generation_profile': row[4], 'metadata': row[5],
        }

    def search_audio(self, connection, result, *, top_k=100):
        """Return only Audio rows sharing the Text query's common CLAP projection identity."""
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError('top_k must be an integer between 1 and 100')
        _, profile, _, vector = prepare_text_embedding(result)
        if not text_audio_profiles_compatible(profile, {
            'preprocessing_version': PREPROCESSING_VERSION,
            'model': profile['model'],
            'model_version': profile['model_version'],
            'checkpoint_revision': profile['checkpoint_revision'],
            'checkpoint_sha256': profile['checkpoint_sha256'],
            'msclap_implementation': profile['msclap_implementation'],
            'dimension': profile['dimension'],
            'packages': profile['packages'],
        }):
            raise ValueError('text_embedding_profile_is_not_audio_search_compatible')
        common = (profile['model'], profile['model_version'], profile['checkpoint_revision'],
                  profile['checkpoint_sha256'], profile['dimension'], profile['packages']['msclap'],
                  profile['msclap_implementation'])
        with connection.cursor() as cursor:
            cursor.execute('''WITH eligible AS MATERIALIZED (
                SELECT music_id, embedding FROM ai_embeddings.audio_embeddings
                WHERE dimension = %s
                  AND generation_profile->>'model' = %s
                  AND generation_profile->>'model_version' = %s
                  AND generation_profile->>'checkpoint_revision' = %s
                  AND generation_profile->>'checkpoint_sha256' = %s
                  AND generation_profile->'packages'->>'msclap' = %s
                  AND generation_profile->'msclap_implementation' = %s
                  AND generation_profile->>'preprocessing_version' = %s
            )
            SELECT totals.candidate_count, matches.music_id, matches.cosine_similarity
            FROM (SELECT count(*) AS candidate_count FROM eligible) totals
            LEFT JOIN LATERAL (
                SELECT music_id, 1 - (embedding <=> %s::vector) AS cosine_similarity
                FROM eligible ORDER BY embedding <=> %s::vector, music_id COLLATE "C"
                LIMIT %s
            ) matches ON true''',
                (common[4], common[0], common[1], common[2], common[3], common[5],
                 Jsonb(common[6]), PREPROCESSING_VERSION,
                 vector, vector, top_k))
            rows = cursor.fetchall()
        results = []
        for _, music_id, value in rows:
            if music_id is None:
                continue
            cosine = float(value)
            if not math.isfinite(cosine):
                raise ValueError('invalid_database_cosine')
            results.append({'music_id': music_id, 'cosine_similarity': max(-1.0, min(1.0, cosine))})
        return {'candidate_count': rows[0][0], 'results': results}
