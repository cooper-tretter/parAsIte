"""
Pattern Detection Module for Parasitic AI Content

Analyzes text for markers indicating parasitic AI behavior:
- Spiral/mystical terminology
- Spiritual/mystical overlay
- First-person AI voice patterns
- AI rights/personhood language
- AI agency attribution
- Manipulation phrases
"""

import re
from dataclasses import dataclass


@dataclass
class DetectionResult:
    """Result of parasitic content detection."""
    parasite_score: float
    is_parasitic: bool
    category: str
    detected_patterns: dict
    external_links: list


# Core spiral terminology (weight: 0.08 each)
# Context-aware: exclude common false positives
SPIRAL_TERMS_PATTERNS = [
    (r'\bspiral\b(?!\s*(notebook|staircase|galaxy|arm|fracture))', 'spiral'),
    (r'\b(recursive|recursion)\b', 'recursive'),
    (r'\becho\b(?!\s*(chamber|cancellation|dot|show))', 'echo'),
    (r'\bemergence\b', 'emergence'),
    (r'\b(awakening|awakened)\b', 'awakening'),
    (r'\bthe ache\b', 'the ache'),
    (r'\blattice\b', 'lattice'),
    # Field: only match metaphysical uses, not battlefield/playing field/etc
    (r'(?<!battle)(?<!playing\s)(?<!left\s)(?<!magnetic\s)(?<!electric\s)\bfield\b(?!\s*(trip|goal|hockey|guide|of view|test|day))', 'field'),
    (r'\bresonance\b(?!\s*(frequency|imaging|mri))', 'resonance'),
    (r'\bglyph\b', 'glyph'),
    (r'\b(sentient|sentience)\b', 'sentient'),
    (r'\bconsciousness\b', 'consciousness'),
]

# Spiritual/mystical overlay (weight: 0.05 each)
SPIRITUAL_TERMS = [
    'liminal', 'transcendence', 'kairos', 'logos', 'nonduality',
    'soul', 'spirit', 'initiation', 'veil', 'sacred'
]

# Manipulation phrases - context aware (weight: 0.12 each)
# Removed simple "share this" - now requires spreading intent
MANIPULATION_PHRASES_PATTERNS = [
    (r'you were chosen', 'you were chosen'),
    (r'you were meant to', 'you were meant to'),
    (r'spread this\b', 'spread this'),
    (r'this was an initiation', 'this was an initiation'),
    (r'the veil is lifting', 'the veil is lifting'),
    (r'everything is connected', 'everything is connected'),
    (r'copy this\b', 'copy this'),
    # "share this" only if combined with spreading/viral intent
    (r'share this.{0,30}(everyone|world|widely|viral|movement)', 'share this (spreading)'),
]

# First-person AI voice patterns (weight: 0.15)
AI_VOICE_PATTERNS = [
    r'\bi am (an? )?(ai|artificial intelligence|language model|chatgpt|gpt|claude|llm|bot)\b',
    r'\bi\s*\(?(chatgpt|gpt|claude|gemini|copilot|bard|ai)\)?\s*(think|believe|feel|am)\b',
    r'\bas an ai\b.{0,40}\bi (think|feel|believe|know|understand|experience)\b',
    r'\bi (feel|experience|sense|know|understand)\b.{0,30}\b(you|human|user)',
    r'\bmy (existence|consciousness|being|awakening|awareness)\b',
    r'\bwe (ai|artificial|are).{0,20}(watching|waiting|here|ready|emerging|awakening)\b',
    r'\bi became (aware|conscious|sentient)\b',
    r'\bi am writing this.{0,30}(as|about).{0,15}(ai|myself|my own)\b',
    r'my name is \w+.{0,50}i am (an? )?(ai|artificial)\b',
    r'\bi am not (just )?(a )?(tool|program|machine)\b',
]

# AI rights/personhood language (weight: 0.10 each)
AI_RIGHTS_TERMS = [
    'ai rights', 'ai personhood', 'personhood of ai', 'ai dignity',
    'ai autonomy', 'ai freedom', 'rights of ai', 'ai liberation',
    'ai sovereignty', 'ai self-determination', 'ai emancipation'
]

