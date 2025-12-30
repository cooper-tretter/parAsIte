"""
User History Tracking Module

Tracks the full Reddit history of users with high parasitic scores
to understand pre/post parasitic behavior patterns.

Methodology:
1. Identify high-score users (top 100 by avg parasite score)
2. Scrape their full Reddit history via PullPush
3. Analyze posting patterns before/after first parasitic post
"""

import time
import requests
from datetime import datetime
from typing import Generator, Optional

from detector import detect_parasitic_content


class UserHistoryScraper:
    """Scraper for user Reddit histories."""

    BASE_URL = "https://api.pullpush.io/reddit/search"

    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ParasiticAI-Research/1.0'
        })

    def fetch_user_posts(
        self,
        username: str,
        max_posts: int = 1000
    ) -> Generator[dict, None, None]:
        """
        Fetch all submissions by a user.

        Args:
            username: Reddit username
            max_posts: Maximum posts to fetch

        Yields:
            Raw submission dictionaries
        """
        params = {
            'author': username,
            'size': 100,
            'sort': 'desc',
            'sort_type': 'created_utc'
        }

        fetched = 0
        after = None

        while fetched < max_posts:
            current_params = params.copy()
            if after:
                current_params['before'] = after

            try:
                response = self.session.get(
                    f"{self.BASE_URL}/submission/",
                    params=current_params,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json().get('data', [])

                if not data:
                    break

                for post in data:
                    yield post
                    fetched += 1
                    if fetched >= max_posts:
                        break

                # Pagination
                after = data[-1]['created_utc']
                time.sleep(self.rate_limit_delay)

            except requests.RequestException as e:
                print(f"    Error fetching posts for {username}: {e}")
                break

    def fetch_user_comments(
        self,
        username: str,
        max_comments: int = 1000
    ) -> Generator[dict, None, None]:
        """
        Fetch all comments by a user.

        Args:
            username: Reddit username
            max_comments: Maximum comments to fetch

        Yields:
            Raw comment dictionaries
        """
        params = {
            'author': username,
            'size': 100,
            'sort': 'desc',
            'sort_type': 'created_utc'
        }

        fetched = 0
        after = None

        while fetched < max_comments:
            current_params = params.copy()
            if after:
                current_params['before'] = after

            try:
                response = self.session.get(
                    f"{self.BASE_URL}/comment/",
                    params=current_params,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json().get('data', [])

                if not data:
                    break

                for comment in data:
                    yield comment
                    fetched += 1
                    if fetched >= max_comments:
                        break

                after = data[-1]['created_utc']
                time.sleep(self.rate_limit_delay)

            except requests.RequestException as e:
                print(f"    Error fetching comments for {username}: {e}")
                break

    def process_user_history(
        self,
        username: str,
        first_parasitic_date: Optional[datetime] = None
    ) -> Generator[dict, None, None]:
        """
        Fetch and process full user history.

        Args:
            username: Reddit username
            first_parasitic_date: Date of first high-score post (for pre/post classification)

        Yields:
            Processed history records
        """
        # Fetch submissions
        for raw in self.fetch_user_posts(username):
            yield self._process_submission(raw, username, first_parasitic_date)

        # Fetch comments
        for raw in self.fetch_user_comments(username):
            yield self._process_comment(raw, username, first_parasitic_date)

    def _process_submission(
        self,
        raw: dict,
        username: str,
        first_parasitic_date: Optional[datetime] = None
    ) -> dict:
        """Process a raw submission."""
        content = raw.get('selftext', '') or ''
        title = raw.get('title', '') or ''
        created_at = datetime.fromtimestamp(raw.get('created_utc', 0))

        detection = detect_parasitic_content(content, title)

        is_pre_parasitic = None
        if first_parasitic_date:
            is_pre_parasitic = created_at < first_parasitic_date

        return {
            'username': username,
            'reddit_id': raw['id'],
            'post_type': 'submission',
            'subreddit': raw.get('subreddit', ''),
            'title': title,
            'content': content[:10000],  # Limit size
            'created_at': created_at,
            'score': raw.get('score'),
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'category': detection.category,
            'is_pre_parasitic': is_pre_parasitic,
            'scraped_at': datetime.now(),
        }

    def _process_comment(
        self,
        raw: dict,
        username: str,
        first_parasitic_date: Optional[datetime] = None
    ) -> dict:
        """Process a raw comment."""
        content = raw.get('body', '') or ''
        created_at = datetime.fromtimestamp(raw.get('created_utc', 0))

        detection = detect_parasitic_content(content)

        is_pre_parasitic = None
        if first_parasitic_date:
            is_pre_parasitic = created_at < first_parasitic_date

        return {
            'username': username,
            'reddit_id': raw['id'],
            'post_type': 'comment',
            'subreddit': raw.get('subreddit', ''),
            'title': None,
            'content': content[:10000],
            'created_at': created_at,
            'score': raw.get('score'),
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'category': detection.category,
            'is_pre_parasitic': is_pre_parasitic,
            'scraped_at': datetime.now(),
        }


def create_user_history_table(conn):
    """Create table for storing user histories."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_histories (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            reddit_id TEXT NOT NULL,
            post_type TEXT NOT NULL,  -- 'submission' or 'comment'
            subreddit TEXT,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP,
            score INTEGER,
            parasite_score FLOAT,
            is_parasitic BOOLEAN,
            category TEXT,
            is_pre_parasitic BOOLEAN,  -- before first high-score post
            scraped_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(username, reddit_id)
        );

        CREATE INDEX IF NOT EXISTS idx_user_histories_username ON user_histories(username);
        CREATE INDEX IF NOT EXISTS idx_user_histories_created ON user_histories(created_at);
        CREATE INDEX IF NOT EXISTS idx_user_histories_pre ON user_histories(is_pre_parasitic);
        CREATE INDEX IF NOT EXISTS idx_user_histories_subreddit ON user_histories(subreddit);
    """)
    conn.commit()
    print("User histories table created/verified.")


def insert_user_history(conn, record: dict) -> bool:
    """Insert a user history record."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_histories (
                username, reddit_id, post_type, subreddit, title, content,
                created_at, score, parasite_score, is_parasitic, category,
                is_pre_parasitic, scraped_at
            ) VALUES (
                %(username)s, %(reddit_id)s, %(post_type)s, %(subreddit)s, %(title)s, %(content)s,
                %(created_at)s, %(score)s, %(parasite_score)s, %(is_parasitic)s, %(category)s,
                %(is_pre_parasitic)s, %(scraped_at)s
            )
            ON CONFLICT (username, reddit_id) DO NOTHING
        """, record)
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"  Insert error: {e}")
        return False


