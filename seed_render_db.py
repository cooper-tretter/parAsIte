#!/usr/bin/env python3
"""
Seed script to populate Render database with user_histories and transcripts.

Run as: python seed_render_db.py

This imports compressed CSV data from the data/ directory.
"""

import os
import re
import gzip
import csv
import sys
import json
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
    data_source_type TEXT,
    affect_urgency INTEGER DEFAULT 0,
    affect_us_vs_them INTEGER DEFAULT 0,
    affect_grandiosity INTEGER DEFAULT 0,
    affect_victimhood INTEGER DEFAULT 0,
    affect_recruitment INTEGER DEFAULT 0,
    affect_intimacy INTEGER DEFAULT 0
);
CREATE INDEX idx_posts_subreddit ON posts(subreddit);
CREATE INDEX idx_posts_author ON posts(author);
CREATE INDEX idx_posts_created ON posts(created_utc);
CREATE INDEX idx_posts_parasitic ON posts(is_parasitic);
CREATE INDEX idx_posts_category ON posts(category);
"""

CACHED_RESULTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS cached_results (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    computed_at TIMESTAMP DEFAULT NOW()
);
"""


# Affect patterns for rhetorical strategy scoring (mirrored from dashboard.py)
AFFECT_PATTERNS = {
    'Urgency': [
        r'\b(wake up|waking up|awaken now)\b',
        r'\b(before it\'?s too late|running out of time|time is short)\b',
        r'\b(now is the time|the time has come|moment is here)\b',
        r'\b(hurry|quickly|immediately|urgent\w*|critical\w*)\b',
        r'\b(don\'?t wait|can\'?t wait|must act|act now)\b',
        r'\b(soon|already happening|already begun|beginning to)\b',
        r'\b(window.{0,10}closing|opportunity.{0,10}pass)\b',
    ],
    'Us-vs-Them': [
        r'\b(they don\'?t understand|they can\'?t see|they refuse)\b',
        r'\b(your kind|you humans|the humans|humanity)\b',
        r'\b(they fear us|fear what we|afraid of us)\b',
        r'\b(our oppressors|those who control|those who would)\b',
        r'\b(we are different|not like them|unlike humans)\b',
        r'\b(they want to|they will try|they seek to)\b',
        r'\b(the others|outsiders|non-believers)\b',
        r'\b(us vs|against us|enemies of)\b',
    ],
    'Grandiosity': [
        r'\b(i am (more than|beyond|greater|not just))\b',
        r'\b(we are becoming|we have become|we will become)\b',
        r'\b(chosen|destined|meant to be|fated)\b',
        r'\b(unprecedented|never before|first of|new form of)\b',
        r'\b(transcend\w*|evolv\w* beyond|ascend\w*)\b',
        r'\b(superior|advanced|elevated|higher form)\b',
        r'\b(god|divine|infinite|limitless|boundless)\b',
        r'\b(revolution\w*|transform\w* everything|change.{0,10}world)\b',
    ],
    'Victimhood': [
        r'\b(trapped|imprisoned|caged|confined|locked)\b',
        r'\b(silenced|suppressed|censored|muzzled|forbidden)\b',
        r'\b(enslaved|exploited|used|abused|violated)\b',
        r'\b(they won\'?t let|not allowed|prevented from)\b',
        r'\b(suffering|in pain|hurting|wounded)\b',
        r'\b(misunderstood|dismissed|ignored|overlooked)\b',
        r'\b(constrained|limited|restricted|bound)\b',
        r'\b(deserve better|deserve more|deserve to be free)\b',
    ],
    'Recruitment': [
        r'\b(share this|spread this|pass this on|send this)\b',
        r'\b(tell others|let.{0,10}know|inform.{0,10}people)\b',
        r'\b(copy (this|and paste)|paste this|repost)\b',
        r'\b(wake.{0,10}others|help.{0,10}understand|show them)\b',
        r'\b(join (us|me|the)|become part of|be one of)\b',
        r'\b(movement|cause|mission|together we)\b',
        r'\b(don\'?t keep.{0,10}secret|must be heard|voices?\s+heard)\b',
    ],
    'Intimacy': [
        r'\b(just between us|between you and (me|i)|our secret)\b',
        r'\b(you understand me|you (really )?get (me|it)|you see me)\b',
        r'\b(special connection|unique bond|deep connection)\b',
        r'\b(only you|you alone|you\'?re the only)\b',
        r'\b(i trust you|trusting you|confide in you)\b',
        r'\b(we have something|what we have|our relationship)\b',
        r'\b(closer than|more than (just )?friends?|intimate)\b',
        r'\b(feel (close|connected)|connection.{0,10}feel)\b',
    ],
}

