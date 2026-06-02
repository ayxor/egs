CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users (profile metadata; passwords live in Keycloak)
CREATE TABLE IF NOT EXISTS users (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    keycloak_user_id  TEXT        UNIQUE NOT NULL,
    email             TEXT        UNIQUE NOT NULL,
    name              TEXT        NOT NULL,
    role              TEXT        NOT NULL CHECK (role IN ('professor', 'student')),
    institution       TEXT        NOT NULL,
    course            TEXT,
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Channels (Class channels and Personal channels)
CREATE TABLE IF NOT EXISTS channels (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              TEXT        NOT NULL,
    description       TEXT,
    owner_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_type      TEXT        NOT NULL CHECK (channel_type IN ('class', 'personal')),
    visibility        TEXT        NOT NULL CHECK (visibility IN ('public', 'unlisted', 'private')),
    course_code       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Channel subscriptions (who belongs to/subscribes to a channel)
CREATE TABLE IF NOT EXISTS channel_subscriptions (
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_id        UUID        NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    subscribed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, channel_id)
);

-- Videos (metadata; binary data lives in Object Storage)
CREATE TABLE IF NOT EXISTS videos (
    id                      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    uploader_id             UUID        NOT NULL REFERENCES users(id),
    institution             TEXT        NOT NULL,
    title                   TEXT        NOT NULL,
    description             TEXT,
    tags                    TEXT[]      DEFAULT '{}',
    course                  TEXT,
    subject                 TEXT,
    storage_bucket          TEXT        NOT NULL,
    raw_storage_key         TEXT,
    processed_storage_key   TEXT,
    thumbnail_key           TEXT,
    status                  TEXT        NOT NULL DEFAULT 'uploaded'
                                        CHECK (status IN ('uploading','uploaded','processing','ready','failed')),
    channel_id              UUID        REFERENCES channels(id) ON DELETE SET NULL,
    views                   INT         NOT NULL DEFAULT 0,
    duration                TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ
);




-- Processing jobs (tracks Video Editor jobs)
CREATE TABLE IF NOT EXISTS processing_jobs (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id          UUID        NOT NULL REFERENCES videos(id),
    external_job_id   TEXT        UNIQUE,
    processed_key     TEXT,
    status            TEXT        NOT NULL DEFAULT 'queued'
                                  CHECK (status IN ('queued','processing','done','failed')),
    percent           INT         NOT NULL DEFAULT 0,
    operations        JSONB,
    error_message     TEXT,
    message           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_videos_institution ON videos(institution);
CREATE INDEX IF NOT EXISTS idx_videos_uploader    ON videos(uploader_id);
CREATE INDEX IF NOT EXISTS idx_videos_deleted     ON videos(deleted_at);
CREATE INDEX IF NOT EXISTS idx_jobs_video         ON processing_jobs(video_id);
CREATE INDEX IF NOT EXISTS idx_jobs_external      ON processing_jobs(external_job_id);
CREATE INDEX IF NOT EXISTS idx_channels_owner     ON channels(owner_id);
CREATE INDEX IF NOT EXISTS idx_channels_visibility ON channels(visibility);
CREATE INDEX IF NOT EXISTS idx_videos_channel     ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_subs_user          ON channel_subscriptions(user_id);

-- Migration for existing databases
ALTER TABLE videos ADD COLUMN IF NOT EXISTS channel_id UUID REFERENCES channels(id) ON DELETE SET NULL;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS views INT NOT NULL DEFAULT 0;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS duration TEXT;
ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS message TEXT;


-- Static seed data synced with Keycloak realm-egs.json
INSERT INTO users (keycloak_user_id, email, name, role, institution)
VALUES ('ae3012a2-df6c-4f26-9203-f70e2f078d97', 'professor@ua.pt', 'Professor User', 'professor', 'Universidade de Aveiro')
ON CONFLICT (email) DO UPDATE SET keycloak_user_id = 'ae3012a2-df6c-4f26-9203-f70e2f078d97', role = 'professor';

INSERT INTO users (keycloak_user_id, email, name, role, institution)
VALUES ('10755f63-cd46-41b5-9f77-ef11b308cd40', 'student@ua.pt', 'Student User', 'student', 'Universidade de Aveiro')
ON CONFLICT (email) DO UPDATE SET keycloak_user_id = '10755f63-cd46-41b5-9f77-ef11b308cd40', role = 'student';
