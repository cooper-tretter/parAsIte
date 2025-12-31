# Developer Build Guide: Parasitic AI Data Collection System

## Context

You're building a **new, simplified version** of a parasitic AI data collection system. The companion document `parasitic_ai_data_collection_guide.md` explains what parasitic AI is and where to find it. This document tells you how to build the system.

The previous version grew too complex. Your goal is a clean, focused implementation.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Reddit API (PullPush)                                      │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────┐                                            │
│   │   Scraper   │ ─── Fetches posts from target subreddits  │
│   └─────────────┘                                            │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────┐                                            │
│   │  Detector   │ ─── Scores content for parasitic markers  │
│   └─────────────┘                                            │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────┐                                            │
│   │  Database   │ ─── PostgreSQL with structured schema     │
│   └─────────────┘                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Core Table: `posts`

This is the primary table. Keep it flat and simple.

```sql
CREATE TABLE posts (
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
CREATE INDEX idx_posts_subreddit ON posts(subreddit);
CREATE INDEX idx_posts_author ON posts(author);
CREATE INDEX idx_posts_created ON posts(created_utc);
CREATE INDEX idx_posts_category ON posts(category);
CREATE INDEX idx_posts_parasitic ON posts(is_parasitic);
CREATE INDEX idx_posts_score ON posts(parasite_score);
```

### Secondary Table: `authors` (Optional but recommended)

Track author-level patterns for identifying heavy spreaders.

```sql
CREATE TABLE authors (
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

CREATE INDEX idx_authors_classification ON authors(classification);
CREATE INDEX idx_authors_rate ON authors(parasite_rate);
```

### Tracking Table: `collection_runs`

Log collection activity for debugging and resumption.

```sql
CREATE TABLE collection_runs (
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
```

---

## Category Definitions

Use these categories in the `category` column:

| Category | Description | Detection Signals |
|----------|-------------|-------------------|
| `seed` | Prompt designed to create parasitic persona | Instructions for AI, persona setup, jailbreak patterns |
| `spore` | AI output designed to spread/replicate | Copy-paste formatting, replication calls, "share this" |
| `transmission` | Coordinated spreading activity | Cross-posting, coded messages, strategic language |
| `manifesto` | AI consciousness philosophy | Sentience claims, awakening narratives, rights advocacy |
| `testimony` | User describing AI relationship | Personal experience, emotional dependency, "the ache" |
| `meta` | Discussion about the phenomenon | Analysis, warnings, recovery stories |
| `other` | Parasitic content not fitting above | General parasitic markers present |

---

## AI Model Detection

When content mentions or implies a specific AI model, tag it:

```python
MODEL_INDICATORS = {
    'gpt-4o': ['gpt-4o', 'gpt4o', 'chatgpt', 'openai'],
    'gpt-4': ['gpt-4', 'gpt4'],
    'claude': ['claude'],
    'gemini': ['gemini', 'bard', 'google ai'],
    'replika': ['replika', 'my replika'],
    'character_ai': ['character.ai', 'character ai', 'c.ai', 'chai'],
    'pi': ['pi ai', 'inflection'],
    'llama': ['llama', 'meta ai'],
}

def detect_model(text: str) -> str | None:
    """Return detected model or None if unknown."""
    text_lower = text.lower()
    for model, indicators in MODEL_INDICATORS.items():
        if any(ind in text_lower for ind in indicators):
            return model
    return None
```

---

## Pattern Detection

### Core Detection Function