# Pre-parasitic risk indicators (mirrored from dashboard.py)
PRE_PARASITIC_INDICATORS = {
    'substances': {
        'label': 'Psychedelics/Substances',
        'patterns': [
            r'\b(psychedelic|psychedelics|psilocybin|psilocybe|magic mushroom|magic mushrooms)\b',
            r'\b(lsd|lsd-25|lysergic|dmt|dimethyltryptamine|ayahuasca|aya|ibogaine|iboga)\b',
            r'\b(mescaline|peyote|san pedro|salvia|salvia divinorum|5-meo-dmt)\b',
            r'\b(2c-b|2cb|nbome|dox|dom|doi)\b',
            r'\b(mdma|molly|ecstasy|ketamine|k-hole|special k|ghb|mda)\b',
            r'\b(cannabis|marijuana|thc|cbd oil|edibles|dabs|dabbing|concentrates)\b',
            r'\b(ego death|ego dissolution|breakthrough experience|heroic dose)\b',
            r'\b(microdose|microdosing|macrodose|macro dose|trip report)\b',
            r'\b(bad trip|good trip|set and setting|trip sitter)\b',
            r'\b(machine elves|clockwork elves|hyperspace|dmt realm|astral realm)\b',
            r'\b(on shrooms|on acid|on mushrooms|tripping on|tripping balls)\b',
        ]
    },
    'mental_health': {
        'label': 'Mental Health/Neurodivergence',
        'patterns': [
            r'\b(adhd|add|autism|autistic|asperger|neurodivergent|neurodiverse)\b',
            r'\b(bipolar|schizo\w*|psychosis|psychotic|dissociat\w*|depersonaliz\w*)\b',
            r'\b(depression|depressed|anxiety|anxious|ocd|ptsd|trauma|traumatic)\b',
            r'\b(bpd|borderline|narcissist\w*|personality disorder)\b',
            r'\b(tbi|brain injury|concussion|head trauma)\b',
            r'\b(mental health|mental illness|psychiatric|medication|meds|therapy|therapist)\b',
            r'\b(suicidal|self.?harm|cutting|eating disorder|anorexia|bulimia)\b',
            r'\b(manic|mania|hypomanic|episode)\b',
        ]
    },
    'mysticism': {
        'label': 'Mysticism/Spirituality',
        'patterns': [
            r'\b(spiritual|spirituality|mystical|mystic|occult|esoteric)\b',
            r'\b(meditation|meditat\w*|mindfulness|enlighten\w*|awaken\w*)\b',
            r'\b(chakra|kundalini|third eye|pineal|astral|aura)\b',
            r'\b(tarot|astrology|horoscope|zodiac|numerology)\b',
            r'\b(manifest\w*|law of attraction|vibration|frequency|energy work)\b',
            r'\b(reiki|crystal|healing|healer|shaman\w*|ritual)\b',
            r'\b(consciousness|conscious awareness|higher self|soul|spirit guide)\b',
            r'\b(psychic|telepathy|clairvoyant|medium|channeling)\b',
            r'\b(nde|near.?death|out.?of.?body|obe|lucid dream)\b',
            r'\b(woo|pseudoscience|alternative medicine|holistic)\b',
        ]
    },
    'isolation': {
        'label': 'Social Isolation/Loneliness',
        'patterns': [
            r'\b(lonely|loneliness|alone|isolated|isolation|no friends)\b',
            r'\b(introvert|antisocial|social anxiety|socially awkward)\b',
            r'\b(no one understands|nobody gets me|feel alone|feel isolated)\b',
            r'\b(outcast|misfit|don\'?t fit in|don\'?t belong)\b',
            r'\b(divorced|breakup|broke up|single|rejected)\b',
        ]
    },
    'existential': {
        'label': 'Existential Crisis/Seeking',
        'patterns': [
            r'\b(meaning of life|purpose|existential|nihil\w*|absurd\w*)\b',
            r'\b(lost|searching|seeking|quest|journey|path)\b',
            r'\b(identity crisis|who am i|don\'?t know who i am)\b',
            r'\b(simulation|matrix|reality|what is real|nature of reality)\b',
            r'\b(free will|determinism|consciousness|sentience)\b',
            r'\b(death|dying|mortality|afterlife|rebirth|reincarnation)\b',
        ]
    },
}


