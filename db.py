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

def get_students_by_course(institution, course):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE institution = %s AND course = %s AND role = 'student' AND is_active = TRUE",
                (institution, course),
            )
            return cur.fetchall()

# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

def create_video(uploader_id, institution, title, description, tags,
                 course, subject, storage_bucket, raw_storage_key,
                 status="uploaded", channel_id=None):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO videos
                    (uploader_id, institution, title, description, tags,
                     course, subject, storage_bucket, raw_storage_key, status, channel_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (uploader_id, institution, title, description, tags,
                 course, subject, storage_bucket, raw_storage_key, status, channel_id),
            )
            return cur.fetchone()


def get_video(video_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT v.*, c.name AS channel_name, c.visibility AS channel_visibility, c.owner_id AS channel_owner_id
                FROM videos v
                LEFT JOIN channels c ON v.channel_id = c.id
                WHERE v.id = %s AND v.deleted_at IS NULL
                """,
                (video_id,),
            )
            return cur.fetchone()


def increment_video_views(video_id):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET views = views + 1 WHERE id = %s",
                (video_id,),
            )


def get_videos_by_uploader(uploader_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, description, tags, course, subject, status, storage_bucket, thumbnail_key, created_at, channel_id, views, duration
                FROM videos
                WHERE uploader_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                (uploader_id,),
            )
            return cur.fetchall()


def update_video(video_id, title, description, tags, course, subject, channel_id=None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE videos
                SET title = %s, description = %s, tags = %s, course = %s, subject = %s, channel_id = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (title, description, tags, course, subject, channel_id, video_id),
            )



def search_videos(user_id=None, q=None, course=None, subject=None,
                  limit=25, offset=0):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["videos.deleted_at IS NULL"]
            params = []

            if user_id:
                visibility_sql = """
                    (
                        videos.channel_id IS NULL OR
                        c.visibility = 'public' OR
                        c.owner_id = %s OR
                        EXISTS (
                            SELECT 1 FROM channel_subscriptions 
                            WHERE user_id = %s AND channel_id = videos.channel_id
                        )
                    )
                """
                conditions.append(visibility_sql)
                params.extend([user_id, user_id])
            else:
                visibility_sql = "(videos.channel_id IS NULL OR c.visibility = 'public')"
                conditions.append(visibility_sql)

            if q:
                conditions.append(
                    "(videos.title ILIKE %s OR videos.description ILIKE %s OR %s = ANY(videos.tags) OR c.name ILIKE %s OR c.course_code ILIKE %s OR u.name ILIKE %s)"
                )
                like_pattern = f"%{q}%"
                params.extend([like_pattern, like_pattern, q, like_pattern, like_pattern, like_pattern])

            if course:
                conditions.append("videos.course = %s")
                params.append(course)

            if subject:
                conditions.append("videos.subject = %s")
                params.append(subject)

            where = " AND ".join(conditions)

            cur.execute(
                f"""
                SELECT COUNT(*) AS total 
                FROM videos 
                LEFT JOIN channels c ON videos.channel_id = c.id
                LEFT JOIN users u ON videos.uploader_id = u.id
                WHERE {where}
                """,
                params,
            )
            total = cur.fetchone()["total"]

            cur.execute(
                f"""
                SELECT videos.id, videos.title, videos.description, videos.tags, videos.course, videos.subject,
                       videos.uploader_id, videos.status, videos.storage_bucket, videos.thumbnail_key, videos.created_at,
                       videos.channel_id, videos.views, videos.duration, c.name AS channel_name, c.visibility AS channel_visibility,
                       u.name AS uploader_name
                FROM videos
                LEFT JOIN channels c ON videos.channel_id = c.id
                LEFT JOIN users u ON videos.uploader_id = u.id
                WHERE {where}
                ORDER BY videos.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            results = cur.fetchall()

            return total, results



def search_public_channels(q, limit=5):
    if not q:
        return []
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.id, c.name, c.description, c.course_code, c.owner_id, c.visibility,
                       u.name AS owner_name
                FROM channels c
                JOIN users u ON c.owner_id = u.id
                WHERE c.visibility = 'public' AND (c.name ILIKE %s OR c.description ILIKE %s OR c.course_code ILIKE %s OR u.name ILIKE %s)
                ORDER BY c.name ASC
                LIMIT %s
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", limit),
            )
            return cur.fetchall()



def delete_video(video_id):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET deleted_at = NOW(), updated_at = NOW() WHERE id = %s",
                (video_id,),
            )


def update_video_status(video_id, status, processed_storage_key=None, thumbnail_key=None, duration=None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            updates = ["status = %s", "updated_at = NOW()"]
            params = [status]
            if processed_storage_key:
                updates.append("processed_storage_key = %s")
                params.append(processed_storage_key)
            if thumbnail_key:
                updates.append("thumbnail_key = %s")
                params.append(thumbnail_key)
            if duration:
                updates.append("duration = %s")
                params.append(duration)
            params.append(video_id)
            sql = f"UPDATE videos SET {', '.join(updates)} WHERE id = %s"
            cur.execute(sql, tuple(params))


# ---------------------------------------------------------------------------
# Processing jobs
# ---------------------------------------------------------------------------

def create_processing_job(video_id, external_job_id, operations, processed_key=None):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO processing_jobs (video_id, external_job_id, operations, processed_key)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (video_id, external_job_id, Json(operations), processed_key),
            )
            return cur.fetchone()


