"""짧은 DB 트랜잭션으로 Audio 처리 소유권과 결과를 함께 관리한다."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.repository.embedding_repository import (
    AudioEmbeddingRepository, EmbeddingConflict, EmbeddingSaveResult,
    generation_profile_sha256, validate_audio_revision, validate_music_id,
)


class ProcessingInProgress(EmbeddingConflict):
    """동일 입력의 현재 소유자가 추론 중이다."""


class AttemptNoLongerProcessing(EmbeddingConflict):
    """인수되었거나 이미 종료된 시도는 결과를 반영할 수 없다."""


@dataclass(frozen=True)
class ProcessingAttempt:
    id: UUID
    music_id: str
    audio_revision: int
    source_sha256: str
    profile_sha256: str


class AudioProcessingRepository:
    def __init__(self, embeddings=None):
        self.embeddings = embeddings if embeddings is not None else AudioEmbeddingRepository()

    def acquire(self, connection, music_id, audio_revision, source_sha256, profile, *, stale_before=None):
        """호출자가 이 트랜잭션을 commit한 뒤에만 반환된 소유권으로 추론한다."""
        validate_music_id(music_id)
        validate_audio_revision(audio_revision)
        if stale_before is not None and (
            not isinstance(stale_before, datetime) or stale_before.utcoffset() is None
        ):
            raise ValueError('stale_before_must_be_timezone_aware')
        if stale_before is not None and stale_before > connection.execute(
            'SELECT clock_timestamp()'
        ).fetchone()[0]:
            raise ValueError('stale_before_must_not_be_in_the_future')
        profile_sha = generation_profile_sha256(profile)
        identity = (music_id, audio_revision, profile_sha)
        connection.execute('''INSERT INTO ai_embeddings.audio_sources
            (music_id, audio_revision, source_sha256) VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING''', (music_id, audio_revision, source_sha256))
        # 같은 revision의 획득·완료는 source -> attempt 순서로 잠근다.
        source, = connection.execute('''SELECT source_sha256 FROM ai_embeddings.audio_sources
            WHERE music_id = %s AND audio_revision = %s FOR UPDATE''', identity[:2]).fetchone()
        if source != source_sha256:
            raise EmbeddingConflict('audio_revision_has_different_source')
        saved = self.embeddings.get(connection, *identity)
        if saved is not None:
            if saved['source_sha256'] != source or saved['generation_profile'] != profile:
                raise EmbeddingConflict('stored_embedding_identity_mismatch')
            return EmbeddingSaveResult(saved['id'], music_id, audio_revision, profile_sha,
                                       False, source, saved['dimension'])

        current = connection.execute('''SELECT attempt_id, started_at
            FROM ai_embeddings.audio_processing_attempts
            WHERE music_id = %s AND audio_revision = %s AND generation_profile_sha256 = %s
              AND state = 'processing' FOR UPDATE''', identity).fetchone()
        if current:
            if stale_before is None or current[1] > stale_before:
                raise ProcessingInProgress('audio_processing_in_progress')
            connection.execute('''UPDATE ai_embeddings.audio_processing_attempts
                SET state = 'failed', finished_at = clock_timestamp(), failure_reason = 'stale_takeover',
                    failure_kind = 'transient', stale_cutoff = %s WHERE attempt_id = %s''',
                               (stale_before, current[0]))
        attempt_id, = connection.execute('''INSERT INTO ai_embeddings.audio_processing_attempts
            (music_id, audio_revision, source_sha256, generation_profile_sha256, state)
            VALUES (%s, %s, %s, %s, 'processing') RETURNING attempt_id''',
            (music_id, audio_revision, source, profile_sha)).fetchone()
        return ProcessingAttempt(attempt_id, music_id, audio_revision, source, profile_sha)

    def complete(self, connection, attempt, result):
        """벡터 저장 실패 시 소유권 상태 전이도 함께 rollback된다."""
        connection.execute('''SELECT 1 FROM ai_embeddings.audio_sources
            WHERE music_id = %s AND audio_revision = %s FOR UPDATE''',
            (attempt.music_id, attempt.audio_revision))
        with connection.transaction():
            return self._complete_locked(connection, attempt, result)

    def _complete_locked(self, connection, attempt, result):
        updated = connection.execute('''UPDATE ai_embeddings.audio_processing_attempts
            SET state = 'ready', finished_at = clock_timestamp()
            WHERE attempt_id = %s AND music_id = %s AND audio_revision = %s
              AND source_sha256 = %s AND generation_profile_sha256 = %s AND state = 'processing'
            ''',
            (attempt.id, attempt.music_id, attempt.audio_revision, attempt.source_sha256, attempt.profile_sha256))
        if not updated.rowcount:
            raise AttemptNoLongerProcessing('attempt_no_longer_processing')
        if result.metadata.get('source_sha256') != attempt.source_sha256:
            raise EmbeddingConflict('audio_source_changed')
        saved = self.embeddings.save(connection, attempt.music_id, attempt.audio_revision, result)
        if saved.generation_profile_sha256 != attempt.profile_sha256:
            raise EmbeddingConflict('audio_generation_profile_changed')
        return saved

    def fail(self, connection, attempt, kind, reason):
        updated = connection.execute('''UPDATE ai_embeddings.audio_processing_attempts
            SET state = 'failed', finished_at = clock_timestamp(), failure_kind = %s, failure_reason = %s
            WHERE attempt_id = %s AND music_id = %s AND audio_revision = %s
              AND source_sha256 = %s AND generation_profile_sha256 = %s AND state = 'processing'
            ''', (kind, reason, attempt.id, attempt.music_id, attempt.audio_revision,
                  attempt.source_sha256, attempt.profile_sha256))
        if not updated.rowcount:
            raise AttemptNoLongerProcessing('attempt_no_longer_processing')