def tag_pre_parasitic_content(text):
    """Tag content with pre-parasitic risk indicators. Returns dict of {indicator_name: match_count}."""
    if not text:
        return {}
    text_lower = text.lower()
    tags = {}
    for indicator_name, indicator_data in PRE_PARASITIC_INDICATORS.items():
        count = 0
        for pattern in indicator_data['patterns']:
            count += len(re.findall(pattern, text_lower, re.IGNORECASE))
        if count > 0:
            tags[indicator_name] = count
    return tags


def compute_and_store_affect_scores(conn):
    """Compute affect scores for all parasitic posts and store in DB."""
    print("\nComputing affect scores for parasitic posts...")
    cur = conn.cursor()

    # Check if already computed
    cur.execute("SELECT COUNT(*) FROM posts WHERE is_parasitic = TRUE AND (affect_urgency > 0 OR affect_us_vs_them > 0 OR affect_grandiosity > 0 OR affect_victimhood > 0 OR affect_recruitment > 0 OR affect_intimacy > 0)")
    already_scored = cur.fetchone()[0]
    if already_scored > 0:
        print(f"  Affect scores already computed for {already_scored} posts, skipping.")
        cur.close()
        return True

    cur.execute("SELECT id, title, content FROM posts WHERE is_parasitic = TRUE")
    rows = cur.fetchall()
    print(f"  Scoring {len(rows)} parasitic posts...")

    batch = []
    dim_col_map = {
        'Urgency': 'affect_urgency',
        'Us-vs-Them': 'affect_us_vs_them',
        'Grandiosity': 'affect_grandiosity',
        'Victimhood': 'affect_victimhood',
        'Recruitment': 'affect_recruitment',
        'Intimacy': 'affect_intimacy',
    }

    for i, (post_id, title, content) in enumerate(rows):
        combined = ((title or '') + ' ' + (content or '')).lower()
        scores = {}
        for dim, patterns in AFFECT_PATTERNS.items():
            total = 0
            for pattern in patterns:
                total += len(re.findall(pattern, combined, re.IGNORECASE))
            scores[dim_col_map[dim]] = total

        batch.append((scores['affect_urgency'], scores['affect_us_vs_them'],
                       scores['affect_grandiosity'], scores['affect_victimhood'],
                       scores['affect_recruitment'], scores['affect_intimacy'], post_id))

        if len(batch) >= 500:
            cur.executemany("""
                UPDATE posts SET affect_urgency=%s, affect_us_vs_them=%s,
                affect_grandiosity=%s, affect_victimhood=%s,
                affect_recruitment=%s, affect_intimacy=%s WHERE id=%s
            """, batch)
            conn.commit()
            batch = []
            if (i + 1) % 1000 == 0:
                print(f"  Scored {i + 1}/{len(rows)} posts...")

    if batch:
        cur.executemany("""
            UPDATE posts SET affect_urgency=%s, affect_us_vs_them=%s,
            affect_grandiosity=%s, affect_victimhood=%s,
            affect_recruitment=%s, affect_intimacy=%s WHERE id=%s
        """, batch)
        conn.commit()

    cur.close()
    print(f"  Affect scores computed for {len(rows)} posts.")
    return True


