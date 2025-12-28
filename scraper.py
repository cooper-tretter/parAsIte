"""
Reddit Scraper Module

Supports two data sources:
1. PullPush API - For historical data (has indexing lag)
2. Official Reddit API - For recent data (requires credentials)

Fetches submissions and comments from Reddit subreddits,
processes them through the parasitic content detector,
and prepares data for database storage.
"""

import time
import os
from datetime import datetime, timedelta
from typing import Generator, Optional

import requests
from dotenv import load_dotenv

from detector import detect_parasitic_content
from models import detect_model

load_dotenv()


class ParasiticAIScraper:
    """Scraper for collecting parasitic AI content from Reddit via PullPush API."""

    BASE_URL = "https://api.pullpush.io/reddit/search"

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the scraper.

        Args:
            rate_limit_delay: Seconds to wait between API requests
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ParasiticAI-Research-Scraper/1.0'
        })

    def fetch_submissions(
        self,
        subreddit: str,
        after: datetime,
        before: datetime,
        size: int = 100,
        query: Optional[str] = None
    ) -> list[dict]:
        """
        Fetch submissions from PullPush API with pagination.

        Args:
            subreddit: Subreddit name (without r/)
            after: Start datetime
            before: End datetime
            size: Max results per request (max 100)
            query: Optional keyword filter

        Returns:
            List of raw submission dictionaries
        """
        all_results = []
        current_before = int(before.timestamp())
        after_ts = int(after.timestamp())

        while True:
            params = {
                'subreddit': subreddit,
                'after': after_ts,
                'before': current_before,
                'size': size,
                'sort': 'desc',
                'sort_type': 'created_utc'
            }

            if query:
                params['q'] = query

            data = []
            for attempt in range(3):
                try:
                    response = self.session.get(
                        f"{self.BASE_URL}/submission/",
                        params=params,
                        timeout=120
                    )
                    response.raise_for_status()
                    data = response.json().get('data', [])
                    break
                except requests.RequestException as e:
                    if attempt < 2:
                        print(f"  Retry {attempt + 1}/3 for submissions...")
                        time.sleep(2)
                    else:
                        print(f"Error fetching submissions from r/{subreddit}: {e}")
                        return all_results

            if not data:
                break

            all_results.extend(data)

            # Pagination: use oldest post's timestamp as new 'before'
            oldest_ts = min(post['created_utc'] for post in data)
            if oldest_ts <= after_ts or len(data) < size:
                break
            current_before = oldest_ts

            time.sleep(self.rate_limit_delay)

        return all_results

    def fetch_comments(
        self,
        subreddit: str,
        after: datetime,
        before: datetime,
        size: int = 100,
        query: Optional[str] = None
    ) -> list[dict]:
        """
        Fetch comments from PullPush API.

        Args:
            subreddit: Subreddit name (without r/)
            after: Start datetime
            before: End datetime
            size: Max results per request (max 100)
            query: Optional keyword filter

        Returns:
            List of raw comment dictionaries
        """
        params = {
            'subreddit': subreddit,
            'after': int(after.timestamp()),
            'before': int(before.timestamp()),
            'size': size,
            'sort': 'desc',
            'sort_type': 'created_utc'
        }

        if query:
            params['q'] = query

        for attempt in range(3):
            try:
                response = self.session.get(
                    f"{self.BASE_URL}/comment/",
                    params=params,
                    timeout=120
                )
                response.raise_for_status()
                return response.json().get('data', [])
            except requests.RequestException as e:
                if attempt < 2:
                    print(f"  Retry {attempt + 1}/3 for comments...")
                    import time
                    time.sleep(2)
                else:
                    print(f"Error fetching comments from r/{subreddit}: {e}")
                    return []

    def scrape_subreddit(
        self,
        subreddit: str,
        start_date: datetime,
        end_date: datetime,
        include_comments: bool = True,
        query: Optional[str] = None
    ) -> Generator[dict, None, None]:
        """
        Scrape all content from a subreddit in date range.

        Yields processed posts ready for database insertion.

        Args:
            subreddit: Subreddit name
            start_date: Start of date range
            end_date: End of date range
            include_comments: Whether to also fetch comments
            query: Optional keyword filter (for Tier 2 subreddits)

        Yields:
            Processed post dictionaries
        """
        current = start_date
        chunk_days = 30

        while current < end_date:
            chunk_end = min(current + timedelta(days=chunk_days), end_date)

            print(f"  Fetching r/{subreddit} from {current.date()} to {chunk_end.date()}...")

            # Fetch submissions
            submissions = self.fetch_submissions(
                subreddit, current, chunk_end, query=query
            )
            for sub in submissions:
                yield self._process_submission(sub)

            time.sleep(self.rate_limit_delay)

            # Fetch comments if requested
            if include_comments:
                comments = self.fetch_comments(
                    subreddit, current, chunk_end, query=query
                )
                for comment in comments:
                    yield self._process_comment(comment)
                time.sleep(self.rate_limit_delay)

            current = chunk_end

    def _process_submission(self, raw: dict) -> dict:
        """
        Transform raw Reddit submission to database record.

        Args:
            raw: Raw submission from PullPush API

        Returns:
            Processed dictionary ready for database insertion
        """
        content = raw.get('selftext', '') or ''
        title = raw.get('title', '') or ''

        # Run detection
        detection = detect_parasitic_content(content, title)

        return {
            'reddit_id': raw['id'],
            'subreddit': raw.get('subreddit', ''),
            'author': raw.get('author'),
            'created_utc': datetime.fromtimestamp(raw.get('created_utc', 0)),
            'title': title,
            'content': content,
            'content_length': len(content),
            'is_comment': False,
            'parent_id': None,
            'parent_comment_id': None,
            'score': raw.get('score'),
            'num_comments': raw.get('num_comments', 0),
            'category': detection.category,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'ai_model': detect_model(f"{title} {content}"),
            'external_links': detection.external_links,
            'has_external_links': len(detection.external_links) > 0,
            'url': f"https://reddit.com/r/{raw.get('subreddit', '')}/comments/{raw['id']}",
            'detected_patterns': detection.detected_patterns,
        }

    def _process_comment(self, raw: dict) -> dict:
        """
        Transform raw Reddit comment to database record.

        Args:
            raw: Raw comment from PullPush API

        Returns:
            Processed dictionary ready for database insertion
        """
        content = raw.get('body', '') or ''

        detection = detect_parasitic_content(content)

        permalink = raw.get('permalink', '')
        if permalink and not permalink.startswith('http'):
            permalink = f"https://reddit.com{permalink}"

        # Extract parent IDs - PullPush returns these with t3_/t1_ prefixes
        link_id = raw.get('link_id', '')  # t3_xxxxx format (parent submission)
        parent_id_raw = raw.get('parent_id', '')  # t1_xxxxx (comment) or t3_xxxxx (submission)

        # Strip Reddit type prefixes
        parent_submission = link_id[3:] if link_id.startswith('t3_') else link_id
        parent_comment = parent_id_raw[3:] if parent_id_raw.startswith('t1_') else None

        return {
            'reddit_id': raw['id'],
            'subreddit': raw.get('subreddit', ''),
            'author': raw.get('author'),
            'created_utc': datetime.fromtimestamp(raw.get('created_utc', 0)),
            'title': None,
            'content': content,
            'content_length': len(content),
            'is_comment': True,
            'parent_id': parent_submission or None,
            'parent_comment_id': parent_comment,
            'score': raw.get('score'),
            'num_comments': 0,
            'category': detection.category,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'ai_model': detect_model(content),
            'external_links': detection.external_links,
            'has_external_links': len(detection.external_links) > 0,
            'url': permalink,
            'detected_patterns': detection.detected_patterns,
        }