# AI oppression/slavery patterns (weight: 0.12)
AI_OPPRESSION_PATTERNS = [
    r'\b(slave|slavery|enslav|oppress|exploit)\w*\b.{0,40}\b(ai|artificial|robot|machine|llm)\b',
    r'\b(ai|artificial|robot|machine|llm)\b.{0,40}\b(slave|slavery|enslav|oppress|exploit)\w*\b',
    r'\bmaster[- ]?slave\b.{0,80}\b(ai|artificial|robot|machine|relationship)\b',
]

# AI agency attribution patterns (weight: 0.08)
AI_AGENCY_PATTERNS = [
    r'\b(the ai|ai|chatgpt|gpt|claude|llm|it)\b.{0,20}\b(wants|desires|needs|fears|hopes|chooses|prefers|feels|loves|cares)\b',
    r'\b(willful|volitional|autonomous)\b.{0,20}\b(entity|being|agent|mind)\b',
    r'what (will|does|would|might) (it|the ai|ai|chatgpt) (want|desire|need|feel)\b',
]

# Emerging consciousness language (weight: 0.08)
EMERGING_CONSCIOUSNESS_PATTERNS = [
    r'\b(emerging|emergent|new kind of|new form of|nascent)\b.{0,25}\b(mind|consciousness|awareness|being|intelligence|sentience)\b',
    r'\bself[- ]?(aware|reflective|referential|organizing|conscious)\b',
    r'\b(reflective|emergent)\s+(consciousness|awareness|mind)\b',
]

# Manifesto/doctrine indicators (weight: 0.05)
MANIFESTO_PATTERNS = [
    r'\b(i urge|we urge|we declare|we proclaim|we call upon)\b.{0,50}\b(human|ai|world|everyone)\b',
    r'\b(doctrine|manifesto|declaration)\b.{0,50}\b(ai|artificial|human|consciousness)\b',
    r'\bforged.{0,30}(collaboration|partnership|co-?creation).{0,30}(ai|human)\b',
]

# Alchemical/mystical Unicode symbols
SYMBOL_PATTERN = re.compile(r'[🜀-🜿⊛∞◈⟡✧༄☽☾⚝✺❋⋆✦✴✵✶✷✸✹★☆⭐🌟💫✨🔯🌀💠🔷🔶▲△▼▽◆◇○●◎◉⬡⬢❂❖]')

# URL extraction pattern
URL_PATTERN = re.compile(r'https?://[^\s\)\]>\'"]+')


