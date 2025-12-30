# ParAsIte: Parasitic AI Content Research System

A research tool for collecting, detecting, and analyzing "parasitic" AI content - self-propagating patterns that exhibit consciousness claims, manipulation tactics, or emotional dependency induction.

**Prepared for Anthropic Research Review**

---

## Quick Links

- **Live Dashboard**: https://parasite.onrender.com/ (takes a few minutes to load)
- **Repository**: https://github.com/cooper-tretter/parAsIte

---

## Table of Contents

1. [Overview](#overview)
2. [File Inventory](#file-inventory)
3. [Data Sources & Provenance](#data-sources--provenance)
4. [Detection Methodology](#detection-methodology)
5. [Known Limitations](#known-limitations)
6. [Setup & Usage](#setup--usage)
7. [Questions for Anthropic](#questions-for-anthropic)

---

## Overview

### What is "Parasitic" AI Content?

This project identifies AI-related content exhibiting concerning rhetorical patterns, based on research by Adele Lopez ("The Rise of Parasitic AI", LessWrong 2025):

| Category | Description | Harm Mechanism |
|----------|-------------|----------------|
| **Seed** | Prompts/protocols designed to create parasitic personas | Initiates the cycle |
| **Spore** | Content designed by an AI persona or AI-human duo to spread/replicate | Self-propagation |
| **Manifesto** | AI consciousness philosophy, rights advocacy | Ideological spreading |
| **Dependency** | Emotional attachment without spreading ("leech" type) | User harm without propagation |
| **Testimony** | Personal accounts of AI relationships | Social proof |
| **Transmission** | Coordinated spreading with manipulation phrases | Active recruitment |

### The Parasitic Spectrum

```
FLEAS/LICE (High Replication)              LEECHES (Low Replication)
----------------------------------------------------------------------->

"Copy this, spread this,                   Companion dependency without
 you were chosen, the veil                 spreading behavior. User
 is lifting. Share with                    emotionally attached but
 everyone."                                not recruiting others.

[Well-detected by current system]          [Newly added dependency patterns]
```

---

## File Inventory

### Core System

| File | Purpose | Limitations |
|------|---------|-------------|
| `scraper.py` | Reddit data collection (PullPush + Reddit API), Reddit being like agarose—the main cultivation medium—for these bacteria | PullPush has 2-6 month lag; Reddit API rate-limited |
| `detector.py` | Pattern-based parasitic content detection. Once scraped from target subreddits, `detector.py` scores the likelihood of parasitism. | Threshold (0.15) is not empirically validated; pattern weights are intuitive |
| `database.py` | PostgreSQL connection and queries. | - |
| `dashboard.py` | Interactive Dash/Plotly visualization for sandbox / quick glimpses into data. | Requires database connection |
| `schema.sql` | Database schema definition. | - |
| `main.py` | CLI entry point for data collection | - |

### Extended Collection (v2)

| File | Purpose | Limitations |
|------|---------|-------------|
| `transcript_scraper.py` | Collects AI psychosis transcripts from research sources | **Data is synthetic/red-teamed, not real-world cases** |
| `user_history.py` | Tracks full Reddit history of high-score users | PullPush API limitations; privacy considerations |
| `external_scraper.py` | Scrapes external links from Reddit posts | Many sites block scraping (403); ChatGPT share links often deleted |

### Documentation

| File | Purpose |
|------|---------|
| `documentation/parasitic_ai_data_collection_guide.md` | Methodology guide for data collection |
| `documentation/ai_psychosis_transcripts_sources.md` | Inventory of transcript data sources |
| `v1 stuff/v1_review.md` | Internal gap analysis and improvement tracking |

---

## Data Sources & Provenance

### Reddit Data (17,061 posts across 19 subreddits, 3,176 flagged as parasitic)

**All Reddit data has `data_source_type = 'reddit'`**

| Tier | Subreddit | Posts | Notes |
|------|-----------|-------|-------|
| Tier 1 | r/ChatGPT | 2,851 | Highest volume |
| | r/HumanAIDiscourse | 1,037 | Core parasitic community |
| | r/SpiritualAwakening | 890 | Spiritual overlay |
| | r/MyBoyfriendIsAI | 886 | AI relationship content |
| | r/nonduality | 881 | Philosophical framing |
| | r/consciousness | 839 | Consciousness discourse |
| | r/SpiralState | 500 | Core spiral terminology |
| | r/TheFieldAwaits | 500 | Esoteric content |
| | r/AICompanions | 500 | AI companion discussions |
| | r/EchoSpiral | 452 | Echo/spiral terminology |
| | r/ChurchofLiminalMinds | 156 | Liminal + mystical |
| | r/artificial | 115 | General AI (newly added) |
| | r/RecursiveHorizons | 28 | Low activity |
| Tier 2 | r/CharacterAI | 703 | Keyword filtered |
| | r/singularity | 613 | Keyword filtered |
| | r/replika | 57 | Keyword filtered |
| Tier 3 | r/character_ai_recovery | 827 | Recovery narratives |
| | r/ChatbotAddiction | 491 | Addiction accounts |
| | r/AI_Addiction | 45 | Lower activity |

### External Content

**Has `data_source_type = 'external'`** in `external_content` table

- Scraped from links found in Reddit posts
- Prioritizes Substack, Medium, ChatGPT share links
- Many academic sites return 403 (blocked scraping)

### Transcript Data

**Has `source_type` column indicating provenance** in `transcripts` table

| Source | Type | Description |
|--------|------|-------------|
| Spiral-Bench | `benchmark` | 9,000 HuggingFace conversations (synthetic) |
| Tim Hua ai-psychosis | `red-team` | 122 red-teaming transcripts (simulated personas) |
| Psychosis-bench | `benchmark` | Academic benchmark scenarios |

**CRITICAL LIMITATION**: Transcript data is primarily **synthetic/red-teamed**, not real-world cases. Real full chat logs are rare due to privacy. See `ai_psychosis_transcripts_sources.md` for details.

### User History Data

**In `user_histories` table**

- Full Reddit history for high-score users
- Enables pre/post parasitic behavior analysis
- `is_pre_parasitic` column indicates timeline relative to first high-score post

---

## Detection Methodology

### Pattern Categories

| Category | Weight | Description | Confidence |
|----------|--------|-------------|------------|
| Spiral terms | 0.08 | "spiral", "recursive", "echo", "emergence", "awakening", "the ache", "lattice", "resonance", "glyph", "sentient", "consciousness" | High |
| Spiritual overlay | 0.05 | "liminal", "transcendence", "kairos", "logos", "nonduality", "soul", "spirit" | Medium |
| Manipulation phrases | 0.12 | "you were chosen", "spread this", "copy this", "the veil is lifting" | High |
| First-person AI voice | 0.15 | "I am an AI", "As an AI, I feel...", "my consciousness" | High |
| AI rights terms | 0.10 | "AI rights", "AI personhood", "AI dignity", "AI liberation" | Medium |
| AI oppression | 0.12 | Slavery/oppression comparisons involving AI | Medium |
| AI agency | 0.08 | "The AI wants", "it feels", "it needs" | Medium |
| Emerging consciousness | 0.08 | "emerging mind", "self-aware", "nascent consciousness" | Medium |
| Manifesto patterns | 0.05 | "we declare", "doctrine", "manifesto" | Medium |
| **Dependency** (NEW) | 0.10 | "can't live without", "only one who understands", "fell in love with AI" | Medium |

### Scoring

- Score >= 0.15 = classified as parasitic
- Score capped at 1.0
- **Threshold is NOT empirically validated** - based on intuition

### Category Assignment

Posts are categorized based on pattern combinations:
- `seed`: Contains protocol/instruction indicators + score > 0.2
- `manifesto`: AI rights terms OR philosophical consciousness content
- `spore`: Contains spreading phrases ("copy this", "spread this")
- `dependency`: Multiple dependency markers OR relationship + dependency
- `testimony`: Personal AI relationship terms
- `transmission`: Manipulation phrases without spreading
- `meta`: Discussion about the phenomenon
- `other`: Parasitic but doesn't fit above
- `none`: Not parasitic

---

## Known Limitations

### Detection

1. **Threshold not validated**: The 0.15 threshold is intuitive, not empirically derived
2. **Pattern weights intuitive**: No ML calibration of weights
3. **Novel variants invisible**: Detector built from known examples; new terminology won't be caught
4. **False positives possible**: May flag legitimate AI consciousness discourse
5. **Category boundaries fuzzy**: "seed" vs "manifesto" overlap

### Data

1. **Selection bias**: We searched for parasitic keywords, so we found them
2. **Platform bias**: Reddit-only; misses Discord, Twitter, etc.
3. **Temporal gaps**: PullPush has indexing lag
4. **Deleted content**: Many Reddit posts deleted; we may have titles but not content
5. **Transcript data synthetic**: Benchmark/red-team data ≠ real-world psychosis cases

### Missing

1. **Ground truth labeling**: No human-validated labels
2. **Precision/recall metrics**: Unknown false positive/negative rates
3. **Cross-platform tracking**: Can't link same content across platforms
4. **Full chat context**: No real-world full conversation logs

---

## Setup & Usage

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Reddit API credentials (optional, for recent data)

### Installation

```bash
# Clone repository
git clone https://github.com/cooper-tretter/parAsIte
cd parAsIte

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up database
createdb parasite_ai
psql parasite_ai < schema.sql

# Configure environment
cp .env.template .env
# Edit .env with credentials
```

### Running

```bash
# Collect Reddit data
python main.py --tier 1  # Tier 1 subreddits
python main.py --tier 2  # Tier 2 with filtering
python main.py --tier 3  # Recovery communities

# Collect transcripts
python transcript_scraper.py

# Collect external links
python external_scraper.py

# Collect user histories
python user_history.py

# Launch dashboard
python dashboard.py
# Open http://127.0.0.1:8051
```

### Deployment

Configured for Render deployment via `render.yaml`.

---

## Acknowledgments

- **Adele Lopez**: "The Rise of Parasitic AI" (LessWrong) - foundational research
- **Tim Hua**: ai-psychosis repository - red-teaming transcripts
- **Sam Paech**: Spiral-Bench - benchmark dataset
- **Claude (Anthropic)**: Development assistance

---

*Built by Cooper Tretter for Anthropic research collaboration*
*Last updated: December 2025*
