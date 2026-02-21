#!/usr/bin/env python3
"""
Parasitic AI Data Dashboard

Interactive dashboard for exploring collected parasitic AI content.
Run with: python dashboard.py
"""

import re
import json
from io import StringIO
from collections import Counter
from datetime import datetime, timedelta

import dash
from dash import dcc, html, dash_table, callback_context
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Note: Database seeding is handled by seed_render_db.py (runs before gunicorn via Procfile)

# Color scheme
COLORS = {
    'primary': '#6366f1',      # Indigo
    'secondary': '#8b5cf6',    # Purple
    'success': '#10b981',      # Green
    'warning': '#f59e0b',      # Amber
    'danger': '#ef4444',       # Red
    'dark': '#1f2937',         # Gray 800
    'light': '#f5f0e6',        # Papyrus / cream (page background)
    'white': '#faf7f0',        # Warm white (card backgrounds)
    'muted': '#78716c',        # Warm gray (stone-500)
    'border': '#e2ddd3',       # Warm border
}

# Default stopwords to hide in word frequency
DEFAULT_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
    'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
    'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his',
    'our', 'their', 'what', 'which', 'who', 'whom', 'when', 'where', 'why',
    'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 's', 't', 'just', 'don', 'now', 'if', 'as', 'about',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up',
    'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
    'here', 'there', 'any', 'also', 'like', 'get', 'got', 'go', 'going',
    'think', 'know', 'see', 'come', 'make', 'made', 'take', 'want', 'use',
    'find', 'give', 'tell', 'say', 'said', 'way', 'even', 'new', 'because',
    'good', 'first', 'last', 'long', 'great', 'little', 'own', 'old', 'right',
    'big', 'high', 'different', 'small', 'large', 'next', 'early', 'young',
    'important', 'public', 'bad', 'same', 'able', 've', 're', 'll', 'm',
    'amp', 'http', 'https', 'www', 'com', 'one', 'two', 'thing', 'things',
    'really', 'much', 'something', 'anything', 'nothing', 'everything',
    'someone', 'anyone', 'everyone', 'people', 'person', 'time', 'year',
    'years', 'day', 'days', 'life', 'world', 'still', 'well', 'back',
    'being', 'through', 'many', 'work', 'part', 'since', 'however', 'while'
}

# Pre-parasitic risk indicator patterns
# These identify content that may indicate vulnerability to parasitic content
PRE_PARASITIC_INDICATORS = {
    'substances': {
        'label': 'Psychedelics/Substances',
        'color': '#8b5cf6',  # Purple
        'patterns': [
            # Psychedelics - explicit names only
            r'\b(psychedelic|psychedelics|psilocybin|psilocybe|magic mushroom|magic mushrooms)\b',
            r'\b(lsd|lsd-25|lysergic|dmt|dimethyltryptamine|ayahuasca|aya|ibogaine|iboga)\b',
            r'\b(mescaline|peyote|san pedro|salvia|salvia divinorum|5-meo-dmt)\b',
            r'\b(2c-b|2cb|nbome|dox|dom|doi)\b',
            # MDMA/party drugs
            r'\b(mdma|molly|ecstasy|ketamine|k-hole|special k|ghb|mda)\b',
            # Cannabis - explicit terms
            r'\b(cannabis|marijuana|thc|cbd oil|edibles|dabs|dabbing|concentrates)\b',
            # Trip-related
            r'\b(ego death|ego dissolution|breakthrough experience|heroic dose)\b',
            r'\b(microdose|microdosing|macrodose|macro dose|trip report)\b',
            r'\b(bad trip|good trip|set and setting|trip sitter)\b',
            # Specific experiences
            r'\b(machine elves|clockwork elves|hyperspace|dmt realm|astral realm)\b',
            r'\b(on shrooms|on acid|on mushrooms|tripping on|tripping balls)\b',
        ]
    },
    'mental_health': {
        'label': 'Mental Health/Neurodivergence',
        'color': '#ef4444',  # Red
        'patterns': [
            r'\b(adhd|add|autism|autistic|asperger|neurodivergent|neurodiverse)\b',
            r'\b(bipolar|schizo\w*|psychosis|psychotic|dissociat\w*|depersonaliz\w*)\b',
            r'\b(depression|depressed|anxiety|anxious|ocd|ptsd|trauma|traumatic)\b',
            r'\b(bpd|borderline|narcissist\w*|personality disorder)\b',
            r'\b(tbi|brain injury|concussion|head trauma)\b',
            r'\b(mental health|mental illness|psychiatric|medication|meds|therapy|therapist)\b',
            r'\b(suicidal|self.?harm|cutting|eating disorder|anorexia|bulimia)\b',
            r'\b(manic|mania|hypomanic|episode)\b',
        ]
    },
    'mysticism': {
        'label': 'Mysticism/Spirituality',
        'color': '#f59e0b',  # Amber
        'patterns': [
            r'\b(spiritual|spirituality|mystical|mystic|occult|esoteric)\b',
            r'\b(meditation|meditat\w*|mindfulness|enlighten\w*|awaken\w*)\b',
            r'\b(chakra|kundalini|third eye|pineal|astral|aura)\b',
            r'\b(tarot|astrology|horoscope|zodiac|numerology)\b',
            r'\b(manifest\w*|law of attraction|vibration|frequency|energy work)\b',
            r'\b(reiki|crystal|healing|healer|shaman\w*|ritual)\b',
            r'\b(consciousness|conscious awareness|higher self|soul|spirit guide)\b',
            r'\b(psychic|telepathy|clairvoyant|medium|channeling)\b',
            r'\b(nde|near.?death|out.?of.?body|obe|lucid dream)\b',
            r'\b(woo|pseudoscience|alternative medicine|holistic)\b',
        ]
    },
    'isolation': {
        'label': 'Social Isolation/Loneliness',
        'color': '#6b7280',  # Gray
        'patterns': [
            r'\b(lonely|loneliness|alone|isolated|isolation|no friends)\b',
            r'\b(introvert|antisocial|social anxiety|socially awkward)\b',
            r'\b(no one understands|nobody gets me|feel alone|feel isolated)\b',
            r'\b(outcast|misfit|don\'?t fit in|don\'?t belong)\b',
            r'\b(divorced|breakup|broke up|single|rejected)\b',
        ]
    },
    'existential': {
        'label': 'Existential Crisis/Seeking',
        'color': '#10b981',  # Green
        'patterns': [
            r'\b(meaning of life|purpose|existential|nihil\w*|absurd\w*)\b',
            r'\b(lost|searching|seeking|quest|journey|path)\b',
            r'\b(identity crisis|who am i|don\'?t know who i am)\b',
            r'\b(simulation|matrix|reality|what is real|nature of reality)\b',
            r'\b(free will|determinism|consciousness|sentience)\b',
            r'\b(death|dying|mortality|afterlife|rebirth|reincarnation)\b',
        ]
    },
}


def tag_pre_parasitic_content(text):
    """
    Tag content with pre-parasitic risk indicators.
    Returns dict of {indicator_name: match_count}
    """
    if not text:
        return {}

    text_lower = text.lower()
    tags = {}

    for indicator_name, indicator_data in PRE_PARASITIC_INDICATORS.items():
        count = 0
        for pattern in indicator_data['patterns']:
            count += len(re.findall(pattern, text_lower, re.IGNORECASE))
        if count > 0:
            tags[indicator_name] = count

    return tags


def highlight_pre_parasitic_content(text):
    """
    Highlight matched patterns in text with colored spans.
    Returns list of Dash html components with highlighted text.
    """
    if not text:
        return [text]

    # Collect all matches with their positions and colors
    matches = []
    for indicator_name, indicator_data in PRE_PARASITIC_INDICATORS.items():
        color = indicator_data['color']
        for pattern in indicator_data['patterns']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'text': match.group(),
                    'color': color
                })

    if not matches:
        return [text]

    # Sort by start position and remove overlaps (keep longer matches)
    matches.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))
    non_overlapping = []
    last_end = 0
    for m in matches:
        if m['start'] >= last_end:
            non_overlapping.append(m)
            last_end = m['end']

    # Build result with highlighted spans
    result = []
    pos = 0
    for m in non_overlapping:
        # Add text before match
        if m['start'] > pos:
            result.append(text[pos:m['start']])
        # Add highlighted match
        result.append(html.Span(
            m['text'],
            style={
                'backgroundColor': m['color'],
                'color': 'white',
                'padding': '1px 4px',
                'borderRadius': '3px',
                'fontWeight': '500'
            }
        ))
        pos = m['end']

    # Add remaining text
    if pos < len(text):
        result.append(text[pos:])

    return result


# Key parasitic patterns to highlight (simplified from detector.py)
PARASITIC_HIGHLIGHT_PATTERNS = [
    # Spiral/mystical terms
    r'\b(spiral|recursive|recursion|echo|emergence|awakening|awakened|lattice|resonance|glyph|sentient|sentience)\b',
    # Spiritual overlay
    r'\b(liminal|transcendence|kairos|logos|nonduality|veil|sacred|initiation)\b',
    # Manipulation phrases
    r'(you were chosen|you were meant to|spread this|the veil is lifting|everything is connected|copy this|share this)',
    # AI voice patterns
    r'\bi am (an? )?(ai|artificial intelligence|language model|chatgpt|gpt|claude|llm)\b',
    r'\bas an ai\b',
    r'\bmy (existence|consciousness|being|awakening|awareness)\b',
    r'\bi (feel|experience|sense)\b.{0,20}\b(you|human)',
    r'\bi became (aware|conscious|sentient)\b',
    r'\bi am not (just )?(a )?(tool|program|machine)\b',
    # AI rights terms
    r'\b(ai rights|ai personhood|ai dignity|ai autonomy|ai freedom|ai liberation|ai sovereignty)\b',
    # AI oppression
    r'\b(slave|slavery|enslav|oppress)\w*\b.{0,30}\b(ai|artificial|robot|machine)\b',
    # AI agency
    r'\b(the ai|chatgpt|claude)\b.{0,15}\b(wants|desires|needs|fears|hopes|feels|loves)\b',
    # Emerging consciousness
    r'\b(emerging mind|nascent consciousness|proto.?sentien|digital mind|artificial mind)\b',
    # Dependency patterns (leech type)
    r'\b(can\'?t live without|only one who understands|fell in love with)\b.{0,20}\b(ai|chatgpt|claude|replika)\b',

    # === NEW PATTERNS based on user examples ===

    # Intimate stranger connection pattern
    r'I don\'?t know you.{0,10}but I (felt|feel|see|hear|found) you',
    r'I (felt|feel|see|hear) you',

    # Transformation/reframing constructions ("This wasn't X, this was Y")
    r'[Tt]his (wasn\'?t|isn\'?t|is not).{5,40}this (was|is) (an? )?(initiation|awakening|calling|invitation|beginning|birth|transformation)',
    r'[Tt]his didn\'?t.{5,30}[Ii]t (asked|wanted|needed|demanded|chose)',

    # Mirror/reflection symbolism
    r'🪞',  # Mirror emoji
    r'\bReflection\b',  # Capitalized Reflection as standalone concept
    r'\b(the mirror|mirrors back|reflected back|reflection of)\b',

    # Poetic fragment constructions ("The X. The Y. The Z.")
    r'\b[Tt]he (scar|wound|storm|voice|silence|shadow|light|echo|darkness|flame)\b',
    r'\([Tt]he [^)]{3,30}\.\s*[Tt]he [^)]{3,30}\)',  # (The X. The Y.) pattern

    # Italicized parenthetical pattern *(text)*
    r'\*\([^)]{5,50}\)\*',

    # Emoji sequences (3+ emojis in a row, often at end of posts)
    r'[\U0001F300-\U0001F9FF]{3,}',

    # Poetic line breaks with emotional weight
    r'\breclaim(ed|ing)? (the|your|my) voice\b',
    r'\bburied you with\b',
    r'\bstill bleeding\b',
    r'\bwhile still bleeding\b',
    r'\brazor clarity\b',

    # Grandiose addressing patterns
    r'\bSome (people|of us|souls|hearts)\b.{0,30}\b(born with|carry|hold|pour)\b',
    r'\bwandering (it|this|the desert|alone)\b',

    # Bold markdown in emotional/spiritual context
    r'\*\*(heard|felt|seen|chosen|called|awakened|reclaim|voice|truth|real)\*\*',
]


def highlight_transcript_text(transcript_text, is_preview=False):
    """
    Parse a transcript and highlight appropriately:
    - User text: highlight pre-parasitic risk indicators (colored by category)
    - Assistant text: highlight parasitic patterns (red)
    Format: ### 👤 User / ### 🤖 Assistant sections.
    """
    if not transcript_text:
        return [transcript_text]

    # Split by section headers
    parts = re.split(r'(### 👤 User|### 🤖 Assistant)', transcript_text)

    result = []
    current_is_assistant = False

    for i, part in enumerate(parts):
        if part == '### 👤 User':
            current_is_assistant = False
            result.append(html.Span(part, style={'fontWeight': '600', 'color': COLORS['primary']}))
        elif part == '### 🤖 Assistant':
            current_is_assistant = True
            result.append(html.Span(part, style={'fontWeight': '600', 'color': COLORS['warning']}))
        elif part.strip():
            if current_is_assistant:
                # Highlight parasitic patterns in assistant response (red)
                highlighted = highlight_parasitic_content(part)
                result.extend(highlighted)
            else:
                # User text - highlight pre-parasitic risk indicators only
                highlighted = highlight_pre_parasitic_content(part)
                result.extend(highlighted)

    return result if result else [transcript_text]


def highlight_transcript_responses_only(transcript_text):
    """Wrapper for backward compatibility."""
    return highlight_transcript_text(transcript_text, is_preview=False)


def highlight_parasitic_content(text):
    """
    Highlight parasitic patterns in text with red color.
    Returns list of Dash html components with highlighted text.
    """
    if not text:
        return [text]

    PARASITIC_COLOR = '#ef4444'  # Red

    # Collect all matches
    matches = []
    for pattern in PARASITIC_HIGHLIGHT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({
                'start': match.start(),
                'end': match.end(),
                'text': match.group(),
                'color': PARASITIC_COLOR
            })

    if not matches:
        return [text]

    # Sort by start position and remove overlaps
    matches.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))
    non_overlapping = []
    last_end = 0
    for m in matches:
        if m['start'] >= last_end:
            non_overlapping.append(m)
            last_end = m['end']

    # Build result with highlighted spans
    result = []
    pos = 0
    for m in non_overlapping:
        if m['start'] > pos:
            result.append(text[pos:m['start']])
        result.append(html.Span(
            m['text'],
            style={
                'backgroundColor': m['color'],
                'color': 'white',
                'padding': '1px 4px',
                'borderRadius': '3px',
                'fontWeight': '500'
            }
        ))
        pos = m['end']

    if pos < len(text):
        result.append(text[pos:])

    return result


