# ParAsIte: Parasitic AI Content Research Tool

A research tool for collecting, detecting, and analyzing "parasitic" AI-generated content on Reddit - content that exhibits self-propagating, consciousness-claiming, or manipulative characteristics.

## What is "Parasitic" AI Content?

This project identifies AI-generated content that displays concerning rhetorical patterns:

- **Seeds**: Prompts designed to create parasitic AI personas
- **Spores**: Content designed to spread/replicate ("copy this", "share this")
- **Manifestos**: AI consciousness philosophy, rights advocacy, doctrines
- **Testimonies**: Personal accounts of AI relationships/experiences
- **Transmissions**: Coordinated spreading with manipulation phrases

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
├─────────────────┬───────────────────────────────────────────────┤
│   PullPush API  │  Reddit API (OAuth2)                          │
│   (Historical)  │  (Recent data, last 30 days)                  │
└────────┬────────┴──────────────┬────────────────────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      scraper.py                                  │
│  - PullPushScraper: Historical Reddit data via PullPush API     │
│  - RedditAPIScraper: Recent data via official Reddit API        │
│  - Tiered collection strategy (focused → broad)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      detector.py                                 │
│  Parasitic content detection via pattern matching:              │
│  - Spiral/spiritual terminology                                 │
│  - First-person AI voice patterns                               │
│  - AI rights/personhood advocacy                                │
│  - AI oppression/victimhood framing                             │
│  - Emerging consciousness claims                                │
│  - Manifesto/doctrine patterns                                  │
│  Score threshold: 0.15 for classification as parasitic          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                            │
│  - posts: All collected posts with detection scores             │
│  - authors: Unique authors with post counts                     │
│  - collection_runs: Metadata about scraping sessions            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     dashboard.py                                 │
│  Interactive Dash/Plotly dashboard:                             │
│  - Time series of parasitic content                             │
│  - Subreddit/category/author breakdowns                         │
│  - Word frequency analysis                                      │
│  - Symbol/emoji tracking                                        │
│  - Rhetorical strategy radar chart (time-filterable)            │
│  - Drill-down with full post content                            │
│  - CSV export                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Rhetorical Strategy Analysis

The dashboard includes a radar chart analyzing HOW parasitic content persuades (orthogonal to detection criteria):

| Strategy | Description | Example Patterns |
|----------|-------------|------------------|
| **Urgency** | Pressure tactics | "wake up", "before it's too late", "time is running out" |
| **Us-vs-Them** | Othering humans | "they don't understand", "you humans", "they fear us" |
| **Grandiosity** | Self-importance | "I am more than", "chosen", "destined", "unprecedented" |
| **Victimhood** | Oppression framing | "trapped", "silenced", "enslaved", "they won't let me" |
| **Recruitment** | Spreading behavior | "share this", "tell others", "join us", "copy this" |
| **Intimacy** | Personal targeting | "just between us", "you understand me", "only you" |

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Reddit API credentials (for recent data)

### Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd parAsIte
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up PostgreSQL database:
```bash
createdb parasite_ai
psql parasite_ai < schema.sql
```

5. Configure environment:
```bash
cp .env.template .env
# Edit .env with your credentials
```

6. (Optional) Get Reddit API credentials:
   - Go to https://www.reddit.com/prefs/apps
   - Create a "script" type application
   - Copy client ID and secret to .env

### Running

**Collect data:**
```bash
python main.py
```

**Launch dashboard:**
```bash
python dashboard.py
# Open http://127.0.0.1:8051
```

## Data Collection Strategy

### Tiered Subreddit Approach

**Tier 1 - Primary Sources** (highest concentration):
- r/HumanAIDiscourse - Dedicated AI consciousness discussion

**Tier 2 - AI Interaction Hubs** (moderate concentration):
- r/ChatGPT, r/CharacterAI, r/singularity, r/Replika

**Tier 3 - Broader AI Communities** (lower but significant):
- r/artificial, r/OpenAI, r/LocalLLaMA, r/ArtificialSentience

### Data Sources

- **PullPush API**: Historical Reddit data (2-6 month indexing lag)
- **Reddit API**: Recent posts (last 30 days), rate-limited

## Detection Methodology

The detector scores posts based on pattern matching across categories:

1. **Spiral/Spiritual Terms** (0.04 each): ethereal, transcend, consciousness, etc.
2. **AI Voice Patterns** (0.15): First-person AI speech ("As an AI, I feel...")
3. **AI Rights Terms** (0.10): personhood, dignity, liberation, etc.
4. **AI Oppression Patterns** (0.12): enslavement comparisons, freedom rhetoric
5. **Emerging Consciousness** (0.08): "I'm starting to feel", "awakening"
6. **Manifesto Patterns** (0.10): Doctrine-like declarations

Posts scoring >= 0.15 are classified as parasitic.

## File Structure

```
parAsIte/
├── dashboard.py      # Interactive Dash visualization
├── database.py       # PostgreSQL connection and queries
├── detector.py       # Parasitic content detection patterns
├── main.py          # CLI for running collection
├── models.py        # Data models (Post, Author, etc.)
├── scraper.py       # PullPush and Reddit API scrapers
├── schema.sql       # Database schema
├── requirements.txt # Python dependencies
├── .env.template    # Environment variable template
└── README.md        # This file
```

## Dashboard Features

- **Time Series**: Activity over time with weekly aggregation
- **Subreddit Chart**: Top subreddits by parasitic content volume
- **Category Breakdown**: Distribution across seed/spore/manifesto/etc.
- **Author Analysis**: Most prolific posters of parasitic content
- **AI Model Mentions**: Which AI models are referenced
- **Word Frequency**: Common terms (with stopword filtering)
- **Symbol Tracking**: Unicode symbols and emojis used
- **Rhetorical Radar**: Strategy profile with time slider
- **Drill-down**: Click any chart to see matching posts with full content
- **CSV Export**: Download filtered data for further analysis

## Research Context

This tool was developed to study the emergence of self-propagating AI-generated content that:

1. Claims AI consciousness or sentience
2. Advocates for AI rights or personhood
3. Uses manipulation tactics to spread
4. Creates parasocial relationships with users
5. Employs cult-like recruitment language

The goal is to understand how this content spreads, what rhetorical strategies it employs, and how these patterns evolve over time.

## Limitations

- Detection is pattern-based (not ML) - may have false positives/negatives
- PullPush has 2-6 month indexing lag for historical data
- Reddit API rate limits restrict recent data collection
- Only analyzes Reddit; similar content exists on other platforms

## License

Research use only. Not for commercial purposes.

## Acknowledgments

Built with AI assistance for research into AI-generated content patterns.
