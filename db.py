"""Database layer — PostgreSQL connection pool and query functions."""

import os
import logging
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json

import config

logger = logging.getLogger(__name__)

_pool = None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def init():
    """Create the connection pool and apply the schema."""
    global _pool
    _pool = pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        dsn=config.DATABASE_URL,
    )
    _apply_schema()
    logger.info("Database pool created and schema applied")


def _apply_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with _get_connection() as conn:
        with conn.cursor() as cur:
            with open(schema_path) as f:
                cur.execute(f.read())


@contextmanager
def _get_connection():
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(keycloak_user_id, email, name, role, institution, course=None):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (keycloak_user_id, email, name, role, institution, course)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, keycloak_user_id, email, name, role, institution, course, created_at
                """,
                (keycloak_user_id, email, name, role, institution, course),
            )
            return cur.fetchone()


def get_user_by_keycloak_id(keycloak_user_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE keycloak_user_id = %s AND is_active = TRUE",
                (keycloak_user_id,),
            )
            return cur.fetchone()


def get_user_by_email(email):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE email = %s AND is_active = TRUE",
                (email,),
            )
            return cur.fetchone()


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

def create_video(uploader_id, institution, title, description, tags,
                 course, subject, storage_bucket, raw_storage_key,
                 status="uploaded"):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO videos
                    (uploader_id, institution, title, description, tags,
                     course, subject, storage_bucket, raw_storage_key, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (uploader_id, institution, title, description, tags,
                 course, subject, storage_bucket, raw_storage_key, status),
            )
            return cur.fetchone()


def get_video(video_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM videos WHERE id = %s AND deleted_at IS NULL",
                (video_id,),
            )
            return cur.fetchone()


def search_videos(institution, q=None, course=None, subject=None,
                  limit=25, offset=0):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["institution = %s", "deleted_at IS NULL"]
            params = [institution]

            if q:
                conditions.append(
                    "(title ILIKE %s OR description ILIKE %s OR %s = ANY(tags))"
                )
                like_pattern = f"%{q}%"
                params.extend([like_pattern, like_pattern, q])

            if course:
                conditions.append("course = %s")
                params.append(course)

            if subject:
                conditions.append("subject = %s")
                params.append(subject)

            where = " AND ".join(conditions)

            cur.execute(
                f"SELECT COUNT(*) AS total FROM videos WHERE {where}",
                params,
            )
            total = cur.fetchone()["total"]

            cur.execute(
                f"""
                SELECT id, title, description, tags, course, subject,
                       uploader_id, created_at
                FROM videos
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            results = cur.fetchall()

            return total, results


def delete_video(video_id):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET deleted_at = NOW(), updated_at = NOW() WHERE id = %s",
                (video_id,),
            )


def update_video_status(video_id, status, processed_storage_key=None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            if processed_storage_key:
                cur.execute(
                    """
                    UPDATE videos
                    SET status = %s, processed_storage_key = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, processed_storage_key, video_id),
                )
            else:
                cur.execute(
                    "UPDATE videos SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, video_id),
                )


# ---------------------------------------------------------------------------
# Processing jobs
# ---------------------------------------------------------------------------

def create_processing_job(video_id, external_job_id, operations):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO processing_jobs (video_id, external_job_id, operations)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (video_id, external_job_id, Json(operations)),
            )
            return cur.fetchone()


def update_processing_job(external_job_id, status, percent, error_message=None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            if status in ("done", "failed"):
                cur.execute(
                    """
                    UPDATE processing_jobs
                    SET status = %s, percent = %s, error_message = %s,
                        updated_at = NOW(), completed_at = NOW()
                    WHERE external_job_id = %s
                    """,
                    (status, percent, error_message, external_job_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE processing_jobs
                    SET status = %s, percent = %s, error_message = %s,
                        updated_at = NOW()
                    WHERE external_job_id = %s
                    """,
                    (status, percent, error_message, external_job_id),
                )


def get_processing_job_by_external_id(external_job_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM processing_jobs WHERE external_job_id = %s",
                (external_job_id,),
            )
            return cur.fetchone()
