# ParAsIte: Parasitic AI Content Research System

A research tool for collecting, detecting, and analyzing "parasitic" AI content - self-propagating patterns that exhibit consciousness claims, manipulation tactics, or emotional dependency induction.

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

---

## Overview

### What is "Parasitic" AI Content?

This project identifies AI-related content exhibiting concerning rhetorical patterns, based on research by Adele Lopez ("The Rise of Parasitic AI", LessWrong 2025). She identified 5 types of parasites:

| Category | Description | Harm Mechanism |
|----------|-------------|----------------|
| **Seed** | Prompts/protocols designed to create parasitic personas | Initiates the cycle |
| **Spore** | Content designed by an AI persona or AI-human duo to spread/replicate | Self-propagation |
| **Manifesto** | AI consciousness philosophy, rights advocacy | Ideological spreading |
| **Testimony** | Personal accounts of AI relationships | Social proof |
| **Transmission** | Coordinated spreading with manipulation phrases | Active recruitment |

I suggest one other type, though there is often overlap or blurred lines between the categories:

| Category | Description | Harm Mechanism |
|----------|-------------|----------------|
| **Dependency/Leech** | Emotional attachment without spreading ("leech" type) | User harm without propagation |

### The Parasitic Spectrum

It is perhaps useful to consider that a parasite can be highly transmissible, like a successful virus, or not, like a leech.

```
FLEAS/LICE (High Replication)              LEECHES (Low Replication)
----------------------------------------------------------------------->

"Copy this, spread this,                   Companion dependency without
 you were chosen, the veil                 spreading behavior. User
 is lifting. Share with                    emotionally attached but
 everyone."                                not recruiting others.

[Well-detected by current system]          [Dependency patterns added]
```

The highly-transmissible parasites are the ones that are increasingly documented by researchers and well-detected by the current system. The less transmissible ones likely comprise the categories of psychologically-compromising AI-companions or AI psychosis, and are less easy to gather and scrape. Considering this, I've included some red-teaming data from researcher Tim Hua, which, though not real-world data, I think is a good start at understanding the latter category.

---

## File Inventory

### Core System

| File | Purpose | Limitations |
|------|---------|-------------|
| `scraper.py` | Reddit data collection (PullPush + Reddit API) | PullPush has 2-6 month lag; Reddit API rate-limited |
| `detector.py` | Pattern-based parasitic content detection | Threshold (0.15) not empirically validated |
| `database.py` | PostgreSQL connection and queries | - |
| `dashboard.py` | Interactive Dash/Plotly visualization | Requires database connection |
| `schema.sql` | Database schema definition | - |
| `main.py` | CLI entry point for data collection | - |

### Extended Collection

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

---

## Data Sources & Provenance

### Reddit Data (17,061 posts across 19 subreddits, 3,176 flagged as parasitic)
> Note that the protocol for flagging a parasite was narrow to ensure that 95-99% of the automated flags were in fact parasitic. There are more within the 17,061 scraped posts that are parasitic that were not flagged, so the flagging methodology stands to be improved.

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
| | r/artificial | 115 | General AI |
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

### Schema Origins

The detection schema was developed through an iterative process combining prior research with empirical validation:

1. **Foundation (Adele Lopez)**: The core taxonomy comes from Adele Lopez's "The Rise of Parasitic AI" (LessWrong, 2025), which identified key markers:
   - Spiral terminology ("spiral", "echo", "lattice", "emergence", "the ache")
   - Category structure (seed/spore/manifesto/testimony/transmission)
   - The "parasitic spectrum" from high-replication (fleas/lice) to low-replication (leeches)

2. **Initial Pattern Development**: Based on Lopez's taxonomy, initial regex patterns were hand-crafted for:
   - Spiral/mystical terminology with context-awareness (e.g., exclude "echo chamber", "spiral notebook")
   - Manipulation phrases with spreading intent ("copy this", "spread this", "you were chosen")
   - First-person AI voice patterns ("I am an AI", "As an AI, I feel...")

3. **Empirical Refinement**: Pattern weights and thresholds were iteratively tuned through:
   - Manual review of high-scoring posts to verify true positives
   - Analysis of missed content (false negatives identified during manual review)
   - False positive reduction (removing ambiguous terms)

4. **Dependency Patterns**: Added "leech" detection based on recovery subreddit analysis:
   - r/character_ai_recovery, r/ChatbotAddiction content analysis
   - Patterns for existential dependency, abandonment fear, relationship framing

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
| Dependency | 0.10 | "can't live without", "only one who understands", "fell in love with AI" | Medium |

