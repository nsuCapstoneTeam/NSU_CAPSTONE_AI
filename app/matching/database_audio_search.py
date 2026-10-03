"""공통 입력 임베딩과 DB의 저장 벡터를 연결하는 곡 단위 음악 검색."""

from app.core.database import connect_database
from app.embedding.audio_embedding import AudioEmbeddingGenerator
from app.matching.normalization import normalize_audio_similarity_score
from app.repository.embedding_repository import AudioEmbeddingRepository


class DatabaseAudioSearch:
    def __init__(self, generator=None, repository=None):
        self.generator = generator if generator is not None else AudioEmbeddingGenerator()
        self.repository = repository if repository is not None else AudioEmbeddingRepository()

    def search(self, audio_path, *, top_k=5):
        """입력 음악만 생성하고 후보는 저장된 벡터로 검색한다. 입력은 DB에 저장하지 않는다."""
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError('top_k must be an integer between 1 and 100')
        query = self.generator.generate(audio_path)
        with connect_database() as connection:
            # 검색 경로에서 실수로 원본·후보를 변경하지 못하도록 트랜잭션도 읽기 전용으로 제한한다.
            connection.execute('SET TRANSACTION READ ONLY')
            found = self.repository.search(connection, query, top_k=top_k)
        results = [dict(row, rank=index + 1,
                        audio_similarity_score=normalize_audio_similarity_score(row['cosine_similarity']))
                   for index, row in enumerate(found['results'])]
        return {
            'status': 'ok' if results else 'no_candidates',
            'candidate_source': 'postgresql-pgvector', 'comparison': 'audio-audio',
            'query_sha256': query.metadata['source_sha256'],
            'embedding_dimension': query.metadata['dimension'],
            'requested_top_k': top_k, 'candidate_count': found['candidate_count'],
            'score_bounds': {'lower': 0.0, 'upper': 1.0, 'status': 'provisional'},
            'results': results,
            'warning': 'Audio similarity index, not event suitability or probability. Track-level results, not artist TOP 5.',
        }
