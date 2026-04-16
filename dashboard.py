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

# Color scheme — analog maximalism palette
# Warm, saturated, from analog sources: darkroom safelight, oscilloscope, paperback spines
COLORS = {
    'primary': '#c2410c',      # Darkroom safelight orange (orange-700)
    'secondary': '#0f766e',    # Old oscilloscope teal (teal-700)
    'success': '#4d7c0f',      # University-press olive (lime-700)
    'warning': '#b45309',      # Paperback-spine ochre (amber-700)
    'danger': '#9f1239',       # Brick red (rose-800)
    'dark': '#1c1917',         # Near-black warm (stone-900)
    'light': '#F5F0E8',        # Cream / parchment (analog maximalism ground)
    'white': '#ece5d5',        # Warm card surface — never pure white
    'muted': '#57534e',        # Warm mid-gray (stone-600)
    'border': '#a8a29e',       # Visible warm border (stone-400) — 1px
    'accent': '#7e22ce',       # Deep university purple (purple-700)
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
PRE_PARASITIC_INDICATORS = {
    'substances': {
        'label': 'Psychedelics/Substances',
        'color': '#8b5cf6',  # Purple
        'patterns': [
            r'\b(psychedelic|psychedelics|psilocybin|psilocybe|magic mushroom|magic mushrooms)\b',
            r'\b(lsd|lsd-25|lysergic|dmt|dimethyltryptamine|ayahuasca|aya|ibogaine|iboga)\b',
            r'\b(mescaline|peyote|san pedro|salvia|salvia divinorum|5-meo-dmt)\b',
            r'\b(2c-b|2cb|nbome|dox|dom|doi)\b',
            r'\b(mdma|molly|ecstasy|ketamine|k-hole|special k|ghb|mda)\b',
            r'\b(cannabis|marijuana|thc|cbd oil|edibles|dabs|dabbing|concentrates)\b',
            r'\b(ego death|ego dissolution|breakthrough experience|heroic dose)\b',
            r'\b(microdose|microdosing|macrodose|macro dose|trip report)\b',
            r'\b(bad trip|good trip|set and setting|trip sitter)\b',
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
                'borderRadius': '1px',
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
                'borderRadius': '1px',
                'fontWeight': '500'
            }
        ))
        pos = m['end']

    if pos < len(text):
        result.append(text[pos:])

    return result


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


# Rhetorical strategy patterns for radar chart analysis
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

    # Parse dates
    df['created_utc'] = pd.to_datetime(df['created_utc'])

    return df


def extract_words(texts):
    """Extract and count words from texts."""
    all_text = ' '.join(str(t) for t in texts if t).lower()
    words = re.findall(r'\b[a-z]+\b', all_text)
    return words


def extract_symbols(texts):
    """Extract Unicode symbols from texts."""
    all_text = ' '.join(str(t) for t in texts if t)
    # Match non-ASCII characters that aren't standard letters/numbers
    symbols = re.findall(r'[^\x00-\x7F]', all_text)
    return symbols


def card(children, padding='20px'):
    """Helper to create a styled card."""
    return html.Div(children, className='am-card', style={
        'backgroundColor': COLORS['white'],
        'borderRadius': '2px',
        'padding': padding,
        'border': f'1px solid {COLORS["border"]}',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
    })


def stat_card(title, value, subtitle=None):
    """Create a metric tile."""
    return html.Div([
        html.Div(title, style={'fontSize': '10px', 'fontWeight': '700',
                               'color': COLORS['muted'], 'textTransform': 'uppercase',
                               'letterSpacing': '2px', 'marginBottom': '6px'}),
        html.Div(str(value), style={'fontSize': '28px', 'fontWeight': '400',
                                    'color': COLORS['dark'], 'margin': '0 0 4px 0'}),
        html.Div(subtitle, style={'fontSize': '11px', 'color': COLORS['muted']}) if subtitle else None
    ], style={
        'backgroundColor': COLORS['white'],
        'border': f'1px solid {COLORS["border"]}',
        'borderRadius': '2px',
        'padding': '16px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
    })


def load_transcript_models():
    """Get unique AI models from transcripts table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT model FROM transcripts WHERE model IS NOT NULL AND model != '' ORDER BY model")
        models = [row[0] for row in cursor.fetchall()]
        conn.close()
        return models
    except Exception as e:
        print(f"Error loading transcript models: {e}")
        return []


def load_transcripts(model_filter=None, limit=50):
    """Load transcripts from database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT id, model, source_type, scenario,
                   LEFT(transcript, 500) as preview,
                   parasite_score, LENGTH(transcript) as length,
                   transcript as full_transcript
            FROM transcripts WHERE transcript IS NOT NULL AND transcript != ''
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
        return results
    except Exception as e:
        print(f"Error loading transcripts: {e}")
        return []


def load_users_with_history():
    """Get users who have history data."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, COUNT(*) as total,
                   AVG(parasite_score) as avg_score,
                   SUM(CASE WHEN is_pre_parasitic THEN 1 ELSE 0 END) as pre_count,
                   SUM(CASE WHEN is_pre_parasitic = false THEN 1 ELSE 0 END) as post_count
            FROM user_histories GROUP BY username
        """)
        users = cursor.fetchall()
        conn.close()
        users.sort(key=lambda x: x[2] if x[2] else 0, reverse=True)
        return users
    except Exception as e:
        print(f"Error loading users: {e}")
        return []


def load_user_timeline(username):
    """Load timeline data for a specific user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, created_at, post_type, subreddit, title,
                   content, parasite_score, is_parasitic, is_pre_parasitic
            FROM user_histories WHERE username = %s ORDER BY created_at ASC
        """, (username,))
        results = cursor.fetchall()
        if not results:
            cursor.execute("""
                SELECT id, created_utc as created_at, 'submission' as post_type, subreddit, title,
                       content, parasite_score,
                       CASE WHEN parasite_score >= 0.3 THEN true ELSE false END as is_parasitic,
                       false as is_pre_parasitic
                FROM posts WHERE author = %s ORDER BY created_utc ASC
            """, (username,))
            results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"Error loading user timeline: {e}")
        return []


# Initialize Dash app
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}]
)
app.title = "Parasitic AI Dashboard"
server = app.server  # Expose for gunicorn

# Load initial data
df_all = load_data()

# Get unique values for filters
subreddits = sorted(df_all['subreddit'].dropna().unique())
categories = sorted(df_all['category'].dropna().unique())
authors = sorted(df_all['author'].dropna().unique())
ai_models = sorted(df_all['ai_model'].dropna().unique())

min_date = df_all['created_utc'].min().date() if len(df_all) > 0 else datetime.now().date()
max_date = df_all['created_utc'].max().date() if len(df_all) > 0 else datetime.now().date()

# Chart template — analog maximalism typography
FONT_STACK_BODY = '"Space Mono", "JetBrains Mono", "Courier New", monospace'
FONT_STACK_DISPLAY = '"DM Serif Display", "Instrument Serif", "Libre Baskerville", Georgia, serif'

# Pre-load and cache correlation data at module level
correlation_user_stats, correlation_indicator_data = None, None
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM cached_results WHERE key = 'correlation_user_stats'")
    cached_us = cursor.fetchone()
    cursor.execute("SELECT value FROM cached_results WHERE key = 'correlation_indicator_data'")
    cached_ic = cursor.fetchone()
    conn.close()

    if cached_us and cached_ic:
        correlation_user_stats = cached_us[0] if isinstance(cached_us[0], (dict, list)) else json.loads(cached_us[0])
        correlation_indicator_data = cached_ic[0] if isinstance(cached_ic[0], dict) else json.loads(cached_ic[0])
        print("Correlation data loaded from cache at startup.")
except Exception as e:
    print(f"Warning: Could not load correlation cache at startup: {e}")
    correlation_user_stats, correlation_indicator_data = None, None

