"""Paths and settings for resume_agent. Secrets from .env only."""
import os
from dotenv import load_dotenv

load_dotenv()

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Paths ─────────────────────────────────────────────────────────────────────
RESUME_ROOT = os.path.abspath(os.path.join(_PROJECT_DIR, "..", "resume"))
DB_PATH = os.path.join(_PROJECT_DIR, "db")
DB_COLLECTION = "job_descriptions"
# Fallback resume folder — used when top-K matched folders have no recent resume
FALLBACK_RESUME_DIR = os.path.join(RESUME_ROOT, "260421_general_resume")

# ── API keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ── Models ────────────────────────────────────────────────────────────────────
TAILOR_MODEL    = "claude-sonnet-4-20250514"
VALIDATOR_MODEL = "claude-haiku-4-5"

# ── RAG ───────────────────────────────────────────────────────────────────────
TOP_K = 3   # number of similar past JDs to retrieve

# ── DOCX style spec (inferred from submitted resumes) ─────────────────────────
DOCX_MARGIN_INCHES  = 0.75
DOCX_FONT_FAMILY    = "Calibri"
DOCX_NAME_SIZE_PT   = 17.0
DOCX_HEADER_SIZE_PT = 11.0
DOCX_BODY_SIZE_PT   = 10.5
DOCX_NAME_COLOR     = "1A3A5C"   # dark navy — name + section headers
DOCX_BODY_COLOR     = "000000"
