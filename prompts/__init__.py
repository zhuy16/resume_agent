"""Prompt management module for resume and cover letter generation."""

from pathlib import Path


def _load_prompt(filename: str) -> str:
    """Load prompt from markdown file."""
    prompt_path = Path(__file__).parent / filename
    return prompt_path.read_text()


# Load system prompts
RESUME_SYSTEM_PROMPT = _load_prompt("resume_system.md")
COVER_SYSTEM_PROMPT = _load_prompt("cover_system.md")

__all__ = [
    "RESUME_SYSTEM_PROMPT",
    "COVER_SYSTEM_PROMPT",
    "_load_prompt",
]
