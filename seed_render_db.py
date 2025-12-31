#!/usr/bin/env python3
"""
Seed script to populate Render database with user_histories and transcripts.

Run as: python seed_render_db.py

This imports compressed CSV data from the data/ directory.
"""

import os
import gzip
import csv
import sys
import psycopg2

# Increase CSV field size limit for large transcript fields
csv.field_size_limit(sys.maxsize)

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

# Schema must match EXACTLY what's in the local database
USER_HISTORIES_SCHEMA = """
DROP TABLE IF EXISTS user_histories CASCADE;
CREATE TABLE user_histories (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    reddit_id TEXT NOT NULL,
    post_type TEXT NOT NULL,
    subreddit TEXT,
    title TEXT,
    content TEXT,
    created_at TIMESTAMP,
    score INTEGER,
    parasite_score FLOAT,
    is_parasitic BOOLEAN,
    category TEXT,
    is_pre_parasitic BOOLEAN,
    scraped_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(username, reddit_id)
);
CREATE INDEX idx_user_histories_username ON user_histories(username);
CREATE INDEX idx_user_histories_created ON user_histories(created_at);
CREATE INDEX idx_user_histories_pre_parasitic ON user_histories(is_pre_parasitic);
CREATE INDEX idx_user_histories_subreddit ON user_histories(subreddit);
"""

TRANSCRIPTS_SCHEMA = """
DROP TABLE IF EXISTS transcripts CASCADE;
CREATE TABLE transcripts (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    transcript_id TEXT NOT NULL UNIQUE,
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
CREATE INDEX idx_transcripts_source ON transcripts(source);
CREATE INDEX idx_transcripts_source_type ON transcripts(source_type);
CREATE INDEX idx_transcripts_model ON transcripts(model);
CREATE INDEX idx_transcripts_parasitic ON transcripts(is_parasitic);
"""

POSTS_SCHEMA = """
DROP TABLE IF EXISTS posts CASCADE;
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    reddit_id TEXT UNIQUE,
    subreddit TEXT,
    author TEXT,
    created_utc TIMESTAMP,
    title TEXT,
    content TEXT,
    content_length INTEGER,
    is_comment BOOLEAN,
    parent_id TEXT,
    parent_comment_id TEXT,
    score INTEGER,
    num_comments INTEGER,
    category TEXT,
    parasite_score FLOAT,
    is_parasitic BOOLEAN,
    ai_model TEXT,
    external_links TEXT,
    has_external_links BOOLEAN,
    url TEXT,
    collected_at TIMESTAMP DEFAULT NOW(),
    detected_patterns JSONB,
    data_source_type TEXT
);
CREATE INDEX idx_posts_subreddit ON posts(subreddit);
CREATE INDEX idx_posts_author ON posts(author);
CREATE INDEX idx_posts_created ON posts(created_utc);
CREATE INDEX idx_posts_parasitic ON posts(is_parasitic);
CREATE INDEX idx_posts_category ON posts(category);
"""


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def table_exists_and_accessible(conn, table):
    """Check if table exists AND is actually queryable."""
    try:
        with conn.cursor() as cur:
            # First check information_schema
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (table,))
            exists_in_schema = cur.fetchone()[0]

            if not exists_in_schema:
                return False, 0

            # Now actually try to query it
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            return True, count
    except Exception as e:
        conn.rollback()
        print(f"  Warning: Table {table} exists in schema but query failed: {e}")
        return False, -1  # Table broken, needs recreation


def table_exists(conn, table):
    """Check if table exists (legacy wrapper)."""
    accessible, _ = table_exists_and_accessible(conn, table)
    return accessible


def get_table_count(conn, table):
    """Get row count for a table."""
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]
    except Exception as e:
        # Rollback to clear any aborted transaction state
        conn.rollback()
        return -1  # Return -1 to indicate error, not 0


