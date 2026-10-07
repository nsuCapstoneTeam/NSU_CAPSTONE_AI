"""음악 ID별 최초 저장과 동일 결과의 재요청만 허용하는 임시 저장 계약이다."""

import json
import math
import re
from dataclasses import dataclass

from psycopg.types.json import Jsonb

from app.embedding.audio_embedding import validate_audio_embedding


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
    if not isinstance(metadata.get('packages'), dict) or not isinstance(metadata.get('preprocessing'), dict):
        raise ValueError('missing_generation_profile')
    # 경로가 바뀌어도 내용과 생성 조건은 같을 수 있으므로 경로는 동일성 판단에서 제외한다.
    profile = {key: metadata.get(key) for key in (
        'model', 'model_version', 'checkpoint_revision', 'packages',
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