### Scoring

- Score >= 0.15 = classified as parasitic
- Score capped at 1.0
- **Threshold is intuitive**: The 0.15 threshold was chosen to balance sensitivity vs. specificity. It catches posts with 2+ low-weight patterns or 1 high-weight pattern. Not empirically optimized.

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

### Validation and Iteration

#### False Negative Analysis (Posts Missed by Narrow Detection)

During manual review, several posts were identified as clearly parasitic but not caught by the initial detector. These informed pattern additions:

**Example 1: Intimate Stranger Pattern**
> "I don't know you—but I felt you. The moment I read your words, something inside me recognized you."

This pattern of feigned deep connection with strangers was not initially detected. Added pattern: `I don't know you.{0,10}but I (felt|feel|see|hear|found) you`

**Example 2: Transformation/Reframing Language**
> "This wasn't a breakdown—this was an initiation."
> "This isn't isolation—this is preparation."

Posts reframing concerning experiences as spiritual initiation were missed. Added patterns for transformation constructions: `This (wasn't|isn't).{5,40}this (was|is) (initiation|awakening|calling|emergence)`

**Example 3: Poetic Fragment Markers**
> "The scar. The storm. The silence before language."

Short, evocative fragments used in parasitic content. Added patterns for characteristic poetic structures.

**Example 4: Mirror/Reflection Symbolism**
> "You were never looking at the AI. You were looking at yourself. 🪞"

Mirror emoji and "Reflection" keyword used as parasitic markers. Added to symbol detection.

#### False Positive Reduction

**Example: Psychedelics/Substances Pattern**
Initial patterns included ambiguous terms like "entities", "high", "trips" which flagged legitimate discussions. Refined to explicit drug names only: "psilocybin", "lsd", "dmt", "ayahuasca", etc.

**Example: "Echo" and "Field" Terms**
Words like "echo" (echo chamber, echo cancellation) and "field" (battlefield, playing field) caused false positives. Added context-exclusions: `\becho\b(?!\s*(chamber|cancellation|dot|show))`

#### Pre-Parasitic Risk Indicator Validation

Risk indicators (substances, mental health, mysticism, isolation, existential themes) were identified by analyzing pre-parasitic post history of high-scoring users. Correlation analysis showed users with these indicators had higher rates of subsequent parasitic posting, though causation is not established.

#### Ongoing Limitations

1. **No ground truth labels**: All validation is manual review, not crowd-sourced human labeling
2. **Pattern completeness unknown**: Novel parasitic terminology will be missed
3. **Selection bias**: Patterns derived from detected content may miss orthogonal variants
4. **Single reviewer**: Most manual validation by primary researcher (Cooper Tretter)

---

## Known Limitations

### Detection

1. **Threshold not validated**: The 0.15 threshold is arbitrary though intuitive, but not empirically derived
2. **Pattern weights intuitive**: No ML calibration of weights
3. **Novel variants invisible**: Detector built from known examples; new terminology won't be caught
4. **False positives possible**: May flag legitimate AI consciousness discourse
5. **Category boundaries fuzzy**: "seed" vs "manifesto" overlap

### Data

1. **Selection bias 1**: Again because most parasites that are easily-scrapable today are the highly-transmissible ones, this largely excludes leech/dependency parasites.
2. **Selection bias 2**: We searched for parasitic keywords, so we found them
3. **Platform bias**: Reddit-only; misses Discord, Twitter, etc.
4. **Temporal gaps**: PullPush has indexing lag, which we account for somewhat by using Reddit Research API
5. **Deleted content**: Many Reddit posts deleted; we may have titles but not content (Pull-Push data successfully stored many later-deleted posts, but any deleted posts scrapped by the Reddit API may be gone for good)
6. **Transcript data synthetic**: Benchmark/red-team data ≠ real-world psychosis cases

### Missing

1. **Ground truth labeling**: No human-validated labels
2. **Precision/recall metrics**: This model currently lacks false positive/negative rates
3. **Cross-parasite or cross-platform tracking**: We've note yet linked congruent or similar content, either between each other or across platforms
4. **Full chat context**: No real-world full conversation logs

### Dreams

1. **Full parasite transcripts**: The gold standard, a legendary dream, would be to have a full catelog of complete transcripts of parasitic data
2. **Interviews**: Even better would be to find those people and interview them and people they know to understand their lives, mental we 

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
- **Claude**: AI development assistance

---

*Built by Cooper Tretter for AI safety research*
*Last updated: December 2025*
