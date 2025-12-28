#!/usr/bin/env python3
"""
Parasitic AI Data Collection System - Main Entry Point

Usage:
    python main.py                      # Run full collection (Tier 1)
    python main.py --subreddit echospiral  # Single subreddit
    python main.py --tier 2             # Tier 2 with keyword filtering
    python main.py --init-db            # Initialize database schema only
"""

import argparse
from datetime import datetime
from dotenv import load_dotenv

from database import (
    get_connection,
    init_schema,
    insert_posts,
    start_collection_run,
    update_collection_run,
    update_author_stats,
    get_last_collection_time,
)
from scraper import (
    ParasiticAIScraper,
    TIER1_SUBREDDITS,
    TIER2_SUBREDDITS,
    TIER3_SUBREDDITS,
    FILTER_KEYWORDS,
    scrape_with_keywords,
)


# Load environment variables
load_dotenv()

# Default date range: Jan 2024 to present
DEFAULT_START = datetime(2024, 1, 1)
DEFAULT_END = datetime.now()


def collect_subreddit(
    conn,
    scraper: ParasiticAIScraper,
    subreddit: str,
    start_date: datetime,
    end_date: datetime,
    query: str = None,
    batch_size: int = 100
) -> dict:
    """
    Collect all content from a single subreddit.

    Args:
        conn: Database connection
        scraper: Initialized scraper instance
        subreddit: Subreddit name
        start_date: Start of collection range
        end_date: End of collection range
        query: Optional keyword filter
        batch_size: Number of posts per batch insert

    Returns:
        Stats dictionary with collection results
    """
    print(f"\n{'='*60}")
    print(f"Collecting r/{subreddit}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    if query:
        print(f"Keyword filter: {query}")
    print(f"{'='*60}")

    # Start collection run tracking
    run_id = start_collection_run(conn, subreddit)

    stats = {
        'posts_fetched': 0,
        'posts_stored': 0,
        'parasitic_found': 0,
        'authors_seen': set()
    }

    try:
        posts_batch = []

        for post in scraper.scrape_subreddit(
            subreddit, start_date, end_date, query=query
        ):
            stats['posts_fetched'] += 1

            if post.get('author'):
                stats['authors_seen'].add(post['author'])

            if post.get('is_parasitic'):
                stats['parasitic_found'] += 1

            posts_batch.append(post)

            # Batch insert
            if len(posts_batch) >= batch_size:
                stored = insert_posts(conn, posts_batch)
                stats['posts_stored'] += stored
                print(f"  Stored {stored}/{len(posts_batch)} posts (total: {stats['posts_stored']})")
                posts_batch = []

        # Insert remaining posts
        if posts_batch:
            stored = insert_posts(conn, posts_batch)
            stats['posts_stored'] += stored

        # Update author statistics
        print(f"  Updating stats for {len(stats['authors_seen'])} authors...")
        for author in stats['authors_seen']:
            if author and author != '[deleted]':
                update_author_stats(conn, author)

        # Mark run complete
        update_collection_run(
            conn, run_id,
            posts_fetched=stats['posts_fetched'],
            posts_stored=stats['posts_stored'],
            parasitic_found=stats['parasitic_found'],
            status='completed'
        )

        print(f"\nCompleted r/{subreddit}:")
        print(f"  Posts fetched: {stats['posts_fetched']}")
        print(f"  Posts stored: {stats['posts_stored']}")
        print(f"  Parasitic found: {stats['parasitic_found']}")

    except Exception as e:
        update_collection_run(
            conn, run_id,
            posts_fetched=stats['posts_fetched'],
            posts_stored=stats['posts_stored'],
            parasitic_found=stats['parasitic_found'],
            status='failed',
            error_message=str(e)
        )
        print(f"Error collecting r/{subreddit}: {e}")
        raise

    return stats


def collect_tier1(conn, scraper: ParasiticAIScraper, incremental: bool = False):
    """Collect all Tier 1 subreddits (no keyword filtering)."""
    print("\n" + "="*60)
    print("TIER 1 COLLECTION: High-yield subreddits")
    print("="*60)

    total_stats = {'fetched': 0, 'stored': 0, 'parasitic': 0}

    for subreddit in TIER1_SUBREDDITS:
        start_date = DEFAULT_START
        if incremental:
            last_time = get_last_collection_time(conn, subreddit)
            if last_time:
                start_date = last_time
                print(f"Resuming r/{subreddit} from {start_date}")

        stats = collect_subreddit(conn, scraper, subreddit, start_date, DEFAULT_END)
        total_stats['fetched'] += stats['posts_fetched']
        total_stats['stored'] += stats['posts_stored']
        total_stats['parasitic'] += stats['parasitic_found']

    print(f"\nTier 1 Complete:")
    print(f"  Total fetched: {total_stats['fetched']}")
    print(f"  Total stored: {total_stats['stored']}")
    print(f"  Total parasitic: {total_stats['parasitic']}")


def collect_tier2(conn, scraper: ParasiticAIScraper):
    """
    Collect Tier 2 subreddits - fetch ALL posts, filter locally.

    Strategy: No server-side keyword filtering (causes timeouts).
    Instead, fetch everything and only store posts with parasite_score > 0.
    """
    print("\n" + "="*60)
    print("TIER 2 COLLECTION: Large communities (local filtering)")
    print("="*60)

    total_stats = {'fetched': 0, 'stored': 0, 'parasitic': 0, 'skipped': 0}

    for subreddit in TIER2_SUBREDDITS:
        print(f"\n{'='*60}")
        print(f"Collecting r/{subreddit}")
        print(f"Date range: {DEFAULT_START.date()} to {DEFAULT_END.date()}")
        print(f"Strategy: Fetch all, filter locally (score > 0)")
        print(f"{'='*60}")

        run_id = start_collection_run(conn, subreddit)
        stats = {'posts_fetched': 0, 'posts_stored': 0, 'parasitic_found': 0,
                 'skipped': 0, 'authors_seen': set()}

        try:
            posts_batch = []

            # Fetch ALL posts (no query parameter), submissions only for speed
            for post in scraper.scrape_subreddit(
                subreddit, DEFAULT_START, DEFAULT_END,
                include_comments=False,  # Skip comments for speed
                query=None  # No server-side filtering
            ):
                stats['posts_fetched'] += 1

                # Only keep posts with any parasitic signal
                if post.get('parasite_score', 0) > 0:
                    if post.get('author'):
                        stats['authors_seen'].add(post['author'])
                    if post.get('is_parasitic'):
                        stats['parasitic_found'] += 1
                    posts_batch.append(post)
                else:
                    stats['skipped'] += 1

                if len(posts_batch) >= 100:
                    stored = insert_posts(conn, posts_batch)
                    stats['posts_stored'] += stored
                    print(f"  Stored {stored} posts (fetched: {stats['posts_fetched']}, skipped: {stats['skipped']})")
                    posts_batch = []

                # Progress indicator every 500 posts
                if stats['posts_fetched'] % 500 == 0:
                    print(f"  Progress: {stats['posts_fetched']} fetched, {stats['skipped']} skipped, {len(posts_batch)} pending")

            if posts_batch:
                stored = insert_posts(conn, posts_batch)
                stats['posts_stored'] += stored

            for author in stats['authors_seen']:
                if author and author != '[deleted]':
                    update_author_stats(conn, author)

            update_collection_run(conn, run_id, stats['posts_fetched'], stats['posts_stored'],
                                  stats['parasitic_found'], 'completed')

            print(f"\nCompleted r/{subreddit}:")
            print(f"  Posts fetched: {stats['posts_fetched']}")
            print(f"  Posts skipped (score=0): {stats['skipped']}")
            print(f"  Posts stored (score>0): {stats['posts_stored']}")
            print(f"  Parasitic (score>=0.15): {stats['parasitic_found']}")

        except Exception as e:
            update_collection_run(conn, run_id, stats['posts_fetched'], stats['posts_stored'],
                                  stats['parasitic_found'], 'failed', str(e))
            print(f"Error: {e}")

        total_stats['fetched'] += stats['posts_fetched']
        total_stats['stored'] += stats['posts_stored']
        total_stats['parasitic'] += stats['parasitic_found']
        total_stats['skipped'] += stats['skipped']

    print(f"\nTier 2 Complete:")
    print(f"  Total fetched: {total_stats['fetched']}")
    print(f"  Total skipped: {total_stats['skipped']}")
    print(f"  Total stored: {total_stats['stored']}")
    print(f"  Total parasitic: {total_stats['parasitic']}")


def collect_tier3(conn, scraper: ParasiticAIScraper):
    """Collect Tier 3 recovery/meta subreddits."""
    print("\n" + "="*60)
    print("TIER 3 COLLECTION: Recovery/meta communities")
    print("="*60)

    total_stats = {'fetched': 0, 'stored': 0, 'parasitic': 0}

    for subreddit in TIER3_SUBREDDITS:
        stats = collect_subreddit(conn, scraper, subreddit, DEFAULT_START, DEFAULT_END)
        total_stats['fetched'] += stats['posts_fetched']
        total_stats['stored'] += stats['posts_stored']
        total_stats['parasitic'] += stats['parasitic_found']

    print(f"\nTier 3 Complete:")
    print(f"  Total fetched: {total_stats['fetched']}")
    print(f"  Total stored: {total_stats['stored']}")
    print(f"  Total parasitic: {total_stats['parasitic']}")


def main():
    parser = argparse.ArgumentParser(
        description='Parasitic AI Data Collection System'
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize database schema and exit'
    )
    parser.add_argument(
        '--subreddit',
        type=str,
        help='Collect from a single subreddit'
    )
    parser.add_argument(
        '--tier',
        type=int,
        choices=[1, 2, 3],
        default=1,
        help='Subreddit tier to collect (default: 1)'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only fetch posts newer than last collection'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD), default: 2024-01-01'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD), default: today'
    )

    args = parser.parse_args()

    # Connect to database
    print("Connecting to database...")
    conn = get_connection()

    # Initialize schema if requested
    if args.init_db:
        init_schema(conn)
        conn.close()
        return

    # Always ensure schema exists
    init_schema(conn)

    # Parse custom dates if provided
    global DEFAULT_START, DEFAULT_END
    if args.start_date:
        DEFAULT_START = datetime.strptime(args.start_date, '%Y-%m-%d')
    if args.end_date:
        DEFAULT_END = datetime.strptime(args.end_date, '%Y-%m-%d')

    # Initialize scraper
    scraper = ParasiticAIScraper()

    try:
        if args.subreddit:
            # Single subreddit mode
            collect_subreddit(
                conn, scraper, args.subreddit,
                DEFAULT_START, DEFAULT_END
            )
        elif args.tier == 1:
            collect_tier1(conn, scraper, incremental=args.incremental)
        elif args.tier == 2:
            collect_tier2(conn, scraper)
        elif args.tier == 3:
            collect_tier3(conn, scraper)

    finally:
        conn.close()

    print("\nCollection complete.")


if __name__ == '__main__':
    main()
