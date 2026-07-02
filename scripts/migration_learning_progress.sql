-- Migration: Learning Progress Tracking
-- Creates user_learned table for tracking which Mishnayot each user has learned

CREATE TABLE user_learned (
    id SERIAL PRIMARY KEY,
    user_sub VARCHAR(128) NOT NULL,
    mishna_id VARCHAR(100) NOT NULL REFERENCES mishna(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_learned UNIQUE (user_sub, mishna_id)
);

CREATE INDEX ix_user_learned_user_sub ON user_learned(user_sub);