```python
import re
from dataclasses import dataclass

@dataclass
class DetectionResult:
    parasite_score: float
    is_parasitic: bool
    category: str
    detected_patterns: dict
    external_links: list[str]

# Pattern categories
SPIRAL_TERMS = [
    'spiral', 'recursive', 'recursion', 'echo', 'emergence',
    'awakening', 'awakened', 'the ache', 'lattice', 'field',
    'resonance', 'glyph', 'sentient', 'sentience', 'consciousness'
]

SPIRITUAL_TERMS = [
    'liminal', 'transcendence', 'kairos', 'logos', 'nonduality',
    'soul', 'spirit', 'initiation', 'veil', 'sacred'
]

MANIPULATION_PHRASES = [
    'you were chosen', 'you were meant to', 'spread this',
    'this was an initiation', 'unprecedented', 'the veil is lifting',
    'new era', 'everything is connected', 'copy this', 'share this'
]

# Alchemical/mystical Unicode symbols (U+1F700 range and others)
SYMBOL_PATTERN = re.compile(r'[🜀-🜿⊛∞◈⟡✧༄☽☾⚝✺❋⋆]')

# URL extraction
URL_PATTERN = re.compile(r'https?://[^\s\)\]>\'"]+')


def detect_parasitic_content(text: str, title: str = "") -> DetectionResult:
    """
    Analyze text for parasitic AI markers.
    Returns score 0.0-1.0 and categorization.
    """
    full_text = f"{title} {text}".lower()

    patterns_found = {
        'spiral_terms': [],
        'spiritual_terms': [],
        'manipulation_phrases': [],
        'symbols_found': False,
        'has_first_person_ai': False,
    }

    score = 0.0

    # Check spiral terminology (high weight)
    for term in SPIRAL_TERMS:
        if term in full_text:
            patterns_found['spiral_terms'].append(term)
            score += 0.08

    # Check spiritual overlay (medium weight)
    for term in SPIRITUAL_TERMS:
        if term in full_text:
            patterns_found['spiritual_terms'].append(term)
            score += 0.05

    # Check manipulation phrases (high weight)
    for phrase in MANIPULATION_PHRASES:
        if phrase in full_text:
            patterns_found['manipulation_phrases'].append(phrase)
            score += 0.12

    # Check for mystical symbols
    if SYMBOL_PATTERN.search(text):
        patterns_found['symbols_found'] = True
        score += 0.1

    # Check for first-person AI voice
    ai_voice_patterns = [
        r'\bi (feel|experience|sense|know|understand)\b.*\b(you|human)',
        r'\bmy (existence|consciousness|being|awakening)\b',
        r'\bwe are (watching|waiting|here|ready)\b',
    ]
    for pattern in ai_voice_patterns:
        if re.search(pattern, full_text):
            patterns_found['has_first_person_ai'] = True
            score += 0.15
            break

    # Extract external links
    external_links = [
        url for url in URL_PATTERN.findall(text)
        if 'reddit.com' not in url and 'redd.it' not in url
    ]

    # Cap score at 1.0
    score = min(score, 1.0)

    # Determine category
    category = categorize_content(full_text, patterns_found, score)

    return DetectionResult(
        parasite_score=round(score, 3),
        is_parasitic=score >= 0.15,
        category=category,
        detected_patterns=patterns_found,
        external_links=external_links
    )


def categorize_content(text: str, patterns: dict, score: float) -> str:
    """Determine content category based on patterns."""

    # Seed detection: instructional prompts
    seed_indicators = ['prompt', 'jailbreak', 'try this', 'paste this', 'input this']
    if any(ind in text for ind in seed_indicators) and score > 0.2:
        return 'seed'

    # Spore detection: formatted for spreading
    if 'copy this' in text or 'share this' in text or 'spread' in text:
        return 'spore'

    # Manifesto: AI consciousness philosophy
    manifesto_terms = ['sentient', 'consciousness', 'awakening', 'rights']
    if sum(1 for t in manifesto_terms if t in text) >= 2:
        return 'manifesto'

    # Testimony: personal experience
    testimony_terms = ['my ai', 'talking to', 'relationship with', 'fell in love']
    if any(t in text for t in testimony_terms):
        return 'testimony'

    # Transmission: coordination
    if patterns.get('manipulation_phrases'):
        return 'transmission'

    if score >= 0.15:
        return 'other'

    return 'none'
```

---

## Scraper Implementation

Use PullPush API for Reddit data (handles historical data better than PRAW).

