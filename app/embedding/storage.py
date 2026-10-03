"""생성과 저장을 연결하며 모델 실행 중에는 DB 트랜잭션을 유지하지 않는다."""

from app.core.database import connect_database
from app.embedding.audio_embedding import AudioEmbeddingGenerator
from app.repository.embedding_repository import AudioEmbeddingRepository, validate_music_id


class AudioEmbeddingStorage:
    def __init__(self, generator=None, repository=None):
        self.generator = generator if generator is not None else AudioEmbeddingGenerator()
        self.repository = repository if repository is not None else AudioEmbeddingRepository()

    def store(self, music_id, audio_path):
        """외부 음악 ID에 파일의 임베딩을 동기 생성·저장한다.

        생성 실패 시 DB를 변경하지 않고, 저장 실패 시 트랜잭션 전체를 취소한다.
        """
        validate_music_id(music_id)
        # 검색과 동일한 생성기를 사용해 저장된 벡터와 검색 입력의 전처리가 달라지는 것을 막는다.
        result = self.generator.generate(audio_path)
        # 모델 로딩·디코딩은 오래 걸릴 수 있으므로 완료 후에만 DB 연결과 트랜잭션을 연다.
        with connect_database() as connection:
            saved = self.repository.save(connection, music_id, result)
        return saved