def update_processing_job(external_job_id, status, percent, error_message=None, message=None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            if status in ("done", "failed"):
                cur.execute(
                    """
                    UPDATE processing_jobs
                    SET status = %s, percent = %s, error_message = %s, message = %s,
                        updated_at = NOW(), completed_at = NOW()
                    WHERE external_job_id = %s
                    """,
                    (status, percent, error_message, message, external_job_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE processing_jobs
                    SET status = %s, percent = %s, error_message = %s, message = %s,
                        updated_at = NOW()
                    WHERE external_job_id = %s
                    """,
                    (status, percent, error_message, message, external_job_id),
                )


def get_processing_job_by_external_id(external_job_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM processing_jobs WHERE external_job_id = %s",
                (external_job_id,),
            )
            return cur.fetchone()


# ---------------------------------------------------------------------------
# Channels & Subscriptions
# ---------------------------------------------------------------------------

def create_channel(owner_id, name, description, channel_type, visibility, course_code=None):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO channels (owner_id, name, description, channel_type, visibility, course_code)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, owner_id, name, description, channel_type, visibility, course_code, created_at
                """,
                (owner_id, name, description, channel_type, visibility, course_code),
            )
            return cur.fetchone()


def update_channel(channel_id, name, description, visibility, course_code=None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE channels
                SET name = %s, description = %s, visibility = %s, course_code = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (name, description, visibility, course_code, channel_id),
            )


def get_channel(channel_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM channels WHERE id = %s",
                (channel_id,),
            )
            return cur.fetchone()


def get_channels(user_id=None):
    """List channels.
    
    If user_id is provided, returns channels owned by the user, public channels,
    and private/unlisted channels the user is subscribed to.
    If no user_id, returns only public channels.
    """
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id:
                cur.execute(
                    """
                    SELECT DISTINCT c.*, u.name AS owner_name,
                           EXISTS(SELECT 1 FROM channel_subscriptions s WHERE s.user_id = %s AND s.channel_id = c.id) AS is_subscribed
                    FROM channels c
                    JOIN users u ON c.owner_id = u.id
                    LEFT JOIN channel_subscriptions s ON c.id = s.channel_id
                    WHERE c.visibility = 'public'
                       OR c.owner_id = %s
                       OR s.user_id = %s
                    ORDER BY c.name ASC
                    """,
                    (user_id, user_id, user_id),
                )
            else:
                cur.execute(
                    """
                    SELECT c.*, u.name AS owner_name, FALSE AS is_subscribed
                    FROM channels c
                    JOIN users u ON c.owner_id = u.id
                    WHERE c.visibility = 'public'
                    ORDER BY c.name ASC
                    """
                )
            return cur.fetchall()


def get_channels_by_owner(owner_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM channels WHERE owner_id = %s ORDER BY name ASC",
                (owner_id,),
            )
            return cur.fetchall()


def subscribe_to_channel(user_id, channel_id):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO channel_subscriptions (user_id, channel_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, channel_id) DO NOTHING
                """,
                (user_id, channel_id),
            )


def unsubscribe_from_channel(user_id, channel_id):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM channel_subscriptions WHERE user_id = %s AND channel_id = %s",
                (user_id, channel_id),
            )


def is_subscribed(user_id, channel_id):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM channel_subscriptions WHERE user_id = %s AND channel_id = %s",
                (user_id, channel_id),
            )
            return cur.fetchone() is not None


def get_user_subscriptions(user_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.*, u.name AS owner_name
                FROM channels c
                JOIN users u ON c.owner_id = u.id
                INNER JOIN channel_subscriptions s ON c.id = s.channel_id
                WHERE s.user_id = %s
                ORDER BY c.name ASC
                """,
                (user_id,),
            )
            return cur.fetchall()


def get_videos_by_channel(channel_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, description, tags, course, subject, status, storage_bucket, thumbnail_key, created_at, channel_id, views, duration
                FROM videos
                WHERE channel_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                (channel_id,),
            )
            return cur.fetchall()


def get_subscribed_feed(user_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT v.id, v.title, v.description, v.tags, v.course, v.subject, v.status, v.storage_bucket, v.thumbnail_key, v.created_at, v.channel_id, v.views, v.duration,
                       c.name AS channel_name, c.visibility AS channel_visibility
                FROM videos v
                INNER JOIN channel_subscriptions s ON v.channel_id = s.channel_id
                INNER JOIN channels c ON v.channel_id = c.id
                WHERE s.user_id = %s AND v.deleted_at IS NULL
                ORDER BY v.created_at DESC
                """,
                (user_id,),
            )
            return cur.fetchall()


def get_channel_subscribers(channel_id):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.name, u.email
                FROM users u
                INNER JOIN channel_subscriptions s ON u.id = s.user_id
                WHERE s.channel_id = %s
                """,
                (channel_id,),
            )
            return cur.fetchall()

