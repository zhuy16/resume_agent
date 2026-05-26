"""
Schema definitions for cover letter generation tool.
"""

from typing import Dict, Any
from schemas.paragraph import PARAGRAPH_SCHEMA


COVER_TOOL: Dict[str, Any] = {
    "name": "write_cover_letter",
    "description": "Output the tailored cover letter as structured paragraphs.",
    "input_schema": {
        "type": "object",
        "properties": {"paragraphs": PARAGRAPH_SCHEMA},
        "required": ["paragraphs"],
    },
}


# Cover letter-specific style validation
COVER_STYLES = ["date", "address", "salutation", "normal", "bullet", "closing", "signature"]


# Cover letter structure constants
COVER_STRUCTURE = [
    ("date", "Today's date spelled out"),
    ("address", "Company + team/dept on one line"),
    ("normal", "Re: line - job title only"),
    ("salutation", "Dear Hiring Manager,"),
    ("normal", "OPENING - 2-3 sentences"),
    ("normal", "FIT PARAGRAPH - 2-3 sentences"),
    ("bullet", "KEY CONTRIBUTION 1"),
    ("bullet", "KEY CONTRIBUTION 2"),
    ("bullet", "KEY CONTRIBUTION 3"),
    ("bullet", "KEY CONTRIBUTION 4"),
    ("normal", "WHY COMPANY + CLOSING - 2-3 sentences"),
    ("closing", "Sincerely,"),
    ("signature", "Candidate full name (e.g. 'Yunhua Zhu, PhD')"),
    ("normal", "phone | email (single line, no label)"),
]