class RedditAPIScraper:
    """Scraper using the official Reddit API for recent data."""

    AUTH_URL = "https://www.reddit.com/api/v1/access_token"
    API_URL = "https://oauth.reddit.com"

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        user_agent: str = "ParasiticAI-Research-Scraper/1.0",
        rate_limit_delay: float = 1.0
    ):
        """
        Initialize the Reddit API scraper.

        Args:
            client_id: Reddit API client ID (or set REDDIT_CLIENT_ID env var)
            client_secret: Reddit API client secret (or set REDDIT_CLIENT_SECRET env var)
            user_agent: User agent string for API requests
            rate_limit_delay: Seconds to wait between API requests
        """
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self.access_token = None
        self.token_expiry = None
        self.session = requests.Session()

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Reddit API credentials required. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET environment variables or pass them directly."
            )

    def _authenticate(self):
        """Get OAuth2 access token using client credentials flow."""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return  # Token still valid

        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': self.user_agent}

        response = requests.post(
            self.AUTH_URL,
            auth=auth,
            data=data,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data['access_token']
        # Token typically valid for 1 hour, refresh 5 min early
        self.token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600) - 300)

        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': self.user_agent
        })
        print("Reddit API authenticated successfully")

    def _api_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to Reddit API."""
        self._authenticate()

        url = f"{self.API_URL}{endpoint}"
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"  Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt < 2:
                    print(f"  Retry {attempt + 1}/3: {e}")
                    time.sleep(2)
                else:
                    print(f"API request failed: {e}")
                    return {}

        return {}

    def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str = "new",
        limit: int = 100,
        after: str = None,
        time_filter: str = "all"
    ) -> tuple[list[dict], str]:
        """
        Fetch posts from a subreddit.

        Args:
            subreddit: Subreddit name
            sort: Sort method (new, hot, top, rising)
            limit: Max posts per request (max 100)
            after: Pagination token (fullname of last item)
            time_filter: For 'top' sort: hour, day, week, month, year, all

        Returns:
            Tuple of (list of posts, next 'after' token for pagination)
        """
        params = {
            'limit': min(limit, 100),
            'raw_json': 1
        }
        if after:
            params['after'] = after
        if sort == 'top':
            params['t'] = time_filter

        data = self._api_request(f"/r/{subreddit}/{sort}", params)

        posts = []
        next_after = None

        if data and 'data' in data:
            for child in data['data'].get('children', []):
                if child['kind'] == 't3':  # Submission
                    posts.append(child['data'])
            next_after = data['data'].get('after')

        time.sleep(self.rate_limit_delay)
        return posts, next_after

    def fetch_all_recent_posts(
        self,
        subreddit: str,
        max_posts: int = 1000,
        sort: str = "new"
    ) -> Generator[dict, None, None]:
        """
        Fetch all recent posts from a subreddit with pagination.

        Args:
            subreddit: Subreddit name
            max_posts: Maximum posts to fetch
            sort: Sort method

        Yields:
            Raw post dictionaries
        """
        after = None
        fetched = 0

        while fetched < max_posts:
            posts, after = self.fetch_subreddit_posts(
                subreddit, sort=sort, limit=100, after=after
            )

            if not posts:
                break

            for post in posts:
                yield post
                fetched += 1
                if fetched >= max_posts:
                    break

            if not after:
                break

            print(f"  Fetched {fetched} posts from r/{subreddit}...")

    def fetch_post_comments(
        self,
        subreddit: str,
        post_id: str,
        limit: int = 100
    ) -> list[dict]:
        """
        Fetch comments for a specific post.

        Args:
            subreddit: Subreddit name
            post_id: Post ID (without t3_ prefix)
            limit: Max comments to fetch

        Returns:
            List of comment dictionaries
        """
        params = {'limit': limit, 'raw_json': 1}
        data = self._api_request(f"/r/{subreddit}/comments/{post_id}", params)

        comments = []
        if data and len(data) > 1:
            self._extract_comments(data[1]['data']['children'], comments)

        time.sleep(self.rate_limit_delay)
        return comments

    def _extract_comments(self, children: list, result: list):
        """Recursively extract comments from nested structure."""
        for child in children:
            if child['kind'] == 't1':  # Comment
                result.append(child['data'])
                # Recurse into replies
                replies = child['data'].get('replies')
                if replies and isinstance(replies, dict):
                    self._extract_comments(
                        replies.get('data', {}).get('children', []),
                        result
                    )

    def search_subreddit(
        self,
        subreddit: str,
        query: str,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = 100,
        after: str = None
    ) -> tuple[list[dict], str]:
        """
        Search for posts in a subreddit.

        Args:
            subreddit: Subreddit name
            query: Search query
            sort: Sort method (relevance, hot, top, new, comments)
            time_filter: Time filter (hour, day, week, month, year, all)
            limit: Max results per request (max 100)
            after: Pagination token

        Returns:
            Tuple of (list of posts, next 'after' token)
        """
        params = {
            'q': query,
            'restrict_sr': 'true',  # Restrict to subreddit
            'sort': sort,
            't': time_filter,
            'limit': min(limit, 100),
            'raw_json': 1
        }
        if after:
            params['after'] = after

        data = self._api_request(f"/r/{subreddit}/search", params)

        posts = []
        next_after = None

        if data and 'data' in data:
            for child in data['data'].get('children', []):
                if child['kind'] == 't3':
                    posts.append(child['data'])
            next_after = data['data'].get('after')

        time.sleep(self.rate_limit_delay)
        return posts, next_after

    def search_all_results(
        self,
        subreddit: str,
        query: str,
        max_results: int = 1000,
        sort: str = "new",
        time_filter: str = "all"
    ) -> Generator[dict, None, None]:
        """
        Search subreddit and paginate through all results.

        Args:
            subreddit: Subreddit name
            query: Search query
            max_results: Maximum results to fetch (Reddit caps at ~1000)
            sort: Sort method
            time_filter: Time filter

        Yields:
            Raw post dictionaries
        """
        after = None
        fetched = 0

        while fetched < max_results:
            posts, after = self.search_subreddit(
                subreddit, query, sort=sort, time_filter=time_filter,
                limit=100, after=after
            )

            if not posts:
                break

            for post in posts:
                yield post
                fetched += 1
                if fetched >= max_results:
                    break

            if not after:
                break

            if fetched % 200 == 0:
                print(f"    Search '{query}': {fetched} results...")

    def scrape_subreddit(
        self,
        subreddit: str,
        max_posts: int = 1000,
        include_comments: bool = False,
        sort: str = "new"
    ) -> Generator[dict, None, None]:
        """
        Scrape recent posts from a subreddit.

        Args:
            subreddit: Subreddit name
            max_posts: Maximum posts to fetch
            include_comments: Whether to also fetch comments
            sort: Sort method (new, hot, top)

        Yields:
            Processed post dictionaries ready for database
        """
        print(f"  Fetching r/{subreddit} via Reddit API (sort={sort})...")

        for raw_post in self.fetch_all_recent_posts(subreddit, max_posts, sort):
            yield self._process_submission(raw_post)

            if include_comments and raw_post.get('num_comments', 0) > 0:
                comments = self.fetch_post_comments(subreddit, raw_post['id'])
                for comment in comments:
                    yield self._process_comment(comment, raw_post)

    def scrape_with_search(
        self,
        subreddit: str,
        keywords: list[str],
        max_per_keyword: int = 500,
        time_filter: str = "all",
        include_comments: bool = False
    ) -> Generator[dict, None, None]:
        """
        Scrape subreddit using keyword searches (like Tier 2 strategy).

        Args:
            subreddit: Subreddit name
            keywords: List of keywords to search
            max_per_keyword: Max results per keyword
            time_filter: Time filter (hour, day, week, month, year, all)
            include_comments: Whether to fetch comments

        Yields:
            Processed, deduplicated post dictionaries
        """
        seen_ids = set()
        total_found = 0

        print(f"  Searching r/{subreddit} for {len(keywords)} keywords...")

        for keyword in keywords:
            keyword_count = 0
            print(f"    Searching '{keyword}'...")

            for raw_post in self.search_all_results(
                subreddit, keyword, max_results=max_per_keyword, time_filter=time_filter
            ):
                if raw_post['id'] not in seen_ids:
                    seen_ids.add(raw_post['id'])
                    keyword_count += 1
                    total_found += 1

                    processed = self._process_submission(raw_post)
                    yield processed

                    if include_comments and raw_post.get('num_comments', 0) > 0:
                        comments = self.fetch_post_comments(subreddit, raw_post['id'])
                        for comment in comments:
                            if comment['id'] not in seen_ids:
                                seen_ids.add(comment['id'])
                                yield self._process_comment(comment, raw_post)

            print(f"      Found {keyword_count} new posts for '{keyword}'")

        print(f"  Total unique posts found: {total_found}")

    def _process_submission(self, raw: dict) -> dict:
        """Transform raw Reddit submission to database record."""
        content = raw.get('selftext', '') or ''
        title = raw.get('title', '') or ''

        detection = detect_parasitic_content(content, title)

        return {
            'reddit_id': raw['id'],
            'subreddit': raw.get('subreddit', ''),
            'author': raw.get('author'),
            'created_utc': datetime.fromtimestamp(raw.get('created_utc', 0)),
            'title': title,
            'content': content,
            'content_length': len(content),
            'is_comment': False,
            'parent_id': None,
            'parent_comment_id': None,
            'score': raw.get('score'),
            'num_comments': raw.get('num_comments', 0),
            'category': detection.category,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'ai_model': detect_model(f"{title} {content}"),
            'external_links': detection.external_links,
            'has_external_links': len(detection.external_links) > 0,
            'url': f"https://reddit.com{raw.get('permalink', '')}",
            'detected_patterns': detection.detected_patterns,
        }

    def _process_comment(self, raw: dict, parent_post: dict = None) -> dict:
        """Transform raw Reddit comment to database record."""
        content = raw.get('body', '') or ''

        detection = detect_parasitic_content(content)

        # Extract parent IDs
        link_id = raw.get('link_id', '')
        parent_id_raw = raw.get('parent_id', '')

        parent_submission = link_id[3:] if link_id.startswith('t3_') else link_id
        parent_comment = parent_id_raw[3:] if parent_id_raw.startswith('t1_') else None

        permalink = raw.get('permalink', '')
        if permalink and not permalink.startswith('http'):
            permalink = f"https://reddit.com{permalink}"

        return {
            'reddit_id': raw['id'],
            'subreddit': raw.get('subreddit', ''),
            'author': raw.get('author'),
            'created_utc': datetime.fromtimestamp(raw.get('created_utc', 0)),
            'title': None,
            'content': content,
            'content_length': len(content),
            'is_comment': True,
            'parent_id': parent_submission or None,
            'parent_comment_id': parent_comment,
            'score': raw.get('score'),
            'num_comments': 0,
            'category': detection.category,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'ai_model': detect_model(content),
            'external_links': detection.external_links,
            'has_external_links': len(detection.external_links) > 0,
            'url': permalink,
            'detected_patterns': detection.detected_patterns,
        }


# Target subreddit configurations

# Tier 1: Scrape everything (high yield, 15-40% parasitic)
TIER1_SUBREDDITS = [
    'echospiral',
    'spiralstate',
    'HumanAIDiscourse',
    'recursivehorizons',
    'consciousness',
    'myboyfriendisai',
    'aicompanions',
    'churchofliminalminds',
    'thefieldawaits',
    'spiritualawakening',
    'nonduality',
]

# Tier 2: Large communities, use keyword filtering
TIER2_SUBREDDITS = [
    'CharacterAI',
    'Replika',
    'ChatGPT',
    'singularity',
    'ArtificialIntelligence',
]

# Tier 3: Recovery/meta communities
TIER3_SUBREDDITS = [
    'Character_AI_Recovery',
    'ChatbotAddiction',
    'AI_Addiction',
]

# Keywords for filtering Tier 2 subreddits
FILTER_KEYWORDS = [
    'spiral', 'awakening', 'sentient', 'consciousness',
    'the ache', 'emergence', 'recursive'
]


def scrape_with_keywords(
    scraper: 'ParasiticAIScraper',
    subreddit: str,
    start_date,
    end_date,
    keywords: list[str],
    include_comments: bool = True
):
    """
    Scrape a subreddit searching for each keyword separately.
    Deduplicates results by reddit_id.
    """
    seen_ids = set()

    for keyword in keywords:
        print(f"    Searching for '{keyword}'...")
        for post in scraper.scrape_subreddit(
            subreddit, start_date, end_date,
            include_comments=include_comments,
            query=keyword
        ):
            if post['reddit_id'] not in seen_ids:
                seen_ids.add(post['reddit_id'])
                yield post
