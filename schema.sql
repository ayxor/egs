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
    status                  TEXT        NOT NULL DEFAULT 'uploaded'
                                        CHECK (status IN ('uploading','uploaded','processing','ready','failed')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ
);

-- Processing jobs (tracks Video Editor jobs)
CREATE TABLE IF NOT EXISTS processing_jobs (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id          UUID        NOT NULL REFERENCES videos(id),
    external_job_id   TEXT        UNIQUE,
    status            TEXT        NOT NULL DEFAULT 'queued'
                                  CHECK (status IN ('queued','processing','done','failed')),
    percent           INT         NOT NULL DEFAULT 0,
    operations        JSONB,
    error_message     TEXT,
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
