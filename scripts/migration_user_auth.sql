-- Migration: User Auth & Personal Area
-- Creates user_favorite and ai_search_log tables
-- Validates: Requirements 6.6, 7.1

CREATE TABLE user_favorite (
    id SERIAL PRIMARY KEY,
    user_sub VARCHAR(128) NOT NULL,
    mishna_id VARCHAR(100) NOT NULL REFERENCES mishna(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_favorite UNIQUE (user_sub, mishna_id)
);

CREATE INDEX ix_user_favorite_user_sub ON user_favorite(user_sub);

CREATE TABLE ai_search_log (
    id SERIAL PRIMARY KEY,
    query_text VARCHAR(500) NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    result_ids TEXT,
    user_sub VARCHAR(128),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_ai_search_log_created ON ai_search_log(created_at DESC);
CREATE INDEX ix_ai_search_log_user_sub ON ai_search_log(user_sub);
