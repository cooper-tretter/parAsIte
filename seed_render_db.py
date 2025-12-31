#!/usr/bin/env python3
"""
Seed script to populate Render database with user_histories and transcripts.

Run as: python seed_render_db.py

This imports compressed CSV data from the data/ directory.
"""

import os
import gzip
import csv
import io
import psycopg2
from psycopg2.extras import execute_values

# Database connection from environment
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'dbname': os.environ.get('DB_NAME', 'parasite_db'),
    'user': os.environ.get('DB_USER', 'parasite_user'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')

# Schema for tables
USER_HISTORIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_histories (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    reddit_id TEXT UNIQUE NOT NULL,
    post_type TEXT NOT NULL,
    subreddit TEXT,
    title TEXT,
    content TEXT,
    created_at TIMESTAMP,
    score INTEGER,
    parasite_score FLOAT,
    is_pre_parasitic BOOLEAN,
    scraped_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_histories_username ON user_histories(username);
CREATE INDEX IF NOT EXISTS idx_user_histories_created ON user_histories(created_at);
CREATE INDEX IF NOT EXISTS idx_user_histories_pre_parasitic ON user_histories(is_pre_parasitic);
"""

TRANSCRIPTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    transcript_id TEXT NOT NULL,
    model TEXT,
    scenario TEXT,
    transcript TEXT,
    turn_count INTEGER,
    parasite_score FLOAT,
    is_parasitic BOOLEAN,
    category TEXT,
    detected_patterns JSONB,
    metadata JSONB,
    scraped_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_transcripts_source ON transcripts(source);
CREATE INDEX IF NOT EXISTS idx_transcripts_source_type ON transcripts(source_type);
CREATE INDEX IF NOT EXISTS idx_transcripts_model ON transcripts(model);
CREATE INDEX IF NOT EXISTS idx_transcripts_parasitic ON transcripts(is_parasitic);
"""


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def ensure_tables(conn):
    """Create tables if they don't exist."""
    with conn.cursor() as cur:
        cur.execute(USER_HISTORIES_SCHEMA)
        cur.execute(TRANSCRIPTS_SCHEMA)
    conn.commit()
    print("Tables ensured.")


def get_table_count(conn, table):
    """Get row count for a table."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def import_csv_gz(conn, table, filepath, columns):
    """Import gzipped CSV into table using COPY."""
    print(f"Importing {filepath} into {table}...")

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        # Skip header
        reader = csv.reader(f)
        header = next(reader)

        # Use COPY for fast import
        with conn.cursor() as cur:
            # Create temp file-like object for COPY
            buffer = io.StringIO()
            writer = csv.writer(buffer)

            count = 0
            for row in reader:
                writer.writerow(row)
                count += 1

            buffer.seek(0)
            cur.copy_expert(
                f"COPY {table} ({','.join(columns)}) FROM STDIN WITH CSV",
                buffer
            )
            conn.commit()
            print(f"  Imported {count} rows into {table}")


def import_user_histories(conn):
    """Import user_histories from CSV."""
    filepath = os.path.join(DATA_DIR, 'user_histories.csv.gz')
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return

    columns = [
        'id', 'username', 'reddit_id', 'post_type', 'subreddit',
        'title', 'content', 'created_at', 'score', 'parasite_score',
        'is_pre_parasitic', 'scraped_at'
    ]
    import_csv_gz(conn, 'user_histories', filepath, columns)


def import_transcripts(conn):
    """Import transcripts from CSV."""
    filepath = os.path.join(DATA_DIR, 'transcripts.csv.gz')
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return

    columns = [
        'id', 'source', 'source_type', 'transcript_id', 'model',
        'scenario', 'transcript', 'turn_count', 'parasite_score',
        'is_parasitic', 'category', 'detected_patterns', 'metadata', 'scraped_at'
    ]
    import_csv_gz(conn, 'transcripts', filepath, columns)


def main():
    print("=" * 50)
    print("ParAsIte Database Seeder")
    print("=" * 50)

    print("\nConnecting to database...")
    conn = get_connection()

    print("Ensuring tables exist...")
    ensure_tables(conn)

    # Check current counts
    uh_count = get_table_count(conn, 'user_histories')
    tr_count = get_table_count(conn, 'transcripts')

    print(f"\nCurrent counts:")
    print(f"  user_histories: {uh_count}")
    print(f"  transcripts: {tr_count}")

    # Import if empty
    if uh_count == 0:
        print("\nImporting user_histories...")
        try:
            import_user_histories(conn)
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("\nuser_histories already has data, skipping import.")

    if tr_count == 0:
        print("\nImporting transcripts...")
        try:
            import_transcripts(conn)
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("\ntranscripts already has data, skipping import.")

    # Final counts
    uh_count = get_table_count(conn, 'user_histories')
    tr_count = get_table_count(conn, 'transcripts')
    print(f"\nFinal counts:")
    print(f"  user_histories: {uh_count}")
    print(f"  transcripts: {tr_count}")

    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
