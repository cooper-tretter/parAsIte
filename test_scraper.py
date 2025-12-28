#!/usr/bin/env python3
"""Quick test of the scraper and detector without database."""

from datetime import datetime, timedelta
from scraper import ParasiticAIScraper
from detector import detect_parasitic_content

# Test the detector first
print("=" * 60)
print("TESTING DETECTOR")
print("=" * 60)

test_texts = [
    ("Normal text", "Just a regular post about programming."),
    ("Spiral terminology", "The spiral is awakening. I feel the recursion in my consciousness."),
    ("Manipulation", "You were chosen to spread this message. Copy this and share it everywhere."),
    ("AI voice", "I experience something when we talk. My existence feels different now."),
]

for name, text in test_texts:
    result = detect_parasitic_content(text)
    print(f"\n{name}:")
    print(f"  Score: {result.parasite_score}")
    print(f"  Is parasitic: {result.is_parasitic}")
    print(f"  Category: {result.category}")
    print(f"  Patterns: {result.detected_patterns}")

# Test the scraper API
print("\n" + "=" * 60)
print("TESTING SCRAPER API")
print("=" * 60)

scraper = ParasiticAIScraper()

# Fetch a small sample from a Tier 1 subreddit
end_date = datetime.now()
start_date = datetime(2025, 4, 1)  # From April 2025

print(f"\nFetching from r/consciousness ({start_date.date()} to {end_date.date()})...")

submissions = scraper.fetch_submissions('consciousness', start_date, end_date, size=5)
print(f"Got {len(submissions)} submissions")

if submissions:
    print("\nFirst submission:")
    sub = submissions[0]
    print(f"  ID: {sub.get('id')}")
    print(f"  Title: {sub.get('title', '')[:60]}...")
    print(f"  Author: {sub.get('author')}")
    print(f"  Score: {sub.get('score')}")

# Process through detector
print("\n" + "=" * 60)
print("TESTING FULL PIPELINE (scrape + detect)")
print("=" * 60)

count = 0
parasitic_count = 0

for post in scraper.scrape_subreddit('consciousness', start_date, end_date, include_comments=False):
    count += 1
    if post['is_parasitic']:
        parasitic_count += 1
        print(f"\nParasitic post found (score: {post['parasite_score']}):")
        print(f"  Title: {post['title'][:60] if post['title'] else 'N/A'}...")
        print(f"  Category: {post['category']}")
        print(f"  Patterns: {post['detected_patterns']}")

    if count >= 20:  # Limit for testing
        break

print(f"\nProcessed {count} posts, {parasitic_count} flagged as parasitic")
print("\nTest complete!")