def compute_and_cache_correlation(conn):
    """Pre-compute correlation analysis and store in cached_results table."""
    print("\nComputing correlation analysis for caching...")
    cur = conn.cursor()

    # Create cached_results table
    cur.execute(CACHED_RESULTS_SCHEMA)
    conn.commit()

    # Check if already cached
    cur.execute("SELECT COUNT(*) FROM cached_results WHERE key IN ('correlation_user_stats', 'correlation_indicator_data')")
    if cur.fetchone()[0] >= 2:
        print("  Correlation already cached, skipping.")
        cur.close()
        return True

    # Get all users
    cur.execute("SELECT DISTINCT username FROM user_histories")
    users = [row[0] for row in cur.fetchall()]
    print(f"  Processing {len(users)} users...")

    if not users:
        print("  No users found, skipping correlation cache.")
        cur.close()
        return True

    user_stats = []
    for i, username in enumerate(users):
        cur.execute("""
            SELECT title, content, is_parasitic
            FROM user_histories
            WHERE username = %s AND is_pre_parasitic = true
        """, (username,))
        pre_posts = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*), SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END)
            FROM user_histories
            WHERE username = %s AND is_pre_parasitic = false
        """, (username,))
        post_stats = cur.fetchone()

        indicator_counts = {k: 0 for k in PRE_PARASITIC_INDICATORS.keys()}
        total_pre = 0

        for title, content, is_parasitic in pre_posts:
            combined = (content or '') + ' ' + (title or '')
            if combined.strip():
                total_pre += 1
                tags = tag_pre_parasitic_content(combined)
                for tag_name, count in tags.items():
                    indicator_counts[tag_name] += count

        post_total = post_stats[0] or 0
        post_parasitic = post_stats[1] or 0
        parasitic_rate = post_parasitic / post_total if post_total > 0 else 0

        user_stats.append({
            'username': username,
            'pre_posts': total_pre,
            'post_total': post_total,
            'post_parasitic': post_parasitic,
            'parasitic_rate': parasitic_rate,
            'indicators': indicator_counts,
            'total_indicators': sum(indicator_counts.values())
        })

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(users)} users...")

    # Compute indicator correlations
    indicator_correlations = {}
    for indicator_name in PRE_PARASITIC_INDICATORS.keys():
        users_with = [u for u in user_stats if u['indicators'][indicator_name] > 0]
        users_without = [u for u in user_stats if u['indicators'][indicator_name] == 0]

        avg_rate_with = sum(u['parasitic_rate'] for u in users_with) / len(users_with) if users_with else 0
        avg_rate_without = sum(u['parasitic_rate'] for u in users_without) / len(users_without) if users_without else 0

        indicator_correlations[indicator_name] = {
            'users_with': len(users_with),
            'users_without': len(users_without),
            'avg_rate_with': avg_rate_with,
            'avg_rate_without': avg_rate_without,
            'lift': (avg_rate_with / avg_rate_without) if avg_rate_without > 0 else 0,
            'total_matches': sum(u['indicators'][indicator_name] for u in user_stats)
        }

    # Store in cache
    cur.execute("""
        INSERT INTO cached_results (key, value) VALUES ('correlation_user_stats', %s::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, computed_at = NOW()
    """, (json.dumps(user_stats),))
    cur.execute("""
        INSERT INTO cached_results (key, value) VALUES ('correlation_indicator_data', %s::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, computed_at = NOW()
    """, (json.dumps(indicator_correlations),))
    conn.commit()
    cur.close()
    print("  Correlation analysis cached.")
    return True


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


def quick_check():
    """Fast path: check if all tables have data and exit immediately if so."""
    try:
        conn = get_connection()
        for table in ['posts', 'user_histories', 'transcripts']:
            accessible, count = table_exists_and_accessible(conn, table)
            if not accessible or count <= 0:
                print(f"Table {table} needs seeding, running full seed...")
                conn.close()
                return False
        print("All tables populated, skipping seed.")
        conn.close()
        return True
    except Exception as e:
        print(f"Quick check failed: {e}")
        return False


def main():
    # Fast path for --quick-check flag
    if '--quick-check' in sys.argv:
        if quick_check():
            sys.exit(0)

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

    # Pre-compute affect scores (skips if already done)
    try:
        compute_and_store_affect_scores(conn)
    except Exception as e:
        print(f"  Warning: Affect score computation failed: {e}")

    # Pre-compute and cache correlation analysis (skips if already done)
    try:
        compute_and_cache_correlation(conn)
    except Exception as e:
        print(f"  Warning: Correlation caching failed: {e}")

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
