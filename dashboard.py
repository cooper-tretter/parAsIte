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
                ])
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
            ], style={'flex': '1'}),
            html.Div([
                card([
                    html.H3("Categories", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                  'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='category-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1'})
        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px'}),

        # Row: Authors + AI Models
        html.Div([
            html.Div([
                card([
                    html.H3("Top Authors", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                   'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='author-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1'}),
            html.Div([
                card([
                    html.H3("AI Models Mentioned", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                                          'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='model-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1'})
        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px'}),

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
            ], style={'flex': '1'}),
            html.Div([
                card([
                    html.H3("Symbols", style={'margin': '0 0 16px 0', 'fontSize': '16px',
                                               'fontWeight': '600', 'color': COLORS['dark']}),
                    dcc.Graph(id='symbol-chart', config={'displayModeBar': False})
                ])
            ], style={'flex': '1'})
        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '20px'}),

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
            html.Div(id='drill-table', style={'maxHeight': '400px', 'overflow': 'auto'})
        ], style={'backgroundColor': COLORS['white'], 'padding': '24px', 'borderRadius': '12px',
                  'maxWidth': '1200px', 'width': '90%', 'maxHeight': '80vh', 'overflow': 'auto',
                  'margin': 'auto', 'marginTop': '10vh',
                  'boxShadow': '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)'})
    ], id='drill-modal', style={'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0',
                                 'width': '100%', 'height': '100%',
                                 'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '1000'}),

    dcc.Store(id='drill-data'),
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
     Output('drill-data', 'data')],
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
        return {'display': 'none'}, None, "", None

    triggered = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered == 'close-modal':
        return {'display': 'none'}, None, "", None

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
    display_df['created_utc'] = display_df['created_utc'].dt.strftime('%Y-%m-%d %H:%M')
    display_df['parasite_score'] = display_df['parasite_score'].round(3)
    display_df['title'] = display_df['title'].fillna('[Comment]').str[:60]
    # Truncate content for display (full content in CSV export)
    display_df['content_preview'] = display_df['content'].fillna('').str[:200].str.replace('\n', ' ') + '...'
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
        data=display_df.to_dict('records'),
        columns=table_columns,
        style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '12px',
                    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    'border': 'none', 'maxWidth': '200px', 'overflow': 'hidden',
                    'textOverflow': 'ellipsis'},
        style_cell_conditional=[
            {'if': {'column_id': 'content_preview'},
             'maxWidth': '400px', 'whiteSpace': 'normal', 'height': 'auto',
             'overflow': 'hidden', 'textOverflow': 'ellipsis'}
        ],
        style_header={'backgroundColor': COLORS['light'], 'fontWeight': '600',
                      'borderBottom': f'1px solid {COLORS["border"]}'},
        style_data={'borderBottom': f'1px solid {COLORS["border"]}'},
        page_size=15,
        sort_action='native',
        markdown_options={'link_target': '_blank'}
    )

    export_data = df[['id', 'reddit_id', 'created_utc', 'subreddit', 'author',
                      'category', 'parasite_score', 'title', 'content', 'url']].to_json(force_ascii=False)

    modal_style = {'display': 'block', 'position': 'fixed', 'top': '0', 'left': '0',
                   'width': '100%', 'height': '100%', 'backgroundColor': 'rgba(0,0,0,0.5)',
                   'zIndex': '1000'}

    return modal_style, table, f"{description}{category_info} ({len(df):,} posts)", export_data


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


if __name__ == '__main__':
    print("Starting Parasitic AI Dashboard...")
    print("Open http://127.0.0.1:8051 in your browser")
    app.run_server(debug=True, port=8051)