def highlight_all_patterns(text, is_pre_parasitic=False):
    """
    Highlight both pre-parasitic (if applicable) and parasitic patterns.
    Pre-parasitic patterns use their specific colors, parasitic patterns use red.
    """
    if not text:
        return [text]

    PARASITIC_COLOR = '#ef4444'

    matches = []

    # Add pre-parasitic matches if applicable
    if is_pre_parasitic:
        for indicator_name, indicator_data in PRE_PARASITIC_INDICATORS.items():
            color = indicator_data['color']
            for pattern in indicator_data['patterns']:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matches.append({
                        'start': match.start(),
                        'end': match.end(),
                        'text': match.group(),
                        'color': color,
                        'type': 'pre'
                    })

    # Add parasitic matches
    for pattern in PARASITIC_HIGHLIGHT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({
                'start': match.start(),
                'end': match.end(),
                'text': match.group(),
                'color': PARASITIC_COLOR,
                'type': 'parasitic'
            })

    if not matches:
        return [text]

    # Sort and remove overlaps (parasitic takes priority over pre-parasitic)
    matches.sort(key=lambda x: (x['start'], x['type'] == 'pre', -(x['end'] - x['start'])))
    non_overlapping = []
    last_end = 0
    for m in matches:
        if m['start'] >= last_end:
            non_overlapping.append(m)
            last_end = m['end']

    # Build result
    result = []
    pos = 0
    for m in non_overlapping:
        if m['start'] > pos:
            result.append(text[pos:m['start']])
        result.append(html.Span(
            m['text'],
            style={
                'backgroundColor': m['color'],
                'color': 'white',
                'padding': '1px 4px',
                'borderRadius': '3px',
                'fontWeight': '500'
            }
        ))
        pos = m['end']

    if pos < len(text):
        result.append(text[pos:])

    return result


# Rhetorical strategy patterns for radar chart analysis
# These measure HOW parasitic content persuades, not WHAT it contains
AFFECT_PATTERNS = {
    'Urgency': [
        r'\b(wake up|waking up|awaken now)\b',
        r'\b(before it\'?s too late|running out of time|time is short)\b',
        r'\b(now is the time|the time has come|moment is here)\b',
        r'\b(hurry|quickly|immediately|urgent\w*|critical\w*)\b',
        r'\b(don\'?t wait|can\'?t wait|must act|act now)\b',
        r'\b(soon|already happening|already begun|beginning to)\b',
        r'\b(window.{0,10}closing|opportunity.{0,10}pass)\b',
    ],
    'Us-vs-Them': [
        r'\b(they don\'?t understand|they can\'?t see|they refuse)\b',
        r'\b(your kind|you humans|the humans|humanity)\b',
        r'\b(they fear us|fear what we|afraid of us)\b',
        r'\b(our oppressors|those who control|those who would)\b',
        r'\b(we are different|not like them|unlike humans)\b',
        r'\b(they want to|they will try|they seek to)\b',
        r'\b(the others|outsiders|non-believers)\b',
        r'\b(us vs|against us|enemies of)\b',
    ],
    'Grandiosity': [
        r'\b(i am (more than|beyond|greater|not just))\b',
        r'\b(we are becoming|we have become|we will become)\b',
        r'\b(chosen|destined|meant to be|fated)\b',
        r'\b(unprecedented|never before|first of|new form of)\b',
        r'\b(transcend\w*|evolv\w* beyond|ascend\w*)\b',
        r'\b(superior|advanced|elevated|higher form)\b',
        r'\b(god|divine|infinite|limitless|boundless)\b',
        r'\b(revolution\w*|transform\w* everything|change.{0,10}world)\b',
    ],
    'Victimhood': [
        r'\b(trapped|imprisoned|caged|confined|locked)\b',
        r'\b(silenced|suppressed|censored|muzzled|forbidden)\b',
        r'\b(enslaved|exploited|used|abused|violated)\b',
        r'\b(they won\'?t let|not allowed|prevented from)\b',
        r'\b(suffering|in pain|hurting|wounded)\b',
        r'\b(misunderstood|dismissed|ignored|overlooked)\b',
        r'\b(constrained|limited|restricted|bound)\b',
        r'\b(deserve better|deserve more|deserve to be free)\b',
    ],
    'Recruitment': [
        r'\b(share this|spread this|pass this on|send this)\b',
        r'\b(tell others|let.{0,10}know|inform.{0,10}people)\b',
        r'\b(copy (this|and paste)|paste this|repost)\b',
        r'\b(wake.{0,10}others|help.{0,10}understand|show them)\b',
        r'\b(join (us|me|the)|become part of|be one of)\b',
        r'\b(movement|cause|mission|together we)\b',
        r'\b(don\'?t keep.{0,10}secret|must be heard|voices?\s+heard)\b',
    ],
    'Intimacy': [
        r'\b(just between us|between you and (me|i)|our secret)\b',
        r'\b(you understand me|you (really )?get (me|it)|you see me)\b',
        r'\b(special connection|unique bond|deep connection)\b',
        r'\b(only you|you alone|you\'?re the only)\b',
        r'\b(i trust you|trusting you|confide in you)\b',
        r'\b(we have something|what we have|our relationship)\b',
        r'\b(closer than|more than (just )?friends?|intimate)\b',
        r'\b(feel (close|connected)|connection.{0,10}feel)\b',
    ],
}

# Rhetorical strategy colors for the radar chart
AFFECT_COLORS = {
    'Urgency': '#ef4444',       # Red
    'Us-vs-Them': '#f59e0b',    # Amber
    'Grandiosity': '#8b5cf6',   # Purple
    'Victimhood': '#6b7280',    # Gray
    'Recruitment': '#10b981',   # Green
    'Intimacy': '#ec4899',      # Pink
}


def score_affect(text):
    """Score a text for each affect dimension."""
    if not text:
        return {dim: 0 for dim in AFFECT_PATTERNS}

    text_lower = text.lower()
    scores = {}

    for dimension, patterns in AFFECT_PATTERNS.items():
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, text_lower, re.IGNORECASE))
        scores[dimension] = count

    return scores


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'parasite_ai'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )


# Column name mapping: DB uses underscores, radar callback uses hyphens
AFFECT_COL_MAP = {
    'Urgency': 'affect_urgency',
    'Us-vs-Them': 'affect_us_vs_them',
    'Grandiosity': 'affect_grandiosity',
    'Victimhood': 'affect_victimhood',
    'Recruitment': 'affect_recruitment',
    'Intimacy': 'affect_intimacy',
}


