# progress.md — resume_agent design & build tracker

## Context (from job_rag analysis)

**Source project**: `../job_rag/`
**Stack carried forward**: Python 3.11, conda, ChromaDB, sentence-transformers, Anthropic Claude API, PyPDF2, python-docx

**RESUME_ROOT**: `/Users/yunhuazhu/Documents/find_a_job/resume/`
- New applications: `resume/{YYMMDD[.N]_Company}/` (root level)
- Past outcomes: `0_slow/`, `rejected/`, `interviewed/`, `interviewing/`

---

## Four pain points to solve

| # | Pain point | Root cause in job_rag | Planned fix |
|---|---|---|---|
| 1 | Static DB — manual `build_db.py` run | No trigger/watcher | Auto-ingest inside `--folder` flow |
| 2 | Formatting — API vs Word/PDF output | `Document()` from scratch, fragile JSON parse | Template `.dotx` + Claude `tool_use` |
| 3 | False claims — prompt-only guard | Single-pass, no verification | Validator Agent (second Claude call) |
| 4 | Manual JD copy to `new_jobs/` | `tailor.py` only reads `new_jobs/` | `--folder` flag, JD auto-detected, output written back in-place |

---

## Planned architecture

```
tailor.py --folder 260511.1_GSK
    │
    ├── 1. FolderResolver       resolve short name → full path under RESUME_ROOT
    ├── 2. FileClassifier       detect JD PDF in folder (reused from find_resumes.py logic)
    ├── 3. IngestAgent          check ChromaDB; embed JD if not present (reused from build_db.py)
    ├── 4. TailorAgent          ChromaDB query → find source resume → Claude rewrite (tool_use)
    ├── 5. ValidatorAgent       second Claude call: cross-check all claims vs source resume
    └── 6. FormatterAgent       render validated paragraphs → DOCX via .dotx template
                                output: {folder}/tailored_draft.docx
```

---

## Reusable components from job_rag

| Component | Source file | Reuse plan |
|---|---|---|
| `_classify_from_filename()` + `_classify_from_content()` | `find_resumes.py:126-178` | Copy into `agents/file_classifier.py` |
| `extract_text()` / `read_pdf()` / `read_docx_structured()` | `build_db.py`, `tailor.py` | Consolidate into `utils/text_extraction.py` |
| Incremental upsert logic | `build_db.py:69-105` | Wrap in `agents/ingest_agent.py` |
| `_add_runs_with_bold()` | `tailor.py:199-206` | Copy into `utils/docx_utils.py` |
| System prompt anti-hallucination rules | `tailor.py:137-165` | Keep as first-pass; Validator is second-pass |
| `config.py` pattern | `config.py` | Extend for new paths |

---

## Build order (TODO)

- [ ] `config.py` — extend from job_rag, add RESUME_ROOT, template path
- [ ] `utils/text_extraction.py` — consolidate PDF/DOCX readers
- [ ] `utils/docx_utils.py` — bold-run helper + template-based writer
- [ ] `agents/file_classifier.py` — JD/resume detection logic
- [ ] `agents/ingest_agent.py` — ChromaDB incremental upsert
- [ ] `agents/tailor_agent.py` — RAG query + Claude tool_use rewrite
- [ ] `agents/validator_agent.py` — claim cross-check (Claude Haiku)
- [ ] `agents/formatter_agent.py` — DOCX rendering from validated paragraphs
- [ ] `tailor.py` — orchestrator + `--folder` CLI entry point
- [ ] `requirements.txt`
- [ ] Test with `260511.1_GSK/` folder

---

## Resolved design decisions

| # | Question | Decision |
|---|---|---|
| 1 | Validator model | Claude Haiku (fast/cheap) — upgrade to Sonnet later if needed |
| 2 | Validator output | Flag violations only (print to console + annotate draft); auto-correct loop deferred to v2 |
| 3 | DOCX template | No `.dotx` file — use inferred style spec from real resumes (see below) |
| 4 | ChromaDB | Reuse `../job_rag/db/` collection; manual re-ingest from a cutoff date is fine; new folders auto-ingested going forward |
| 5 | Cover letter | Included — `tailor.py --folder` generates both `tailored_resume_draft.docx` and `tailored_cover_draft.docx` |

---

## Inferred DOCX template spec (from real submitted resumes)

Inspected: GSK, Hengrui, AZ, Merck, general resume DOCXs.

| Element | Style name | Font size | Bold | Color | Space after |
|---|---|---|---|---|---|
| Candidate name | `Normal` | 17–18 pt | Yes | `1A3A5C` (dark navy) | 2.0 pt |
| Section header (ALL CAPS) | `Normal` | 11–12 pt | Yes | `1A3A5C` | 2.0 pt |
| Job title / company line | `Normal` | 10.5 pt | Yes | `000000` | 1.5 pt |
| Bullet points | `List Paragraph` | 10.5 pt | No | `000000` | 2.0–2.5 pt |
| Contact / date lines | `Normal` | 10.5 pt | No | `000000` | 2.0 pt |

**Margins**: 0.75" all sides (consistent across most recent submissions).
**Font family**: Calibri throughout (confirmed from `job_rag` style definitions).
**Section divider**: thin horizontal rule under ALL-CAPS headers (navy `1A3A5C`).

> Note: `job_rag` used `Heading 1` / `Heading 2` / `List Bullet` — your real resumes use `Normal` + `List Paragraph`. The new `FormatterAgent` will match your actual style names.

---

## Cover letter style notes

Cover letters follow the same margin/font as resumes. Structure:
- Date + addressee block (`Normal`, 10.5pt)
- Body paragraphs (`Normal`, 10.5pt, justified)
- Closing (`Normal`, 10.5pt)
Claude will generate cover letter as separate paragraph list; same `FormatterAgent` renders it.
