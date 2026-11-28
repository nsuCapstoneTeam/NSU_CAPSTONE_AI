"""생성과 저장을 연결하며 모델 실행 중에는 DB 트랜잭션을 유지하지 않는다."""

from app.core.database import connect_database
from app.embedding.audio_embedding import AudioEmbeddingError, AudioEmbeddingGenerator, validated_audio_sha256
from app.embedding.text_embedding import TextEmbeddingGenerator
from app.repository.audio_processing_repository import (
    AttemptNoLongerProcessing, AudioProcessingRepository,
)
from app.repository.embedding_repository import (
    EmbeddingConflict, EmbeddingSaveResult,
    TextEmbeddingRepository,
    validate_music_id,
    validate_audio_revision,
)


class AudioEmbeddingStorage:
    def __init__(self, generator=None, repository=None):
        self.generator = generator if generator is not None else AudioEmbeddingGenerator()
        self.attempts = AudioProcessingRepository(repository)

    def store(self, music_id, audio_path, *, audio_revision, stale_before=None):
        """정확한 identity를 재사용하거나 새 처리 소유권을 얻은 뒤 생성한다."""
        validate_music_id(music_id)
        validate_audio_revision(audio_revision)
        source_sha = validated_audio_sha256(audio_path)
        profile = self.generator.generation_profile(audio_path)
        with connect_database() as connection:
            attempt = self.attempts.acquire(connection, music_id, audio_revision, source_sha,
                                            profile, stale_before=stale_before)
        if isinstance(attempt, EmbeddingSaveResult):
            if validated_audio_sha256(audio_path) != source_sha:
                raise AudioEmbeddingError('audio_source_changed', audio_path)
            return attempt
        kind, reason = 'transient', 'audio_generation_failed'
        try:
            result = self.generator.generate(audio_path, expected_sha256=source_sha)
            kind, reason = 'transient', 'audio_storage_failed'
            with connect_database() as connection:
                return self.attempts.complete(connection, attempt, result)
        except AttemptNoLongerProcessing:
            raise
        except Exception as error:
            if isinstance(error, AudioEmbeddingError):
                if error.reason in ('audio_duration_below_minimum', 'audio_duration_above_maximum',
                                    'audio_file_empty'):
                    kind, reason = 'input', error.reason
                elif error.reason in ('audio_source_changed', 'audio_embedding_failed',
                                      'audio_decode_or_preprocessing_failed'):
                    reason = error.reason
            elif isinstance(error, EmbeddingConflict) and str(error) in (
                'audio_source_changed', 'audio_generation_profile_changed'
            ):
                reason = str(error)
            try:
                with connect_database() as connection:
                    self.attempts.fail(connection, attempt, kind, reason)
            except AttemptNoLongerProcessing:
                # COMMIT 응답 유실이나 인수 뒤에는 새 소유자의 결과를 그대로 보존한다.
                pass
            except Exception as record_error:
                raise error from record_error
            raise


class TextEmbeddingStorage:
    """Generate and persist a validated CLAP query without assuming an Event ID contract."""

    def __init__(self, generator=None, repository=None):
        self.generator = generator if generator is not None else TextEmbeddingGenerator()
        self.repository = repository if repository is not None else TextEmbeddingRepository()

    def store(self, query_text):
        result = self.generator.generate(query_text)
        # DB 트랜잭션은 모델 생성이 끝난 뒤에만 연다.
        with connect_database() as connection:
            saved = self.repository.save(connection, result)
        return saved