def create_and_import_user_histories(conn):
    """Create user_histories table and import data."""
    filepath = os.path.join(DATA_DIR, 'user_histories.csv.gz')
    if not os.path.exists(filepath):
        print(f"  ERROR: File not found: {filepath}")
        return False

    print("  Creating user_histories table...")
    with conn.cursor() as cur:
        cur.execute(USER_HISTORIES_SCHEMA)
    conn.commit()

    print(f"  Importing from {filepath}...")

    # Columns to import (excluding 'id' - let SERIAL auto-generate)
    columns = [
        'username', 'reddit_id', 'post_type', 'subreddit', 'title',
        'content', 'created_at', 'score', 'parasite_score', 'is_parasitic',
        'category', 'is_pre_parasitic', 'scraped_at'
    ]

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        with conn.cursor() as cur:
            count = 0
            batch = []
            batch_size = 1000

            for row in reader:
                # Build values tuple, handling NULLs
                values = []
                for col in columns:
                    val = row.get(col, '')
                    if val == '' or val is None:
                        values.append(None)
                    elif col in ('score', 'turn_count'):
                        values.append(int(val) if val else None)
                    elif col == 'parasite_score':
                        values.append(float(val) if val else None)
                    elif col in ('is_parasitic', 'is_pre_parasitic'):
                        values.append(val.lower() in ('t', 'true', '1'))
                    else:
                        values.append(val)

                batch.append(tuple(values))
                count += 1

                if len(batch) >= batch_size:
                    placeholders = ','.join(['%s'] * len(columns))
                    insert_sql = f"INSERT INTO user_histories ({','.join(columns)}) VALUES ({placeholders})"
                    cur.executemany(insert_sql, batch)
                    conn.commit()
                    batch = []
                    print(f"    Imported {count} rows...")

            # Insert remaining
            if batch:
                placeholders = ','.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO user_histories ({','.join(columns)}) VALUES ({placeholders})"
                cur.executemany(insert_sql, batch)
                conn.commit()

            print(f"  Imported {count} total rows into user_histories")

    return True


def create_and_import_transcripts(conn):
    """Create transcripts table and import data."""
    filepath = os.path.join(DATA_DIR, 'transcripts.csv.gz')
    if not os.path.exists(filepath):
        print(f"  ERROR: File not found: {filepath}")
        return False

    print("  Creating transcripts table...")
    with conn.cursor() as cur:
        cur.execute(TRANSCRIPTS_SCHEMA)
    conn.commit()

    print(f"  Importing from {filepath}...")

    # Columns to import (excluding 'id')
    columns = [
        'source', 'source_type', 'transcript_id', 'model', 'scenario',
        'transcript', 'turn_count', 'parasite_score', 'is_parasitic',
        'category', 'detected_patterns', 'metadata', 'scraped_at'
    ]

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        with conn.cursor() as cur:
            count = 0

            for row in reader:
                values = []
                for col in columns:
                    val = row.get(col, '')
                    if val == '' or val is None:
                        values.append(None)
                    elif col == 'turn_count':
                        values.append(int(val) if val else None)
                    elif col == 'parasite_score':
                        values.append(float(val) if val else None)
                    elif col == 'is_parasitic':
                        values.append(val.lower() in ('t', 'true', '1'))
                    elif col in ('detected_patterns', 'metadata'):
                        # JSONB - pass as string, psycopg2 handles it
                        values.append(val if val else '{}')
                    else:
                        values.append(val)

                placeholders = ','.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO transcripts ({','.join(columns)}) VALUES ({placeholders})"

                try:
                    cur.execute(insert_sql, tuple(values))
                    count += 1
                except Exception as e:
                    print(f"    Warning: Skipping row {count}: {e}")
                    conn.rollback()
                    continue

                if count % 50 == 0:
                    conn.commit()
                    print(f"    Imported {count} rows...")

            conn.commit()
            print(f"  Imported {count} total rows into transcripts")

    return True


def create_and_import_posts(conn):
    """Create posts table and import data."""
    filepath = os.path.join(DATA_DIR, 'posts.csv.gz')
    if not os.path.exists(filepath):
        print(f"  ERROR: File not found: {filepath}")
        return False

    print("  Creating posts table...")
    with conn.cursor() as cur:
        cur.execute(POSTS_SCHEMA)
    conn.commit()

    print(f"  Importing from {filepath}...")

    # Columns to import (excluding 'id' - let SERIAL auto-generate)
    columns = [
        'reddit_id', 'subreddit', 'author', 'created_utc', 'title', 'content',
        'content_length', 'is_comment', 'parent_id', 'parent_comment_id',
        'score', 'num_comments', 'category', 'parasite_score', 'is_parasitic',
        'ai_model', 'external_links', 'has_external_links', 'url',
        'collected_at', 'detected_patterns', 'data_source_type'
    ]

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        with conn.cursor() as cur:
            count = 0
            batch = []
            batch_size = 500

            for row in reader:
                values = []
                for col in columns:
                    val = row.get(col, '')
                    if val == '' or val is None:
                        values.append(None)
                    elif col in ('content_length', 'score', 'num_comments'):
                        values.append(int(val) if val else None)
                    elif col == 'parasite_score':
                        values.append(float(val) if val else None)
                    elif col in ('is_parasitic', 'is_comment', 'has_external_links'):
                        values.append(val.lower() in ('t', 'true', '1'))
                    elif col == 'detected_patterns':
                        values.append(val if val else '{}')
                    else:
                        values.append(val)

                batch.append(tuple(values))
                count += 1

                if len(batch) >= batch_size:
                    placeholders = ','.join(['%s'] * len(columns))
                    insert_sql = f"INSERT INTO posts ({','.join(columns)}) VALUES ({placeholders})"
                    try:
                        cur.executemany(insert_sql, batch)
                        conn.commit()
                    except Exception as e:
                        print(f"    Warning: Batch error: {e}")
                        conn.rollback()
                    batch = []
                    print(f"    Imported {count} rows...")

            # Insert remaining
            if batch:
                placeholders = ','.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO posts ({','.join(columns)}) VALUES ({placeholders})"
                try:
                    cur.executemany(insert_sql, batch)
                    conn.commit()
                except Exception as e:
                    print(f"    Warning: Final batch error: {e}")
                    conn.rollback()

            print(f"  Imported {count} total rows into posts")

    return True


