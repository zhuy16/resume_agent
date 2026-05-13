"""
FormatterAgent — render validated paragraph lists to DOCX files.
Writes tailored_resume_draft.docx and tailored_cover_draft.docx into the target folder.
"""
import os
import re

from utils.docx_utils import build_document


def _company_slug(folder_path: str) -> str:
    """Extract company name from folder e.g. '260512.1_NIST' → 'NIST'."""
    leaf = os.path.basename(folder_path.rstrip("/"))
    # strip leading date prefix like 260512.1_ or 260512_
    name = re.sub(r"^\d[\d.]*_", "", leaf)
    # keep only alphanumeric + hyphen, title-case
    name = re.sub(r"[^A-Za-z0-9\-]", "", name)
    return name or "Company"


class FormatterAgent:
    """Render resume and cover letter paragraph lists to DOCX files."""

    def run(
        self,
        folder_path: str,
        resume_paragraphs: list[dict],
        cover_paragraphs: list[dict],
        violations: list[dict] | None = None,
    ) -> dict:
        """
        Writes DOCX files to folder_path.
        If violations exist, prepends a warning paragraph to the resume draft.
        Returns {"resume_path": str, "cover_path": str | None}.
        """
        slug = _company_slug(folder_path)
        resume_out = os.path.join(folder_path, f"ZhuYunhua_{slug}_resume.docx")
        cover_out  = os.path.join(folder_path, f"ZhuYunhua_{slug}_cover.docx") if cover_paragraphs else None

        # Append violation warnings at end (after page break) so they don't disrupt resume pages
        final_resume = list(resume_paragraphs)
        if violations:
            final_resume.append({"style": "page_break", "text": ""})
            final_resume.append({"style": "header", "text": "⚠ VALIDATOR FLAGS — REVIEW BEFORE SENDING"})
            for i, v in enumerate(violations, 1):
                final_resume.append({"style": "normal",
                                     "text": f'{i}. "{v["draft_text"][:120]}"'})
                final_resume.append({"style": "bullet",
                                     "text": f'Issue: {v["issue"]}'})

        print("\n  Writing DOCX files...")
        build_document(final_resume, resume_out)
        if cover_paragraphs and cover_out:
            build_document(cover_paragraphs, cover_out)

        return {
            "resume_path": resume_out,
            "cover_path":  cover_out,
        }
