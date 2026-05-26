"""
Schema definitions for resume generation tool.
"""

from typing import Dict, Any
from schemas.paragraph import PARAGRAPH_SCHEMA


RESUME_TOOL: Dict[str, Any] = {
    "name": "write_resume",
    "description": "Output the fully rewritten tailored resume as structured paragraphs.",
    "input_schema": {
        "type": "object",
        "properties": {"paragraphs": PARAGRAPH_SCHEMA},
        "required": ["paragraphs"],
    },
}


# Resume-specific style validation
RESUME_STYLES = ["name", "header", "job_title", "bullet", "normal"]
