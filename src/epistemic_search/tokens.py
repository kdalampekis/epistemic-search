"""Shared, explicitly approximate token measurement for local text."""


def count_tokens(text: str) -> int:
    """Whitespace-token estimate v1, NOT a model tokenizer."""
    return len(text.split())
