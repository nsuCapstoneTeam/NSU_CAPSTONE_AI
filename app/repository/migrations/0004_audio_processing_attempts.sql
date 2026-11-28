CREATE TABLE ai_embeddings.audio_processing_attempts (
    attempt_id uuid PRIMARY KEY DEFAULT uuidv7(),
    music_id text NOT NULL,
    audio_revision bigint NOT NULL,
    source_sha256 text NOT NULL,
    generation_profile_sha256 text NOT NULL CHECK (generation_profile_sha256 ~ '^[0-9a-f]{64}$'),
    state text NOT NULL CHECK (state IN ('processing', 'ready', 'failed')),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    failure_reason text,
    failure_kind text CHECK (failure_kind IN ('input', 'transient')),
    stale_cutoff timestamptz,
    FOREIGN KEY (music_id, audio_revision, source_sha256)
        REFERENCES ai_embeddings.audio_sources (music_id, audio_revision, source_sha256),
    CHECK ((state = 'processing') = (finished_at IS NULL)),
    CHECK ((state = 'failed') = (failure_reason IS NOT NULL)),
    CHECK ((state = 'failed') = (failure_kind IS NOT NULL)),
    CHECK (failure_reason IS NULL OR length(trim(failure_reason)) > 0),
    CHECK ((stale_cutoff IS NOT NULL) = (failure_reason IS NOT DISTINCT FROM 'stale_takeover'))
);

CREATE UNIQUE INDEX audio_processing_current_owner
    ON ai_embeddings.audio_processing_attempts (music_id, audio_revision, generation_profile_sha256)
    WHERE state = 'processing';