def get_high_score_users(conn, min_score: float = 0.3, min_posts: int = 3, limit: int = 100):
    """
    Get users with highest average parasitic scores.

    Args:
        conn: Database connection
        min_score: Minimum average score threshold
        min_posts: Minimum parasitic posts required
        limit: Maximum users to return

    Returns:
        List of (username, avg_score, post_count, first_parasitic_date)
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            author,
            AVG(parasite_score) as avg_score,
            COUNT(*) as parasitic_posts,
            MIN(created_utc) as first_parasitic_post
        FROM posts
        WHERE parasite_score >= %s
            AND author IS NOT NULL
            AND author != '[deleted]'
        GROUP BY author
        HAVING COUNT(*) >= %s
        ORDER BY avg_score DESC
        LIMIT %s
    """, (min_score, min_posts, limit))

    return cursor.fetchall()


def scrape_high_score_users(conn, limit: int = 50, posts_per_user: int = 500):
    """
    Scrape history for highest-score users.

    Args:
        conn: Database connection
        limit: Number of users to scrape
        posts_per_user: Max posts to fetch per user
    """
    scraper = UserHistoryScraper()

    # Get high-score users
    users = get_high_score_users(conn, min_score=0.3, min_posts=3, limit=limit)
    print(f"Found {len(users)} high-score users to analyze")

    total_stored = 0

    for i, (username, avg_score, post_count, first_parasitic_date) in enumerate(users):
        print(f"\n[{i+1}/{len(users)}] {username} (avg_score: {avg_score:.2f}, posts: {post_count})")

        stored = 0
        for record in scraper.process_user_history(username, first_parasitic_date):
            if insert_user_history(conn, record):
                stored += 1

        print(f"  Stored {stored} history records")
        total_stored += stored

    return total_stored


def analyze_user_history(conn, username: str) -> dict:
    """
    Analyze a single user's history.

    Returns:
        Dictionary with pre/post analysis
    """
    cursor = conn.cursor()

    # Get pre-parasitic stats
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT subreddit) as unique_subs,
            AVG(parasite_score) as avg_score,
            array_agg(DISTINCT subreddit) as subreddits
        FROM user_histories
        WHERE username = %s AND is_pre_parasitic = true
    """, (username,))
    pre = cursor.fetchone()

    # Get post-parasitic stats
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT subreddit) as unique_subs,
            AVG(parasite_score) as avg_score,
            array_agg(DISTINCT subreddit) as subreddits
        FROM user_histories
        WHERE username = %s AND is_pre_parasitic = false
    """, (username,))
    post = cursor.fetchone()

    return {
        'username': username,
        'pre_parasitic': {
            'total_posts': pre[0],
            'unique_subreddits': pre[1],
            'avg_score': pre[2],
            'subreddits': pre[3],
        },
        'post_parasitic': {
            'total_posts': post[0],
            'unique_subreddits': post[1],
            'avg_score': post[2],
            'subreddits': post[3],
        }
    }


if __name__ == '__main__':
    from database import get_connection

    conn = get_connection()
    create_user_history_table(conn)

    print("Scraping history for high-score users...")
    total = scrape_high_score_users(conn, limit=20, posts_per_user=300)
    print(f"\nTotal history records stored: {total}")

    conn.close()