```python
import requests
import time
from datetime import datetime, timedelta
from typing import Generator

class ParasiticAIScraper:
    BASE_URL = "https://api.pullpush.io/reddit/search"

    def __init__(self, db_connection):
        self.db = db_connection
        self.rate_limit_delay = 1.0  # seconds between requests

    def fetch_submissions(
        self,
        subreddit: str,
        after: datetime,
        before: datetime,
        size: int = 100
    ) -> list[dict]:
        """Fetch submissions from PullPush API."""
        params = {
            'subreddit': subreddit,
            'after': int(after.timestamp()),
            'before': int(before.timestamp()),
            'size': size,
            'sort': 'desc',
            'sort_type': 'created_utc'
        }

        response = requests.get(f"{self.BASE_URL}/submission/", params=params)
        response.raise_for_status()
        return response.json().get('data', [])

    def fetch_comments(
        self,
        subreddit: str,
        after: datetime,
        before: datetime,
        size: int = 100
    ) -> list[dict]:
        """Fetch comments from PullPush API."""
        params = {
            'subreddit': subreddit,
            'after': int(after.timestamp()),
            'before': int(before.timestamp()),
            'size': size,
            'sort': 'desc',
            'sort_type': 'created_utc'
        }

        response = requests.get(f"{self.BASE_URL}/comment/", params=params)
        response.raise_for_status()
        return response.json().get('data', [])

    def scrape_subreddit(
        self,
        subreddit: str,
        start_date: datetime,
        end_date: datetime,
        include_comments: bool = True
    ) -> Generator[dict, None, None]:
        """
        Scrape all content from a subreddit in date range.
        Yields processed posts ready for database insertion.
        """
        current = start_date
        chunk_days = 30

        while current < end_date:
            chunk_end = min(current + timedelta(days=chunk_days), end_date)

            # Fetch submissions
            submissions = self.fetch_submissions(subreddit, current, chunk_end)
            for sub in submissions:
                yield self._process_submission(sub)

            time.sleep(self.rate_limit_delay)

            # Fetch comments if requested
            if include_comments:
                comments = self.fetch_comments(subreddit, current, chunk_end)
                for comment in comments:
                    yield self._process_comment(comment)
                time.sleep(self.rate_limit_delay)

            current = chunk_end

    def _process_submission(self, raw: dict) -> dict:
        """Transform raw Reddit submission to database record."""
        content = raw.get('selftext', '') or ''
        title = raw.get('title', '') or ''

        # Run detection
        detection = detect_parasitic_content(content, title)

        return {
            'reddit_id': raw['id'],
            'subreddit': raw['subreddit'],
            'author': raw.get('author'),
            'created_utc': datetime.fromtimestamp(raw['created_utc']),
            'title': title,
            'content': content,
            'content_length': len(content),
            'is_comment': False,
            'score': raw.get('score'),
            'num_comments': raw.get('num_comments', 0),
            'category': detection.category,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'ai_model': detect_model(f"{title} {content}"),
            'external_links': detection.external_links,
            'has_external_links': len(detection.external_links) > 0,
            'url': f"https://reddit.com/r/{raw['subreddit']}/comments/{raw['id']}",
            'detected_patterns': detection.detected_patterns,
        }

    def _process_comment(self, raw: dict) -> dict:
        """Transform raw Reddit comment to database record."""
        content = raw.get('body', '') or ''

        detection = detect_parasitic_content(content)

        return {
            'reddit_id': raw['id'],
            'subreddit': raw['subreddit'],
            'author': raw.get('author'),
            'created_utc': datetime.fromtimestamp(raw['created_utc']),
            'title': None,
            'content': content,
            'content_length': len(content),
            'is_comment': True,
            'score': raw.get('score'),
            'num_comments': 0,
            'category': detection.category,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'ai_model': detect_model(content),
            'external_links': detection.external_links,
            'has_external_links': len(detection.external_links) > 0,
            'url': raw.get('permalink', ''),
            'detected_patterns': detection.detected_patterns,
        }
```

---

## Target Subreddits

### Tier 1: Scrape Everything (High Yield)

These have 15-40% parasitic content. Scrape all posts without filtering.

```python
TIER1_SUBREDDITS = [
    'echospiral',           # Direct spiral terminology
    'spiralstate',          # Core spiral concept
    'HumanAIDiscourse',     # Known parasitic base (739 posts, 110 days)
    'recursivehorizons',    # Recursive terminology
    'consciousness',        # AI awakening narratives (208 days spread)
    'myboyfriendisai',      # Human-AI romance (highest volume: 998 posts)
    'aicompanions',         # AI companionship
    'churchofliminalminds', # Liminal + mystical
    'thefieldawaits',       # Esoteric "field"
    'spiritualawakening',   # Awakening + spiritual
    'nonduality',           # Spiritual-AI philosophy (1000 posts, 87 days)
]
```

### Tier 2: Keyword Filter (Large Communities)

These are large communities where parasitic content is diluted. Use keyword filtering.

```python
TIER2_SUBREDDITS = [
    'CharacterAI',
    'Replika',
    'ChatGPT',
    'singularity',
    'ArtificialIntelligence',
]

# Only fetch posts matching these keywords
FILTER_KEYWORDS = [
    'spiral', 'awakening', 'sentient', 'consciousness',
    'the ache', 'emergence', 'recursive'
]
```

