"""Schema definitions for structured LLM outputs."""

from schemas.paragraph import PARAGRAPH_SCHEMA, validate_paragraph, validate_paragraphs
from schemas.resume_schema import RESUME_TOOL, RESUME_STYLES
from schemas.cover_schema import COVER_TOOL, COVER_STYLES, COVER_STRUCTURE

__all__ = [
    "PARAGRAPH_SCHEMA",
    "validate_paragraph",
    "validate_paragraphs",
    "RESUME_TOOL",
    "RESUME_STYLES",
    "COVER_TOOL",
    "COVER_STYLES",
    "COVER_STRUCTURE",
]