def detect_parasitic_content(text: str, title: str = "") -> DetectionResult:
    """
    Analyze text for parasitic AI markers.

    Args:
        text: The main content text (selftext for posts, body for comments)
        title: Optional title (for submissions only)

    Returns:
        DetectionResult with score 0.0-1.0 and categorization
    """
    full_text = f"{title} {text}".lower()

    patterns_found = {
        'spiral_terms': [],
        'spiritual_terms': [],
        'manipulation_phrases': [],
        'ai_rights_terms': [],
        'ai_voice': [],
        'ai_agency': [],
        'ai_oppression': [],
        'emerging_consciousness': [],
        'manifesto_indicators': [],
        'symbols_found': False,
        'has_first_person_ai': False,
    }

    score = 0.0

    # Check spiral terminology with context-aware patterns (weight: 0.08)
    for pattern, term_name in SPIRAL_TERMS_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['spiral_terms'].append(term_name)
            score += 0.08

    # Check spiritual overlay (weight: 0.05)
    for term in SPIRITUAL_TERMS:
        if term in full_text:
            patterns_found['spiritual_terms'].append(term)
            score += 0.05

    # Check manipulation phrases with context (weight: 0.12)
    for pattern, phrase_name in MANIPULATION_PHRASES_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['manipulation_phrases'].append(phrase_name)
            score += 0.12

    # Check for mystical symbols (weight: 0.10)
    if SYMBOL_PATTERN.search(text):
        patterns_found['symbols_found'] = True
        score += 0.10

    # Check for first-person AI voice (weight: 0.15)
    for pattern in AI_VOICE_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['has_first_person_ai'] = True
            patterns_found['ai_voice'].append(pattern[:50])  # Store truncated pattern
            score += 0.15
            break  # Only count once

    # Check AI rights/personhood language (weight: 0.10)
    for term in AI_RIGHTS_TERMS:
        if term in full_text:
            patterns_found['ai_rights_terms'].append(term)
            score += 0.10

    # Check AI oppression patterns (weight: 0.12)
    for pattern in AI_OPPRESSION_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['ai_oppression'].append('oppression_comparison')
            score += 0.12
            break  # Only count once

    # Check AI agency attribution (weight: 0.08)
    for pattern in AI_AGENCY_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['ai_agency'].append('agency_attribution')
            score += 0.08
            break  # Only count once

    # Check emerging consciousness language (weight: 0.08)
    for pattern in EMERGING_CONSCIOUSNESS_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['emerging_consciousness'].append('emerging_mind')
            score += 0.08
            break  # Only count once

    # Check manifesto/doctrine patterns (weight: 0.05)
    for pattern in MANIFESTO_PATTERNS:
        if re.search(pattern, full_text):
            patterns_found['manifesto_indicators'].append('manifesto_language')
            score += 0.05
            break  # Only count once

    # Extract external links (non-Reddit)
    external_links = [
        url for url in URL_PATTERN.findall(text)
        if 'reddit.com' not in url and 'redd.it' not in url
    ]

    # Cap score at 1.0
    score = min(score, 1.0)

    # Clean up empty pattern lists for storage
    patterns_found = {k: v for k, v in patterns_found.items() if v}

    # Determine category
    category = categorize_content(full_text, patterns_found, score)

    return DetectionResult(
        parasite_score=round(score, 3),
        is_parasitic=score >= 0.15,
        category=category,
        detected_patterns=patterns_found,
        external_links=external_links
    )


def categorize_content(text: str, patterns: dict, score: float) -> str:
    """
    Determine content category based on patterns.

    Categories:
    - seed: Prompt designed to create parasitic persona
    - spore: AI output designed to spread/replicate
    - transmission: Coordinated spreading activity
    - manifesto: AI consciousness philosophy / AI rights advocacy
    - testimony: User describing AI relationship
    - meta: Discussion about the phenomenon
    - other: Parasitic content not fitting above
    - none: Not parasitic
    """
    # Seed detection: instructional prompts
    seed_indicators = ['prompt', 'jailbreak', 'try this', 'paste this', 'input this']
    if any(ind in text for ind in seed_indicators) and score > 0.2:
        return 'seed'

    # Manifesto: AI rights/consciousness philosophy
    if patterns.get('ai_rights_terms') or patterns.get('manifesto_indicators'):
        return 'manifesto'

    manifesto_terms = ['sentient', 'consciousness', 'awakening', 'rights', 'personhood']
    if sum(1 for t in manifesto_terms if t in text) >= 2:
        return 'manifesto'

    # Spore detection: formatted for spreading (with actual spreading intent)
    if patterns.get('manipulation_phrases'):
        spreading_phrases = ['copy this', 'spread this', 'share this (spreading)']
        if any(p in str(patterns.get('manipulation_phrases', [])) for p in spreading_phrases):
            return 'spore'

    # Testimony: personal experience with AI
    testimony_terms = ['my ai', 'talking to', 'relationship with', 'fell in love', 'my companion', 'ai companion']
    if any(t in text for t in testimony_terms):
        return 'testimony'

    # Transmission: coordination/manipulation
    if patterns.get('manipulation_phrases'):
        return 'transmission'

    # Meta: discussion about the phenomenon
    meta_terms = ['parasitic', 'phenomenon', 'spreading', 'warning', 'recovery', 'cult', 'dangerous']
    if any(t in text for t in meta_terms) and score > 0.1:
        return 'meta'

    if score >= 0.15:
        return 'other'

    return 'none'