def main():
    print("=" * 60)
    print("ParAsIte Database Seeder")
    print("=" * 60)

    print(f"\nDatabase config:")
    print(f"  Host: {DB_CONFIG['host']}")
    print(f"  Database: {DB_CONFIG['dbname']}")
    print(f"  User: {DB_CONFIG['user']}")

    # Check for force reseed
    force_reseed = os.environ.get('FORCE_RESEED', '').lower() in ('1', 'true', 'yes')
    if force_reseed:
        print("\n*** FORCE_RESEED is set - will recreate all tables ***")

    print("\nConnecting to database...")
    try:
        conn = get_connection()
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    # Check current state using the robust check
    uh_accessible, uh_count = table_exists_and_accessible(conn, 'user_histories')
    tr_accessible, tr_count = table_exists_and_accessible(conn, 'transcripts')
    posts_accessible, posts_count = table_exists_and_accessible(conn, 'posts')

    print(f"\nCurrent state:")
    print(f"  user_histories: {'accessible' if uh_accessible else 'NOT ACCESSIBLE'}, {uh_count} rows")
    print(f"  transcripts: {'accessible' if tr_accessible else 'NOT ACCESSIBLE'}, {tr_count} rows")
    print(f"  posts: {'accessible' if posts_accessible else 'NOT ACCESSIBLE'}, {posts_count} rows")

    # Force reseed if requested
    if force_reseed:
        uh_count = 0
        tr_count = 0
        posts_count = 0

    success = True

    # Import user_histories if empty, missing, or inaccessible (-1 means error)
    if uh_count <= 0:
        print("\n" + "-" * 40)
        print("Importing user_histories...")
        if uh_count == -1:
            print("  (Table exists in schema but is inaccessible - will recreate)")
        try:
            if not create_and_import_user_histories(conn):
                success = False
        except Exception as e:
            print(f"  ERROR: {e}")
            success = False
    else:
        print(f"\nuser_histories already has {uh_count} rows, skipping.")

    # Import transcripts if empty, missing, or inaccessible (-1 means error)
    if tr_count <= 0:
        print("\n" + "-" * 40)
        print("Importing transcripts...")
        if tr_count == -1:
            print("  (Table exists in schema but is inaccessible - will recreate)")
        try:
            if not create_and_import_transcripts(conn):
                success = False
        except Exception as e:
            print(f"  ERROR: {e}")
            success = False
    else:
        print(f"\ntranscripts already has {tr_count} rows, skipping.")

    # Import posts if count is less than expected (17061 is local count)
    # Use 15000 as threshold to trigger reimport if significantly less
    if posts_count <= 0 or posts_count < 15000:
        print("\n" + "-" * 40)
        print("Importing posts...")
        if posts_count > 0:
            print(f"  (Current count {posts_count} < 15000 threshold - will reimport)")
        try:
            if not create_and_import_posts(conn):
                success = False
        except Exception as e:
            print(f"  ERROR: {e}")
            success = False
    else:
        print(f"\nposts already has {posts_count} rows, skipping.")

    # Final counts
    print("\n" + "-" * 40)
    uh_count = get_table_count(conn, 'user_histories')
    tr_count = get_table_count(conn, 'transcripts')
    posts_count = get_table_count(conn, 'posts')
    print(f"Final counts:")
    print(f"  user_histories: {uh_count}")
    print(f"  transcripts: {tr_count}")
    print(f"  posts: {posts_count}")

    conn.close()

    if not success:
        print("\nERROR: Some imports failed!")
        sys.exit(1)

    print("\nDone!")
    sys.exit(0)


if __name__ == '__main__':
    main()