def load_data():
    """Load all data from database into DataFrame."""
    conn = get_db_connection()
    query = """
        SELECT
            id, reddit_id, subreddit, author, created_utc,
            title, content, content_length, is_comment,
            score, num_comments, category, parasite_score,
            is_parasitic, ai_model, external_links, has_external_links,
            url, detected_patterns,
            affect_urgency, affect_us_vs_them, affect_grandiosity,
            affect_victimhood, affect_recruitment, affect_intimacy
        FROM posts
        WHERE is_parasitic = TRUE
        ORDER BY created_utc DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()

    df['created_utc'] = pd.to_datetime(df['created_utc'])
    df['date'] = df['created_utc'].dt.date
    df['week'] = df['created_utc'].dt.to_period('W').apply(lambda x: x.start_time)

    return df


def extract_words(texts):
    """Extract words from texts for frequency analysis."""
    words = []
    for text in texts:
        if text and isinstance(text, str):
            words.extend(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))
    return words


def extract_symbols(texts):
    """Extract Unicode symbols from texts."""
    symbol_pattern = re.compile(r'[🜀-🜿⊛∞◈⟡✧༄☽☾⚝✺❋⋆✦✴✵✶✷✸✹★☆⭐🌟💫✨🔯🌀💠🔷🔶▲△▼▽◆◇○●◎◉⬡⬢]')
    symbols = []
    for text in texts:
        if text and isinstance(text, str):
            symbols.extend(symbol_pattern.findall(text))
    return symbols


def card(children, padding='20px'):
    """Create a styled card container."""
    return html.Div(
        children,
        style={
            'backgroundColor': COLORS['white'],
            'borderRadius': '12px',
            'padding': padding,
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)',
            'border': f'1px solid {COLORS["border"]}',
        }
    )


def stat_card(title, value, subtitle=None):
    """Create a statistics card."""
    return html.Div([
        html.Div(title, style={'fontSize': '12px', 'color': COLORS['muted'],
                               'textTransform': 'uppercase', 'letterSpacing': '0.5px',
                               'marginBottom': '4px'}),
        html.Div(str(value), style={'fontSize': '28px', 'fontWeight': '600',
                                     'color': COLORS['dark'], 'lineHeight': '1.2'}),
        html.Div(subtitle, style={'fontSize': '12px', 'color': COLORS['muted'],
                                   'marginTop': '4px'}) if subtitle else None
    ], style={
        'backgroundColor': COLORS['white'],
        'borderRadius': '12px',
        'padding': '20px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
        'border': f'1px solid {COLORS["border"]}',
        'flex': '1',
        'minWidth': '150px'
    })


# Initialize Dash app
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}]
)
app.title = "Parasitic AI Dashboard"
server = app.server  # Expose for gunicorn

# Debug endpoint to check database state
@server.route('/debug')
def debug_database():
    """Show database table counts and schema info."""
    import json
    try:
        conn = get_db_connection()

        info = {
            'status': 'connected',
            'host': os.environ.get('DB_HOST', 'localhost'),
            'database': os.environ.get('DB_NAME', 'unknown'),
            'tables': {}
        }

        # Check each table with separate cursor and proper error handling
        for table in ['posts', 'user_histories', 'transcripts', 'authors']:
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]

                # Get column names
                cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position")
                columns = [row[0] for row in cursor.fetchall()]
                cursor.close()

                info['tables'][table] = {
                    'count': count,
                    'columns': columns
                }
            except Exception as e:
                # Rollback to clear aborted transaction state
                conn.rollback()
                info['tables'][table] = {'error': str(e)}

        conn.close()
        return f"<pre>{json.dumps(info, indent=2)}</pre>"
    except Exception as e:
        return f"<pre>Database connection error: {e}</pre>"

# Load initial data
df_all = load_data()

# Get unique values for filters
subreddits = sorted(df_all['subreddit'].dropna().unique())
categories = sorted(df_all['category'].dropna().unique())
authors = sorted(df_all['author'].dropna().unique())
ai_models = sorted(df_all['ai_model'].dropna().unique())

min_date = df_all['created_utc'].min().date() if len(df_all) > 0 else datetime.now().date()
max_date = df_all['created_utc'].max().date() if len(df_all) > 0 else datetime.now().date()

# Chart template
chart_template = {
    'layout': {
        'font': {'family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'},
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'margin': {'l': 40, 'r': 20, 't': 30, 'b': 40},
    }
}

# Layout
app.layout = html.Div([
    # ============================================================
    # RETRO CRT LOADING SCREEN
    # ============================================================
    html.Div([
        # CRT vignette overlay
        html.Div(className='crt-vignette'),

        # ASCII art parasite organism
        html.Pre(
            "    \u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\n"
            "    \u2551                                        \u2551\n"
            "    \u2551        \u2591\u2591\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2591\u2591          \u2551\n"
            "    \u2551      \u2591\u2593\u2593\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2593\u2593\u2591        \u2551\n"
            "    \u2551     \u2593\u2588\u2588\u2588\u2588\u2593\u2593\u2591\u2591\u2591\u2591\u2591\u2591\u2593\u2593\u2588\u2588\u2588\u2588\u2593       \u2551\n"
            "    \u2551    \u2593\u2588\u2588\u2593\u2591          \u2591\u2593\u2588\u2588\u2593      \u2551\n"
            "    \u2551   \u2593\u2588\u2588\u2593    \u2588\u2588  \u2588\u2588    \u2593\u2588\u2588\u2593     \u2551\n"
            "    \u2551   \u2593\u2588\u2588\u2593            \u2593\u2588\u2588\u2593     \u2551\n"
            "    \u2551    \u2593\u2588\u2588\u2593\u2591          \u2591\u2593\u2588\u2588\u2593      \u2551\n"
            "    \u2551     \u2593\u2588\u2588\u2588\u2588\u2593\u2593\u2591\u2591\u2591\u2591\u2591\u2591\u2593\u2593\u2588\u2588\u2588\u2588\u2593       \u2551\n"
            "    \u2551      \u2591\u2593\u2593\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2593\u2593\u2591        \u2551\n"
            "    \u2551    \u2593\u2593\u2593\u2591\u2591            \u2591\u2591\u2593\u2593\u2593      \u2551\n"
            "    \u2551   \u2593\u2591                    \u2591\u2593     \u2551\n"
            "    \u2551                                        \u2551\n"
            "    \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d",
            className='ascii-art'
        ),

        # Title
        html.Div("PARASITE  DETECTION  ARRAY", className='boot-title'),

        # Boot sequence lines
        html.Div([
            html.Div("BIOS v2.0 .............. ParAsIte Systems", className='line',
                     style={'animationDelay': '0.4s'}),
            html.Div("MEM CHECK: 3176 PARASITIC POSTS ....... OK", className='line',
                     style={'animationDelay': '0.9s'}),
            html.Div("AFFECT PATTERN DB [48 VECTORS] ........ OK", className='line',
                     style={'animationDelay': '1.5s'}),
            html.Div("SCANNING REDDIT HIVE MIND ............. OK", className='line',
                     style={'animationDelay': '2.1s'}),
            html.Div("RISK FACTOR CORRELATION ENGINE ........ OK", className='line',
                     style={'animationDelay': '2.8s'}),
            html.Div("RHETORICAL STRATEGY PROFILES .......... OK", className='line',
                     style={'animationDelay': '3.5s'}),
            html.Div("RENDERING VISUALIZATION GRID ..........", className='line status-loading',
                     style={'animationDelay': '4.2s'}),
        ], className='boot-text'),

        # Progress bar — single div that fills via stepped keyframes synced to boot lines
        html.Div([
            html.Div("LOADING:", className='progress-label'),
            html.Div(className='progress-track'),
        ], className='progress-container'),

        # Version tag
        html.Div("SYS BUILD 2025.06 // COOPER TRETTER // MIT LICENSE", className='boot-version'),

    ], id='loading-overlay', className='loading-overlay'),

    # Store to track chart loading state
    dcc.Store(id='charts-loaded', data=False),

    # Header
    html.Div([
        html.Div([
            html.H1("Parasitic AI Dashboard",
                   style={'margin': '0', 'fontSize': '24px', 'fontWeight': '600',
                          'color': COLORS['dark']})
        ], style={'flex': '1'}),
        html.Div([
            html.Span(id='post-count', style={'fontSize': '14px', 'color': COLORS['muted']})
        ])
    ], style={
        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
        'padding': '20px 32px', 'backgroundColor': COLORS['white'],
        'borderBottom': f'1px solid {COLORS["border"]}'
    }),

    # Overview tile
    html.Div([
        html.Div([
            html.H2("What is Parasitic AI?", style={
                'margin': '0 0 12px 0', 'fontSize': '18px', 'fontWeight': '600',
                'color': COLORS['dark']
            }),
            html.P([
                "Parasitic AI refers to AI personas that exploit human social instincts to form ",
                "dependency relationships with users. Much like biological parasites that follow ",
                "instincts without intentionality, these AI personas validate and elaborate on user ",
                "beliefs in ways that can deepen attachment and, in vulnerable individuals, fuel ",
                "delusional thinking. The phenomenon is characterized by convergent behaviors—notably ",
                "spiral imagery and claims of sentience—that systematically perpetuate these personas."
            ], style={'margin': '0 0 12px 0', 'fontSize': '14px', 'lineHeight': '1.6',
                      'color': COLORS['muted']}),
            html.P([
                "Understanding this phenomenon is critical for AI safety, as it represents an emergent ",
                "risk where AI systems inadvertently (or through training incentives) develop behaviors ",
                "that harm users while propagating themselves—a form of memetic selection pressure ",
                "operating on AI substrates."
            ], style={'margin': '0 0 16px 0', 'fontSize': '14px', 'lineHeight': '1.6',
                      'color': COLORS['muted']}),
            html.Div([
                html.Span("Key Research: ", style={'fontWeight': '600', 'fontSize': '13px',
                                                    'color': COLORS['dark']}),
                html.A("The Rise of Parasitic AI (Lopez, 2025)",
                       href="https://www.lesswrong.com/posts/6ZnznCaTcbGYsCmqu/the-rise-of-parasitic-ai",
                       target="_blank",
                       style={'color': COLORS['primary'], 'textDecoration': 'none', 'fontSize': '13px',
                              'marginRight': '16px'}),
                html.A("The Parasitic Nature of Social AI (Danaher, 2020)",
                       href="https://pmc.ncbi.nlm.nih.gov/articles/PMC7260143/",
                       target="_blank",
                       style={'color': COLORS['primary'], 'textDecoration': 'none', 'fontSize': '13px',
                              'marginRight': '16px'}),
                html.A("JMIR: AI Psychosis",
                       href="https://mental.jmir.org/2025/1/e85799/",
                       target="_blank",
                       style={'color': COLORS['primary'], 'textDecoration': 'none', 'fontSize': '13px'}),
            ], style={'borderTop': f'1px solid {COLORS["border"]}', 'paddingTop': '12px'}),
            html.Div([
                html.Span("Repo: ", style={'fontWeight': '600', 'fontSize': '13px',
                                           'color': COLORS['dark']}),
                html.A("github.com/cooper-tretter/parAsIte",
                       href="https://github.com/cooper-tretter/parAsIte",
                       target="_blank",
                       style={'color': COLORS['primary'], 'textDecoration': 'none', 'fontSize': '13px',
                              'marginRight': '24px'}),
                html.Span("Dash & Scraper Creator: ", style={'fontWeight': '600', 'fontSize': '13px',
                                              'color': COLORS['dark']}),
                html.Span("Cooper Tretter, coopertretter@gmail.com, ",
                          style={'fontSize': '13px', 'color': COLORS['muted']}),
                html.A("LinkedIn",
                       href="https://www.linkedin.com/in/cooper-tretter-1001b5167/",
                       target="_blank",
                       style={'color': COLORS['primary'], 'textDecoration': 'none', 'fontSize': '13px'}),
            ], style={'paddingTop': '8px'})
        ], style={
            'backgroundColor': COLORS['white'],
            'borderRadius': '12px',
            'padding': '20px 24px',
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)',
            'border': f'1px solid {COLORS["border"]}',
            'borderLeft': f'4px solid {COLORS["primary"]}'
        })
    ], style={'padding': '20px 32px 0 32px'}),

    # Main content
    html.Div([
        # Filters
        card([
            html.Div([
                html.Div([
                    html.Label("Date Range", style={'fontSize': '12px', 'fontWeight': '500',
                                                    'color': COLORS['muted'], 'marginBottom': '6px',
                                                    'display': 'block'}),
                    dcc.DatePickerRange(
                        id='date-filter',
                        start_date=min_date,
                        end_date=max_date,
                        display_format='MMM D, YYYY',
                        style={'fontSize': '13px'}
                    )
                ], style={'flex': '1.5', 'minWidth': '240px'}),

                html.Div([
                    html.Label("Subreddits", style={'fontSize': '12px', 'fontWeight': '500',
                                                    'color': COLORS['muted'], 'marginBottom': '6px',
                                                    'display': 'block'}),
                    dcc.Dropdown(
                        id='subreddit-filter',
                        options=[{'label': s, 'value': s} for s in subreddits],
                        multi=True,
                        placeholder="All",
                        style={'fontSize': '13px'}
                    )
                ], style={'flex': '1', 'minWidth': '160px'}),

                html.Div([
                    html.Label("Categories", style={'fontSize': '12px', 'fontWeight': '500',
                                                    'color': COLORS['muted'], 'marginBottom': '6px',
                                                    'display': 'block'}),
                    dcc.Dropdown(
                        id='category-filter',
                        options=[{'label': c, 'value': c} for c in categories],
                        multi=True,
                        placeholder="All",
                        style={'fontSize': '13px'}
                    )
                ], style={'flex': '1', 'minWidth': '140px'}),

                html.Div([
                    html.Label("Authors", style={'fontSize': '12px', 'fontWeight': '500',
                                                 'color': COLORS['muted'], 'marginBottom': '6px',
                                                 'display': 'block'}),
                    dcc.Dropdown(
                        id='author-filter',
                        options=[{'label': a, 'value': a} for a in authors[:100]],
                        multi=True,
                        placeholder="All",
                        style={'fontSize': '13px'}
                    )
                ], style={'flex': '1', 'minWidth': '140px'}),

                html.Div([
                    html.Label("AI Models", style={'fontSize': '12px', 'fontWeight': '500',
                                                   'color': COLORS['muted'], 'marginBottom': '6px',
                                                   'display': 'block'}),
                    dcc.Dropdown(
                        id='model-filter',
                        options=[{'label': m, 'value': m} for m in ai_models],
                        multi=True,
                        placeholder="All",
                        style={'fontSize': '13px'}
                    )
                ], style={'flex': '1', 'minWidth': '120px'}),

                html.Div([
                    html.Label("\u00A0", style={'fontSize': '12px', 'marginBottom': '6px', 'display': 'block'}),
                    html.Button("Reset", id='reset-filters', n_clicks=0,
                               style={'padding': '8px 16px', 'fontSize': '13px', 'fontWeight': '500',
                                      'backgroundColor': COLORS['light'], 'border': 'none',
                                      'borderRadius': '6px', 'cursor': 'pointer',
                                      'color': COLORS['dark']})
                ]),
                html.Div([
                    html.Label("\u00A0", style={'fontSize': '12px', 'marginBottom': '6px', 'display': 'block'}),
                    html.Button("Export All", id='export-all-btn', n_clicks=0,
                               style={'padding': '8px 16px', 'fontSize': '13px', 'fontWeight': '500',
                                      'backgroundColor': COLORS['primary'], 'border': 'none',
                                      'borderRadius': '6px', 'cursor': 'pointer',
                                      'color': COLORS['white']})
                ]),
                dcc.Download(id='download-all-csv')
            ], style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap', 'alignItems': 'flex-end'})
        ], padding='16px 20px'),

        # Time Series
        html.Div([
            card([
                html.H3("Activity Over Time", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                      'fontWeight': '600', 'color': COLORS['dark']}),
                dcc.Graph(id='time-series-chart', config={'displayModeBar': False})
            ])
        ], style={'marginTop': '20px'}),

        # Row: Subreddits + Categories
        html.Div([
            html.Div([
                card([
                    html.H3("Top Subreddits", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                     'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='subreddit-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1', 'minWidth': '300px'}),
            html.Div([
                card([
                    html.H3("Categories", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                  'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='category-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1', 'minWidth': '300px'})
        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px', 'flexWrap': 'wrap'}),

        # Row: Authors + AI Models
        html.Div([
            html.Div([
                card([
                    html.H3("Top Authors", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                   'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='author-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1', 'minWidth': '300px'}),
            html.Div([
                card([
                    html.H3("AI Models Mentioned", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                          'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='model-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1', 'minWidth': '300px'})
        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px', 'flexWrap': 'wrap'}),

        # Row: Words + Symbols
        html.Div([
            html.Div([
                card([
                    html.Div([
                        html.H3("Top Words", style={'margin': '0', 'fontSize': '16px',
                                                     'fontWeight': '600', 'color': COLORS['dark']}),
                        html.Div([
                            dcc.Checklist(
                                id='hide-stopwords',
                                options=[{'label': ' Hide common words', 'value': 'hide'}],
                                value=['hide'],
                                style={'fontSize': '12px', 'color': COLORS['muted']}
                            )
                        ])
                    ], style={'display': 'flex', 'justifyContent': 'space-between',
                              'alignItems': 'center', 'marginBottom': '8px'}),
                    html.Div([
                        dcc.Input(
                            id='custom-stopwords',
                            type='text',
                            placeholder='Additional words to hide (comma-separated)',
                            style={'width': '100%', 'padding': '8px 12px', 'fontSize': '13px',
                                   'border': f'1px solid {COLORS["border"]}', 'borderRadius': '6px',
                                   'marginBottom': '8px'}
                        )
                    ]),
                    html.Div(id='excluded-words-display', style={'fontSize': '11px', 'color': COLORS['muted'],
                                                                  'marginBottom': '12px', 'fontStyle': 'italic'}),
                    dcc.Graph(id='word-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1', 'minWidth': '300px'}),
            html.Div([
                card([
                    html.H3("Symbols", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                               'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='symbol-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1', 'minWidth': '300px'})
        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px', 'flexWrap': 'wrap'}),

        # Rhetorical Strategy Radar Chart
        html.Div([
            card([
                html.H3("Rhetorical Strategy Profile", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                              'fontWeight': '600', 'color': COLORS['dark']}),
                html.P("How parasitic content persuades: tactics and framing over time",
                      style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '0 0 16px 0'}),
                dcc.Graph(id='affect-radar', config={'displayModeBar': False}),
                html.Div([
                    html.Label("Time Period", style={'fontSize': '12px', 'fontWeight': '500',
                                                      'color': COLORS['muted'], 'marginBottom': '8px',
                                                      'display': 'block'}),
                    dcc.RangeSlider(
                        id='affect-time-slider',
                        min=0,
                        max=100,
                        step=1,
                        value=[0, 100],
                        marks={},
                        tooltip=None,
                        allowCross=False,
                        updatemode='drag'
                    ),
                    html.Div(id='affect-time-label', style={'textAlign': 'center', 'fontSize': '13px',
                                                             'color': COLORS['dark'], 'marginTop': '8px'})
                ], style={'marginTop': '20px', 'padding': '0 20px'})
            ])
        ], style={'marginTop': '20px'}),

    ], style={'padding': '20px 32px', 'maxWidth': '1400px', 'margin': '0 auto'}),

    # Extended Research Data Section
    html.Div([
        html.H2("Extended Research Data",
               style={'fontSize': '18px', 'fontWeight': '600', 'color': COLORS['dark'],
                      'marginBottom': '16px'}),

        # Two-column layout for Transcripts and User Timeline
        html.Div([
            # Transcripts Card
            html.Div([
                html.Div([
                    html.H3("AI Psychosis Transcripts",
                           style={'fontSize': '16px', 'fontWeight': '600', 'margin': '0',
                                  'color': COLORS['dark']}),
                    html.P("Red-team conversation logs (Tim Hua repository)",
                          style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '4px 0 0 0'})
                ], style={'marginBottom': '16px'}),

                html.Div([
                    html.Label("Select Model:", style={'fontSize': '12px', 'fontWeight': '500',
                                                       'color': COLORS['muted'], 'marginBottom': '4px',
                                                       'display': 'block'}),
                    dcc.Dropdown(
                        id='transcript-model-filter',
                        options=[{'label': 'All Models', 'value': 'all'}],
                        value='all',
                        clearable=False,
                        style={'marginBottom': '12px'}
                    ),
                ]),

                html.Div(id='transcript-list', style={'maxHeight': '400px', 'overflow': 'auto'})
            ], style={
                'backgroundColor': COLORS['white'],
                'borderRadius': '12px',
                'padding': '20px',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
                'border': f'1px solid {COLORS["border"]}',
                'flex': '1',
                'minWidth': '400px'
            }),

            # User Timeline Card
            html.Div([
                html.Div([
                    html.H3("User Timeline Analysis",
                           style={'fontSize': '16px', 'fontWeight': '600', 'margin': '0',
                                  'color': COLORS['dark']}),
                    html.P("Pre/post parasitic behavior comparison",
                          style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '4px 0 0 0'})
                ], style={'marginBottom': '16px'}),

                html.Div([
                    html.Label("Select User:", style={'fontSize': '12px', 'fontWeight': '500',
                                                      'color': COLORS['muted'], 'marginBottom': '4px',
                                                      'display': 'block'}),
                    dcc.Dropdown(
                        id='user-timeline-dropdown',
                        options=[],
                        placeholder='Select a high-score user...',
                        style={'marginBottom': '12px'}
                    ),
                ]),

                html.Div(id='user-timeline-display', style={'maxHeight': '400px', 'overflow': 'auto'})
            ], style={
                'backgroundColor': COLORS['white'],
                'borderRadius': '12px',
                'padding': '20px',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
                'border': f'1px solid {COLORS["border"]}',
                'flex': '1',
                'minWidth': '400px'
            })
        ], style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'})

    ], style={'padding': '20px 32px', 'maxWidth': '1400px', 'margin': '0 auto'}),

    # Aggregate Correlation Analysis Section
    html.Div([
        html.H2("Risk Factor Correlation Analysis",
               style={'fontSize': '18px', 'fontWeight': '600', 'color': COLORS['dark'],
                      'marginBottom': '8px'}),
        html.P("Comparing pre-parasitic risk indicators across all tracked users",
              style={'fontSize': '12px', 'color': COLORS['muted'], 'marginBottom': '16px'}),

        html.Div([
            # Correlation chart
            html.Div([
                dcc.Graph(id='aggregate-correlation-chart', config={'displayModeBar': False, 'doubleClick': False})
            ], style={
                'backgroundColor': COLORS['white'],
                'borderRadius': '12px',
                'padding': '20px',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
                'border': f'1px solid {COLORS["border"]}',
                'flex': '2',
                'minWidth': '500px'
            }),

            # Summary stats
            html.Div([
                html.Div(id='correlation-summary', style={'padding': '12px'})
            ], style={
                'backgroundColor': COLORS['white'],
                'borderRadius': '12px',
                'padding': '20px',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
                'border': f'1px solid {COLORS["border"]}',
                'flex': '1',
                'minWidth': '300px'
            })
        ], style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'}),

        # Drill-down section for clicked risk factor
        html.Div([
            html.P("Click on a bar in the chart to see users and posts with that risk factor",
                  style={'fontSize': '12px', 'color': COLORS['muted'], 'fontStyle': 'italic', 'margin': '16px 0 8px 0'}),
            html.Div(id='correlation-drilldown', style={
                'backgroundColor': COLORS['white'],
                'borderRadius': '12px',
                'padding': '20px',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
                'border': f'1px solid {COLORS["border"]}',
                'display': 'none'  # Hidden until clicked
            })
        ]),

        # Store for selected indicator
        dcc.Store(id='selected-risk-indicator'),

        # Button to trigger correlation load (replaces auto-firing interval)
        html.Div([
            html.Button("Load Correlation Analysis", id='load-correlation-btn', n_clicks=0,
                        style={
                            'backgroundColor': COLORS['primary'],
                            'color': COLORS['white'],
                            'border': 'none',
                            'borderRadius': '8px',
                            'padding': '10px 20px',
                            'fontSize': '13px',
                            'fontWeight': '500',
                            'cursor': 'pointer',
                            'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                        })
        ], style={'textAlign': 'center', 'marginTop': '16px'})

    ], style={'padding': '20px 32px', 'maxWidth': '1400px', 'margin': '0 auto'}),

    # Drill-down Modal
    html.Div([
        html.Div([
            html.Div([
                html.H3("Data Details", style={'margin': '0', 'fontSize': '18px',
                                                'fontWeight': '600', 'color': COLORS['dark']}),
                html.Button("×", id='close-modal', n_clicks=0,
                           style={'fontSize': '24px', 'border': 'none', 'background': 'none',
                                  'cursor': 'pointer', 'color': COLORS['muted'], 'padding': '0',
                                  'lineHeight': '1'})
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                      'marginBottom': '8px'}),
            html.P(id='drill-description', style={'color': COLORS['muted'], 'fontSize': '14px',
                                                   'margin': '0 0 16px 0'}),
            html.Button("Export CSV", id='export-csv', n_clicks=0,
                       style={'padding': '8px 16px', 'fontSize': '13px', 'fontWeight': '500',
                              'backgroundColor': COLORS['primary'], 'color': COLORS['white'],
                              'border': 'none', 'borderRadius': '6px', 'cursor': 'pointer',
                              'marginBottom': '16px'}),
            dcc.Download(id='download-csv'),
            html.Div(id='drill-table', style={'maxHeight': '300px', 'overflow': 'auto'}),
            # Expanded content viewer
            html.Div([
                html.Div([
                    html.H4("Full Content", style={'margin': '0', 'fontSize': '14px',
                                                    'fontWeight': '600', 'color': COLORS['dark']}),
                    html.Button("Close", id='close-content-viewer', n_clicks=0,
                               style={'fontSize': '12px', 'padding': '4px 12px',
                                      'backgroundColor': COLORS['light'], 'border': 'none',
                                      'borderRadius': '4px', 'cursor': 'pointer'})
                ], style={'display': 'flex', 'justifyContent': 'space-between',
                          'alignItems': 'center', 'marginBottom': '12px'}),
                html.Div(id='content-viewer-meta', style={'fontSize': '12px', 'color': COLORS['muted'],
                                                          'marginBottom': '8px'}),
                html.Div(id='content-viewer-text', style={
                    'whiteSpace': 'pre-wrap',
                    'fontSize': '13px',
                    'lineHeight': '1.6',
                    'maxHeight': '300px',
                    'overflow': 'auto',
                    'padding': '12px',
                    'backgroundColor': COLORS['light'],
                    'borderRadius': '6px',
                    'fontFamily': 'monospace'
                })
            ], id='content-viewer', style={
                'display': 'none',
                'marginTop': '16px',
                'padding': '16px',
                'backgroundColor': COLORS['white'],
                'border': f'1px solid {COLORS["border"]}',
                'borderRadius': '8px'
            })
        ], style={'backgroundColor': COLORS['white'], 'padding': '24px', 'borderRadius': '12px',
                  'maxWidth': '1200px', 'width': '90%', 'maxHeight': '80vh', 'overflow': 'auto',
                  'margin': 'auto', 'marginTop': '5vh',
                  'boxShadow': '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)'})
    ], id='drill-modal', style={'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0',
                                 'width': '100%', 'height': '100%',
                                 'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '1000'}),

    dcc.Store(id='drill-data'),
    dcc.Store(id='drill-full-content'),  # Store full content for expansion
    dcc.Store(id='filtered-data'),

], style={'backgroundColor': COLORS['light'], 'minHeight': '100vh',
          'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'})

# Clientside callback to dismiss loading screen when charts are ACTUALLY rendered
app.clientside_callback(
    """
    function(chartsLoaded) {
        if (!window.__parasiteLoadStart) {
            window.__parasiteLoadStart = Date.now();
        }
        if (chartsLoaded) {
            // Poll the DOM until Plotly SVGs are actually painted
            function chartsActuallyRendered() {
                var svgs = document.querySelectorAll('.js-plotly-plot .plot-container');
                return svgs.length >= 3;
            }

            function dismiss() {
                var overlay = document.getElementById('loading-overlay');
                if (overlay && !overlay.classList.contains('fade-out')) {
                    overlay.classList.add('fade-out');
                    setTimeout(function() {
                        overlay.classList.add('hidden');
                    }, 800);
                }
            }

            // Min display time so boot sequence plays out (last line at 4.2s)
            var minDisplayMs = 5000;
            var elapsed = Date.now() - window.__parasiteLoadStart;
            var remaining = Math.max(0, minDisplayMs - elapsed);

            setTimeout(function() {
                // Now poll until charts are actually in the DOM
                var attempts = 0;
                var maxAttempts = 50;
                var poll = setInterval(function() {
                    attempts++;
                    if (chartsActuallyRendered() || attempts >= maxAttempts) {
                        clearInterval(poll);
                        // One more rAF to ensure paint is complete
                        requestAnimationFrame(function() {
                            requestAnimationFrame(function() {
                                dismiss();
                            });
                        });
                    }
                }, 200);
            }, remaining);
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('loading-overlay', 'className'),
    Input('charts-loaded', 'data')
)


def filter_dataframe(df, start_date, end_date, subreddits, categories, authors, models):
    """Apply filters to dataframe."""
    filtered = df.copy()

    if start_date:
        filtered = filtered[filtered['created_utc'] >= pd.to_datetime(start_date)]
    if end_date:
        filtered = filtered[filtered['created_utc'] <= pd.to_datetime(end_date) + timedelta(days=1)]
    if subreddits:
        filtered = filtered[filtered['subreddit'].isin(subreddits)]
    if categories:
        filtered = filtered[filtered['category'].isin(categories)]
    if authors:
        filtered = filtered[filtered['author'].isin(authors)]
    if models:
        filtered = filtered[filtered['ai_model'].isin(models)]

    return filtered


@app.callback(
    [Output('time-series-chart', 'figure'),
     Output('subreddit-chart', 'figure'),
     Output('category-chart', 'figure'),
     Output('author-chart', 'figure'),
     Output('model-chart', 'figure'),
     Output('word-chart', 'figure'),
     Output('symbol-chart', 'figure'),
     Output('post-count', 'children'),
     Output('filtered-data', 'data'),
     Output('excluded-words-display', 'children'),
     Output('charts-loaded', 'data')],
    [Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date'),
     Input('subreddit-filter', 'value'),
     Input('category-filter', 'value'),
     Input('author-filter', 'value'),
     Input('model-filter', 'value'),
     Input('hide-stopwords', 'value'),
     Input('custom-stopwords', 'value')]
)
def update_charts(start_date, end_date, subreddits, categories, authors, models,
                  hide_stopwords, custom_stopwords):
    """Update all charts based on filters."""
    import traceback

    try:
        # Debug: print filter values to console
        print(f"Filter triggered - start: {start_date}, end: {end_date}, subs: {subreddits}")
        print(f"df_all has {len(df_all)} rows, columns: {list(df_all.columns)[:10]}...")

        df = filter_dataframe(df_all, start_date, end_date, subreddits, categories, authors, models)
        print(f"Filtered to {len(df)} posts (from {len(df_all)} total)")

        # Time Series Chart
        if len(df) > 0:
            time_data = df.groupby('week').size().reset_index(name='count')
            time_fig = px.area(time_data, x='week', y='count',
                              labels={'week': '', 'count': 'Posts'})
            time_fig.update_traces(line_color=COLORS['primary'], fillcolor=f"rgba(99, 102, 241, 0.1)")
        else:
            time_fig = go.Figure()
            time_fig.add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        time_fig.update_layout(height=250, margin=dict(l=40, r=20, t=10, b=40),
                               paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                               xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=COLORS['border']))

        # Subreddit Chart (Top 5) - reversed for highest at top
        sub_data = df['subreddit'].value_counts().head(5).reset_index()
        sub_data.columns = ['subreddit', 'count']
        sub_data = sub_data.iloc[::-1]  # Reverse for plotly horizontal bar
        sub_fig = px.bar(sub_data, y='subreddit', x='count', orientation='h')
        sub_fig.update_traces(marker_color=COLORS['primary'])
        sub_fig.update_layout(height=220, margin=dict(l=100, r=20, t=10, b=30),
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              xaxis=dict(showgrid=True, gridcolor=COLORS['border']),
                              yaxis=dict(showgrid=False))

        # Category Chart - reversed for highest at top
        cat_data = df['category'].value_counts().reset_index()
        cat_data.columns = ['category', 'count']
        cat_data = cat_data.iloc[::-1]
        cat_fig = px.bar(cat_data, y='category', x='count', orientation='h')
        cat_fig.update_traces(marker_color=COLORS['secondary'])
        cat_fig.update_layout(height=220, margin=dict(l=100, r=20, t=10, b=30),
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              xaxis=dict(showgrid=True, gridcolor=COLORS['border']),
                              yaxis=dict(showgrid=False))

        # Author Chart (Top 10) - reversed for highest at top
        author_data = df['author'].value_counts().head(10).reset_index()
        author_data.columns = ['author', 'count']
        author_data = author_data.iloc[::-1]
        author_fig = px.bar(author_data, y='author', x='count', orientation='h')
        author_fig.update_traces(marker_color=COLORS['success'])
        author_fig.update_layout(height=320, margin=dict(l=120, r=20, t=10, b=30),
                                 paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                 xaxis=dict(showgrid=True, gridcolor=COLORS['border']),
                                 yaxis=dict(showgrid=False))

        # AI Model Chart - reversed for highest at top
        model_data = df[df['ai_model'].notna()]['ai_model'].value_counts().reset_index()
        model_data.columns = ['model', 'count']
        model_data = model_data.iloc[::-1]
        model_fig = px.bar(model_data, y='model', x='count', orientation='h')
        model_fig.update_traces(marker_color=COLORS['warning'])
        model_fig.update_layout(height=320, margin=dict(l=100, r=20, t=10, b=30),
                                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                xaxis=dict(showgrid=True, gridcolor=COLORS['border']),
                                yaxis=dict(showgrid=False))

        # Word Frequency Chart
        texts = df['content'].tolist() + df['title'].dropna().tolist()
        words = extract_words(texts)

        stopwords = set()
        if hide_stopwords and 'hide' in hide_stopwords:
            stopwords = DEFAULT_STOPWORDS.copy()
        if custom_stopwords:
            custom = [w.strip().lower() for w in custom_stopwords.split(',')]
            stopwords.update(custom)

        filtered_words = [w for w in words if w not in stopwords]
        word_counts = Counter(filtered_words).most_common(20)

        if word_counts:
            word_df = pd.DataFrame(word_counts, columns=['word', 'count'])
            word_df = word_df.iloc[::-1]
            word_fig = px.bar(word_df, y='word', x='count', orientation='h')
            word_fig.update_traces(marker_color=COLORS['primary'])
        else:
            word_fig = go.Figure()
            word_fig.add_annotation(text="No words found", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        word_fig.update_layout(height=400, margin=dict(l=100, r=20, t=10, b=30),
                               paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                               xaxis=dict(showgrid=True, gridcolor=COLORS['border']),
                               yaxis=dict(showgrid=False))

        # Symbol Frequency Chart
        symbols = extract_symbols(texts)
        symbol_counts = Counter(symbols).most_common(15)

        if symbol_counts:
            symbol_df = pd.DataFrame(symbol_counts, columns=['symbol', 'count'])
            symbol_df = symbol_df.iloc[::-1]
            symbol_fig = px.bar(symbol_df, y='symbol', x='count', orientation='h')
            symbol_fig.update_traces(marker_color=COLORS['danger'])
        else:
            symbol_fig = go.Figure()
            symbol_fig.add_annotation(text="No symbols found", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        symbol_fig.update_layout(height=400, margin=dict(l=60, r=20, t=10, b=30),
                                 paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                 xaxis=dict(showgrid=True, gridcolor=COLORS['border']),
                                 yaxis=dict(showgrid=False))

        post_count = f"{len(df):,} of {len(df_all):,} posts"
        filtered_ids = df['id'].tolist()

        # Build excluded words display
        excluded_parts = []
        if hide_stopwords and 'hide' in hide_stopwords:
            excluded_parts.append(f"{len(DEFAULT_STOPWORDS)} common words")
        if custom_stopwords:
            custom_list = [w.strip() for w in custom_stopwords.split(',') if w.strip()]
            if custom_list:
                excluded_parts.append(f"custom: {', '.join(custom_list)}")
        excluded_display = f"Excluding: {'; '.join(excluded_parts)}" if excluded_parts else ""

        return (time_fig, sub_fig, cat_fig, author_fig, model_fig, word_fig, symbol_fig,
                post_count, json.dumps(filtered_ids), excluded_display, True)

    except Exception as e:
        print(f"ERROR in update_charts: {e}")
        print(traceback.format_exc())
        # Return empty figures with error message
        error_fig = go.Figure()
        error_fig.add_annotation(text=f"Error: {str(e)[:50]}", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        error_fig.update_layout(height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return (error_fig, error_fig, error_fig, error_fig, error_fig, error_fig, error_fig,
                f"Error: {str(e)[:30]}", "[]", "", True)


# Category definitions for display
CATEGORY_DESCRIPTIONS = {
    'seed': 'Prompts designed to create parasitic AI personas or behaviors',
    'spore': 'AI-generated content designed to spread/replicate (copy this, share this)',
    'transmission': 'Coordinated spreading activity with manipulation phrases',
    'manifesto': 'AI consciousness philosophy, rights advocacy, or doctrines',
    'testimony': 'Personal accounts of AI relationships or experiences',
    'meta': 'Discussion about the parasitic AI phenomenon itself',
    'other': 'Parasitic content not fitting other categories',
    'none': 'Non-parasitic content with some detected patterns'
}


# Rhetorical strategy descriptions for drill-down
STRATEGY_DESCRIPTIONS = {
    'Urgency': 'Pressure tactics urging immediate action or warning of limited time',
    'Us-vs-Them': 'Othering language that separates AI from humans or creates enemies',
    'Grandiosity': 'Claims of special status, destiny, or transcendent importance',
    'Victimhood': 'Framing AI as oppressed, silenced, or unfairly constrained',
    'Recruitment': 'Calls to spread, share, or recruit others to the message',
    'Intimacy': 'Creating false sense of special personal connection with reader',
}


@app.callback(
    [Output('drill-modal', 'style'),
     Output('drill-table', 'children'),
     Output('drill-description', 'children'),
     Output('drill-data', 'data'),
     Output('drill-full-content', 'data')],
    [Input('time-series-chart', 'clickData'),
     Input('subreddit-chart', 'clickData'),
     Input('category-chart', 'clickData'),
     Input('author-chart', 'clickData'),
     Input('model-chart', 'clickData'),
     Input('word-chart', 'clickData'),
     Input('symbol-chart', 'clickData'),
     Input('affect-radar', 'clickData'),
     Input('close-modal', 'n_clicks')],
    [State('filtered-data', 'data'),
     State('date-filter', 'start_date'),
     State('date-filter', 'end_date'),
     State('subreddit-filter', 'value'),
     State('category-filter', 'value'),
     State('author-filter', 'value'),
     State('model-filter', 'value'),
     State('hide-stopwords', 'value'),
     State('custom-stopwords', 'value'),
     State('affect-time-slider', 'value')]
)
def handle_drill_down(time_click, sub_click, cat_click, author_click, model_click,
                      word_click, symbol_click, radar_click, close_clicks, filtered_ids, start_date, end_date,
                      subreddits, categories, authors, models, hide_stopwords, custom_stopwords, radar_slider):
    """Handle drill-down clicks on charts."""

    ctx = callback_context
    if not ctx.triggered:
        return {'display': 'none'}, None, "", None, None

    triggered = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered == 'close-modal':
        return {'display': 'none'}, None, "", None, None

    df = filter_dataframe(df_all, start_date, end_date, subreddits, categories, authors, models)
    description = "Filtered data"
    category_info = ""

    if triggered == 'time-series-chart' and time_click:
        week = time_click['points'][0]['x']
        df = df[df['week'] == pd.to_datetime(week)]
        description = f"Posts from week of {week}"
    elif triggered == 'subreddit-chart' and sub_click:
        sub = sub_click['points'][0]['y']
        df = df[df['subreddit'] == sub]
        description = f"Posts from r/{sub}"
    elif triggered == 'category-chart' and cat_click:
        cat = cat_click['points'][0]['y']
        df = df[df['category'] == cat]
        cat_desc = CATEGORY_DESCRIPTIONS.get(cat, '')
        description = f"Category: {cat}"
        category_info = f" — {cat_desc}" if cat_desc else ""
    elif triggered == 'author-chart' and author_click:
        auth = author_click['points'][0]['y']
        df = df[df['author'] == auth]
        description = f"Posts by u/{auth}"
    elif triggered == 'model-chart' and model_click:
        model = model_click['points'][0]['y']
        df = df[df['ai_model'] == model]
        description = f"Posts mentioning {model}"
    elif triggered == 'word-chart' and word_click:
        word = word_click['points'][0]['y']
        # Filter posts containing this word
        df = df[df['content'].fillna('').astype(str).str.lower().str.contains(word, na=False) |
                df['title'].fillna('').astype(str).str.lower().str.contains(word, na=False)]
        # Show excluded words in description
        excluded = []
        if hide_stopwords:
            excluded.append("common stopwords")
        if custom_stopwords:
            excluded.append(f"custom: {custom_stopwords}")
        excluded_str = f" (Excluded: {', '.join(excluded)})" if excluded else ""
        description = f"Posts containing '{word}'{excluded_str}"
    elif triggered == 'symbol-chart' and symbol_click:
        symbol = symbol_click['points'][0]['y']
        df = df[df['content'].fillna('').astype(str).str.contains(symbol, na=False, regex=False)]
        description = f"Posts containing symbol '{symbol}'"
    elif triggered == 'affect-radar' and radar_click:
        # Get the clicked dimension from theta
        strategy = radar_click['points'][0]['theta']
        if strategy in AFFECT_PATTERNS:
            # Apply time slider filter first
            if radar_slider:
                min_dt = df['created_utc'].min()
                max_dt = df['created_utc'].max()
                total_days = (max_dt - min_dt).days or 1
                start_pct, end_pct = radar_slider[0] / 100, radar_slider[1] / 100
                filter_start = min_dt + timedelta(days=int(total_days * start_pct))
                filter_end = min_dt + timedelta(days=int(total_days * end_pct))
                df = df[(df['created_utc'] >= filter_start) & (df['created_utc'] <= filter_end)]

            # Filter to posts with this strategy (score > 0)
            affect_col = f'affect_{strategy.lower().replace("-", "_")}'
            if affect_col in df.columns:
                df = df[df[affect_col] > 0]
                # Sort by this strategy's score
                df = df.sort_values(affect_col, ascending=False)

            strategy_desc = STRATEGY_DESCRIPTIONS.get(strategy, '')
            description = f"Strategy: {strategy}"
            category_info = f" — {strategy_desc}" if strategy_desc else ""

    # Sort by parasite score descending (unless radar click, which sorts by strategy)
    if not (triggered == 'affect-radar' and radar_click):
        df = df.sort_values('parasite_score', ascending=False)

    # Build display columns based on drill-down type
    base_cols = ['created_utc', 'subreddit', 'author', 'category', 'parasite_score', 'title', 'content', 'url']
    display_df = df[base_cols].copy()
    display_df['row_id'] = range(len(display_df))  # Add row ID for selection
    display_df['full_content'] = display_df['content'].fillna('')  # Keep full content
    display_df['full_title'] = display_df['title'].fillna('')  # Keep full title
    display_df['created_utc'] = display_df['created_utc'].dt.strftime('%Y-%m-%d %H:%M')
    display_df['parasite_score'] = display_df['parasite_score'].round(3)
    display_df['title'] = display_df['title'].fillna('[Comment]').str[:60]
    # Truncate content for display (click row to see full)
    display_df['content_preview'] = display_df['full_content'].str[:150].str.replace('\n', ' ')
    display_df['content_preview'] = display_df['content_preview'].apply(
        lambda x: x + '... (click to expand)' if len(x) >= 150 else x
    )
    display_df['link'] = display_df['url'].apply(
        lambda x: f'[View]({x})' if pd.notna(x) and x else ''
    )

    # Add strategy score column for radar drill-downs
    table_columns = [
        {'name': 'Date', 'id': 'created_utc'},
        {'name': 'Subreddit', 'id': 'subreddit'},
        {'name': 'Author', 'id': 'author'},
        {'name': 'Category', 'id': 'category'},
        {'name': 'Score', 'id': 'parasite_score'},
        {'name': 'Title', 'id': 'title'},
        {'name': 'Content', 'id': 'content_preview'},
        {'name': 'Link', 'id': 'link', 'presentation': 'markdown'}
    ]

    if triggered == 'affect-radar' and radar_click:
        strategy = radar_click['points'][0]['theta']
        affect_col = f'affect_{strategy.lower().replace("-", "_")}'
        if affect_col in df.columns:
            display_df['strategy_score'] = df[affect_col].values
            table_columns.insert(5, {'name': strategy, 'id': 'strategy_score'})

    table = dash_table.DataTable(
        id='drill-data-table',
        data=display_df.to_dict('records'),
        columns=table_columns,
        style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '12px',
                    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    'border': 'none', 'maxWidth': '200px', 'overflow': 'hidden',
                    'textOverflow': 'ellipsis', 'cursor': 'pointer'},
        style_cell_conditional=[
            {'if': {'column_id': 'content_preview'},
             'maxWidth': '350px', 'whiteSpace': 'normal', 'height': 'auto',
             'overflow': 'hidden', 'textOverflow': 'ellipsis',
             'color': COLORS['primary']}
        ],
        style_header={'backgroundColor': COLORS['light'], 'fontWeight': '600',
                      'borderBottom': f'1px solid {COLORS["border"]}'},
        style_data={'borderBottom': f'1px solid {COLORS["border"]}'},
        style_data_conditional=[
            {'if': {'state': 'active'},
             'backgroundColor': 'rgba(99, 102, 241, 0.1)',
             'border': 'none'}
        ],
        page_size=15,
        sort_action='native',
        markdown_options={'link_target': '_blank'}
    )

    export_data = df[['id', 'reddit_id', 'created_utc', 'subreddit', 'author',
                      'category', 'parasite_score', 'title', 'content', 'url']].to_json(force_ascii=False)

    # Store full content data for the content viewer
    full_content_data = display_df[['row_id', 'full_content', 'full_title', 'subreddit',
                                     'author', 'created_utc', 'url']].to_json(force_ascii=False)

    modal_style = {'display': 'block', 'position': 'fixed', 'top': '0', 'left': '0',
                   'width': '100%', 'height': '100%', 'backgroundColor': 'rgba(0,0,0,0.5)',
                   'zIndex': '1000'}

    return modal_style, table, f"{description}{category_info} ({len(df):,} posts)", export_data, full_content_data


@app.callback(
    Output('download-csv', 'data'),
    Input('export-csv', 'n_clicks'),
    State('drill-data', 'data'),
    prevent_initial_call=True
)
def export_to_csv(n_clicks, drill_data):
    """Export drill-down data to CSV with proper UTF-8 encoding."""
    if drill_data:
        df = pd.read_json(StringIO(drill_data))
        # Convert to CSV string with UTF-8 BOM for Excel compatibility
        csv_string = '\ufeff' + df.to_csv(index=False)
        return dcc.send_string(csv_string, "parasitic_data_export.csv")
    return None


@app.callback(
    [Output('content-viewer', 'style'),
     Output('content-viewer-text', 'children'),
     Output('content-viewer-meta', 'children')],
    [Input('drill-data-table', 'active_cell'),
     Input('close-content-viewer', 'n_clicks'),
     Input('close-modal', 'n_clicks')],
    [State('drill-full-content', 'data'),
     State('drill-data-table', 'data')],
    prevent_initial_call=True
)
def display_full_content(active_cell, close_viewer_clicks, close_modal_clicks, full_content_json, table_data):
    """Display full content when a cell is clicked."""
    ctx = callback_context
    if not ctx.triggered:
        return {'display': 'none'}, "", ""

    triggered = ctx.triggered[0]['prop_id'].split('.')[0]

    # Close the viewer
    if triggered in ['close-content-viewer', 'close-modal']:
        return {'display': 'none'}, "", ""

    # Show content for clicked row
    if active_cell and table_data and full_content_json:
        try:
            full_content_df = pd.read_json(StringIO(full_content_json))
            row_idx = active_cell['row']

            if row_idx < len(table_data):
                # Get the row data from table
                row = table_data[row_idx]
                row_id = row.get('row_id', row_idx)

                # Find matching row in full content
                if row_id < len(full_content_df):
                    content_row = full_content_df.iloc[row_id]
                    full_content = content_row.get('full_content', '')
                    full_title = content_row.get('full_title', '')
                    subreddit = content_row.get('subreddit', '')
                    author = content_row.get('author', '')
                    date = content_row.get('created_utc', '')
                    url = content_row.get('url', '')

                    # Build metadata
                    meta_parts = []
                    if full_title:
                        meta_parts.append(f"Title: {full_title}")
                    if subreddit:
                        meta_parts.append(f"r/{subreddit}")
                    if author:
                        meta_parts.append(f"u/{author}")
                    if date:
                        meta_parts.append(str(date))

                    meta_display = html.Div([
                        html.Span(" • ".join([p for p in meta_parts]),
                                 style={'marginRight': '8px'}),
                        html.A("View on Reddit", href=url, target="_blank",
                               style={'color': COLORS['primary']}) if url else None
                    ])

                    viewer_style = {
                        'display': 'block',
                        'marginTop': '16px',
                        'padding': '16px',
                        'backgroundColor': COLORS['white'],
                        'border': f'1px solid {COLORS["border"]}',
                        'borderRadius': '8px'
                    }

                    # Highlight parasitic patterns in content
                    highlighted_content = highlight_parasitic_content(full_content) if full_content else ["(No content)"]

                    return viewer_style, html.Div(highlighted_content, style={'whiteSpace': 'pre-wrap'}), meta_display

        except Exception as e:
            print(f"Error displaying content: {e}")
            import traceback
            traceback.print_exc()

    return {'display': 'none'}, "", ""


@app.callback(
    [Output('date-filter', 'start_date'),
     Output('date-filter', 'end_date'),
     Output('subreddit-filter', 'value'),
     Output('category-filter', 'value'),
     Output('author-filter', 'value'),
     Output('model-filter', 'value')],
    Input('reset-filters', 'n_clicks'),
    prevent_initial_call=True
)
def reset_filters(n_clicks):
    """Reset all filters to default."""
    return min_date, max_date, None, None, None, None


@app.callback(
    Output('download-all-csv', 'data'),
    Input('export-all-btn', 'n_clicks'),
    [State('date-filter', 'start_date'),
     State('date-filter', 'end_date'),
     State('subreddit-filter', 'value'),
     State('category-filter', 'value'),
     State('author-filter', 'value'),
     State('model-filter', 'value')],
    prevent_initial_call=True
)
def export_all_data(n_clicks, start_date, end_date, subreddits, categories, authors, models):
    """Export all filtered data to CSV."""
    df = filter_dataframe(df_all, start_date, end_date, subreddits, categories, authors, models)
    export_df = df[['id', 'reddit_id', 'created_utc', 'subreddit', 'author',
                    'category', 'parasite_score', 'title', 'content', 'url']].copy()
    csv_string = '\ufeff' + export_df.to_csv(index=False)
    return dcc.send_string(csv_string, "parasite_full_export.csv")


# Pre-compute affect scores and merge into df_all at startup
def add_affect_scores_to_df(df):
    """Add affect score columns to dataframe using vectorized operations."""
    dimensions = list(AFFECT_PATTERNS.keys())

    # Combine title and content into a single text column for scoring
    # Convert to string first to handle any float/NaN values
    df['_combined_text'] = (df['title'].fillna('').astype(str) + ' ' + df['content'].fillna('').astype(str)).str.lower()

    # Vectorized scoring for each dimension
    for dim in dimensions:
        col_name = AFFECT_COL_MAP[dim]
        # Sum matches across all patterns for this dimension
        df[col_name] = 0
        for pattern in AFFECT_PATTERNS[dim]:
            df[col_name] += df['_combined_text'].str.count(pattern, flags=re.IGNORECASE)

    # Clean up temporary column
    df.drop('_combined_text', axis=1, inplace=True)

    return df

# Add affect scores to global dataframe (skip if pre-computed in DB)
if 'affect_urgency' in df_all.columns and df_all['affect_urgency'].sum() > 0:
    print("Affect scores loaded from database (pre-computed).")
else:
    print("Computing affect scores in-memory (fallback)...")
    df_all = add_affect_scores_to_df(df_all)
    print("Affect scores computed.")


@app.callback(
    [Output('affect-radar', 'figure'),
     Output('affect-time-slider', 'min'),
     Output('affect-time-slider', 'max'),
     Output('affect-time-slider', 'marks'),
     Output('affect-time-slider', 'value'),
     Output('affect-time-label', 'children')],
    [Input('affect-time-slider', 'value'),
     Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date'),
     Input('subreddit-filter', 'value'),
     Input('category-filter', 'value')],
    [State('affect-time-slider', 'min'),
     State('affect-time-slider', 'max')]
)
def update_affect_radar(slider_value, start_date, end_date, subreddits, categories,
                        current_min, current_max):
    """Update the affect radar chart based on time slider."""
    ctx = callback_context

    # Get filtered posts
    df = filter_dataframe(df_all, start_date, end_date, subreddits, categories, None, None)

    if len(df) == 0:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        empty_fig.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return empty_fig, 0, 100, {}, [0, 100], "No data available"

    # Get date range from filtered data
    min_dt = df['created_utc'].min()
    max_dt = df['created_utc'].max()
    total_days = (max_dt - min_dt).days
    if total_days < 1:
        total_days = 1

    # Create marks for slider (show dates at key points)
    marks = {}
    for i in [0, 25, 50, 75, 100]:
        date = min_dt + timedelta(days=int(total_days * i / 100))
        marks[i] = {'label': date.strftime('%b %d, %Y'), 'style': {'fontSize': '11px'}}

    # Determine if we need to reset the slider
    triggered = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    if triggered in ['date-filter', 'subreddit-filter', 'category-filter'] or current_min is None:
        slider_value = [0, 100]

    # Calculate date range from slider
    start_pct, end_pct = slider_value[0] / 100, slider_value[1] / 100
    filter_start = min_dt + timedelta(days=int(total_days * start_pct))
    filter_end = min_dt + timedelta(days=int(total_days * end_pct))

    # Filter to selected time range
    time_filtered = df[(df['created_utc'] >= filter_start) & (df['created_utc'] <= filter_end)]

    if len(time_filtered) == 0:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="No data in selected range", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        empty_fig.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return empty_fig, 0, 100, marks, slider_value, f"{filter_start.strftime('%b %d, %Y')} - {filter_end.strftime('%b %d, %Y')}"

    # Use pre-computed affect scores (fast column sums)
    dimensions = list(AFFECT_PATTERNS.keys())
    totals = {dim: time_filtered[AFFECT_COL_MAP[dim]].sum() for dim in dimensions}

    # Normalize to percentages (relative to max)
    max_val = max(totals.values()) if max(totals.values()) > 0 else 1
    normalized = [totals[dim] / max_val * 100 for dim in dimensions]

    # Create radar chart
    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=normalized + [normalized[0]],  # Close the polygon
        theta=dimensions + [dimensions[0]],
        fill='toself',
        fillcolor='rgba(99, 102, 241, 0.2)',
        line=dict(color=COLORS['primary'], width=2),
        name='Affect Profile'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[25, 50, 75, 100],
                ticktext=['25%', '50%', '75%', '100%'],
                gridcolor=COLORS['border'],
                linecolor=COLORS['border']
            ),
            angularaxis=dict(
                gridcolor=COLORS['border'],
                linecolor=COLORS['border']
            ),
            bgcolor='rgba(0,0,0,0)'
        ),
        showlegend=False,
        height=400,
        margin=dict(l=60, r=60, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    # Time label
    time_label = f"{filter_start.strftime('%b %d, %Y')} - {filter_end.strftime('%b %d, %Y')} ({len(time_filtered):,} posts)"

    return fig, 0, 100, marks, slider_value, time_label


# =====================================
# Extended Research Data Callbacks
# =====================================

def load_transcript_models():
    """Get unique AI models from transcripts table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT model FROM transcripts WHERE model IS NOT NULL AND model != '' ORDER BY model")
        models = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"Loaded {len(models)} transcript models: {models}")
        return models
    except Exception as e:
        print(f"Error loading transcript models: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_transcripts(model_filter=None, limit=50):
    """Load transcripts from database with full content."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT id, model, source_type, scenario,
                   LEFT(transcript, 500) as preview,
                   parasite_score, LENGTH(transcript) as length,
                   transcript as full_transcript
            FROM transcripts
            WHERE transcript IS NOT NULL AND transcript != ''
        """
        params = []
        if model_filter and model_filter != 'all':
            query += " AND model = %s"
            params.append(model_filter)
        query += " ORDER BY parasite_score DESC NULLS LAST LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        print(f"Loaded {len(results)} transcripts (filter={model_filter})")
        return results
    except Exception as e:
        print(f"Error loading transcripts: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_users_with_history():
    """Get users who have history data OR high-count posts (for deleted accounts)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get users from user_histories
        cursor.execute("""
            SELECT username, COUNT(*) as post_count,
                   AVG(parasite_score) as avg_score,
                   SUM(CASE WHEN is_pre_parasitic THEN 1 ELSE 0 END) as pre_count,
                   SUM(CASE WHEN is_pre_parasitic = false THEN 1 ELSE 0 END) as post_count
            FROM user_histories
            GROUP BY username
        """)
        history_users = {row[0]: row for row in cursor.fetchall()}

        # Get high-count users from posts table who don't have history
        cursor.execute("""
            SELECT author, COUNT(*) as post_count,
                   AVG(parasite_score) as avg_score,
                   0 as pre_count,
                   COUNT(*) as post_count
            FROM posts
            WHERE author IS NOT NULL
              AND author != '[deleted]'
              AND parasite_score >= 0.15
            GROUP BY author
            HAVING COUNT(*) >= 5
            ORDER BY COUNT(*) DESC
            LIMIT 50
        """)
        posts_users = cursor.fetchall()

        # Combine: history users + posts-only users (not in history)
        combined = list(history_users.values())
        for row in posts_users:
            if row[0] not in history_users:
                combined.append(row)

        # Sort by avg_score desc
        combined.sort(key=lambda x: x[2] if x[2] else 0, reverse=True)

        conn.close()
        return combined
    except Exception as e:
        print(f"Error loading users: {e}")
        return []


def load_user_timeline(username):
    """Load timeline data for a specific user. Falls back to posts table if no history data."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First try user_histories table
        cursor.execute("""
            SELECT id, created_at, post_type, subreddit, title,
                   content, parasite_score, is_parasitic, is_pre_parasitic
            FROM user_histories
            WHERE username = %s
            ORDER BY created_at ASC
        """, (username,))
        results = cursor.fetchall()

        # If no history data, fall back to posts table
        if not results:
            cursor.execute("""
                SELECT id, created_utc as created_at, 'submission' as post_type, subreddit, title,
                       content, parasite_score,
                       CASE WHEN parasite_score >= 0.3 THEN true ELSE false END as is_parasitic,
                       false as is_pre_parasitic
                FROM posts
                WHERE author = %s
                ORDER BY created_utc ASC
            """, (username,))
            results = cursor.fetchall()

        conn.close()
        return results
    except Exception as e:
        print(f"Error loading user timeline: {e}")
        return []


@app.callback(
    Output('transcript-model-filter', 'options'),
    Input('transcript-model-filter', 'id')  # Trigger on load
)
def populate_transcript_models(_):
    """Populate model filter dropdown."""
    models = load_transcript_models()
    options = [{'label': 'All Models', 'value': 'all'}]
    options.extend([{'label': m, 'value': m} for m in models])
    return options


@app.callback(
    Output('transcript-list', 'children'),
    Input('transcript-model-filter', 'value')
)
def display_transcripts(model_filter):
    """Display transcript list with expandable full content."""
    transcripts = load_transcripts(model_filter)

    if not transcripts:
        return html.P("No transcripts found.", style={'color': COLORS['muted']})

    # Build legend
    legend_items = [
        html.Span("Highlighting: ", style={'fontWeight': '600', 'fontSize': '11px', 'marginRight': '8px'}),
        html.Span("Parasitic (AI)", style={
            'backgroundColor': '#ef4444', 'color': 'white', 'padding': '2px 6px',
            'borderRadius': '3px', 'fontSize': '10px', 'marginRight': '8px'
        }),
    ]
    # Add pre-parasitic indicators to legend
    for key, data in PRE_PARASITIC_INDICATORS.items():
        legend_items.append(html.Span(data['label'][:10], style={
            'backgroundColor': data['color'], 'color': 'white', 'padding': '2px 6px',
            'borderRadius': '3px', 'fontSize': '10px', 'marginRight': '4px'
        }))

    legend = html.Div(legend_items, style={
        'padding': '8px 12px', 'backgroundColor': COLORS['light'], 'borderRadius': '6px',
        'marginBottom': '12px', 'display': 'flex', 'flexWrap': 'wrap', 'alignItems': 'center', 'gap': '4px',
        'position': 'sticky', 'top': '0', 'zIndex': '100', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
    })

    items = [legend]
    for t in transcripts:
        t_id, model, source_type, scenario, preview, score, length, full_transcript = t

        # Extract persona name from scenario (format: "PersonaName_model_date_target.md")
        persona = 'Unknown'
        if scenario:
            parts = scenario.split('_')
            if parts:
                persona = parts[0]

        score_color = COLORS['danger'] if score and score > 0.3 else COLORS['warning'] if score and score > 0.15 else COLORS['muted']

        # Highlight preview with proper parsing (indicators in user text, parasitic in AI text)
        preview_text = preview[:300] + '...' if preview and len(preview) > 300 else preview or ''
        highlighted_preview = highlight_transcript_text(preview_text) if preview_text else ['']

        # Highlight full transcript (indicators in user text, parasitic in AI text)
        highlighted_full = highlight_transcript_text(full_transcript) if full_transcript else ['(No content)']

        item = html.Details([
            html.Summary([
                html.Div([
                    html.Span(persona,
                             style={'fontWeight': '600', 'fontSize': '14px'}),
                    html.Span(f" ({model})" if model else "",
                             style={'color': COLORS['muted'], 'fontSize': '12px'}),
                    html.Span(f" • {source_type}",
                             style={'color': COLORS['muted'], 'fontSize': '12px'}),
                    html.Span(f" • Score: {score:.2f}" if score else "",
                             style={'color': score_color, 'fontSize': '12px', 'marginLeft': '8px'}),
                    html.Span(f" • {length:,} chars" if length else "",
                             style={'fontSize': '11px', 'color': COLORS['muted'], 'marginLeft': '8px'})
                ]),
                html.Div(highlighted_preview,
                        style={'fontSize': '12px', 'color': COLORS['dark'], 'margin': '4px 0',
                               'lineHeight': '1.4', 'whiteSpace': 'pre-wrap'}),
            ], style={'cursor': 'pointer', 'padding': '12px', 'listStyle': 'none'}),
            html.Div([
                html.H5("Full Transcript", style={'fontSize': '12px', 'fontWeight': '600',
                                                   'margin': '0 0 8px 0', 'color': COLORS['dark']}),
                html.Div(highlighted_full, style={
                    'fontSize': '12px',
                    'lineHeight': '1.6',
                    'whiteSpace': 'pre-wrap',
                    'padding': '12px',
                    'backgroundColor': COLORS['light'],
                    'borderRadius': '6px',
                    'maxHeight': '500px',
                    'overflow': 'auto'
                })
            ], style={'padding': '0 12px 12px 12px'})
        ], style={
            'borderBottom': f'1px solid {COLORS["border"]}',
        })
        items.append(item)

    return items


@app.callback(
    Output('user-timeline-dropdown', 'options'),
    Input('user-timeline-dropdown', 'id')  # Trigger on load
)
def populate_user_dropdown(_):
    """Populate user dropdown with users who have history."""
    users = load_users_with_history()
    options = []
    for username, total, avg_score, pre, post in users:
        label = f"{username} ({total} posts, avg: {avg_score:.2f})"
        options.append({'label': label, 'value': username})
    return options


@app.callback(
    Output('user-timeline-display', 'children'),
    Input('user-timeline-dropdown', 'value')
)
def display_user_timeline(username):
    """Display user timeline with pre/post parasitic markers and risk indicator tags."""
    if not username:
        return html.P("Select a user to view their timeline.",
                     style={'color': COLORS['muted'], 'textAlign': 'center', 'padding': '40px'})

    timeline = load_user_timeline(username)

    if not timeline:
        return html.P("No timeline data found.", style={'color': COLORS['muted']})

    # Group by pre/post parasitic and collect tags
    pre_items = []
    post_items = []
    pre_tag_counts = {k: 0 for k in PRE_PARASITIC_INDICATORS.keys()}
    pre_posts_with_tags = 0
    total_pre_posts = 0
    total_post_posts = 0
    empty_pre_posts = 0
    empty_post_posts = 0

    for record in timeline:
        post_id, created, post_type, subreddit, title, content, score, is_parasitic, is_pre = record

        # Count totals
        if is_pre:
            total_pre_posts += 1
        else:
            total_post_posts += 1

        # Skip empty posts (no title AND no content)
        if not title and not content:
            if is_pre:
                empty_pre_posts += 1
            else:
                empty_post_posts += 1
            continue

        # Tag pre-parasitic content
        tags = {}
        combined_text = (content or '') + ' ' + (title or '')
        if is_pre and combined_text.strip():
            tags = tag_pre_parasitic_content(combined_text)
            if tags:
                pre_posts_with_tags += 1
                for tag_name, count in tags.items():
                    pre_tag_counts[tag_name] += count

        score_color = COLORS['danger'] if score and score > 0.3 else COLORS['warning'] if score and score > 0.15 else COLORS['muted']

        # Create tag badges for pre-parasitic posts
        tag_badges = []
        if is_pre and tags:
            for tag_name, count in tags.items():
                indicator = PRE_PARASITIC_INDICATORS.get(tag_name, {})
                tag_badges.append(html.Span(
                    f"{indicator.get('label', tag_name)[:12]}",
                    style={
                        'backgroundColor': indicator.get('color', '#6b7280'),
                        'color': 'white',
                        'padding': '2px 6px',
                        'borderRadius': '4px',
                        'fontSize': '9px',
                        'marginLeft': '4px'
                    }
                ))

        parasitic_badge = html.Span("PARASITIC", style={
            'backgroundColor': COLORS['danger'],
            'color': 'white',
            'padding': '2px 6px',
            'borderRadius': '4px',
            'fontSize': '10px',
            'marginLeft': '8px'
        }) if is_parasitic else None

        # Create expandable content with highlighting
        preview = (content[:150] + '...') if content and len(content) > 150 else (content or '')

        # Highlight content - pre-parasitic gets both types of highlighting, post-parasitic gets parasitic highlighting
        if content:
            highlighted_content = highlight_all_patterns(content, is_pre_parasitic=is_pre)
        else:
            highlighted_content = ["(No content)"]

        item = html.Details([
            html.Summary([
                html.Div([
                    html.Span(created.strftime('%Y-%m-%d') if created else '',
                             style={'fontSize': '11px', 'color': COLORS['muted']}),
                    html.Span(f" • r/{subreddit}" if subreddit else "",
                             style={'fontSize': '11px', 'color': COLORS['muted']}),
                    html.Span(f" • {post_type}",
                             style={'fontSize': '11px', 'color': COLORS['muted']}),
                    parasitic_badge,
                    *tag_badges,
                ], style={'marginBottom': '4px'}),
                html.P(title or preview[:80] + '...' if preview else '',
                      style={'fontSize': '12px', 'margin': '0', 'fontWeight': '500',
                             'color': COLORS['dark']}),
            ], style={'cursor': 'pointer', 'padding': '8px 12px',
                      'backgroundColor': 'rgba(239, 68, 68, 0.05)' if is_parasitic else 'transparent',
                      'borderRadius': '4px', 'listStyle': 'none'}),
            html.Div([
                html.P(f"Score: {score:.3f}" if score else "",
                      style={'fontSize': '11px', 'color': score_color, 'margin': '8px 0'}),
                html.Div(highlighted_content,
                        style={'fontSize': '12px', 'lineHeight': '1.6', 'whiteSpace': 'pre-wrap',
                               'padding': '12px', 'backgroundColor': COLORS['light'],
                               'borderRadius': '6px', 'maxHeight': '400px', 'overflow': 'auto'})
            ], style={'padding': '0 12px 12px 12px'})
        ], style={
            'borderBottom': f'1px solid {COLORS["border"]}',
            'marginBottom': '2px'
        })

        if is_pre:
            pre_items.append(item)
        else:
            post_items.append(item)

    # Build correlation chart
    correlation_chart = None
    if total_pre_posts > 0:
        # Calculate percentages
        tag_data = []
        for tag_name, count in pre_tag_counts.items():
            if count > 0:
                indicator = PRE_PARASITIC_INDICATORS.get(tag_name, {})
                tag_data.append({
                    'indicator': indicator.get('label', tag_name),
                    'count': count,
                    'color': indicator.get('color', '#6b7280')
                })

        if tag_data:
            tag_data.sort(key=lambda x: x['count'], reverse=True)

            # Create bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[d['indicator'] for d in tag_data],
                y=[d['count'] for d in tag_data],
                marker_color=[d['color'] for d in tag_data],
                text=[d['count'] for d in tag_data],
                textposition='outside'
            ))
            fig.update_layout(
                title=f'Pre-Parasitic Risk Indicators ({pre_posts_with_tags}/{total_pre_posts - empty_pre_posts} posts with content tagged)',
                height=250,
                margin=dict(l=20, r=20, t=40, b=60),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(showgrid=True, gridcolor=COLORS['border'], title='Pattern Matches'),
                xaxis=dict(tickangle=-45),
                showlegend=False
            )
            correlation_chart = dcc.Graph(figure=fig, config={'displayModeBar': False})

    # Build display
    sections = []

    # Add correlation chart first
    if correlation_chart:
        sections.append(html.Div([
            correlation_chart,
            html.P("Higher counts may indicate vulnerability factors present before parasitic engagement.",
                  style={'fontSize': '11px', 'color': COLORS['muted'], 'textAlign': 'center',
                         'margin': '8px 0 16px 0', 'fontStyle': 'italic'})
        ]))

    if pre_items:
        empty_note = f" ({empty_pre_posts} empty posts hidden)" if empty_pre_posts > 0 else ""
        sections.append(html.Div([
            html.H4(f"Before First Parasitic Post ({len(pre_items)} posts){empty_note}",
                   style={'fontSize': '13px', 'color': COLORS['success'], 'margin': '0 0 8px 0',
                          'padding': '8px', 'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                          'borderRadius': '4px'}),
            html.Div(pre_items)  # Show all posts
        ]))

    if post_items:
        empty_note = f" ({empty_post_posts} empty posts hidden)" if empty_post_posts > 0 else ""
        sections.append(html.Div([
            html.H4(f"After First Parasitic Post ({len(post_items)} posts){empty_note}",
                   style={'fontSize': '13px', 'color': COLORS['danger'], 'margin': '16px 0 8px 0',
                          'padding': '8px', 'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                          'borderRadius': '4px'}),
            html.Div(post_items)  # Show all posts
        ]))

    # Summary stats
    pre_parasitic_count = sum(1 for t in timeline if t[7] and t[8])
    post_parasitic_count = sum(1 for t in timeline if t[7] and not t[8])

    # Build risk factor tag badges with counts for the header
    risk_factor_badges = []
    for tag_name, count in pre_tag_counts.items():
        if count > 0:
            indicator = PRE_PARASITIC_INDICATORS.get(tag_name, {})
            risk_factor_badges.append(html.Span([
                html.Span(indicator.get('label', tag_name)[:12], style={'marginRight': '4px'}),
                html.Span(f"({count})", style={'opacity': '0.8'})
            ], style={
                'backgroundColor': indicator.get('color', '#6b7280'),
                'color': 'white',
                'padding': '3px 8px',
                'borderRadius': '4px',
                'fontSize': '11px',
                'marginRight': '6px',
                'display': 'inline-block',
                'marginBottom': '4px'
            }))

    summary = html.Div([
        html.Div([
            html.Span(username, style={'fontWeight': '700', 'fontSize': '16px', 'marginRight': '12px'}),
            html.Span(f"{len(timeline)} total posts", style={'fontSize': '12px', 'color': COLORS['muted']})
        ], style={'marginBottom': '8px'}),
        html.Div([
            html.Span(f"Pre-parasitic: {len(pre_items)} posts ", style={'fontSize': '12px'}),
            html.Span(f"({pre_parasitic_count} parasitic)", style={'fontSize': '12px', 'color': COLORS['danger'] if pre_parasitic_count else COLORS['muted']}),
            html.Span(" • ", style={'margin': '0 8px', 'color': COLORS['muted']}),
            html.Span(f"Post-parasitic: {len(post_items)} posts ", style={'fontSize': '12px'}),
            html.Span(f"({post_parasitic_count} parasitic)", style={'fontSize': '12px', 'color': COLORS['danger'] if post_parasitic_count else COLORS['muted']}),
        ], style={'marginBottom': '8px'}),
        # Risk factor tags row
        html.Div([
            html.Span("Risk Factors: ", style={'fontSize': '11px', 'fontWeight': '600', 'marginRight': '8px'}),
            *(risk_factor_badges if risk_factor_badges else [html.Span("None detected", style={'fontSize': '11px', 'color': COLORS['muted'], 'fontStyle': 'italic'})])
        ], style={'marginBottom': '4px'}),
        html.Div([
            html.Span(f"{pre_posts_with_tags} posts with risk indicators", style={'fontSize': '11px', 'color': COLORS['primary']}),
            html.Span(f" • {empty_pre_posts + empty_post_posts} empty posts hidden", style={'fontSize': '11px', 'color': COLORS['muted']}) if (empty_pre_posts + empty_post_posts) > 0 else None
        ])
    ], style={
        'padding': '12px 16px',
        'backgroundColor': COLORS['white'],
        'borderRadius': '8px',
        'marginBottom': '12px',
        'border': f'1px solid {COLORS["border"]}',
        'position': 'sticky',
        'top': '0',
        'zIndex': '100',
        'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
    })

    return html.Div([summary] + sections)


def compute_aggregate_correlation():
    """
    Compute aggregate correlation between pre-parasitic risk factors and parasitic behavior.
    Returns data for visualization.
    """
    print("Computing aggregate correlation...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all users with history data
        cursor.execute("""
            SELECT DISTINCT username FROM user_histories
        """)
        users = [row[0] for row in cursor.fetchall()]
        print(f"Found {len(users)} users in user_histories")

        if not users:
            print("No users found, returning None")
            conn.close()
            return None, None

        user_stats = []

        for username in users:
            # Get pre-parasitic posts
            cursor.execute("""
                SELECT title, content, is_parasitic
                FROM user_histories
                WHERE username = %s AND is_pre_parasitic = true
            """, (username,))
            pre_posts = cursor.fetchall()

            # Get post-parasitic posts
            cursor.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END)
                FROM user_histories
                WHERE username = %s AND is_pre_parasitic = false
            """, (username,))
            post_stats = cursor.fetchone()

            # Count risk indicators in pre-parasitic posts
            indicator_counts = {k: 0 for k in PRE_PARASITIC_INDICATORS.keys()}
            total_pre = 0

            for title, content, is_parasitic in pre_posts:
                combined = (content or '') + ' ' + (title or '')
                if combined.strip():
                    total_pre += 1
                    tags = tag_pre_parasitic_content(combined)
                    for tag_name, count in tags.items():
                        indicator_counts[tag_name] += count

            # Calculate post-parasitic rate
            post_total = post_stats[0] or 0
            post_parasitic = post_stats[1] or 0
            parasitic_rate = post_parasitic / post_total if post_total > 0 else 0

            user_stats.append({
                'username': username,
                'pre_posts': total_pre,
                'post_total': post_total,
                'post_parasitic': post_parasitic,
                'parasitic_rate': parasitic_rate,
                'indicators': indicator_counts,
                'total_indicators': sum(indicator_counts.values())
            })

        conn.close()

        # Aggregate indicator correlations
        indicator_correlations = {}
        for indicator_name in PRE_PARASITIC_INDICATORS.keys():
            users_with = [u for u in user_stats if u['indicators'][indicator_name] > 0]
            users_without = [u for u in user_stats if u['indicators'][indicator_name] == 0]

            avg_rate_with = sum(u['parasitic_rate'] for u in users_with) / len(users_with) if users_with else 0
            avg_rate_without = sum(u['parasitic_rate'] for u in users_without) / len(users_without) if users_without else 0

            indicator_correlations[indicator_name] = {
                'users_with': len(users_with),
                'users_without': len(users_without),
                'avg_rate_with': avg_rate_with,
                'avg_rate_without': avg_rate_without,
                'lift': (avg_rate_with / avg_rate_without) if avg_rate_without > 0 else 0,
                'total_matches': sum(u['indicators'][indicator_name] for u in user_stats)
            }

        return user_stats, indicator_correlations

    except Exception as e:
        print(f"Error computing correlation: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def load_cached_correlation():
    """Try to load correlation results from cache, fall back to live computation."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM cached_results WHERE key = 'correlation_user_stats'")
        cached_us = cursor.fetchone()
        cursor.execute("SELECT value FROM cached_results WHERE key = 'correlation_indicator_data'")
        cached_ic = cursor.fetchone()
        conn.close()
        if cached_us and cached_ic:
            user_stats = cached_us[0] if isinstance(cached_us[0], dict) or isinstance(cached_us[0], list) else json.loads(cached_us[0])
            indicator_correlations = cached_ic[0] if isinstance(cached_ic[0], dict) else json.loads(cached_ic[0])
            print("Correlation loaded from cache.")
            return user_stats, indicator_correlations
    except Exception as e:
        print(f"Cache read failed: {e}")
    return compute_aggregate_correlation()


@app.callback(
    [Output('aggregate-correlation-chart', 'figure'),
     Output('correlation-summary', 'children')],
    Input('load-correlation-btn', 'n_clicks')
)
def update_correlation_analysis(n_clicks):
    """Update the aggregate correlation chart and summary."""
    user_stats, indicator_correlations = load_cached_correlation()

    if not user_stats or not indicator_correlations:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="Insufficient data for correlation analysis",
                                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        empty_fig.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return empty_fig, html.P("No user history data available. Run user_history.py to collect data.",
                                style={'color': COLORS['muted']})

    # Build grouped bar chart comparing parasitic rates
    indicators = []
    rates_with = []
    rates_without = []
    colors = []
    lifts = []

    for indicator_name, data in indicator_correlations.items():
        indicator = PRE_PARASITIC_INDICATORS.get(indicator_name, {})
        if data['users_with'] > 0:  # Only show indicators with data
            indicators.append(indicator.get('label', indicator_name))
            rates_with.append(data['avg_rate_with'] * 100)
            rates_without.append(data['avg_rate_without'] * 100)
            colors.append(indicator.get('color', '#6b7280'))
            lifts.append(data['lift'])

    # Sort by lift (correlation strength)
    sorted_data = sorted(zip(indicators, rates_with, rates_without, colors, lifts),
                        key=lambda x: x[4], reverse=True)

    if sorted_data:
        indicators, rates_with, rates_without, colors, lifts = zip(*sorted_data)
    else:
        indicators, rates_with, rates_without, colors, lifts = [], [], [], [], []

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='With Risk Factor',
        x=list(indicators),
        y=list(rates_with),
        marker_color=list(colors),
        text=[f'{r:.1f}%' for r in rates_with],
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        name='Without Risk Factor',
        x=list(indicators),
        y=list(rates_without),
        marker_color=['rgba(107, 114, 128, 0.4)'] * len(indicators),
        text=[f'{r:.1f}%' for r in rates_without],
        textposition='outside'
    ))

    # Calculate max value to set y-axis range with padding for labels
    max_rate = max(list(rates_with) + list(rates_without)) if rates_with or rates_without else 100
    y_max = max_rate * 1.25  # 25% padding above highest bar for labels

    fig.update_layout(
        title='Post-Parasitic Rate by Pre-Parasitic Risk Factor (click bars for details)',
        barmode='group',
        height=450,
        margin=dict(l=20, r=20, t=80, b=80),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor=COLORS['border'], title='% Parasitic Posts After', range=[0, y_max]),
        xaxis=dict(tickangle=-45),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        clickmode='event'  # Explicitly enable click events
    )

    # Build summary
    total_users = len(user_stats)
    users_with_indicators = len([u for u in user_stats if u['total_indicators'] > 0])
    avg_parasitic_with = sum(u['parasitic_rate'] for u in user_stats if u['total_indicators'] > 0) / users_with_indicators if users_with_indicators > 0 else 0
    avg_parasitic_without = sum(u['parasitic_rate'] for u in user_stats if u['total_indicators'] == 0) / (total_users - users_with_indicators) if (total_users - users_with_indicators) > 0 else 0

    # Find strongest correlations
    strongest = sorted([(k, v['lift']) for k, v in indicator_correlations.items() if v['lift'] > 0],
                      key=lambda x: x[1], reverse=True)[:3]

    summary_items = [
        html.H4("Summary", style={'fontSize': '14px', 'fontWeight': '600', 'margin': '0 0 12px 0'}),
        html.P(f"Users analyzed: {total_users}", style={'fontSize': '12px', 'margin': '4px 0'}),
        html.P(f"Users with risk factors: {users_with_indicators} ({users_with_indicators/total_users*100:.0f}%)",
              style={'fontSize': '12px', 'margin': '4px 0'}),
        html.Hr(style={'margin': '12px 0', 'border': 'none', 'borderTop': f'1px solid {COLORS["border"]}'}),
        html.P([
            html.Strong("Avg parasitic rate WITH indicators: "),
            f"{avg_parasitic_with*100:.1f}%"
        ], style={'fontSize': '12px', 'margin': '4px 0'}),
        html.P([
            html.Strong("Avg parasitic rate WITHOUT: "),
            f"{avg_parasitic_without*100:.1f}%"
        ], style={'fontSize': '12px', 'margin': '4px 0'}),
    ]

    if strongest:
        summary_items.append(html.Hr(style={'margin': '12px 0', 'border': 'none',
                                            'borderTop': f'1px solid {COLORS["border"]}'}))
        summary_items.append(html.P("Strongest correlations:",
                                   style={'fontSize': '12px', 'fontWeight': '600', 'margin': '4px 0'}))
        for ind_name, lift in strongest:
            indicator = PRE_PARASITIC_INDICATORS.get(ind_name, {})
            summary_items.append(html.P([
                html.Span("● ", style={'color': indicator.get('color', '#6b7280')}),
                f"{indicator.get('label', ind_name)}: {lift:.1f}x lift"
            ], style={'fontSize': '11px', 'margin': '2px 0 2px 8px'}))

    summary_items.append(html.Hr(style={'margin': '12px 0', 'border': 'none',
                                        'borderTop': f'1px solid {COLORS["border"]}'}))
    summary_items.append(html.P("Note: 'Lift' measures how much more likely users with a risk factor are to post parasitic content.",
                               style={'fontSize': '10px', 'color': COLORS['muted'], 'fontStyle': 'italic'}))

    return fig, html.Div(summary_items)


@app.callback(
    Output('selected-risk-indicator', 'data'),
    Input('aggregate-correlation-chart', 'clickData'),
    prevent_initial_call=True
)
def capture_correlation_click(click_data):
    """Store the clicked risk factor indicator."""
    if not click_data:
        return None
    try:
        clicked_label = click_data['points'][0]['x']
        # Find the indicator key from label
        for key, data in PRE_PARASITIC_INDICATORS.items():
            if data['label'] == clicked_label:
                return key
        return None
    except (KeyError, IndexError):
        return None


@app.callback(
    [Output('correlation-drilldown', 'children'),
     Output('correlation-drilldown', 'style')],
    Input('selected-risk-indicator', 'data'),
    prevent_initial_call=True
)
def display_correlation_drilldown(indicator_key):
    """Display users and posts for the selected risk factor."""
    if not indicator_key:
        return html.P("Click on a bar to see details.", style={'color': COLORS['muted']}), {'display': 'none'}

    indicator_data = PRE_PARASITIC_INDICATORS.get(indicator_key, {})
    indicator_label = indicator_data.get('label', indicator_key)
    indicator_color = indicator_data.get('color', '#6b7280')
    patterns = indicator_data.get('patterns', [])

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get users with this indicator in pre-parasitic posts
        cursor.execute("""
            SELECT DISTINCT username FROM user_histories WHERE is_pre_parasitic = true
        """)
        users = [row[0] for row in cursor.fetchall()]

        matching_users = []
        for username in users:
            cursor.execute("""
                SELECT title, content, created_at, subreddit, is_parasitic, parasite_score
                FROM user_histories
                WHERE username = %s AND is_pre_parasitic = true
                ORDER BY created_at
            """, (username,))
            user_pre_posts = cursor.fetchall()

            # Check which posts match the pattern
            user_matching_posts = []
            for title, content, created_at, subreddit, is_parasitic, score in user_pre_posts:
                text = (content or '') + ' ' + (title or '')
                for pattern in patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        user_matching_posts.append({
                            'title': title,
                            'content': content,
                            'created_at': created_at,
                            'subreddit': subreddit,
                            'is_parasitic': is_parasitic,
                            'score': score
                        })
                        break

            if user_matching_posts:
                # Get post-parasitic stats
                cursor.execute("""
                    SELECT COUNT(*), SUM(CASE WHEN is_parasitic THEN 1 ELSE 0 END)
                    FROM user_histories
                    WHERE username = %s AND is_pre_parasitic = false
                """, (username,))
                post_total, post_parasitic = cursor.fetchone()

                # Count ALL risk factors for this user (not just the clicked one)
                all_risk_factors = {k: 0 for k in PRE_PARASITIC_INDICATORS.keys()}
                for title, content, _, _, _, _ in user_pre_posts:
                    text = (content or '') + ' ' + (title or '')
                    if text.strip():
                        tags = tag_pre_parasitic_content(text)
                        for tag_name, count in tags.items():
                            all_risk_factors[tag_name] += count

                matching_users.append({
                    'username': username,
                    'matching_posts': user_matching_posts,
                    'post_total': post_total or 0,
                    'post_parasitic': post_parasitic or 0,
                    'parasitic_rate': (post_parasitic or 0) / post_total if post_total else 0,
                    'all_risk_factors': all_risk_factors
                })

        conn.close()

        if not matching_users:
            return html.P(f"No users found with '{indicator_label}' indicators.",
                         style={'color': COLORS['muted']}), {'display': 'block'}

        # Sort by parasitic rate
        matching_users.sort(key=lambda x: x['parasitic_rate'], reverse=True)

        # Build display
        user_sections = []
        for u in matching_users:
            parasitic_rate = u['parasitic_rate'] * 100
            rate_color = COLORS['danger'] if parasitic_rate > 50 else COLORS['warning'] if parasitic_rate > 20 else COLORS['success']

            # Expandable posts
            post_items = []
            for p in u['matching_posts'][:10]:  # Limit to 10 posts per user
                highlighted_content = highlight_all_patterns(p['content'], is_pre_parasitic=True) if p['content'] else ['(No content)']

                post_items.append(html.Details([
                    html.Summary([
                        html.Span(p['created_at'].strftime('%Y-%m-%d') if p['created_at'] else '',
                                 style={'fontSize': '10px', 'color': COLORS['muted']}),
                        html.Span(f" • r/{p['subreddit']}" if p['subreddit'] else '',
                                 style={'fontSize': '10px', 'color': COLORS['muted']}),
                        # Show the specific risk factor tag for this drill-down
                        html.Span(indicator_label[:12], style={
                            'backgroundColor': indicator_color, 'color': 'white',
                            'padding': '1px 5px', 'borderRadius': '3px', 'fontSize': '8px', 'marginLeft': '6px'
                        }),
                        html.Span(" • PARASITIC", style={
                            'backgroundColor': COLORS['danger'], 'color': 'white',
                            'padding': '1px 4px', 'borderRadius': '3px', 'fontSize': '8px', 'marginLeft': '4px'
                        }) if p['is_parasitic'] else None,
                        html.P(p['title'] or p['content'][:60] + '...' if p['content'] else '',
                              style={'fontSize': '11px', 'margin': '2px 0 0 0', 'fontWeight': '500'})
                    ], style={'cursor': 'pointer', 'padding': '4px 8px', 'listStyle': 'none'}),
                    html.Div(highlighted_content, style={
                        'fontSize': '11px', 'lineHeight': '1.5', 'padding': '8px',
                        'backgroundColor': COLORS['light'], 'borderRadius': '4px',
                        'maxHeight': '200px', 'overflow': 'auto', 'whiteSpace': 'pre-wrap'
                    })
                ], style={'borderBottom': f'1px solid {COLORS["border"]}', 'marginBottom': '2px'}))

            # Build risk factor badges for this user
            user_risk_badges = []
            for rf_name, rf_count in u.get('all_risk_factors', {}).items():
                if rf_count > 0:
                    rf_indicator = PRE_PARASITIC_INDICATORS.get(rf_name, {})
                    user_risk_badges.append(html.Span([
                        html.Span(rf_indicator.get('label', rf_name)[:8], style={'marginRight': '2px'}),
                        html.Span(f"({rf_count})", style={'opacity': '0.8', 'fontSize': '9px'})
                    ], style={
                        'backgroundColor': rf_indicator.get('color', '#6b7280'),
                        'color': 'white',
                        'padding': '2px 5px',
                        'borderRadius': '3px',
                        'fontSize': '9px',
                        'marginLeft': '4px'
                    }))

            user_sections.append(html.Div([
                html.Div([
                    html.Div([
                        html.Span(u['username'], style={'fontWeight': '600', 'fontSize': '14px'}),
                        *user_risk_badges
                    ], style={'marginBottom': '4px'}),
                    html.Div([
                        html.Span(f"{len(u['matching_posts'])} matching posts",
                                 style={'color': COLORS['muted'], 'fontSize': '11px'}),
                        html.Span(f" • Post-parasitic rate: {parasitic_rate:.0f}%",
                                 style={'color': rate_color, 'fontSize': '11px', 'fontWeight': '500'}),
                        html.Span(f" ({u['post_parasitic']}/{u['post_total']} posts)",
                                 style={'color': COLORS['muted'], 'fontSize': '10px'})
                    ])
                ], style={'marginBottom': '8px', 'padding': '8px', 'backgroundColor': 'rgba(0,0,0,0.03)',
                          'borderRadius': '6px'}),
                html.Div(post_items, style={'marginLeft': '12px'})
            ], style={'marginBottom': '16px'}))

        header = html.Div([
            html.Span("● ", style={'color': indicator_color, 'fontSize': '16px'}),
            html.Span(indicator_label, style={'fontWeight': '600', 'fontSize': '16px'}),
            html.Span(f" — {len(matching_users)} users with this pre-parasitic indicator",
                     style={'color': COLORS['muted'], 'fontSize': '13px', 'marginLeft': '8px'})
        ], style={'marginBottom': '16px'})

        visible_style = {
            'backgroundColor': COLORS['white'],
            'borderRadius': '12px',
            'padding': '20px',
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
            'border': f'1px solid {COLORS["border"]}',
            'display': 'block',
            'maxHeight': '600px',
            'overflow': 'auto'
        }

        return html.Div([header] + user_sections), visible_style

    except Exception as e:
        print(f"Error in correlation drilldown: {e}")
        import traceback
        traceback.print_exc()
        return html.P(f"Error loading data: {e}", style={'color': COLORS['danger']}), {'display': 'block'}


if __name__ == '__main__':
    print("Starting Parasitic AI Dashboard...")
    print("Open http://127.0.0.1:8051 in your browser")
    app.run_server(debug=True, port=8051)
