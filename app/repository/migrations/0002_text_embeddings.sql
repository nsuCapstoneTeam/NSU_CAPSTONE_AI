-- Text query identity is independent of backend Event IDs and Audio music IDs.
CREATE TABLE ai_embeddings.text_embeddings (
    query_text_sha256 text NOT NULL CHECK (query_text_sha256 ~ '^[0-9a-f]{64}$'),
    generation_version text NOT NULL CHECK (length(btrim(generation_version)) > 0),
    generation_profile_sha256 text NOT NULL CHECK (generation_profile_sha256 ~ '^[0-9a-f]{64}$'),
    dimension integer NOT NULL CHECK (dimension BETWEEN 1 AND 16000),
    embedding vector NOT NULL,
    generation_profile jsonb NOT NULL CHECK (jsonb_typeof(generation_profile) = 'object'),
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (query_text_sha256, generation_profile_sha256),
    CHECK (vector_dims(embedding) = dimension),
    CHECK (vector_norm(embedding) > 0)
);

CREATE INDEX text_embeddings_generation_profile_idx
    ON ai_embeddings.text_embeddings (generation_version, dimension);
