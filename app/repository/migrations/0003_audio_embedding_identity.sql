-- 기존 row는 Backend revision 매핑 없이 추정하거나 삭제하지 않는다.
-- 적용 도구의 트랜잭션 안에서 guard와 DDL을 함께 수행한다.
LOCK TABLE ai_embeddings.audio_embeddings IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM ai_embeddings.audio_embeddings) THEN
        RAISE EXCEPTION 'audio_revision_mapping_required: existing audio rows must not be guessed or deleted';
    END IF;
    BEGIN
        PERFORM pg_catalog.uuidv7();
    EXCEPTION WHEN undefined_function THEN
        RAISE EXCEPTION 'uuidv7_unavailable: PostgreSQL uuidv7() is required';
    END;
END
$$;

CREATE TABLE ai_embeddings.audio_sources (
    music_id text NOT NULL CHECK (length(btrim(music_id)) BETWEEN 1 AND 200),
    audio_revision bigint NOT NULL CHECK (audio_revision >= 1),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (music_id, audio_revision),
    UNIQUE (music_id, audio_revision, source_sha256)
);

ALTER TABLE ai_embeddings.audio_embeddings
    ADD COLUMN id uuid NOT NULL DEFAULT uuidv7(),
    ADD COLUMN audio_revision bigint NOT NULL CHECK (audio_revision >= 1),
    ADD COLUMN generation_profile_sha256 text NOT NULL
        CHECK (generation_profile_sha256 ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT audio_embeddings_uuidv7_check
        CHECK (uuid_extract_version(id) IS NOT DISTINCT FROM 7),
    DROP CONSTRAINT audio_embeddings_pkey,
    ADD PRIMARY KEY (id),
    ADD CONSTRAINT audio_embeddings_identity_key
        UNIQUE (music_id, audio_revision, generation_profile_sha256),
    ADD CONSTRAINT audio_embeddings_source_fkey
        FOREIGN KEY (music_id, audio_revision, source_sha256)
        REFERENCES ai_embeddings.audio_sources (music_id, audio_revision, source_sha256);
