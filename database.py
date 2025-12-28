"""
Database Module for Parasitic AI Data Collection

Handles PostgreSQL connections, schema initialization, and data insertion.
"""

import os
import json
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values, Json


def get_connection():
    """
    Create a database connection from environment variables.

    Required env vars:
        DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    Optional:
        DB_PORT (default: 5432)
    """
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'parasite_ai'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )


def init_schema(conn):
    """Initialize database schema from schema.sql file."""
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("Database schema initialized successfully.")


def insert_posts(conn, posts: list[dict]) -> int:
    """
    Batch insert posts into the database.

    Args:
        conn: Database connection
        posts: List of post dictionaries from scraper

    Returns:
        Number of posts inserted (excludes duplicates)
    """
    if not posts:
        return 0

    insert_sql = """
        INSERT INTO posts (
            reddit_id, subreddit, author, created_utc,
            title, content, content_length, is_comment,
            parent_id, parent_comment_id,
            score, num_comments,
            category, parasite_score, is_parasitic,
            ai_model, external_links, has_external_links,
            url, detected_patterns
        ) VALUES %s
        ON CONFLICT (reddit_id) DO NOTHING
    """

    values = []
    for post in posts:
        values.append((
            post['reddit_id'],
            post['subreddit'],
            post.get('author'),
            post['created_utc'],
            post.get('title'),
            post['content'],
            post['content_length'],
            post.get('is_comment', False),
            post.get('parent_id'),
            post.get('parent_comment_id'),
            post.get('score'),
            post.get('num_comments', 0),
            post.get('category'),
            post.get('parasite_score'),
            post.get('is_parasitic'),
            post.get('ai_model'),
            post.get('external_links', []),
            post.get('has_external_links', False),
            post.get('url'),
            Json(post.get('detected_patterns', {}))
        ))

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values)
        inserted = cur.rowcount

    conn.commit()
    return inserted


def start_collection_run(conn, subreddit: str) -> int:
    """
    Start a new collection run and return its ID.

    Args:
        conn: Database connection
        subreddit: Subreddit being collected

    Returns:
        Run ID for tracking
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO collection_runs (subreddit, status)
            VALUES (%s, 'running')
            RETURNING id
            """,
            (subreddit,)
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def update_collection_run(
    conn,
    run_id: int,
    posts_fetched: int = 0,
    posts_stored: int = 0,
    parasitic_found: int = 0,
    status: str = 'running',
    error_message: Optional[str] = None
):
    """Update a collection run with progress or completion status."""
    with conn.cursor() as cur:
        if status in ('completed', 'failed'):
            cur.execute(
                """
                UPDATE collection_runs
                SET posts_fetched = %s,
                    posts_stored = %s,
                    parasitic_found = %s,
                    status = %s,
                    error_message = %s,
                    completed_at = NOW()
                WHERE id = %s
                """,
                (posts_fetched, posts_stored, parasitic_found, status, error_message, run_id)
            )
        else:
            cur.execute(
                """
                UPDATE collection_runs
                SET posts_fetched = %s,
                    posts_stored = %s,
                    parasitic_found = %s,
                    status = %s
                WHERE id = %s
                """,
                (posts_fetched, posts_stored, parasitic_found, status, run_id)
            )
    conn.commit()


def update_author_stats(conn, username: str):
    """
    Update author statistics after new posts are collected.

    Args:
        conn: Database connection
        username: Author username to update
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO authors (username, total_posts, parasitic_posts, parasite_rate,
                                 first_seen, last_seen, active_subreddits, classification)
            SELECT
                author,
                COUNT(*) as total_posts,
                SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) as parasitic_posts,
                ROUND(100.0 * SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) / COUNT(*), 3) as parasite_rate,
                MIN(created_utc) as first_seen,
                MAX(created_utc) as last_seen,
                ARRAY_AGG(DISTINCT subreddit) as active_subreddits,
                CASE
                    WHEN 100.0 * SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) / COUNT(*) >= 50 THEN 'high'
                    WHEN 100.0 * SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) / COUNT(*) >= 25 THEN 'moderate'
                    WHEN 100.0 * SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) / COUNT(*) >= 10 THEN 'low'
                    ELSE 'minimal'
                END as classification
            FROM posts
            WHERE author = %s
            GROUP BY author
            ON CONFLICT (username) DO UPDATE SET
                total_posts = EXCLUDED.total_posts,
                parasitic_posts = EXCLUDED.parasitic_posts,
                parasite_rate = EXCLUDED.parasite_rate,
                first_seen = EXCLUDED.first_seen,
                last_seen = EXCLUDED.last_seen,
                active_subreddits = EXCLUDED.active_subreddits,
                classification = EXCLUDED.classification,
                updated_at = NOW()
            """,
            (username,)
        )
    conn.commit()


def get_last_collection_time(conn, subreddit: str) -> Optional[datetime]:
    """
    Get the timestamp of the most recent post collected from a subreddit.

    Useful for incremental collection (only fetch new posts).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(created_utc)
            FROM posts
            WHERE subreddit = %s
            """,
            (subreddit,)
        )
        result = cur.fetchone()
        return result[0] if result and result[0] else None
