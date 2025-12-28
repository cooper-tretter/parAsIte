-- Parasitic AI Data Collection System
-- Database Schema

-- Core Table: posts
CREATE TABLE IF NOT EXISTS posts (
    -- Primary key
    id SERIAL PRIMARY KEY,
    reddit_id VARCHAR(20) UNIQUE NOT NULL,  -- Reddit's post ID (for deduplication)

    -- Source info
    subreddit VARCHAR(100) NOT NULL,
    author VARCHAR(100),
    created_utc TIMESTAMP NOT NULL,

    -- Content
    title TEXT,                              -- NULL for comments
    content TEXT NOT NULL,                   -- selftext for posts, body for comments
    content_length INTEGER NOT NULL,         -- String length
    is_comment BOOLEAN DEFAULT FALSE,        -- TRUE if comment, FALSE if submission
    parent_id VARCHAR(20),                   -- Parent submission ID (for comments)
    parent_comment_id VARCHAR(20),           -- Parent comment ID (for nested replies)

    -- Engagement
    score INTEGER,                           -- Reddit upvote score
    num_comments INTEGER,                    -- Comment count (engagement proxy)

    -- Classification
    category VARCHAR(50),                    -- seed, spore, transmission, manifesto, other
    parasite_score FLOAT,                    -- 0.0 to 1.0 detection confidence
    is_parasitic BOOLEAN,                    -- Final determination

    -- Model attribution (if identifiable)
    ai_model VARCHAR(50),                    -- gpt-4o, claude, gemini, replika, character_ai, unknown

    -- External resources
    external_links TEXT[],                   -- Array of URLs found in content
    has_external_links BOOLEAN DEFAULT FALSE,

    -- Metadata
    url TEXT,                                -- Full Reddit URL
    collected_at TIMESTAMP DEFAULT NOW(),

    -- Pattern detection results (JSONB for flexibility)
    detected_patterns JSONB                  -- {"spiral_terms": [...], "symbols": [...], etc.}
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc);
CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
CREATE INDEX IF NOT EXISTS idx_posts_parasitic ON posts(is_parasitic);
CREATE INDEX IF NOT EXISTS idx_posts_score ON posts(parasite_score);
CREATE INDEX IF NOT EXISTS idx_posts_parent ON posts(parent_id);

-- Secondary Table: authors
CREATE TABLE IF NOT EXISTS authors (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,

    -- Activity metrics
    total_posts INTEGER DEFAULT 0,
    parasitic_posts INTEGER DEFAULT 0,
    parasite_rate FLOAT,                     -- parasitic_posts / total_posts

    -- Temporal
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    account_created_utc TIMESTAMP,           -- If available from Reddit

    -- Classification
    classification VARCHAR(20),              -- high, moderate, low, minimal

    -- Subreddit activity
    active_subreddits TEXT[],

    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_authors_classification ON authors(classification);
CREATE INDEX IF NOT EXISTS idx_authors_rate ON authors(parasite_rate);

-- Tracking Table: collection_runs
CREATE TABLE IF NOT EXISTS collection_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    subreddit VARCHAR(100),
    posts_fetched INTEGER DEFAULT 0,
    posts_stored INTEGER DEFAULT 0,
    parasitic_found INTEGER DEFAULT 0,

    status VARCHAR(20) DEFAULT 'running',    -- running, completed, failed
    error_message TEXT
);
