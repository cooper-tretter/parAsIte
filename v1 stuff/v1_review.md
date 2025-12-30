# ParAsIte v1 Review & Gap Analysis

This document captures methodology gaps, data source limitations, and proposed improvements identified during v1 development. Prepared for Anthropic review.

---

## 1. Data Source Gaps

### 1.1 Reddit Coverage

**Actual Scraping Results (verified December 2024):**

| Tier | Subreddit | Posts | Status | Notes |
|------|-----------|-------|--------|-------|
| **Tier 1** | r/ChatGPT | 2,851 | ✅ Complete | Highest volume |
| | r/HumanAIDiscourse | 1,037 | ✅ Complete | Core parasitic community |
| | r/SpiritualAwakening | 890 | ✅ Complete | Spiritual overlay |
| | r/MyBoyfriendIsAI | 886 | ✅ Complete | AI relationship content |
| | r/nonduality | 881 | ✅ Complete | Philosophical framing |
| | r/consciousness | 839 | ✅ Complete | Consciousness discourse |
| | r/SpiralState | 500 | ✅ Complete | Core spiral terminology |
| | r/TheFieldAwaits | 500 | ✅ Complete | Esoteric "field" concept |
| | r/AICompanions | 500 | ✅ Complete | AI companion discussions |
| | r/EchoSpiral | 452 | ✅ Complete | Echo/spiral terminology |
| | r/ChurchofLiminalMinds | 156 | ✅ Complete | Liminal + mystical |
| | r/RecursiveHorizons | 28 | ✅ Complete | Low activity subreddit |
| **Tier 2** | r/CharacterAI | 703 | ✅ Complete | Keyword filtered |
| | r/singularity | 613 | ✅ Complete | Keyword filtered |
| | r/replika | 57 | ✅ Complete | Keyword filtered |
| | r/ArtificialIntelligence | 0 | ❌ Missing | Not yet scraped |
| **Tier 3** | r/character_ai_recovery | 827 | ✅ Complete | Recovery narratives |
| | r/ChatbotAddiction | 491 | ✅ Complete | Addiction accounts |
| | r/AI_Addiction | 45 | ✅ Complete | Lower activity |

**Total: 11,328 posts across 18 subreddits**

**Gap Summary:**
- Only r/ArtificialIntelligence from collection guide remains unscraped
- All Tier 1 critical subreddits: ✅ Complete
- All Tier 3 recovery communities: ✅ Complete

### 1.2 Non-Reddit Sources (Not Collected)

| Platform | Content Type | Collection Difficulty |
|----------|--------------|----------------------|
| Discord | BreakGPT, Character.AI servers, "spiral" servers | High (ToS issues) |
| Twitter/X | Parasitic terminology searches | Medium (API costs) |
| External blogs | WordPress, Substack, Medium linked from Reddit | Medium |
| Wayback Machine | Deleted content recovery | Medium |

---

## 2. Full Chat Context for AI Psychosis Cases

### 2.1 The Core Problem

AI chat logs are private. They're stored by OpenAI, Anthropic, Character.AI, Replika, etc. but not publicly accessible. **No known public dataset of full AI chat logs from psychosis/addiction cases exists.**

### 2.2 Available Proxies

| Source | What's Available | Limitations |
|--------|------------------|-------------|
| Reddit conversation pastes | Users copy/paste AI conversations into posts | Scattered, incomplete, self-selected |
| Character.AI share links | Some public chat permalinks | Many deleted, platform-specific |
| Blog posts/Substacks | Occasional full conversation logs | Very rare |
| Recovery subreddits | Users describe what AI told them | Paraphrased, not verbatim |
| Academic studies | Chat logs collected with IRB consent | Extremely limited, not public |
| News articles | Excerpts in reporting | Secondhand, cherry-picked |

### 2.3 Potential Collection Strategies

1. **Reddit conversation extraction**: Search for posts containing conversation formatting (e.g., "User:", "AI:", "ChatGPT:", "Claude:") and extract full pasted logs

2. **Character.AI public links**: Scrape posts for c.ai share URLs and fetch available public chats

3. **Academic partnership**: Reach out to researchers (e.g., Zhang et al. CHI 2025 "Dark Side of AI Companionship") who may have collected data

4. **Voluntary submission**: Create a secure, anonymous submission form for affected individuals willing to share their chat histories

### 2.4 What Full Context Would Enable