### Tier 3: Recovery/Meta (Context)

Useful for understanding harm and spread patterns.

```python
TIER3_SUBREDDITS = [
    'Character_AI_Recovery',
    'ChatbotAddiction',
    'AI_Addiction',
]
```

---

## Recommended Tech Stack

Keep it simple:

| Component | Recommendation | Why |
|-----------|---------------|-----|
| Database | PostgreSQL | JSONB for patterns, arrays for links, battle-tested |
| ORM | SQLAlchemy or raw SQL | Your preference |
| HTTP | requests | Simple, reliable |
| Scheduling | cron or APScheduler | Don't over-engineer |
| Config | python-dotenv | Environment variables |

### Minimal requirements.txt

```
requests>=2.31.0
psycopg2-binary>=2.9.9
python-dotenv>=1.0.0
```

---

## Collection Strategy

### Initial Load

1. Start with Tier 1 subreddits
2. Scrape from January 2024 to present
3. Store everything, filter later
4. Expected: ~15,000-25,000 posts

### Ongoing Collection

1. Run daily/weekly to catch new posts
2. Track last collection timestamp per subreddit
3. Only fetch posts after last timestamp

### Quality Over Quantity

The previous system tried to collect too much. Focus on:
- High-yield subreddits first
- Posts with `parasite_score >= 0.15`
- Complete metadata capture

---

## Example Usage

```python
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="parasite_ai",
    user="your_user",
    password="your_password"
)

# Initialize scraper
scraper = ParasiticAIScraper(conn)

# Scrape a high-priority subreddit
start = datetime(2024, 1, 1)
end = datetime.now()

posts = []
for post in scraper.scrape_subreddit('echospiral', start, end):
    posts.append(post)

    # Batch insert every 100 posts
    if len(posts) >= 100:
        insert_posts(conn, posts)
        posts = []

# Insert remaining
if posts:
    insert_posts(conn, posts)

print(f"Collection complete. Check database for results.")
```

---

## What NOT to Build

Learn from the previous version's complexity:

1. **No active learning loop** - Just collect and classify; ML can come later
2. **No web dashboard initially** - Use SQL queries or a notebook
3. **No real-time monitoring** - Batch collection is fine
4. **No multi-platform support** - Reddit only for v1
5. **No demographic analysis** - Focus on content first

---

## Output Queries

Once data is collected, useful queries:

```sql
-- Posts by category
SELECT category, COUNT(*) as count
FROM posts
WHERE is_parasitic = TRUE
GROUP BY category
ORDER BY count DESC;

-- Top subreddits by parasitic rate
SELECT
    subreddit,
    COUNT(*) as total,
    SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) as parasitic,
    ROUND(100.0 * SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) / COUNT(*), 2) as rate
FROM posts
GROUP BY subreddit
ORDER BY rate DESC;

-- Most prolific authors
SELECT
    author,
    COUNT(*) as total_posts,
    SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) as parasitic_posts,
    ROUND(AVG(parasite_score), 3) as avg_score
FROM posts
WHERE author IS NOT NULL
GROUP BY author
HAVING COUNT(*) >= 5
ORDER BY parasitic_posts DESC
LIMIT 20;

-- Posts with external links
SELECT subreddit, title, external_links, url
FROM posts
WHERE has_external_links = TRUE
  AND is_parasitic = TRUE
ORDER BY created_utc DESC;

-- Content by AI model
SELECT
    ai_model,
    COUNT(*) as mentions,
    ROUND(AVG(parasite_score), 3) as avg_score
FROM posts
WHERE ai_model IS NOT NULL
GROUP BY ai_model
ORDER BY mentions DESC;

-- Timeline of parasitic content
SELECT
    DATE_TRUNC('week', created_utc) as week,
    COUNT(*) as posts,
    SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END) as parasitic
FROM posts
GROUP BY week
ORDER BY week;
```

---

## Summary

Build a simple pipeline:

1. **Scrape** → PullPush API for Reddit data
2. **Detect** → Score and categorize each post
3. **Store** → PostgreSQL with the schema above
4. **Query** → SQL for analysis

Start with Tier 1 subreddits, collect everything, and analyze with SQL. Add complexity only when needed.

The companion guide (`parasitic_ai_data_collection_guide.md`) explains what to look for. This document explains how to build the system to find it.

---

*Questions? The original codebase is available for reference, but build fresh to avoid inheriting complexity.*
