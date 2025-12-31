-- Run this in Render's PSQL Shell to create missing tables
-- Go to: Render Dashboard > Database > Shell tab

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

-- Verify tables created
\dt
