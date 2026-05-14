# resume_agent

Multi-agent resume tailoring system — successor to `job_rag`.

## Background

The previous `job_rag` project established a RAG pipeline that embedded past job descriptions into ChromaDB, retrieved the most similar past application for a new role, and used Claude to rewrite a resume. It worked but had four pain points:

1. **Static DB** — required a manual `build_db.py` run whenever new jobs were added
2. **Formatting drift** — generated DOCX used wrong style names (`Heading 1` vs the actual `Normal` + `List Paragraph` used in real submitted resumes)
3. **No fact-checking** — single LLM pass with prompt-only hallucination guard
4. **Manual JD copy** — had to copy the JD PDF into a `new_jobs/` staging folder before running

`resume_agent` fixes all four and adds cover letter generation, validation, and an interactive embedding visualizer.

---

## Recent Updates (May 2025)

### ✅ Major Improvements
- **Quality Control System**: Comprehensive source resume validation with smart fallback to better matches
- **Enhanced Validation**: Added `ValidatorAgent` using Claude Haiku to cross-check all claims against source resume
- **Customer Support Detection**: Automatic role detection for support/training positions with tailored content
- **Portfolio Patch Integration**: Automatically enriches portfolio section from fallback resume when missing
- **Consistent Formatting**: Fixed bullet styles, date formats, and company naming conventions
- **Smart File Classification**: Improved detection of JD vs resume files with special case handling
- **Output Naming**: Files now use `ZhuYunhua_{Company}_resume.docx` format for better organization

### 🔧 Bug Fixes
- **BioNTech End Date**: Fixed "Present" → "09/2025" across all source resumes and prompts
- **Experience Years**: Enforced "10+ years" consistently (no "12 years" variations)
- **GSK Community of Practice**: Corrected "founded" → "initiated and led"
- **Cover Letter Bullets**: Restored bullets for scanning while maintaining rich prose
- **JSON Parsing**: Added guard for Claude API returning string instead of dict
- **Portfolio Dashes**: Stripped leading dashes to ensure consistent bullet formatting

### 🚀 New Features
- **Quality Control System**: Source resume validation with scoring and automatic fallback
- **Customer Support Role Detection**: Automatic identification and tailoring for support positions
- **Enhanced Cover Letters**: Role-specific generation with training emphasis
- **Embedding Visualization**: Interactive UMAP map with domain/outcome coloring and final-round stars
- **Supplemental Facts**: Pass portfolio patch content to validator to reduce false positives
- **Page Break Handling**: Validator warnings moved to separate page to avoid formatting issues
- **Progress Indicators**: Added console feedback for PDF processing and API calls

### 🛡️ Quality Control System
- **Source Validation**: Checks minimum content length, proper sections (name, headers, bullets)
- **Job Description Detection**: Prevents using JD files as source material
- **Smart Fallback**: Tries 2nd/3rd best matches when primary fails QC
- **Placeholder Prevention**: Eliminates `<UNKNOWN>` placeholders through quality validation
- **Error Handling**: Graceful handling of missing directories and inaccessible files
- **QC Reporting**: Detailed feedback with scores and specific issue identification

---

## Project structure

```
resume_agent/
  tailor.py                   ← main CLI — tailor resume + cover letter
  viz.py                      ← standalone embedding map CLI
  config.py                   ← paths, model names, DOCX style constants
  requirements.txt
  .env                        ← ANTHROPIC_API_KEY (never commit)
  db/                         ← ChromaDB vector store (259 JDs, never commit)
  agents/
    file_classifier.py        ← detect JD / resume / cover letter in any folder
    ingest_agent.py           ← embed new JD into ChromaDB; bulk re-ingest by date
    tailor_agent.py           ← RAG query + Claude Sonnet rewrite (tool_use)
    validator_agent.py        ← Claude Haiku claim cross-check vs source resume
    formatter_agent.py        ← render paragraph list → styled DOCX
    viz_agent.py              ← UMAP 2D map + TF-IDF axis words + final-round stars
  utils/
    text_extraction.py        ← PDF + DOCX text extraction
    docx_utils.py             ← DOCX style definitions + right-tab date alignment
  docs/
    usage.md                  ← full CLI reference (this file expanded)
```

---

## Setup

```bash
conda activate job-rag          # reuse existing environment

cp .env.example .env
# edit .env → ANTHROPIC_API_KEY=sk-ant-...

pip install -r requirements.txt  # adds plotly, umap-learn if not present
```

---

## Quick start

```bash
# Tailor resume + cover letter for a new job
python tailor.py --folder 260512_NewCompany

# Same + generate embedding map showing where this job sits
python tailor.py --folder 260512_NewCompany --viz

# Just the map (no tailoring)
python viz.py --highlight 260512_NewCompany
```

---

## All commands

### `tailor.py` — resume + cover letter

```bash
python tailor.py --folder FOLDER [--top-k N] [--viz]
python tailor.py --reingest-from YYMMDD
```

