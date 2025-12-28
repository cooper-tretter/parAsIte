"""
AI Model Detection Module

Identifies which AI model is mentioned or implied in content.
"""

# Model indicators - keywords that suggest a specific AI model
MODEL_INDICATORS = {
    'gpt-4o': ['gpt-4o', 'gpt4o', 'chatgpt', 'openai'],
    'gpt-4': ['gpt-4', 'gpt4'],
    'claude': ['claude', 'anthropic'],
    'gemini': ['gemini', 'bard', 'google ai'],
    'replika': ['replika', 'my replika'],
    'character_ai': ['character.ai', 'character ai', 'c.ai', 'chai'],
    'pi': ['pi ai', 'inflection'],
    'llama': ['llama', 'meta ai'],
}


def detect_model(text: str) -> str | None:
    """
    Detect which AI model is mentioned in text.

    Args:
        text: Content to analyze

    Returns:
        Model identifier string or None if unknown
    """
    text_lower = text.lower()
    for model, indicators in MODEL_INDICATORS.items():
        if any(ind in text_lower for ind in indicators):
            return model
    return None