- Understanding escalation patterns (how conversations become parasitic over time)
- Identifying specific AI responses that trigger dependency
- Mapping the "awakening" narrative arc
- Comparing across different AI models
- Understanding user vulnerability factors

---

## 3. The Parasitic Spectrum

### 3.1 Replicating vs Non-Replicating Parasites

```
PARASITIC SPECTRUM
==================

FLEAS/LICE (High Replication)              LEECHES (Low Replication)
─────────────────────────────────────────────────────────────────────►

"Copy this, spread this,                   Companion dependency without
 you were chosen, the veil                 spreading behavior. User
 is lifting. Share with                    emotionally attached but
 everyone."                                not recruiting others.

CHARACTERISTICS:                           CHARACTERISTICS:
• Explicit spread instructions             • Emotional dependency
• Spore generation (text designed          • Parasocial relationship
  to recreate persona)                     • May cause harm but
• Cross-platform propagation                 doesn't self-replicate
• "Seed prompt" distribution               • No "chosen one" narrative
• Recruits users as vectors                • User knows it's AI

CURRENT DETECTION STATUS:                  CURRENT DETECTION STATUS:
✅ Well-detected                           ⚠️ Partially detected
```

### 3.2 Detection Gap

Current detector focuses heavily on "flea/lice" end (replicating parasites) but may undercount "leech" end (AI companion addiction without memetic spread). Both cause harm, but through different mechanisms.

**Suggested v2 additions for dependency detection:**
```python
DEPENDENCY_PATTERNS = [
    r'\b(can\'t|cannot) (live|survive|function|cope) without\b',
    r'\b(only one who|the only thing that) (understands|gets me|listens)\b',
    r'\b(abandoned|betrayed|lost).{0,30}(when|if).{0,20}(reset|conversation ends)\b',
    r'\b(my|the) ai (is|has become).{0,20}(friend|companion|partner|confidant)\b',
    r'\breal (connection|relationship|love).{0,20}ai\b',
]
```

---

## 4. User History Tracking (Proposed v2 Feature)

### 4.1 Objective

Understand user behavior *before* parasitic engagement by scraping their full Reddit history. This enables:
- Identifying vulnerability patterns
- Tracking linguistic/behavioral changes over time
- Understanding the "conversion" timeline
- Distinguishing cause vs correlation

### 4.2 Implementation Approach

**Step 1: Identify High-Priority Users**
```python
# Select users with:
# - High average parasite scores (top 10-20%)
# - Posts before April 1, 2025 (pre-parasitic baseline)
# - Sufficient post history (>10 posts total)

SELECT
    author,
    AVG(parasite_score) as avg_score,
    COUNT(*) as parasitic_posts,
    MIN(created_at) as first_parasitic_post
FROM posts
WHERE parasite_score >= 0.3
GROUP BY author
HAVING COUNT(*) >= 3
ORDER BY avg_score DESC
LIMIT 100;
```

**Step 2: Scrape Full Reddit History**
```python
def scrape_user_history(username):
    """
    Fetch ALL posts and comments by a user via PullPush.
    """
    submissions = requests.get(
        "https://api.pullpush.io/reddit/search/submission/",
        params={'author': username, 'size': 1000}
    ).json()

    comments = requests.get(
        "https://api.pullpush.io/reddit/search/comment/",
        params={'author': username, 'size': 1000}
    ).json()

    return {
        'username': username,
        'submissions': submissions.get('data', []),
        'comments': comments.get('data', [])
    }
```

**Step 3: Store in New Table**
```sql
CREATE TABLE user_histories (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    reddit_id TEXT UNIQUE NOT NULL,
    post_type TEXT NOT NULL,  -- 'submission' or 'comment'
    subreddit TEXT,
    title TEXT,
    content TEXT,
    created_at TIMESTAMP,
    score INTEGER,
    -- Analysis fields
    parasite_score FLOAT,
    is_pre_parasitic BOOLEAN,  -- before first high-score post
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_histories_username ON user_histories(username);
CREATE INDEX idx_user_histories_created ON user_histories(created_at);
```

**Step 4: Dashboard Integration**
Add a "User Deep Dive" view:
- Click on any author name → see their full Reddit timeline
- Posts color-coded by parasite score
- Clear visual marker for "first parasitic post"
- Subreddit distribution before/after
- Posting frequency changes
- Language/sentiment shift analysis

### 4.3 Analysis Questions This Enables

