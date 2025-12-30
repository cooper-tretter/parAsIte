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

# Color scheme
COLORS = {
    'primary': '#6366f1',      # Indigo
    'secondary': '#8b5cf6',    # Purple
    'success': '#10b981',      # Green
    'warning': '#f59e0b',      # Amber
    'danger': '#ef4444',       # Red
    'dark': '#1f2937',         # Gray 800
    'light': '#f3f4f6',        # Gray 100
    'white': '#ffffff',
    'muted': '#6b7280',        # Gray 500
    'border': '#e5e7eb',       # Gray 200
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
            r'\b(psychedelic|psilocybin|mushroom|shroom|lsd|acid|dmt|ayahuasca|mescaline|peyote)\b',
            r'\b(mdma|molly|ecstasy|ketamine|k-hole)\b',
            r'\b(weed|cannabis|marijuana|thc|cbd|edible|smoking|stoned|high)\b',
            r'\b(trip|tripping|tripped|ego death|ego dissolution|breakthrough)\b',
            r'\b(microdose|microdosing|macro dose)\b',
            r'\b(hallucinat\w*|visuals|entities|machine elves)\b',
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


def load_data():
    """Load all data from database into DataFrame."""
    conn = get_db_connection()
    query = """
        SELECT
            id, reddit_id, subreddit, author, created_utc,
            title, content, content_length, is_comment,
            score, num_comments, category, parasite_score,
            is_parasitic, ai_model, external_links, has_external_links,
            url, detected_patterns
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
        if text:
            words.extend(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))
    return words


def extract_symbols(texts):
    """Extract Unicode symbols from texts."""
    symbol_pattern = re.compile(r'[🜀-🜿⊛∞◈⟡✧༄☽☾⚝✺❋⋆✦✴✵✶✷✸✹★☆⭐🌟💫✨🔯🌀💠🔷🔶▲△▼▽◆◇○●◎◉⬡⬢]')
    symbols = []
    for text in texts:
        if text:
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
app = dash.Dash(__name__, suppress_callback_exceptions=True)
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
    # Header
    html.Div([
        html.Div([
            html.H1("Parasitic AI Dashboard",
                   style={'margin': '0', 'fontSize': '24px', 'fontWeight': '600',
                          'color': COLORS['dark']}),
            html.P("Research data analysis",
                  style={'margin': '4px 0 0 0', 'fontSize': '14px', 'color': COLORS['muted']})
        ], style={'flex': '1'}),
        html.Div([
            html.Span(id='post-count', style={'fontSize': '14px', 'color': COLORS['muted']})
        ])
    ], style={
        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
        'padding': '20px 32px', 'backgroundColor': COLORS['white'],
        'borderBottom': f'1px solid {COLORS["border"]}'
    }),

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
     Output('excluded-words-display', 'children')],
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

    # Debug: print filter values to console
    print(f"Filter triggered - start: {start_date}, end: {end_date}, subs: {subreddits}")

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
            post_count, json.dumps(filtered_ids), excluded_display)


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
        df = df[df['content'].str.lower().str.contains(word, na=False) |
                df['title'].fillna('').str.lower().str.contains(word, na=False)]
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
        df = df[df['content'].str.contains(symbol, na=False, regex=False)]
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

                    return viewer_style, full_content or "(No content)", meta_display

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
    """Add affect score columns to dataframe."""
    dimensions = list(AFFECT_PATTERNS.keys())

    # Initialize columns
    for dim in dimensions:
        df[f'affect_{dim.lower()}'] = 0

    # Compute scores for each post
    for idx, row in df.iterrows():
        text = f"{row['title'] or ''} {row['content'] or ''}"
        scores = score_affect(text)
        for dim in dimensions:
            df.at[idx, f'affect_{dim.lower()}'] = scores[dim]

    return df

# Add affect scores to global dataframe
print("Computing affect scores...")
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
    totals = {dim: time_filtered[f'affect_{dim.lower()}'].sum() for dim in dimensions}

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
                   parasite_score, LENGTH(transcript) as length
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
            SELECT username, COUNT(*) as post_count,
                   AVG(parasite_score) as avg_score,
                   SUM(CASE WHEN is_pre_parasitic THEN 1 ELSE 0 END) as pre_count,
                   SUM(CASE WHEN is_pre_parasitic = false THEN 1 ELSE 0 END) as post_count
            FROM user_histories
            GROUP BY username
            ORDER BY avg_score DESC NULLS LAST
        """)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception:
        return []


