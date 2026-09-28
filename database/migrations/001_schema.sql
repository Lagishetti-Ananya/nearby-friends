-- Applied on first Postgres start via docker-entrypoint (../schema.sql is the canonical copy).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    location_sharing_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    nearby_radius DOUBLE PRECISION NOT NULL DEFAULT 5.0,
    CONSTRAINT users_nearby_radius_positive CHECK (nearby_radius > 0)
);

CREATE TABLE IF NOT EXISTS friendships (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, friend_id),
    CONSTRAINT friendships_no_self CHECK (user_id <> friend_id)
);

CREATE TABLE IF NOT EXISTS location_history (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT location_history_lat CHECK (latitude >= -90 AND latitude <= 90),
    CONSTRAINT location_history_lon CHECK (longitude >= -180 AND longitude <= 180)
);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at);
CREATE INDEX IF NOT EXISTS idx_friendships_friend_id ON friendships (friend_id);
CREATE INDEX IF NOT EXISTS idx_location_history_user_time ON location_history (user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_location_history_time ON location_history (recorded_at DESC);
