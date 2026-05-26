"""
Shared paragraph schema for resume and cover letter generation.
Defines the structure for structured output from Claude tool-use.
"""

from typing import Dict, Any


PARAGRAPH_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "style": {
                "type": "string",
                "enum": [
                    "name", "header", "job_title", "bullet", "normal",
                    "date", "address", "salutation", "closing", "signature"
                ],
                "description": (
                    "name=candidate name (resume only), "
                    "header=ALL-CAPS section header (resume only), "
                    "job_title=Title | Company (date goes at end after last pipe — see format rule), "
                    "bullet=achievement bullet point, "
                    "normal=contact info / body paragraph, "
                    "date=letter date line, address=addressee block line, "
                    "salutation=Dear..., closing=Sincerely etc., signature=sender name"
                ),
            },
            "text": {"type": "string"},
        },
        "required": ["style", "text"],
    },
}


def validate_paragraph(para: dict) -> bool:
    """Validate a single paragraph has required fields."""
    return (
        isinstance(para, dict)
        and "style" in para
        and "text" in para
        and para["style"] in PARAGRAPH_SCHEMA["items"]["properties"]["style"]["enum"]
    )


def validate_paragraphs(paragraphs: list) -> bool:
    """Validate a list of paragraphs."""
    return all(validate_paragraph(p) for p in paragraphs)