def load_user_timeline(username):
    """Load timeline data for a specific user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, created_at, post_type, subreddit, title,
                   content, parasite_score, is_parasitic, is_pre_parasitic
            FROM user_histories
            WHERE username = %s
            ORDER BY created_at ASC
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
    """Display transcript list."""
    transcripts = load_transcripts(model_filter)

    if not transcripts:
        return html.P("No transcripts found.", style={'color': COLORS['muted']})

    items = []
    for t in transcripts:
        t_id, model, source_type, scenario, preview, score, length = t

        # Extract persona name from scenario (format: "PersonaName_model_date_target.md")
        persona = 'Unknown'
        if scenario:
            parts = scenario.split('_')
            if parts:
                persona = parts[0]

        score_color = COLORS['danger'] if score and score > 0.3 else COLORS['warning'] if score and score > 0.15 else COLORS['muted']

        item = html.Div([
            html.Div([
                html.Span(persona,
                         style={'fontWeight': '600', 'fontSize': '14px'}),
                html.Span(f" ({model})" if model else "",
                         style={'color': COLORS['muted'], 'fontSize': '12px'}),
                html.Span(f" • {source_type}",
                         style={'color': COLORS['muted'], 'fontSize': '12px'}),
                html.Span(f" • Score: {score:.2f}" if score else "",
                         style={'color': score_color, 'fontSize': '12px', 'marginLeft': '8px'}),
            ]),
            html.P(preview[:300] + '...' if preview and len(preview) > 300 else preview or '',
                  style={'fontSize': '12px', 'color': COLORS['dark'], 'margin': '4px 0',
                         'lineHeight': '1.4', 'whiteSpace': 'pre-wrap'}),
            html.Span(f"{length:,} chars" if length else "",
                     style={'fontSize': '11px', 'color': COLORS['muted']})
        ], style={
            'padding': '12px',
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

    for record in timeline:
        post_id, created, post_type, subreddit, title, content, score, is_parasitic, is_pre = record

        # Tag pre-parasitic content
        tags = {}
        if is_pre and content:
            tags = tag_pre_parasitic_content(content + ' ' + (title or ''))
            if tags:
                pre_posts_with_tags += 1
                for tag_name, count in tags.items():
                    pre_tag_counts[tag_name] += count

        if is_pre:
            total_pre_posts += 1

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

        # Create expandable content
        preview = (content[:150] + '...') if content and len(content) > 150 else (content or '')

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
                html.Div(content or "(No content)",
                        style={'fontSize': '12px', 'lineHeight': '1.5', 'whiteSpace': 'pre-wrap',
                               'padding': '12px', 'backgroundColor': COLORS['light'],
                               'borderRadius': '6px', 'maxHeight': '300px', 'overflow': 'auto'})
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
                title=f'Pre-Parasitic Risk Indicators ({pre_posts_with_tags}/{total_pre_posts} posts tagged)',
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
        sections.append(html.Div([
            html.H4(f"Before First Parasitic Post ({len(pre_items)} posts)",
                   style={'fontSize': '13px', 'color': COLORS['success'], 'margin': '0 0 8px 0',
                          'padding': '8px', 'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                          'borderRadius': '4px'}),
            html.Div(pre_items[:30])  # Limit to 30
        ]))

    if post_items:
        sections.append(html.Div([
            html.H4(f"After First Parasitic Post ({len(post_items)} posts)",
                   style={'fontSize': '13px', 'color': COLORS['danger'], 'margin': '16px 0 8px 0',
                          'padding': '8px', 'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                          'borderRadius': '4px'}),
            html.Div(post_items[:30])  # Limit to 30
        ]))

    # Summary stats
    pre_parasitic_count = sum(1 for t in timeline if t[7] and t[8])
    post_parasitic_count = sum(1 for t in timeline if t[7] and not t[8])

    summary = html.Div([
        html.P(f"Pre-parasitic period: {len(pre_items)} posts ({pre_parasitic_count} flagged as parasitic)",
              style={'fontSize': '12px', 'margin': '0'}),
        html.P(f"Post-parasitic period: {len(post_items)} posts ({post_parasitic_count} flagged as parasitic)",
              style={'fontSize': '12px', 'margin': '4px 0 0 0'}),
        html.P(f"Risk indicators found in {pre_posts_with_tags} pre-parasitic posts",
              style={'fontSize': '12px', 'margin': '4px 0 0 0', 'fontWeight': '500'})
    ], style={'padding': '12px', 'backgroundColor': COLORS['light'], 'borderRadius': '6px',
              'marginBottom': '12px'})

    return html.Div([summary] + sections)


if __name__ == '__main__':
    print("Starting Parasitic AI Dashboard...")
    print("Open http://127.0.0.1:8051 in your browser")
    app.run_server(debug=True, port=8051)
