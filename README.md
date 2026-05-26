# resume_agent

**AI-powered resume and cover letter generator** with retrieval augmentation, fact-checking, and human-in-the-loop approval.

Given a job description PDF, the system retrieves the most similar past application from a vector database, uses Claude to rewrite the resume/cover letter for the new role, validates all claims against the source, and generates properly formatted DOCX files matching the style of real submitted resumes.

---

## What It Does

1. **Semantic Search** — Find the best matching past resume using ChromaDB + sentence embeddings
2. **AI Generation** — Claude rewrites resume and cover letter tailored to the new job
3. **Fact Validation** — Cross-checks every claim against source resume to prevent hallucinations
4. **Human Review** — Interactive approval checkpoints before finalizing (optional)
5. **DOCX Output** — Formatted matching real resume styles (custom bullets, right-aligned dates)

---

## Quick Start

```bash
# Setup
conda activate job-rag
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
pip install -r requirements.txt

# Generate resume + cover letter
python tailor.py --folder 260512_NewCompany

# Interactive mode with human checkpoints
python interactive.py --folder 260512_NewCompany

# Auto-approve mode (batch processing)
python interactive.py --folder 260512_NewCompany --auto

# Generate embedding visualization
python viz.py --highlight 260512_NewCompany
```

**Output**: `ZhuYunhua_{Company}_resume.docx` and `ZhuYunhua_{Company}_cover.docx`

---

## Architecture Overview

**Multi-agent system** with 8 specialized agents:

| Agent | Purpose |
|-------|---------|
| `FileClassifier` | Detects JD/resume/cover letter files |
| `IngestAgent` | Embeds new JDs into ChromaDB |
| `TailorAgent` | RAG query + Claude generation |
| `ReviewerAgent` | Style and job-fit critique |
| `ValidatorAgent` | Fact-checking vs source resume |
| `FormatterAgent` | Renders DOCX with custom styles |
| `Orchestrator` | Stateful workflow coordination |
| `VizAgent` | Embedding visualization (UMAP) |

**Key Design Decisions**:
- **Prompts extracted** to markdown files (`prompts/`)
- **Schemas centralized** for structured LLM output (`schemas/`)
- **Services separated** for business logic (`services/`)
- **Evaluation framework** with 12 tests (`evals/`)
- **Human checkpoints** for approval (resume + cover)
- **Execution tracing** for observability

See [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) for detailed design docs.

---

## Project structure

```
resume_agent/
  tailor.py                   ← main CLI — tailor resume + cover letter
  interactive.py              ← NEW: human-in-the-loop workflow CLI
  viz.py                      ← standalone embedding map CLI
  config.py                   ← paths, model names, DOCX style constants
  requirements.txt
  .env                        ← ANTHROPIC_API_KEY (never commit)
  db/                         ← ChromaDB vector store (259 JDs, never commit)
  prompts/                    ← NEW: versioned prompts (Phase 1)
    resume_system.md          ← 80-line resume generation guidelines
    cover_system.md           ← 75-line cover letter structure rules
  schemas/                    ← NEW: centralized schemas (Phase 1)
    paragraph.py              ← shared paragraph schema + validation
    resume_schema.py          ← RESUME_TOOL for Claude
    cover_schema.py           ← COVER_TOOL + structure constants
  services/                   ← NEW: business logic (Phase 1)
    retrieval.py              ← ChromaDB query operations
    source_selection.py       ← QC + fallback logic
    llm_client.py             ← Claude wrapper + TracedLLMClient
  agents/
    file_classifier.py        ← detect JD / resume / cover letter in any folder
    ingest_agent.py           ← embed new JD into ChromaDB; bulk re-ingest by date
    tailor_agent.py           ← RAG query + Claude Sonnet rewrite (tool_use)
    validator_agent.py        ← Claude Haiku claim cross-check vs source resume
    formatter_agent.py        ← render paragraph list → styled DOCX
    viz_agent.py              ← UMAP 2D map + TF-IDF axis words + final-round stars
    reviewer_agent.py         ← NEW: style + role-fit critique (Phase 2)
    orchestrator.py           ← NEW: stateful workflow with human checkpoints (Phase 3)
  evals/                      ← NEW: test framework (Phase 2)
    test_hallucination.py     ← 4 tests for factual accuracy
    test_structure.py         ← 8 tests for resume/cover structure
    runner.py                 ← test execution + quality reports
    golden_examples/          ← success criteria templates
  utils/
    text_extraction.py        ← PDF + DOCX text extraction
    docx_utils.py             ← DOCX style definitions + right-tab date alignment
  docs/
    usage.md                  ← full CLI reference (this file expanded)
```

---

## CLI Reference

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

### `interactive.py` — human-in-the-loop workflow (NEW)

```bash
python interactive.py --folder FOLDER [--auto] [--save]
```

| Flag | Default | Description |
|---|---|---|
| `--folder` / `-f` | — | Folder name (e.g. `260512_NewCompany`) |
| `--auto` / `-a` | off | Auto-approve all checkpoints (skip human review) |
| `--save` / `-s` | on | Save output DOCX files after approval |

**Workflow with human checkpoints:**
```
[1/9] RETRIEVING              → Query ChromaDB for similar past jobs
[2/9] SELECTING_SOURCE        → QC check + fallback if needed
[3/9] GENERATING_RESUME       → Claude Sonnet resume generation
[4/9] REVIEWING_RESUME        → AI critique (scores + recommendations)
[5/9] AWAITING_RESUME_APPROVAL → ⏸️ Human review & approval
[6/9] GENERATING_COVER        → Claude Sonnet cover letter generation
[7/9] REVIEWING_COVER         → AI critique
[8/9] AWAITING_COVER_APPROVAL → ⏸️ Human review & approval
[9/9] VALIDATING              → Final fact-check vs source resume
```

**Interactive approval** shows:
- Source resume quality score
- AI review scores (overall, style, fit)
- Content preview
- Yes/No approval prompt

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

## Docker Usage

Run the entire system with Docker Compose (includes Redis for job queue):

```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

**Services**:
- `app`: FastAPI server on port 8000
- `redis`: Job queue backend on port 6379
- `worker`: Background job processor (optional)

---

## API Usage

The FastAPI server provides REST endpoints for programmatic access:

### Start API Server

```bash
# Local development
uvicorn api.main:app --reload --port 8000

# Or with Docker
docker-compose up -d app
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check (DB connection) |
| `/jobs` | POST | Create new resume generation job |
| `/jobs` | GET | List recent jobs |
| `/jobs/{id}/status` | GET | Get job status and progress |
| `/jobs/{id}/approve/{checkpoint}` | POST | Approve human checkpoint |

### Example API Calls

```bash
# Create a job
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_folder": "260512_NewCompany", "auto_approve": false}'

# Check job status (replace JOB_ID with actual UUID)
curl http://localhost:8000/jobs/JOB_ID/status

# Approve resume checkpoint
curl -X POST http://localhost:8000/jobs/JOB_ID/approve/resume \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "feedback": "Looks good"}'
```

### Interactive API Docs

Open http://localhost:8000/docs for Swagger UI with try-it-out functionality.

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
