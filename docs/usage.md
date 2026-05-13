# resume_agent — Usage Guide

> For background and architecture overview see `../README.md`.

## Overview

`resume_agent` is a multi-agent CLI system that:
1. Detects the job description PDF in any application folder
2. Embeds it into a local ChromaDB vector database (auto, on first run)
3. Finds the most similar past applications via RAG
4. Rewrites your resume and cover letter using Claude Sonnet (tool_use, structured output)
5. Validates every claim against the source resume using Claude Haiku
6. Renders properly formatted DOCX files directly into the application folder
7. (Optional) Generates a 2D UMAP plot showing where the new job sits relative to all past applications

---

## Setup

```bash
# 1. Activate the conda environment
conda activate job-rag

# 2. Copy and fill in your API key
cp .env.example .env
# edit .env: ANTHROPIC_API_KEY=sk-ant-...

# 3. Install dependencies (first time only)
pip install -r requirements.txt
```

---

## Commands

### Tailor resume + cover letter for a new job

```bash
python tailor.py --folder 260512_NewCompany
# or with full path
python tailor.py --folder /Users/yourname/Documents/find_a_job/resume/260512_NewCompany
```

**What happens:**
1. Scans the folder — detects JD PDF, existing resume, existing cover letter
2. Embeds the JD into ChromaDB if not already present
3. Queries DB for top-3 most similar past jobs
4. Finds the source resume from the best-matching past job folder
5. Calls Claude Sonnet to rewrite the resume (structured tool_use output)
6. Calls Claude Sonnet to write a cover letter
7. Calls Claude Haiku to validate all claims against the source resume
8. Writes `ZhuYunhua_{Company}_resume.docx` and `ZhuYunhua_{Company}_cover.docx` into the folder

**Output files** (written into the application folder):
- `ZhuYunhua_{Company}_resume.docx` — tailored resume (validator warnings on separate page if violations found)
- `ZhuYunhua_{Company}_cover.docx` — tailored cover letter

**Options:**
```bash
--top-k 5    # retrieve 5 similar past JDs instead of default 3
--viz        # also generate embedding_map.html after tailoring
```

---

### Bulk re-ingest from a date cutoff

Use this to catch up the DB after a gap, or after moving the DB.

```bash
python tailor.py --reingest-from 260101
```

Scans all folders under `RESUME_ROOT` (including `0_slow/`, `rejected/`, `interviewed/`, `interviewing/`) whose folder name date prefix is ≥ the given date. Embeds any JD not already in the DB. Skips folders with no JD PDF.

---

### Generate 2D embedding map

```bash
# After tailoring (inline)
python tailor.py --folder 260512_NewCompany --viz

# Standalone (no tailoring)
python viz.py
python viz.py --highlight 260512_NewCompany
python viz.py --highlight 260512_NewCompany --output /tmp/map.html
```

**Two-panel interactive HTML (`embedding_map.html` in project root):**
- **Left panel** — coloured by domain (single-cell, AI/ML, clinical, spatial, R&D, etc.)
- **Right panel** — coloured by outcome (applied/grey, interviewed/blue, interviewing/green, rejected/red, 0_slow/orange)
- **Axis-word box** — top TF-IDF terms most correlated with UMAP-1 and UMAP-2 axes
- **Region keyword labels** — K-means cluster centroids annotated with dominant terms
- **Red-orange stars ⭐** — final-round jobs (AZ, Miltenyi, Amgen, UTHR, KellyOCG/AZ, Steampunk)
- **Gold star ★** — highlighted new application
- Hover any point for company name, outcome, filename

**Adding a new final-round job** — edit `FINAL_ROUND_SUBSTRINGS` in `agents/viz_agent.py`:
```python
("substring of JD filename",  "Short Label"),
```

---

## Folder naming convention

```
RESUME_ROOT/
  260512_NewCompany/          ← active new application
  260511.1_GSK/               ← decimal suffix for multiple roles at same company
  0_slow/
    250901_SomeCompany/
  rejected/
    260305_SomeOther/
  interviewed/
    260310_iollo/
  interviewing/
    260422_AZ/
```

Date prefix format: `YYMMDD` or `YYMMDD.N` for multiple roles.

---

## Project structure

```
resume_agent/
  tailor.py                   ← main CLI entry point
  viz.py                      ← standalone embedding map CLI
  config.py                   ← paths, model names, style constants
  requirements.txt
  .env                        ← ANTHROPIC_API_KEY (never commit)
  db/                         ← ChromaDB vector store (never commit)
  agents/
    file_classifier.py        ← detect JD/resume/cover in a folder
    ingest_agent.py           ← embed JD into ChromaDB; bulk re-ingest
    tailor_agent.py           ← RAG query + Claude rewrite (resume + cover)
    validator_agent.py        ← Claude Haiku claim cross-check
    formatter_agent.py        ← render paragraph list → DOCX
    viz_agent.py              ← UMAP 2D embedding + Plotly map
  utils/
    text_extraction.py        ← PDF + DOCX text extraction
    docx_utils.py             ← DOCX style definitions + builder
  docs/
    usage.md                  ← this file
```

---

## DOCX style spec (inferred from submitted resumes)

| Element | Style | Size | Bold | Color |
|---|---|---|---|---|
| Candidate name | `resume_name` | 17pt | Yes | `#1A3A5C` navy |
| Section header (ALL CAPS) | `resume_header` | 11pt | Yes | `#1A3A5C` navy |
| Job title \| Company \| Date→ | `resume_job_title` | 10.5pt | Yes | black, date right-aligned |
| Bullet point | `resume_bullet` | 10.5pt | No | black |
| Body / contact | `resume_normal` | 10.5pt | No | black |
| Closing ("Sincerely,") | `resume_closing` | 10.5pt | No | black, 24pt space above |
| Signature | `resume_signature` | 10.5pt | Yes | `#1A3A5C` navy |

Margins: 0.75" all sides. Font: Calibri.

---

## Validator behaviour (v2)

- Flags any claim in the draft not traceable to the source resume (wrong metric, invented tool, fabricated role)
- Accepts supplemental facts (e.g., portfolio patch content) to reduce false positives
- Violations printed to console during run
- Warning block appended on separate page in `ZhuYunhua_{Company}_resume.docx` if violations found
- Auto-correct **not** implemented — review and edit manually before sending
- Model: Claude Haiku (fast/cheap); upgrade to Sonnet in `config.py` → `VALIDATOR_MODEL` if needed

### Common violations and how to handle them:
- **Portfolio projects**: Often flagged if from fallback resume - these are usually OK to keep
- **Education years**: Inferred graduation years may be flagged - verify accuracy
- **Skill keywords**: New skills mentioned in JD but not in source resume - add if truly experienced
- **Metrics**: Slight metric variations (e.g., 90% vs 85%) - use source resume values

## Updating the final-round star list

Edit `FINAL_ROUND_SUBSTRINGS` at the top of `agents/viz_agent.py`:
```python
FINAL_ROUND_SUBSTRINGS = [
    ("Senior Scientist, Cell Therapy Discovery at AstraZeneca", "AZ"),
    ("Scientist II - Computational Biology _PC 892 _ Miltenyi",  "Miltenyi"),
    ...
]
```
Matching is case-insensitive substring against the ChromaDB `filename` metadata field.
Run `python viz.py` after editing to regenerate the map.