| Flag | Default | Description |
|---|---|---|
| `--folder` / `-f` | — | Folder name (e.g. `260512_NewCompany`) or full path |
| `--top-k` | 3 | Number of similar past JDs to retrieve from DB |
| `--viz` | off | Also generate `embedding_map.html` after tailoring |
| `--reingest-from` | — | Bulk-embed all folders from this date prefix onward, then exit |

**Pipeline steps (logged to console):**
```
[1/5] FileClassifier   — detect JD PDF, existing resume, cover letter
[2/5] IngestAgent      — embed JD into ChromaDB if not already present
[3/5] TailorAgent      — RAG query + Claude Sonnet rewrite (resume + cover)
[4/5] ValidatorAgent   — Claude Haiku fact-check all claims vs source resume
[5/5] FormatterAgent   — write tailored_resume_draft.docx + tailored_cover_draft.docx
[6/6] VizAgent         — (only with --viz) generate embedding_map.html
```

**Output** (written into the application folder):
- `ZhuYunhua_{Company}_resume.docx` (e.g., `ZhuYunhua_AbbVie_resume.docx`)
- `ZhuYunhua_{Company}_cover.docx` (e.g., `ZhuYunhua_AbbVie_cover.docx`)
- Validator violations appended on separate page if any are found

### `viz.py` — embedding map

```bash
python viz.py [--highlight FOLDER] [--output PATH]
```

Generates `embedding_map.html` — an interactive two-panel Plotly scatter plot:
- **Left panel**: coloured by domain (single-cell, AI/ML, clinical, spatial, etc.)
- **Right panel**: coloured by outcome (applied, interviewed, interviewing, rejected, 0_slow)
- **Axis-word box**: top TF-IDF terms correlated with each UMAP axis (bottom-left of left panel)
- **Region labels**: K-means cluster centroids annotated with dominant keywords
- **Red-orange stars ⭐**: hardcoded final-round jobs (AZ, Miltenyi, Amgen, UTHR, KellyOCG, Steampunk)
- **Gold star ★**: the highlighted new application

To add a new final-round job to the map, append to `FINAL_ROUND_SUBSTRINGS` in `agents/viz_agent.py`:
```python
("substring of JD filename",  "Short Label"),
```

---

## Agent descriptions

### `FileClassifier`
Scans an application folder and classifies every PDF/DOCX by filename keywords and content heuristics. Returns paths for the JD, source resume, and existing cover letter. Skips `tailored_*` output files.

### `IngestAgent`
Checks whether the JD is already in ChromaDB (by file path as doc ID). If not, extracts text and upserts with metadata (filename, folder, company, outcome). Also provides `bulk_ingest_from_date(YYMMDD)` to catch up the DB from a cutoff date.

### `TailorAgent`
Queries ChromaDB for the top-K most similar past JDs. Finds the source resume from the best-matched folder. Calls **Claude Sonnet** twice via `tool_use` (structured JSON output — no fragile regex): once for the resume, once for the cover letter. Each bullet follows the format: *action verb + method/tool + quantified outcome*.

### `ValidatorAgent`
Calls **Claude Haiku** to cross-check every factual claim in the draft against the source resume. Returns a list of violations (unverifiable claims). Accepts supplemental facts (e.g., portfolio patch content) to reduce false positives. Violations are printed to console and appended on a separate page in the output DOCX.

### `FormatterAgent`
Renders the validated paragraph list to DOCX using custom styles inferred from real submitted resumes: `Normal` + `List Paragraph` (not Word's default `Heading`/`List Bullet`). Job title lines have a right-aligned tab stop for the date range. Section headers get a navy bottom rule. Handles page breaks and ensures consistent bullet formatting (strips leading dashes).

### `VizAgent`
Fetches all embeddings from ChromaDB, runs UMAP (cosine metric), computes TF-IDF Spearman correlations for axis-word annotation, runs K-means for region labels, and renders an interactive two-panel Plotly HTML map.

---

## DOCX style spec

Inferred from 5 real submitted resumes (GSK, Hengrui, AZ, Merck, general).

| Element | Style | Size | Bold | Color |
|---|---|---|---|---|
| Candidate name | `resume_name` | 17pt | Yes | `#1A3A5C` navy |
| Section header | `resume_header` | 11pt | Yes | `#1A3A5C` + bottom rule |
| Job title \| Company → Date | `resume_job_title` | 10.5pt | Yes | black, date right-tabbed |
| Bullet | `resume_bullet` | 10.5pt | No | black |
| Body / contact | `resume_normal` | 10.5pt | No | black |
| Closing | `resume_closing` | 10.5pt | No | black, 24pt space above |
| Signature | `resume_signature` | 10.5pt | Yes | `#1A3A5C` navy |

Margins: 0.75" all sides. Font: Calibri.

---

## Folder naming convention

```
RESUME_ROOT/  (= ../resume/ relative to this project)
  YYMMDD_Company/           active new application
  YYMMDD.N_Company/         decimal suffix for multiple roles at same company
  0_slow/YYMMDD_Company/    no response
  rejected/YYMMDD_Company/
  interviewed/YYMMDD_Company/
  interviewing/YYMMDD_Company/
```