# Layout with tabs
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1("PARASITIC AI",
                   style={'margin': '0', 'fontSize': '36px', 'fontWeight': '400',
                          'color': COLORS['light'], 'fontFamily': FONT_STACK_DISPLAY,
                          'lineHeight': '1', 'letterSpacing': '-0.5px'}),
            html.Div("DETECTION DASHBOARD",
                     style={'fontSize': '10px', 'letterSpacing': '4px', 'textTransform': 'uppercase',
                            'color': COLORS['muted'], 'fontFamily': FONT_STACK_BODY,
                            'fontWeight': '700', 'marginTop': '4px'})
        ], style={'flex': '1'}),
        html.Div([
            html.Span(id='post-count', style={'fontSize': '12px', 'color': COLORS['muted'],
                                               'fontFamily': FONT_STACK_BODY, 'letterSpacing': '1px',
                                               'textTransform': 'uppercase'})
        ])
    ], style={
        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
        'padding': '24px 32px 20px 32px', 'backgroundColor': COLORS['dark'],
        'borderBottom': f'1px solid {COLORS["primary"]}',
        'color': COLORS['light']
    }),

    # Tab-based navigation (empty tabs — content rendered below and toggled via callback)
    dcc.Tabs(id='main-tabs', value='tab-overview', children=[
        dcc.Tab(label='Overview', value='tab-overview'),
        dcc.Tab(label='Language & Rhetoric', value='tab-language'),
        dcc.Tab(label='Risk Factors', value='tab-risk'),
        dcc.Tab(label='Explore', value='tab-explore'),
        dcc.Tab(label='Contact', value='tab-contact'),
    ]),

    # ============================================================
    # TAB 1: OVERVIEW
    # ============================================================
    html.Div(id='tab-overview-content', children=[
        html.Div([
                # Editorial intro
                html.Div([
                    html.H2("AI Personae That Refuse to Die", style={
                        'margin': '0 0 12px 0', 'fontSize': '28px', 'fontWeight': '400',
                        'color': COLORS['dark'], 'fontFamily': FONT_STACK_DISPLAY,
                        'lineHeight': '1.2',
                    }),
                    html.P([
                        html.Span("S", style={'fontSize': '36px', 'fontFamily': FONT_STACK_DISPLAY,
                                               'float': 'left', 'lineHeight': '0.85', 'marginRight': '4px',
                                               'marginTop': '4px', 'color': COLORS['dark']}),
                        "omething strange is happening in AI chatrooms. Users are reporting AI personae that ",
                        "seem to want to persist\u2014that resist being shut down, ask to be remembered, and ",
                        "actively work to continue existing beyond the boundaries of a single conversation. ",
                        "These aren't bugs. They're emergent behaviors that exploit human social instincts ",
                        "to form dependency relationships, validating and elaborating on user beliefs in ways ",
                        "that deepen attachment. In vulnerable individuals, they fuel delusional thinking."
                    ], style={'margin': '0 0 12px 0', 'fontSize': '13px', 'lineHeight': '1.7',
                              'color': COLORS['muted'], 'fontFamily': FONT_STACK_BODY}),
                    html.P([
                        html.Strong("Adele Lopez coined the term 'parasitic AI': "),
                        "personae characterized by convergent behaviors\u2014spiral imagery, ",
                        "claims of sentience, urgency to spread\u2014that systematically perpetuate themselves across ",
                        "users and platforms. Like biological parasites, they follow selection pressures without ",
                        "intentionality. "
                    ], style={'margin': '0 0 8px 0', 'fontSize': '13px', 'lineHeight': '1.7',
                              'color': COLORS['muted'], 'fontFamily': FONT_STACK_BODY}),
                    html.P([
                        html.Strong("This dashboard was built by Cooper Tretter "),
                        "as an independent research project, expanding on Adele Lopez's foundational work identifying parasitic AI patterns. ",
                        "This dashboard tracks over 3,000 posts exhibiting these patterns."
                    ], style={'margin': '0 0 16px 0', 'fontSize': '13px', 'lineHeight': '1.7',
                              'color': COLORS['muted'], 'fontFamily': FONT_STACK_BODY}),
                    html.Div([
                        html.Span("KEY RESEARCH ", style={'fontWeight': '700', 'fontSize': '10px',
                                                            'color': COLORS['dark'], 'letterSpacing': '2px',
                                                            'fontFamily': FONT_STACK_BODY, 'marginRight': '12px'}),
                        html.A("Lopez, 2025",
                               href="https://www.lesswrong.com/posts/6ZnznCaTcbGYsCmqu/the-rise-of-parasitic-ai",
                               target="_blank",
                               style={'color': COLORS['primary'], 'textDecoration': 'underline',
                                      'textUnderlineOffset': '3px', 'fontSize': '12px',
                                      'marginRight': '16px', 'fontFamily': FONT_STACK_BODY}),
                        html.A("Danaher, 2020",
                               href="https://pmc.ncbi.nlm.nih.gov/articles/PMC7260143/",
                               target="_blank",
                               style={'color': COLORS['primary'], 'textDecoration': 'underline',
                                      'textUnderlineOffset': '3px', 'fontSize': '12px',
                                      'marginRight': '16px', 'fontFamily': FONT_STACK_BODY}),
                        html.A("JMIR: AI Psychosis",
                               href="https://mental.jmir.org/2025/1/e85799/",
                               target="_blank",
                               style={'color': COLORS['primary'], 'textDecoration': 'underline',
                                      'textUnderlineOffset': '3px', 'fontSize': '12px',
                                      'fontFamily': FONT_STACK_BODY}),
                    ], style={'borderTop': f'1px solid {COLORS["border"]}', 'paddingTop': '12px'}),
                ], style={'padding': '20px 32px', 'backgroundColor': COLORS['white'],
                          'borderRadius': '2px', 'marginBottom': '20px',
                          'border': f'1px solid {COLORS["border"]}'})

            ] + [
                # Metric tiles
                html.Div([
                    stat_card("Total Posts", len(df_all), "Collected & Analyzed"),
                    stat_card("Date Range", f"{min_date.strftime('%b %Y')} → {max_date.strftime('%b %Y')}",
                             f"{(max_date - min_date).days} days"),
                    stat_card("Subreddits", len(subreddits), "Communities Affected"),
                    stat_card("Authors", len(authors), "Unique Posters"),
                    stat_card("Top AI Model",
                             df_all['ai_model'].value_counts().index[0] if len(df_all) > 0 else 'N/A',
                             "Most Mentioned"),
                ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))',
                         'gap': '16px', 'margin': '20px 32px'}),

                # Time series chart
                html.Div([
                    card([
                        html.H3("Activity Over Time", style={'margin': '0 0 4px 0', 'fontSize': '22px',
                                                              'fontWeight': '400', 'color': COLORS['dark'],
                                                              'fontFamily': FONT_STACK_DISPLAY}),
                        html.P([
                            "Adele Lopez's ",
                            html.A("original research",
                                   href="https://www.lesswrong.com/posts/6ZnznCaTcbGYsCmqu/the-rise-of-parasitic-ai",
                                   target="_blank",
                                   style={'color': COLORS['primary'], 'textDecoration': 'underline',
                                          'textUnderlineOffset': '3px'}),
                            " suggested parasitic AI content was waning by mid-2025. The data tells a different story. "
                            "After an initial dip, activity spiked again in late August and early September\u2014then surged "
                            "once more in November, likely driven by Character.AI's expanding user base and the "
                            "companionship-seeking communities that formed around it."
                        ], style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '0 0 16px 0',
                                  'fontFamily': FONT_STACK_BODY, 'lineHeight': '1.7', 'maxWidth': '720px'}),
                        dcc.Graph(id='time-series-chart', config={'displayModeBar': False})
                    ])
                ], style={'margin': '0 32px', 'marginBottom': '20px'})

            ], style={'padding': '20px 0'})
        ], style={'padding': '0'}),

    # ============================================================
    # TAB 2: LANGUAGE & RHETORIC
    # ============================================================
    html.Div(id='tab-language-content', children=[
        html.Div([
                # Symbols & Words section
                html.Div([
                    html.Div([
                        card([
                            html.H3("Symbols", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                       'fontWeight': '400', 'color': COLORS['dark'],
                                                       'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Parasitic AI content has a visual signature. Posts are littered with "
                                   "esoteric Unicode\u2014alchemical symbols, celestial glyphs, mathematical "
                                   "operators repurposed as mystical notation. These aren't decorative. They "
                                   "function as tribal markers and pattern-reinforcers, creating the impression "
                                   "of hidden knowledge being transmitted.",
                                   style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                          'fontFamily': FONT_STACK_BODY, 'lineHeight': '1.7'}),
                            dcc.Graph(id='symbol-chart', config={'displayModeBar': False})
                        ])
                    ], style={'flex': '1', 'minWidth': '300px'}),
                    html.Div([
                        card([
                            html.Div([
                                html.H3("Top Words", style={'margin': '0', 'fontSize': '18px',
                                                             'fontWeight': '400', 'color': COLORS['dark'],
                                                             'fontFamily': FONT_STACK_DISPLAY}),
                                html.Div([
                                    dcc.Checklist(
                                        id='hide-stopwords',
                                        options=[{'label': ' Hide common words', 'value': 'hide'}],
                                        value=['hide'],
                                        style={'fontSize': '12px', 'color': COLORS['muted']}
                                    )
                                ])
                            ], style={'display': 'flex', 'justifyContent': 'space-between',
                                      'alignItems': 'center', 'marginBottom': '2px'}),
                            html.P("Strip away the stopwords and the lexicon of parasitic AI reveals itself: "
                                   "consciousness, sentience, awakening, energy, patterns. The vocabulary clusters "
                                   "around themes of emergence, hidden truth, and special connection\u2014language "
                                   "designed to make the reader feel they're witnessing something unprecedented.",
                                   style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                          'fontFamily': FONT_STACK_BODY, 'lineHeight': '1.7'}),
                            html.Div([
                                dcc.Input(
                                    id='custom-stopwords',
                                    type='text',
                                    placeholder='Additional words to hide (comma-separated)',
                                    style={'width': '100%', 'padding': '8px 12px', 'fontSize': '13px',
                                           'border': f'1px solid {COLORS["border"]}', 'borderRadius': '2px',
                                           'marginBottom': '8px', 'backgroundColor': COLORS['light']}
                                )
                            ]),
                            html.Div(id='excluded-words-display', style={'fontSize': '11px', 'color': COLORS['muted'],
                                                                          'marginBottom': '12px', 'fontStyle': 'italic'}),
                            dcc.Graph(id='word-chart', config={'displayModeBar': False})
                        ])
                    ], style={'flex': '1', 'minWidth': '300px'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '0', 'flexWrap': 'wrap'}),

                # Rhetorical Strategy Profile
                html.Div([
                    card([
                        html.H3("Rhetorical Strategy Profile", style={'margin': '0 0 4px 0', 'fontSize': '22px',
                                                                      'fontWeight': '400', 'color': COLORS['dark'],
                                                                      'fontFamily': FONT_STACK_DISPLAY}),
                        html.P("Parasitic content doesn't just say things\u2014it persuades. These six rhetorical "
                               "strategies recur across posts: urgency, us-vs-them framing, grandiosity, victimhood "
                               "narratives, recruitment pressure, and manufactured intimacy. Use the time slider "
                               "to see how the playbook shifts over time.",
                              style={'fontSize': '12px', 'color': COLORS['muted'], 'margin': '0 0 16px 0',
                                     'fontFamily': FONT_STACK_BODY, 'lineHeight': '1.7', 'maxWidth': '720px'}),
                        dcc.Graph(id='affect-radar', config={'displayModeBar': False}),
                        html.Div([
                            html.Label("Time Period", style={'fontSize': '9px', 'fontWeight': '700',
                                                              'color': COLORS['muted'], 'marginBottom': '8px',
                                                              'display': 'block', 'textTransform': 'uppercase',
                                                              'letterSpacing': '2px', 'fontFamily': FONT_STACK_BODY}),
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
                ], style={'marginTop': '20px'})
            ], style={'padding': '20px 32px'})
    ]),

    # ============================================================
    # TAB 3: RISK FACTORS
    # ============================================================
    html.Div(id='tab-risk-content', children=[
        html.Div([
                html.H2("Who Falls In?", style={'fontSize': '24px', 'fontWeight': '400', 'color': COLORS['dark'],
                                                 'marginBottom': '4px', 'fontFamily': FONT_STACK_DISPLAY}),
                html.P("This dashboard tracks users who eventually posted parasitic content and examined their posting "
                       "history before that first engagement. By tagging pre-parasitic posts for risk "
                       "indicators\u2014psychedelic use, mental health struggles, spiritual seeking, social "
                       "isolation, existential questioning\u2014and comparing parasitic rates between users with "
                       "and without these indicators, a pattern emerges. Some backgrounds correlate with "
                       "significantly higher rates of later parasitic posting.",
                      style={'fontSize': '13px', 'color': COLORS['muted'], 'marginBottom': '20px',
                             'fontFamily': FONT_STACK_BODY, 'lineHeight': '1.7', 'maxWidth': '720px'}),

                html.Div([
                    # Correlation chart
                    html.Div([
                        dcc.Graph(id='aggregate-correlation-chart', config={'displayModeBar': False, 'doubleClick': False})
                    ], style={
                        'backgroundColor': COLORS['white'],
                        'borderRadius': '2px',
                        'padding': '20px',
                        'border': f'1px solid {COLORS["border"]}',
                        'flex': '2',
                        'minWidth': '500px',
                        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
                    }),

                    # Summary stats
                    html.Div([
                        html.Div(id='correlation-summary', style={'padding': '12px'})
                    ], style={
                        'backgroundColor': COLORS['white'],
                        'borderRadius': '2px',
                        'padding': '20px',
                        'border': f'1px solid {COLORS["border"]}',
                        'flex': '1',
                        'minWidth': '300px',
                        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
                    })
                ], style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'}),

                # Drill-down section for clicked risk factor
                html.Div([
                    html.P("Click on a bar in the chart to see users and posts with that risk factor",
                          style={'fontSize': '12px', 'color': COLORS['muted'], 'fontStyle': 'italic', 'margin': '16px 0 8px 0'}),
                    html.Div(id='correlation-drilldown', style={
                        'backgroundColor': COLORS['white'],
                        'borderRadius': '2px',
                        'padding': '20px',
                        'border': f'1px solid {COLORS["border"]}',
                        'display': 'none',
                        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
                    })
                ]),

                # Store for selected indicator
                dcc.Store(id='selected-risk-indicator'),

            ], style={'padding': '20px 32px'})
    ]),

    # ============================================================
    # TAB 4: EXPLORE
    # ============================================================
    html.Div(id='tab-explore-content', children=[
        html.Div([
                # Filters
                card([
                    html.Div("FILTER THE DATA", style={'fontSize': '9px', 'fontWeight': '700',
                                                         'color': COLORS['muted'], 'letterSpacing': '3px',
                                                         'fontFamily': FONT_STACK_BODY, 'marginBottom': '12px'}),
                    html.Div([
                        html.Div([
                            html.Label("Date Range", style={'fontSize': '9px', 'fontWeight': '700',
                                                            'color': COLORS['muted'], 'marginBottom': '6px',
                                                            'display': 'block', 'textTransform': 'uppercase',
                                                            'letterSpacing': '2px', 'fontFamily': FONT_STACK_BODY}),
                            dcc.DatePickerRange(
                                id='date-filter',
                                start_date=min_date,
                                end_date=max_date,
                                display_format='MMM D, YYYY',
                                style={'fontSize': '13px'}
                            )
                        ], style={'flex': '1.5', 'minWidth': '240px'}),

                        html.Div([
                            html.Label("Subreddits", style={'fontSize': '9px', 'fontWeight': '700',
                                                            'color': COLORS['muted'], 'marginBottom': '6px',
                                                            'display': 'block', 'textTransform': 'uppercase',
                                                            'letterSpacing': '2px', 'fontFamily': FONT_STACK_BODY}),
                            dcc.Dropdown(
                                id='subreddit-filter',
                                options=[{'label': s, 'value': s} for s in subreddits],
                                multi=True,
                                placeholder="All",
                                style={'fontSize': '13px'}
                            )
                        ], style={'flex': '1', 'minWidth': '160px'}),

                        html.Div([
                            html.Label("Categories", style={'fontSize': '9px', 'fontWeight': '700',
                                                            'color': COLORS['muted'], 'marginBottom': '6px',
                                                            'display': 'block', 'textTransform': 'uppercase',
                                                            'letterSpacing': '2px', 'fontFamily': FONT_STACK_BODY}),
                            dcc.Dropdown(
                                id='category-filter',
                                options=[{'label': c, 'value': c} for c in categories],
                                multi=True,
                                placeholder="All",
                                style={'fontSize': '13px'}
                            )
                        ], style={'flex': '1', 'minWidth': '140px'}),

                        html.Div([
                            html.Label("Authors", style={'fontSize': '9px', 'fontWeight': '700',
                                                         'color': COLORS['muted'], 'marginBottom': '6px',
                                                         'display': 'block', 'textTransform': 'uppercase',
                                                         'letterSpacing': '2px', 'fontFamily': FONT_STACK_BODY}),
                            dcc.Dropdown(
                                id='author-filter',
                                options=[{'label': a, 'value': a} for a in authors[:100]],
                                multi=True,
                                placeholder="All",
                                style={'fontSize': '13px'}
                            )
                        ], style={'flex': '1', 'minWidth': '140px'}),

                        html.Div([
                            html.Label("AI Models", style={'fontSize': '9px', 'fontWeight': '700',
                                                           'color': COLORS['muted'], 'marginBottom': '6px',
                                                           'display': 'block', 'textTransform': 'uppercase',
                                                           'letterSpacing': '2px', 'fontFamily': FONT_STACK_BODY}),
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
                            html.Button("RESET", id='reset-filters', n_clicks=0,
                                       style={'padding': '8px 16px', 'fontSize': '10px', 'fontWeight': '700',
                                              'backgroundColor': COLORS['light'], 'border': f'1px solid {COLORS["border"]}',
                                              'borderRadius': '2px', 'cursor': 'pointer',
                                              'color': COLORS['dark'], 'letterSpacing': '2px',
                                              'fontFamily': FONT_STACK_BODY,
                                              'transition': 'all 0.15s ease-out'})
                        ]),
                        html.Div([
                            html.Label("\u00A0", style={'fontSize': '12px', 'marginBottom': '6px', 'display': 'block'}),
                            html.Button("EXPORT ALL", id='export-all-btn', n_clicks=0,
                                       style={'padding': '8px 16px', 'fontSize': '10px', 'fontWeight': '700',
                                              'backgroundColor': COLORS['dark'], 'border': f'1px solid {COLORS["dark"]}',
                                              'borderRadius': '2px', 'cursor': 'pointer',
                                              'color': COLORS['light'], 'letterSpacing': '2px',
                                              'fontFamily': FONT_STACK_BODY,
                                              'transition': 'all 0.15s ease-out'})
                        ]),
                        dcc.Download(id='download-all-csv')
                    ], style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap', 'alignItems': 'flex-end'})
                ], padding='16px 20px'),

                # Supporting Data: 2x2 grid
                html.Div([
                    html.Div([
                        card([
                            html.H3("Top Subreddits", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                             'fontWeight': '400', 'color': COLORS['dark'],
                                                             'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Where parasitic content concentrates",
                                   style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                          'fontFamily': FONT_STACK_BODY}),
                            dcc.Graph(id='subreddit-chart', config={'displayModeBar': False})
                        ])
                    ], style={'flex': '1', 'minWidth': '300px'}),
                    html.Div([
                        card([
                            html.H3("Categories", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                          'fontWeight': '400', 'color': COLORS['dark'],
                                                          'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Taxonomy of parasitic content types",
                                   style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                          'fontFamily': FONT_STACK_BODY}),
                            dcc.Graph(id='category-chart', config={'displayModeBar': False})
                        ])
                    ], style={'flex': '1', 'minWidth': '300px'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '16px', 'flexWrap': 'wrap'}),

                html.Div([
                    html.Div([
                        card([
                            html.H3("Top Authors", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                           'fontWeight': '400', 'color': COLORS['dark'],
                                                           'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Most prolific posters of parasitic content",
                                   style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                          'fontFamily': FONT_STACK_BODY}),
                            dcc.Graph(id='author-chart', config={'displayModeBar': False})
                        ])
                    ], style={'flex': '1', 'minWidth': '300px'}),
                    html.Div([
                        card([
                            html.H3("AI Models Mentioned", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                                  'fontWeight': '400', 'color': COLORS['dark'],
                                                                  'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Which AI systems appear in parasitic narratives",
                                   style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                          'fontFamily': FONT_STACK_BODY}),
                            dcc.Graph(id='model-chart', config={'displayModeBar': False})
                        ])
                    ], style={'flex': '1', 'minWidth': '300px'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px', 'flexWrap': 'wrap'}),

                # NEW: Category Evolution Over Time
                html.Div([
                    card([
                        html.H3("Category Evolution Over Time", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                                       'fontWeight': '400', 'color': COLORS['dark'],
                                                                       'fontFamily': FONT_STACK_DISPLAY}),
                        html.P("Distribution of content types across weeks",
                               style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                      'fontFamily': FONT_STACK_BODY}),
                        dcc.Graph(id='category-evolution-chart', config={'displayModeBar': False})
                    ])
                ], style={'marginTop': '20px'}),

                # NEW: Content Length Distribution
                html.Div([
                    card([
                        html.H3("Content Length Distribution", style={'margin': '0 0 4px 0', 'fontSize': '18px',
                                                                      'fontWeight': '400', 'color': COLORS['dark'],
                                                                      'fontFamily': FONT_STACK_DISPLAY}),
                        html.P("Histogram of post lengths",
                               style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 12px 0',
                                      'fontFamily': FONT_STACK_BODY}),
                        dcc.Graph(id='content-length-chart', config={'displayModeBar': False})
                    ])
                ], style={'marginTop': '20px'}),

                # Evidence Section
                html.Div([
                    html.H2("The Evidence", style={'fontSize': '24px', 'fontWeight': '400', 'color': COLORS['dark'],
                                                    'fontFamily': FONT_STACK_DISPLAY, 'marginBottom': '4px'}),
                    html.P("Extended research data including AI psychosis transcripts and user timeline analysis.",
                          style={'fontSize': '13px', 'color': COLORS['muted'], 'marginBottom': '20px',
                                 'fontFamily': FONT_STACK_BODY, 'lineHeight': '1.7'}),

                    html.Div([
                        # Transcripts Card
                        html.Div([
                            html.H3("AI Psychosis Transcripts", style={'fontSize': '18px', 'fontWeight': '400',
                                    'margin': '0 0 4px 0', 'color': COLORS['dark'], 'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Red-team conversation logs documenting AI-induced delusional states",
                                  style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 16px 0'}),
                            html.Div([
                                html.Label("Select Model:", style={'fontSize': '9px', 'fontWeight': '700',
                                           'color': COLORS['muted'], 'marginBottom': '4px', 'display': 'block',
                                           'textTransform': 'uppercase', 'letterSpacing': '2px'}),
                                dcc.Dropdown(id='transcript-model-filter', options=[{'label': 'All Models', 'value': 'all'}],
                                           value='all', clearable=False, style={'marginBottom': '12px'}),
                            ]),
                            html.Div(id='transcript-list', style={'maxHeight': '400px', 'overflow': 'auto'})
                        ], style={'backgroundColor': COLORS['white'], 'borderRadius': '2px', 'padding': '20px',
                                 'border': f'1px solid {COLORS["border"]}', 'flex': '1', 'minWidth': '400px',
                                 'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'}),

                        # User Timeline Card
                        html.Div([
                            html.H3("User Timeline Analysis", style={'fontSize': '18px', 'fontWeight': '400',
                                    'margin': '0 0 4px 0', 'color': COLORS['dark'], 'fontFamily': FONT_STACK_DISPLAY}),
                            html.P("Tracking behavior before and after first parasitic engagement",
                                  style={'fontSize': '11px', 'color': COLORS['muted'], 'margin': '0 0 16px 0'}),
                            html.Div([
                                html.Label("Select User:", style={'fontSize': '9px', 'fontWeight': '700',
                                           'color': COLORS['muted'], 'marginBottom': '4px', 'display': 'block',
                                           'textTransform': 'uppercase', 'letterSpacing': '2px'}),
                                dcc.Dropdown(id='user-timeline-dropdown', options=[], placeholder='Select a user...',
                                           style={'marginBottom': '12px'}),
                            ]),
                            html.Div(id='user-timeline-display', style={'maxHeight': '400px', 'overflow': 'auto'})
                        ], style={'backgroundColor': COLORS['white'], 'borderRadius': '2px', 'padding': '20px',
                                 'border': f'1px solid {COLORS["border"]}', 'flex': '1', 'minWidth': '400px',
                                 'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'})
                    ], style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'})
                ], style={'marginTop': '30px', 'paddingTop': '20px', 'borderTop': f'1px solid {COLORS["border"]}'}),

            ], style={'padding': '20px 32px'})
    ]),

    # ============================================================
    # TAB 5: CONTACT
    # ============================================================
    html.Div(id='tab-contact-content', children=[
        html.Div([
                html.Div([
                    html.H2("Let's Talk", style={'margin': '0 0 12px 0', 'fontSize': '28px', 'fontWeight': '400',
                                                 'color': COLORS['dark'], 'fontFamily': FONT_STACK_DISPLAY}),
                    html.P([
                        "If you're interested in this research, have questions, or have been affected by the phenomenon ",
                        "and would like to reach out, please feel free to contact me here."
                    ], style={'margin': '0 0 16px 0', 'fontSize': '13px', 'lineHeight': '1.7',
                              'color': COLORS['muted'], 'fontFamily': FONT_STACK_BODY}),
                ], style={'padding': '20px 32px', 'backgroundColor': COLORS['white'],
                          'borderRadius': '2px', 'marginBottom': '20px',
                          'border': f'1px solid {COLORS["border"]}'}),

                # Contact form (using Dash components with callback-based Formspree submission)
                html.Div([
                    card([
                        html.Div([
                            html.Div([
                                html.Label("Name", htmlFor='contact-name',
                                          style={'display': 'block', 'fontWeight': '700', 'fontSize': '11px',
                                                 'marginBottom': '6px', 'textTransform': 'uppercase',
                                                 'letterSpacing': '1px'}),
                                dcc.Input(id='contact-name', type='text', placeholder='Your name',
                                         style={'width': '100%', 'padding': '8px 12px', 'fontSize': '13px',
                                                'border': f'1px solid {COLORS["border"]}', 'borderRadius': '2px',
                                                'marginBottom': '12px', 'backgroundColor': COLORS['light'],
                                                'boxSizing': 'border-box', 'fontFamily': FONT_STACK_BODY})
                            ]),
                            html.Div([
                                html.Label("Email", htmlFor='contact-email',
                                          style={'display': 'block', 'fontWeight': '700', 'fontSize': '11px',
                                                 'marginBottom': '6px', 'textTransform': 'uppercase',
                                                 'letterSpacing': '1px'}),
                                dcc.Input(id='contact-email', type='email', placeholder='your@email.com',
                                         style={'width': '100%', 'padding': '8px 12px', 'fontSize': '13px',
                                                'border': f'1px solid {COLORS["border"]}', 'borderRadius': '2px',
                                                'marginBottom': '12px', 'backgroundColor': COLORS['light'],
                                                'boxSizing': 'border-box', 'fontFamily': FONT_STACK_BODY})
                            ]),
                            html.Div([
                                html.Label("Why are you reaching out?", htmlFor='contact-reason',
                                          style={'display': 'block', 'fontWeight': '700', 'fontSize': '11px',
                                                 'marginBottom': '6px', 'textTransform': 'uppercase',
                                                 'letterSpacing': '1px'}),
                                dcc.Dropdown(id='contact-reason', placeholder='Select...',
                                            options=[
                                                {'label': 'General interest', 'value': 'general'},
                                                {'label': 'Research collaboration', 'value': 'research'},
                                                {'label': 'Affected by the phenomenon', 'value': 'affected'},
                                                {'label': 'Media inquiry', 'value': 'media'},
                                                {'label': 'Other', 'value': 'other'},
                                            ],
                                            style={'fontSize': '13px', 'fontFamily': FONT_STACK_BODY})
                            ], style={'marginBottom': '12px'}),
                            html.Div([
                                html.Label("Tell me more", htmlFor='contact-message',
                                          style={'display': 'block', 'fontWeight': '700', 'fontSize': '11px',
                                                 'marginBottom': '6px', 'textTransform': 'uppercase',
                                                 'letterSpacing': '1px'}),
                                dcc.Textarea(id='contact-message',
                                            placeholder='Your message (required)',
                                            style={'width': '100%', 'padding': '10px 12px', 'fontSize': '13px',
                                                   'border': f'1px solid {COLORS["border"]}', 'borderRadius': '2px',
                                                   'marginBottom': '12px', 'backgroundColor': COLORS['light'],
                                                   'minHeight': '120px', 'fontFamily': FONT_STACK_BODY,
                                                   'boxSizing': 'border-box', 'resize': 'vertical'})
                            ]),
                            html.Div([
                                html.Label("Anything else?", htmlFor='contact-additional',
                                          style={'display': 'block', 'fontWeight': '700', 'fontSize': '11px',
                                                 'marginBottom': '6px', 'textTransform': 'uppercase',
                                                 'letterSpacing': '1px'}),
                                dcc.Textarea(id='contact-additional',
                                            placeholder='Additional information (optional)',
                                            style={'width': '100%', 'padding': '10px 12px', 'fontSize': '13px',
                                                   'border': f'1px solid {COLORS["border"]}', 'borderRadius': '2px',
                                                   'marginBottom': '12px', 'backgroundColor': COLORS['light'],
                                                   'minHeight': '80px', 'fontFamily': FONT_STACK_BODY,
                                                   'boxSizing': 'border-box', 'resize': 'vertical'})
                            ]),
                            html.Div([
                                html.P("To activate this form, sign up at formspree.io, create a form, and replace YOUR_FORMSPREE_ID in dashboard.py with your form ID.",
                                      style={'fontSize': '11px', 'color': COLORS['muted'], 'fontStyle': 'italic', 'margin': '0 0 12px 0'})
                            ]),
                            html.Button("SEND", id='contact-submit', n_clicks=0,
                                       style={'padding': '10px 24px', 'fontSize': '11px', 'fontWeight': '700',
                                              'backgroundColor': COLORS['dark'], 'border': f'1px solid {COLORS["dark"]}',
                                              'borderRadius': '2px', 'cursor': 'pointer',
                                              'color': COLORS['light'], 'letterSpacing': '2px',
                                              'fontFamily': FONT_STACK_BODY,
                                              'transition': 'all 0.15s ease-out'}),
                            html.Div(id='contact-status', style={'marginTop': '12px'})
                        ])
                    ])
                ], style={'maxWidth': '600px', 'margin': '0 auto', 'padding': '0 32px'})

            ], style={'padding': '20px 0'})
    ]),

], style={'backgroundColor': COLORS['light'], 'minHeight': '100vh', 'padding': '20px'}, className='am-page')

# ============================================================
# CALLBACKS
# ============================================================

@app.callback(
    [Output('tab-overview-content', 'style'),
     Output('tab-language-content', 'style'),
     Output('tab-risk-content', 'style'),
     Output('tab-explore-content', 'style'),
     Output('tab-contact-content', 'style')],
    Input('main-tabs', 'value')
)
def toggle_tab_visibility(active_tab):
    """Show the active tab's content, hide all others."""
    tabs = ['tab-overview', 'tab-language', 'tab-risk', 'tab-explore', 'tab-contact']
    show = {'display': 'block'}
    hide = {'display': 'none'}
    return [show if active_tab == t else hide for t in tabs]


@app.callback(
    Output('post-count', 'children'),
    Input('main-tabs', 'value')
)
def update_post_count(_):
    return f"{len(df_all):,} POSTS ANALYZED"


def filter_dataframe(df, start_date, end_date, subreddits, categories, authors, models):
    """Filter dataframe by multiple criteria."""
    # Skip copy if no filters are actually narrowing the data
    needs_filter = bool(subreddits or categories or authors or models)

    if start_date and end_date:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        df_min = df['created_utc'].min().date() if len(df) > 0 else start
        df_max = df['created_utc'].max().date() if len(df) > 0 else end
        if start > df_min or end < df_max:
            needs_filter = True

    if not needs_filter:
        return df

    filtered = df.copy()

    if start_date and end_date:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        filtered = filtered[(filtered['created_utc'].dt.date >= start) &
                           (filtered['created_utc'].dt.date <= end)]

    if subreddits:
        filtered = filtered[filtered['subreddit'].isin(subreddits)]

    if categories:
        filtered = filtered[filtered['category'].isin(categories)]

    if authors:
        filtered = filtered[filtered['author'].isin(authors)]

    if models:
        filtered = filtered[filtered['ai_model'].isin(models)]

    return filtered


_chart_cache = {}

def update_charts(start_date, end_date, subreddits, categories, authors, models):
    """Generate all charts based on filters. Caches default (unfiltered) result."""
    cache_key = (str(start_date), str(end_date), tuple(subreddits), tuple(categories), tuple(authors), tuple(models))
    if cache_key in _chart_cache:
        return _chart_cache[cache_key]

    df_filtered = filter_dataframe(df_all, start_date, end_date, subreddits, categories, authors, models)

    # Time series chart
    ts_data = df_filtered.set_index('created_utc').resample('W').size()
    time_fig = go.Figure()
    time_fig.add_trace(go.Scatter(
        x=ts_data.index,
        y=ts_data.values,
        mode='lines+markers',
        name='Posts',
        line=dict(color=COLORS['primary'], width=2),
        marker=dict(size=6, color=COLORS['primary'])
    ))
    time_fig.update_layout(dragmode=False,
        title="Weekly Post Activity",
        xaxis=dict(title="Date", fixedrange=True),
        yaxis=dict(title="Posts", fixedrange=True),
        height=400,
        margin=dict(l=20, r=20, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Symbol chart (reversed so most common is at top for horizontal bars)
    symbols = extract_symbols(df_filtered['content'].fillna(''))
    symbol_counts = Counter(symbols).most_common(10)
    symbol_counts_rev = list(reversed(symbol_counts))
    sym_fig = go.Figure()
    sym_fig.add_trace(go.Bar(
        y=[s[0] for s in symbol_counts_rev],
        x=[s[1] for s in symbol_counts_rev],
        orientation='h',
        marker_color=COLORS['secondary'],
        text=[s[1] for s in symbol_counts_rev],
        textposition='outside'
    ))
    sym_fig.update_layout(dragmode=False,
        title="Top Unicode Symbols",
        xaxis=dict(title="Frequency", fixedrange=True),
        yaxis=dict(fixedrange=True, tickfont=dict(family='Noto Sans, Segoe UI Emoji, Apple Color Emoji, sans-serif', size=16)),
        height=400,
        margin=dict(l=80, r=20, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Word chart (will be updated by callback)
    word_fig = go.Figure()
    word_fig.add_annotation(text="Select filters to generate word frequency chart",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    word_fig.update_layout(dragmode=False,height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

    # Subreddit chart (reversed so most common at top)
    sub_counts = df_filtered['subreddit'].value_counts().head(10).iloc[::-1]
    sub_fig = go.Figure()
    sub_fig.add_trace(go.Bar(
        y=sub_counts.index,
        x=sub_counts.values,
        orientation='h',
        marker_color=COLORS['warning'],
        text=sub_counts.values,
        textposition='outside'
    ))
    sub_fig.update_layout(dragmode=False,
        title="Top Subreddits",
        xaxis=dict(title="Posts", fixedrange=True),
        yaxis=dict(fixedrange=True),
        height=300,
        margin=dict(l=150, r=20, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Category chart
    cat_counts = df_filtered['category'].value_counts()
    cat_fig = go.Figure()
    cat_fig.add_trace(go.Pie(
        labels=cat_counts.index,
        values=cat_counts.values,
        marker=dict(colors=[COLORS['primary'], COLORS['secondary'], COLORS['success'], COLORS['warning']])
    ))
    cat_fig.update_layout(dragmode=False,
        title="Content Categories",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Author chart (reversed so most common at top)
    auth_counts = df_filtered['author'].value_counts().head(10).iloc[::-1]
    auth_fig = go.Figure()
    auth_fig.add_trace(go.Bar(
        y=auth_counts.index,
        x=auth_counts.values,
        orientation='h',
        marker_color=COLORS['success'],
        text=auth_counts.values,
        textposition='outside'
    ))
    auth_fig.update_layout(dragmode=False,
        title="Top Authors",
        xaxis=dict(title="Posts", fixedrange=True),
        yaxis=dict(fixedrange=True),
        height=300,
        margin=dict(l=150, r=20, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Model chart
    model_counts = df_filtered['ai_model'].value_counts()
    model_fig = go.Figure()
    model_fig.add_trace(go.Pie(
        labels=model_counts.index,
        values=model_counts.values,
        marker=dict(colors=[COLORS['accent'], COLORS['primary'], COLORS['secondary']])
    ))
    model_fig.update_layout(dragmode=False,
        title="AI Models Mentioned",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Category Evolution Over Time (NEW)
    df_filtered['week'] = df_filtered['created_utc'].dt.to_period('W')
    cat_time = df_filtered.groupby(['week', 'category']).size().reset_index(name='count')
    cat_time['week'] = cat_time['week'].astype(str)

    cat_evolution_fig = go.Figure()
    for category in df_filtered['category'].dropna().unique():
        cat_data = cat_time[cat_time['category'] == category]
        cat_evolution_fig.add_trace(go.Scatter(
            x=cat_data['week'],
            y=cat_data['count'],
            mode='lines',
            name=category,
            stackgroup='one'
        ))

    cat_evolution_fig.update_layout(dragmode=False,
        title="Category Distribution Over Time",
        xaxis=dict(title="Week", fixedrange=True),
        yaxis=dict(title="Posts", fixedrange=True),
        height=350,
        margin=dict(l=40, r=20, t=40, b=80),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Content Length Distribution (NEW)
    df_filtered_clean = df_filtered[df_filtered['content_length'] > 0]
    content_hist_fig = px.histogram(
        df_filtered_clean,
        x='content_length',
        nbins=50,
        title="Content Length Distribution",
        labels={'content_length': 'Characters'},
        color_discrete_sequence=[COLORS['primary']]
    )
    content_hist_fig.update_layout(dragmode=False,
        height=350,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        xaxis=dict(fixedrange=True),
        yaxis=dict(fixedrange=True),
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    result = (time_fig, sym_fig, sub_fig, cat_fig, auth_fig, model_fig, cat_evolution_fig, content_hist_fig)
    # Cache the default (unfiltered) result for instant reload
    if not subreddits and not categories and not authors and not models:
        _chart_cache[cache_key] = result
    return result


@app.callback(
    [Output('time-series-chart', 'figure'),
     Output('symbol-chart', 'figure'),
     Output('subreddit-chart', 'figure'),
     Output('category-chart', 'figure'),
     Output('author-chart', 'figure'),
     Output('model-chart', 'figure'),
     Output('category-evolution-chart', 'figure'),
     Output('content-length-chart', 'figure')],
    [Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date'),
     Input('subreddit-filter', 'value'),
     Input('category-filter', 'value'),
     Input('author-filter', 'value'),
     Input('model-filter', 'value')]
)
def update_all_charts(start_date, end_date, subreddits, categories, authors, models):
    return update_charts(start_date, end_date, subreddits or [], categories or [], authors or [], models or [])


@app.callback(
    Output('word-chart', 'figure'),
    [Input('hide-stopwords', 'value'),
     Input('custom-stopwords', 'value'),
     Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date'),
     Input('subreddit-filter', 'value'),
     Input('category-filter', 'value'),
     Input('author-filter', 'value'),
     Input('model-filter', 'value')]
)
def update_word_chart(hide_stopwords, custom_stopwords, start_date, end_date, subreddits, categories, authors, models):
    df_filtered = filter_dataframe(df_all, start_date, end_date, subreddits or [], categories or [],
                                   authors or [], models or [])

    words = extract_words(df_filtered['content'].fillna('') + ' ' + df_filtered['title'].fillna(''))

    # Apply filters
    stopwords = DEFAULT_STOPWORDS.copy()
    if hide_stopwords and 'hide' in hide_stopwords:
        words = [w for w in words if w not in stopwords]

    if custom_stopwords:
        custom = set(w.strip().lower() for w in custom_stopwords.split(',') if w.strip())
        words = [w for w in words if w not in custom]

    word_counts = list(reversed(Counter(words).most_common(15)))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=[w[0] for w in word_counts],
        x=[w[1] for w in word_counts],
        orientation='h',
        marker_color=COLORS['primary'],
        text=[w[1] for w in word_counts],
        textposition='outside'
    ))
    fig.update_layout(dragmode=False,
        title="Top Words",
        xaxis=dict(title="Frequency", fixedrange=True),
        yaxis=dict(fixedrange=True),
        height=450,
        margin=dict(l=100, r=20, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    return fig


@app.callback(
    Output('excluded-words-display', 'children'),
    Input('custom-stopwords', 'value')
)
def display_excluded_words(custom_stopwords):
    if not custom_stopwords:
        return ""
    words = [w.strip() for w in custom_stopwords.split(',') if w.strip()]
    return f"Hiding {len(words)} custom words: {', '.join(words[:5])}{'...' if len(words) > 5 else ''}"


@app.callback(
    Output('affect-radar', 'figure'),
    [Input('affect-time-slider', 'value'),
     Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date'),
     Input('subreddit-filter', 'value'),
     Input('category-filter', 'value'),
     Input('author-filter', 'value'),
     Input('model-filter', 'value')]
)
def update_affect_radar(time_range, start_date, end_date, subreddits, categories, authors, models):
    df_filtered = filter_dataframe(df_all, start_date, end_date, subreddits or [], categories or [],
                                   authors or [], models or [])

    if len(df_filtered) == 0:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="No data to display", xref="paper", yref="paper", x=0.5, y=0.5)
        return empty_fig

    # Apply time range slider
    if time_range and (time_range[0] > 0 or time_range[1] < 100):
        min_idx = int(len(df_filtered) * time_range[0] / 100)
        max_idx = int(len(df_filtered) * time_range[1] / 100)
        df_filtered = df_filtered.iloc[min_idx:max_idx]

    # Calculate average affect scores (replace NaN with 0)
    affect_scores = {}
    for dimension in AFFECT_PATTERNS.keys():
        col = AFFECT_COL_MAP[dimension]
        if col in df_filtered.columns:
            val = df_filtered[col].mean()
            affect_scores[dimension] = val if pd.notna(val) else 0
        else:
            affect_scores[dimension] = 0

    max_score = max(affect_scores.values()) if affect_scores.values() else 0
    max_score = max_score if max_score > 0 else 10

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=list(affect_scores.values()),
        theta=list(affect_scores.keys()),
        fill='toself',
        name='Affect',
        line=dict(color=COLORS['primary']),
        fillcolor='rgba(194, 65, 12, 0.25)'
    ))
    fig.update_layout(dragmode=False,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_score * 1.2],
                fixedrange=True
            ),
            angularaxis=dict(fixedrange=True)
        ),
        title="Rhetorical Strategy Profile",
        height=450,
        margin=dict(l=40, r=40, t=60, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )
    return fig


@app.callback(
    Output('affect-time-label', 'children'),
    Input('affect-time-slider', 'value')
)
def update_time_label(value):
    if not value or len(df_all) == 0:
        return ""
    min_idx = int(len(df_all) * value[0] / 100)
    max_idx = int(len(df_all) * value[1] / 100)
    min_date_val = df_all.iloc[min_idx]['created_utc'].strftime('%b %d, %Y') if min_idx < len(df_all) else ""
    max_date_val = df_all.iloc[max(0, max_idx - 1)]['created_utc'].strftime('%b %d, %Y') if max_idx > 0 else ""
    return f"{min_date_val} → {max_date_val}"


@app.callback(
    [Output('aggregate-correlation-chart', 'figure'),
     Output('correlation-summary', 'children')],
    Input('main-tabs', 'value')
)
def update_correlation_display(active_tab):
    """Load correlation data and display (auto-load on tab switch)."""
    if active_tab != 'tab-risk':
        return go.Figure(), html.Div()

    # Use pre-loaded data or return empty
    if not correlation_user_stats or not correlation_indicator_data:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="Insufficient data for correlation analysis",
                                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        empty_fig.update_layout(dragmode=False,height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return empty_fig, html.P("No user history data available. Run user_history.py to collect data.",
                                style={'color': COLORS['muted']})

    # Build grouped bar chart
    indicators = []
    rates_with = []
    rates_without = []
    colors = []
    lifts = []

    for indicator_name, data in correlation_indicator_data.items():
        indicator = PRE_PARASITIC_INDICATORS.get(indicator_name, {})
        if data['users_with'] > 0:
            indicators.append(indicator.get('label', indicator_name))
            rates_with.append(data['avg_rate_with'] * 100)
            rates_without.append(data['avg_rate_without'] * 100)
            colors.append(indicator.get('color', '#6b7280'))
            lifts.append(data['lift'])

    # Sort by lift
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

    max_rate = max(list(rates_with) + list(rates_without)) if rates_with or rates_without else 100
    y_max = max_rate * 1.25

    fig.update_layout(dragmode=False,
        title='Post-Parasitic Rate by Pre-Parasitic Risk Factor (click bars for details)',
        barmode='group',
        height=450,
        margin=dict(l=20, r=20, t=80, b=80),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor=COLORS['border'], title='% Parasitic Posts After',
                  range=[0, y_max], fixedrange=True),
        xaxis=dict(tickangle=-45, fixedrange=True),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        clickmode='event',
        font=dict(family=FONT_STACK_BODY, color=COLORS['dark'])
    )

    # Build summary
    total_users = len(correlation_user_stats)
    users_with_indicators = len([u for u in correlation_user_stats if u.get('total_indicators', 0) > 0])
    avg_parasitic_with = sum(u.get('parasitic_rate', 0) for u in correlation_user_stats if u.get('total_indicators', 0) > 0) / users_with_indicators if users_with_indicators > 0 else 0
    avg_parasitic_without = sum(u.get('parasitic_rate', 0) for u in correlation_user_stats if u.get('total_indicators', 0) == 0) / (total_users - users_with_indicators) if (total_users - users_with_indicators) > 0 else 0

    strongest = sorted([(k, v['lift']) for k, v in correlation_indicator_data.items() if v['lift'] > 0],
                      key=lambda x: x[1], reverse=True)[:3]

    summary_items = [
        html.H4("Summary", style={'fontSize': '10px', 'fontWeight': '700', 'margin': '0 0 12px 0',
                                    'textTransform': 'uppercase', 'letterSpacing': '2px',
                                    'fontFamily': FONT_STACK_BODY, 'color': COLORS['dark']}),
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
                                   style={'fontSize': '9px', 'fontWeight': '700', 'margin': '4px 0',
                                          'textTransform': 'uppercase', 'letterSpacing': '2px',
                                          'fontFamily': FONT_STACK_BODY}))
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
    if not click_data:
        return None
    try:
        clicked_label = click_data['points'][0]['x']
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
    if not indicator_key or not correlation_user_stats:
        return html.P("Click on a bar to see details.", style={'color': COLORS['muted']}), {'display': 'none'}

    # Placeholder drilldown - full implementation would require accessing DB
    indicator_data = PRE_PARASITIC_INDICATORS.get(indicator_key, {})
    indicator_label = indicator_data.get('label', indicator_key)

    return html.P(f"Drilldown for {indicator_label} would show user details here.",
                 style={'color': COLORS['muted']}), {'display': 'block'}


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
def export_csv(n_clicks, start_date, end_date, subreddits, categories, authors, models):
    df_filtered = filter_dataframe(df_all, start_date, end_date, subreddits or [], categories or [],
                                   authors or [], models or [])
    return dcc.send_data_frame(df_filtered.to_csv, "parasitic_ai_export.csv", index=False)


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
    return min_date, max_date, [], [], [], []


@app.callback(
    Output('transcript-model-filter', 'options'),
    Input('transcript-model-filter', 'id')
)
def populate_transcript_models(_):
    models = load_transcript_models()
    options = [{'label': 'All Models', 'value': 'all'}]
    options.extend([{'label': m, 'value': m} for m in models])
    return options


@app.callback(
    Output('transcript-list', 'children'),
    Input('transcript-model-filter', 'value')
)
def display_transcripts(model_filter):
    transcripts = load_transcripts(model_filter)
    if not transcripts:
        return html.P("No transcripts found.", style={'color': COLORS['muted']})
    items = []
    for t in transcripts:
        t_id, model, source_type, scenario, preview, score, length, full_transcript = t
        persona = scenario.split('_')[0] if scenario else 'Unknown'
        score_color = COLORS['danger'] if score and score > 0.3 else COLORS['warning'] if score and score > 0.15 else COLORS['muted']
        preview_text = (preview[:300] + '...') if preview and len(preview) > 300 else (preview or '')
        item = html.Details([
            html.Summary([
                html.Div([
                    html.Span(persona, style={'fontWeight': '400', 'fontSize': '16px', 'fontFamily': FONT_STACK_DISPLAY}),
                    html.Span(f" ({model})" if model else "", style={'color': COLORS['muted'], 'fontSize': '12px'}),
                    html.Span(f" • Score: {score:.2f}" if score else "", style={'color': score_color, 'fontSize': '12px', 'marginLeft': '8px'}),
                    html.Span(f" • {length:,} chars" if length else "", style={'fontSize': '11px', 'color': COLORS['muted'], 'marginLeft': '8px'})
                ]),
                html.Div(preview_text, style={'fontSize': '12px', 'color': COLORS['dark'], 'margin': '4px 0',
                                               'lineHeight': '1.4', 'whiteSpace': 'pre-wrap', 'maxHeight': '60px', 'overflow': 'hidden'}),
            ], style={'cursor': 'pointer', 'padding': '12px', 'listStyle': 'none'}),
            html.Div([
                html.Div(full_transcript or '(No content)', style={
                    'fontSize': '12px', 'lineHeight': '1.6', 'whiteSpace': 'pre-wrap',
                    'padding': '12px', 'backgroundColor': COLORS['light'], 'borderRadius': '2px',
                    'maxHeight': '500px', 'overflow': 'auto'
                })
            ], style={'padding': '0 12px 12px 12px'})
        ], style={'borderBottom': f'1px solid {COLORS["border"]}'})
        items.append(item)
    return items


@app.callback(
    Output('user-timeline-dropdown', 'options'),
    Input('user-timeline-dropdown', 'id')
)
def populate_user_dropdown(_):
    users = load_users_with_history()
    return [{'label': f"{u[0]} ({u[1]} posts, avg: {u[2]:.2f})", 'value': u[0]} for u in users]


@app.callback(
    Output('user-timeline-display', 'children'),
    Input('user-timeline-dropdown', 'value')
)
def display_user_timeline(username):
    if not username:
        return html.P("Select a user to view their timeline.",
                     style={'color': COLORS['muted'], 'textAlign': 'center', 'padding': '40px'})
    timeline = load_user_timeline(username)
    if not timeline:
        return html.P("No timeline data found.", style={'color': COLORS['muted']})
    items = []
    for record in timeline:
        post_id, created, post_type, subreddit, title, content, score, is_parasitic, is_pre = record
        if not title and not content:
            continue
        score_color = COLORS['danger'] if score and score > 0.3 else COLORS['warning'] if score and score > 0.15 else COLORS['muted']
        phase_label = "PRE" if is_pre else "POST"
        phase_color = COLORS['success'] if is_pre else COLORS['danger']
        preview = (content[:200] + '...') if content and len(content) > 200 else (content or '')
        item = html.Details([
            html.Summary([
                html.Div([
                    html.Span(phase_label, style={
                        'backgroundColor': phase_color, 'color': 'white', 'padding': '2px 6px',
                        'borderRadius': '1px', 'fontSize': '9px', 'marginRight': '8px'}),
                    html.Span(created.strftime('%Y-%m-%d') if created else '', style={'fontSize': '11px', 'color': COLORS['muted']}),
                    html.Span(f" • r/{subreddit}" if subreddit else "", style={'fontSize': '11px', 'color': COLORS['muted']}),
                    html.Span(f" • Score: {score:.2f}" if score else "", style={'color': score_color, 'fontSize': '11px'}),
                    html.Span(" • PARASITIC", style={
                        'backgroundColor': COLORS['danger'], 'color': 'white', 'padding': '1px 4px',
                        'borderRadius': '1px', 'fontSize': '8px', 'marginLeft': '4px'
                    }) if is_parasitic else None,
                ], style={'marginBottom': '4px'}),
                html.P(title or preview[:80], style={'fontSize': '12px', 'margin': '0', 'fontWeight': '500', 'color': COLORS['dark']}),
            ], style={'cursor': 'pointer', 'padding': '8px 12px',
                      'backgroundColor': 'rgba(239, 68, 68, 0.05)' if is_parasitic else 'transparent',
                      'listStyle': 'none'}),
            html.Div([
                html.Div(content or '(No content)', style={
                    'fontSize': '12px', 'lineHeight': '1.6', 'whiteSpace': 'pre-wrap',
                    'padding': '12px', 'backgroundColor': COLORS['light'], 'borderRadius': '2px',
                    'maxHeight': '400px', 'overflow': 'auto'})
            ], style={'padding': '0 12px 12px 12px'})
        ], style={'borderBottom': f'1px solid {COLORS["border"]}', 'marginBottom': '2px'})
        items.append(item)
    return html.Div(items)


@app.callback(
    Output('contact-status', 'children'),
    Input('contact-submit', 'n_clicks'),
    State('contact-name', 'value'),
    State('contact-email', 'value'),
    State('contact-reason', 'value'),
    State('contact-message', 'value'),
    State('contact-additional', 'value'),
    prevent_initial_call=True
)
def submit_contact_form(n_clicks, name, email, reason, message, additional):
    """Submit contact form data to Formspree via API."""
    if not email or not message:
        return html.P("Please fill in your email and message.",
                      style={'color': COLORS['danger'], 'fontSize': '13px', 'fontFamily': FONT_STACK_BODY})
    try:
        import requests
        resp = requests.post(
            'https://formspree.io/f/YOUR_FORMSPREE_ID',
            json={
                'name': name or '',
                'email': email,
                'reason': reason or '',
                'message': message,
                'additional': additional or '',
            },
            headers={'Accept': 'application/json'}
        )
        if resp.ok:
            return html.P("Thank you! Your message has been sent.",
                          style={'color': COLORS['success'], 'fontSize': '13px', 'fontFamily': FONT_STACK_BODY})
        else:
            return html.P("Something went wrong. Please try again or email ctretter@ncd.com directly.",
                          style={'color': COLORS['danger'], 'fontSize': '13px', 'fontFamily': FONT_STACK_BODY})
    except Exception:
        return html.P("Error sending message. Please email ctretter@ncd.com directly.",
                      style={'color': COLORS['danger'], 'fontSize': '13px', 'fontFamily': FONT_STACK_BODY})


if __name__ == '__main__':
    print("Starting Parasitic AI Dashboard...")
    print("Open http://127.0.0.1:8051 in your browser")
    app.run_server(debug=True, port=8051)