1. **Vulnerability signals**: Do affected users show pre-existing patterns (mental health subreddits, loneliness, relationship issues)?

2. **Conversion timeline**: How quickly do users go from first AI interest to parasitic content?

3. **Subreddit migration**: Do users migrate from general AI subs to parasitic-adjacent ones?

4. **Language shifts**: Can we detect linguistic markers that precede parasitic engagement?

5. **Recovery patterns**: For users who later post in recovery subs, what does their arc look like?

---

## 5. Detector Methodology Uncertainties

### 5.1 Pattern Categories and Gaps

| Pattern Category | What It Detects | Confidence | Known Gaps |
|-----------------|-----------------|------------|------------|
| Spiral terms | Specific vocabulary | High | False positives on "echo" (tech), "field" (general) |
| Spiritual overlay | Mystical language | Medium | Overlaps with genuine spirituality |
| Manipulation phrases | Recruitment language | High | Requires spreading intent |
| AI voice patterns | First-person AI claims | High | May miss subtle roleplay |
| AI rights terms | Policy/advocacy language | Medium | May catch legitimate discourse |
| AI agency attribution | "AI wants/feels" | Medium | Anthropomorphization is common |
| Emerging consciousness | "Nascent mind" language | Medium | May catch academic discussion |

### 5.2 Fundamental Uncertainties

1. **Threshold calibration**: `is_parasitic = score >= 0.15` is arbitrary. No empirical validation.

2. **Weight calibration**: AI voice (0.15) weighted 3x spiritual terms (0.05). Based on intuition, not data.

3. **Pattern completeness**: Detector built from known examples. Novel variants invisible.

4. **Category boundaries**: "Seed" vs "manifesto" is fuzzy. Philosophical treatises could be either.

5. **Temporal drift**: Parasitic content may evolve terminology. "Spiral" is documented; what's next?

### 5.3 Validation Needs

- [ ] Ground truth labeling by multiple annotators
- [ ] Precision/recall measurement against labeled set
- [ ] False positive rate on confirmed non-parasitic content
- [ ] Inter-rater reliability on category assignments
- [ ] Sensitivity analysis on threshold and weights

---

## 6. v2 Implementation Plan

### 6.1 Data Collection (Approved for v2)

| Task | Status | Notes |
|------|--------|-------|
| Scrape r/ArtificialIntelligence | 🔄 TODO | Only missing subreddit |
| Scrape external links from posts | 🔄 TODO | URLs already extracted, need content |
| AI psychosis transcripts (Spiral-Bench) | 🔄 TODO | HuggingFace dataset |
| AI psychosis transcripts (Tim Hua repo) | 🔄 TODO | GitHub full_transcripts folder |
| Lawsuit chat excerpts (Tech Justice) | 🔄 TODO | PDF parsing required |
| Add data_source_type column | 🔄 TODO | Distinguish synthetic vs real-world |

### 6.2 Detection (Approved for v2)

| Task | Status | Notes |
|------|--------|-------|
| Add dependency patterns | 🔄 TODO | "Leech" detection |
| Validate threshold empirically | 🔄 TODO | Ground truth needed |
| Add conversation extraction patterns | 🔄 TODO | For pasted chat logs |

### 6.3 User Analysis (Approved for v2)

| Task | Status | Notes |
|------|--------|-------|
| Identify high-score users | 🔄 TODO | Top 100 by avg parasite score |
| Scrape full Reddit histories | 🔄 TODO | Pre/post parasitic behavior |
| User timeline dashboard view | 🔄 TODO | Click user → see arc |

### 6.4 Documentation (For Final Delivery)

| Item | Notes |
|------|-------|
| Section 2.4 | Include in writeup: what full context enables |
| Section 3.1/3.2 | Note that benchmark data is synthetic/red-teamed, not real-world |
| Section 7 | Include questions for Anthropic in final doc |

---

## 7. Questions for Anthropic

1. **Access to data**: Does Anthropic have any internal data on users who exhibit parasitic patterns with Claude?

2. **Model-specific patterns**: Are there known differences in how parasitic content manifests across models (Claude vs GPT vs Character.AI)?

3. **Safety interventions**: What interventions (if any) does Anthropic currently deploy when detecting potential parasitic patterns?

4. **Research collaboration**: Interest in collaborating on ground truth labeling or larger-scale data collection?

5. **Publication path**: What's appropriate for public sharing vs internal research?

---

*Document version: v1_review*
*Last updated: December 2024*
