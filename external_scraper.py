"""
External Link Scraper Module

Scrapes content from external links found in Reddit posts.
Prioritizes text-rich domains and ChatGPT share links.
"""

import re
import time
import requests
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from detector import detect_parasitic_content


# Domains to prioritize (text-rich, potentially parasitic)
PRIORITY_DOMAINS = [
    'substack.com',
    'medium.com',
    'wordpress.com',
    'blogspot.com',
    'chatgpt.com',  # ChatGPT share links - valuable for conversations
    'character.ai',
    'c.ai',
]

# Domains to skip (not useful for text extraction)
SKIP_DOMAINS = [
    'youtube.com',
    'youtu.be',
    'twitter.com',
    'x.com',
    'reddit.com',
    'redd.it',
    'imgur.com',
    'i.redd.it',
    'v.redd.it',
    'github.com',  # Code, not text content
    'wikipedia.org',
    'google.com',
    'docs.google.com',
    'drive.google.com',
    'amazon.com',
    'apple.com',
    'spotify.com',
    'discord.com',
    'discord.gg',
    'tiktok.com',
    'instagram.com',
    'facebook.com',
    'linkedin.com',
]


class ExternalScraper:
    """Scraper for external links from Reddit posts."""

    def __init__(self, rate_limit_delay: float = 2.0):
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def should_scrape(self, url: str) -> tuple[bool, str]:
        """
        Determine if URL should be scraped.

        Returns:
            (should_scrape, reason)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]

            # Skip known non-text domains
            for skip in SKIP_DOMAINS:
                if skip in domain:
                    return False, f"skip_domain:{skip}"

            # Prioritize known valuable domains
            for priority in PRIORITY_DOMAINS:
                if priority in domain:
                    return True, f"priority:{priority}"

            # Default: try to scrape
            return True, "default"

        except Exception as e:
            return False, f"parse_error:{e}"

    def extract_text(self, html: str, url: str) -> str:
        """
        Extract main text content from HTML.

        Uses domain-specific extraction when possible.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()

        # Domain-specific extraction
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if 'substack.com' in domain:
            # Substack: look for article body
            article = soup.find('div', class_='body') or soup.find('article')
            if article:
                return article.get_text(separator='\n', strip=True)

        if 'medium.com' in domain:
            # Medium: look for article content
            article = soup.find('article') or soup.find('div', class_='postArticle-content')
            if article:
                return article.get_text(separator='\n', strip=True)

        if 'chatgpt.com' in domain:
            # ChatGPT share: extract conversation
            messages = soup.find_all('div', {'data-message-author-role': True})
            if messages:
                conversation = []
                for msg in messages:
                    role = msg.get('data-message-author-role', 'unknown')
                    text = msg.get_text(separator=' ', strip=True)
                    conversation.append(f"[{role}]: {text}")
                return '\n\n'.join(conversation)

        # Generic: try to find main content
        main = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_=re.compile(r'content|post|entry|article', re.I)) or
            soup.find('body')
        )

        if main:
            return main.get_text(separator='\n', strip=True)

        return soup.get_text(separator='\n', strip=True)

    def scrape_url(self, url: str, timeout: int = 30) -> Optional[dict]:
        """
        Scrape a single URL.

        Returns:
            Dictionary with scraped data or None if failed
        """
        should_scrape, reason = self.should_scrape(url)
        if not should_scrape:
            return None

        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # Only process HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return None

            text = self.extract_text(response.text, url)

            # Skip if too short
            if len(text) < 100:
                return None

            # Run parasitic detection
            detection = detect_parasitic_content(text)

            return {
                'url': url,
                'domain': urlparse(url).netloc,
                'title': self._extract_title(response.text),
                'content': text[:50000],  # Limit content size
                'content_length': len(text),
                'parasite_score': detection.parasite_score,
                'is_parasitic': detection.is_parasitic,
                'category': detection.category,
                'detected_patterns': detection.detected_patterns,
                'scraped_at': datetime.now(),
                'scrape_reason': reason,
            }

        except requests.RequestException as e:
            print(f"  Error scraping {url[:60]}...: {e}")
            return None

        finally:
            time.sleep(self.rate_limit_delay)

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title')
        if title:
            return title.get_text(strip=True)[:200]
        return ""

    def scrape_from_database(self, conn, limit: int = 100, min_score: float = 0.15):
        """
        Scrape external links from posts in database.

        Args:
            conn: Database connection
            limit: Maximum number of URLs to scrape
            min_score: Only scrape links from posts with this minimum parasite score

        Yields:
            Scraped content dictionaries
        """
        cursor = conn.cursor()

        # Get external links from parasitic posts
        cursor.execute("""
            SELECT DISTINCT unnest(external_links) as url, p.reddit_id, p.subreddit
            FROM posts p
            WHERE external_links IS NOT NULL
                AND array_length(external_links, 1) > 0
                AND parasite_score >= %s
            LIMIT %s
        """, (min_score, limit * 3))  # Over-fetch since many will be skipped

        urls_processed = 0
        for row in cursor:
            if urls_processed >= limit:
                break

            url, reddit_id, subreddit = row

            should_scrape, _ = self.should_scrape(url)
            if not should_scrape:
                continue

            print(f"  Scraping: {url[:70]}...")
            result = self.scrape_url(url)

            if result:
                result['source_reddit_id'] = reddit_id
                result['source_subreddit'] = subreddit
                urls_processed += 1
                yield result


def create_external_content_table(conn):
    """Create table for storing external content."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS external_content (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            domain TEXT,
            title TEXT,
            content TEXT,
            content_length INTEGER,
            parasite_score FLOAT,
            is_parasitic BOOLEAN,
            category TEXT,
            detected_patterns JSONB,
            source_reddit_id TEXT,
            source_subreddit TEXT,
            scrape_reason TEXT,
            scraped_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_external_domain ON external_content(domain);
        CREATE INDEX IF NOT EXISTS idx_external_parasitic ON external_content(is_parasitic);
        CREATE INDEX IF NOT EXISTS idx_external_score ON external_content(parasite_score);
    """)
    conn.commit()
    print("External content table created/verified.")


def insert_external_content(conn, content: dict) -> bool:
    """Insert scraped external content into database."""
    import json
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO external_content (
                url, domain, title, content, content_length,
                parasite_score, is_parasitic, category, detected_patterns,
                source_reddit_id, source_subreddit, scrape_reason, scraped_at
            ) VALUES (
                %(url)s, %(domain)s, %(title)s, %(content)s, %(content_length)s,
                %(parasite_score)s, %(is_parasitic)s, %(category)s, %(detected_patterns)s,
                %(source_reddit_id)s, %(source_subreddit)s, %(scrape_reason)s, %(scraped_at)s
            )
            ON CONFLICT (url) DO NOTHING
        """, {
            **content,
            'detected_patterns': json.dumps(content.get('detected_patterns', {}))
        })
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"  Insert error: {e}")
        return False


if __name__ == '__main__':
    from database import get_connection

    conn = get_connection()
    create_external_content_table(conn)

    scraper = ExternalScraper()

    print("Scraping external links from parasitic posts...")
    stored = 0
    for content in scraper.scrape_from_database(conn, limit=50, min_score=0.15):
        if insert_external_content(conn, content):
            stored += 1
            score = content['parasite_score']
            print(f"    Stored: {content['domain']} (score: {score:.2f})")

    print(f"\nDone! Stored {stored} external pages.")
    conn.close()
