-- 음악 ID 발급 주체와 타입이 미정이므로 외부 ID를 문자열로 받고 FK는 아직 연결하지 않는다.
CREATE TABLE ai_embeddings.audio_embeddings (
    music_id text PRIMARY KEY CHECK (length(btrim(music_id)) BETWEEN 1 AND 200),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    model text NOT NULL CHECK (length(model) > 0),
    model_version text NOT NULL CHECK (length(model_version) > 0),
    preprocessing_version text NOT NULL CHECK (length(preprocessing_version) > 0),
    dimension integer NOT NULL CHECK (dimension BETWEEN 1 AND 16000),
    -- 모델 변경 시 다른 차원도 기록할 수 있지만 행 안의 차원 정보는 반드시 일치해야 한다.
    embedding vector NOT NULL,
    generation_profile jsonb NOT NULL CHECK (jsonb_typeof(generation_profile) = 'object'),
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (vector_dims(embedding) = dimension),
    CHECK (vector_norm(embedding) > 0)
);

-- 같은 파일을 여러 음악 ID가 참조할 수 있으므로 해시는 전역 UNIQUE로 제한하지 않는다.
CREATE INDEX audio_embeddings_source_sha256_idx
    ON ai_embeddings.audio_embeddings (source_sha256);
