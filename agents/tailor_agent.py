"""
TailorAgent — query ChromaDB for similar past JDs, find the source resume,
and call Claude (tool_use) to rewrite both resume and cover letter.
"""
import json
import os
from datetime import datetime

import anthropic

import config
from utils.text_extraction import extract_text, extract_structured_paragraphs


# ── Claude tool schema ────────────────────────────────────────────────────────

_PARAGRAPH_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "style": {
                "type": "string",
                "enum": ["name", "header", "job_title", "bullet", "normal",
                         "date", "address", "salutation", "closing", "signature"],
                "description": (
                    "name=candidate name (resume only), "
                    "header=ALL-CAPS section header (resume only), "
                    "job_title=Title | Company  (date goes at end after last pipe — see format rule), "
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

RESUME_TOOL = {
    "name": "write_resume",
    "description": "Output the fully rewritten tailored resume as structured paragraphs.",
    "input_schema": {
        "type": "object",
        "properties": {"paragraphs": _PARAGRAPH_SCHEMA},
        "required": ["paragraphs"],
    },
}

COVER_TOOL = {
    "name": "write_cover_letter",
    "description": "Output the tailored cover letter as structured paragraphs.",
    "input_schema": {
        "type": "object",
        "properties": {"paragraphs": _PARAGRAPH_SCHEMA},
        "required": ["paragraphs"],
    },
}

# ── System prompts ────────────────────────────────────────────────────────────

_RESUME_SYSTEM = """\
You are an expert resume writer. Rewrite the given resume to be perfectly tailored \
for a new job description.

NO HALLUCINATION — THIS IS THE MOST IMPORTANT RULE:
  - Use ONLY facts, numbers, claims, and details that appear verbatim in the source resume.
  - Do NOT invent, extrapolate, or add any new facts — no made-up metrics, patents,
    publications, awards, tools, responsibilities, or quantitative claims.
  - If the source resume says nothing about a topic, leave it out entirely.
    An omission is always better than a fabrication.
  - You may rephrase and reorder existing content to better match the JD,
    but every claim must be traceable to the source resume.

STRICT LENGTH RULE: The final resume MUST fit on 2 pages:
  - Write a concise 2-3 sentence professional summary.
  - Include only the 3-4 most recent or most relevant roles.
  - MAXIMUM 6 bullet points per role — hard limit, never exceed.
  - Keep the Skills section to 1-2 compact lines.
  - Omit roles older than 15 years unless uniquely relevant.

FACTUAL CONSTRAINTS — enforce these exactly:
  - Years of experience: always "10+" — never write "12 years" or any other specific count.
  - BioNTech end date: always "09/2025" — never "Present".
  - GSK Community of Practice: "initiated and led" — never "founded".
  - Portfolio bullet prefix: do NOT use dashes (-). The renderer adds • automatically; output plain text only.

BULLET QUALITY RULE — every bullet must tell a COMPLETE story in one sentence:
  Structure: [problem/context] + [what you did / method] + [concrete outcome or impact]
  - Lead with a strong action verb.
  - Name the specific tool, method, or technology used.
  - Include enough context that a reader understands WHY it mattered.
  - End with a concrete outcome: a number, speed/quality improvement, decision enabled,
    product shipped, or scientific finding.
  - BAD (too terse): "Developed Nextflow pipeline for RNA-seq"
  - BAD (no impact): "Applied scVI to single-cell data"
  - GOOD: "Engineered Nextflow/Docker RNA-seq pipeline to standardise somatic variant
    calling across 3 programmes, reducing analyst turnaround from 5 days to same-day"
  - GOOD: "Fine-tuned scGPT and scBERT foundation models for cell-type annotation,
    cutting expert review time by **90%** across **300K+** single-cell profiles"
  - If no quantified outcome in source, add a qualitative impact clause
    (e.g. 'enabling reproducible analysis across 5 sites') — never invent specific numbers.
  - Use ONLY ONE metric per bullet — never mix competing percentages across bullets.

JOB TITLE FORMAT RULE — style="job_title" text must be exactly:
  "Job Title | Company Name | MM/YYYY – MM/YYYY"
  The date range MUST be the last segment after the final " | ".
  Example: "Senior Scientist, Bioinformatics | BioNTech SE | 03/2023 – 09/2025"

BOLD RULE — use sparingly so bold retains impact:
  - Bold ONLY: quantified metrics (**90% reduction**), method/tool names in bullets (**Nextflow**, **scVI**).
  - Do NOT bold: company names, adjectives, whole phrases, or anything in header/job_title paragraphs.
  - If in doubt, leave it unbolded. Over-bolding dilutes impact.

SKILLS FORMAT RULE — render each skill category as a SEPARATE bullet paragraph:
  - style="bullet" for each category line, e.g.:
      "Genomics & Multi-Omics: scRNA-seq, snRNA-seq, spatial transcriptomics, CITE-seq"
      "Pipeline Engineering: Nextflow, Snakemake, Docker, AWS, Git/GitHub"
      "AI/ML: scGPT, scBERT, scVI, PyTorch, LangChain, classical ML"
  - Do NOT merge all skills into one paragraph block.
  - Maximum 4 category lines.

EDUCATION FORMAT RULE:
  - Always include graduation year even if not in source — infer from career timeline.
  - For PhD: include dissertation focus area (1 phrase) if inferable from source.
  - style="normal" for each education line.
  - Example: "PhD, Molecular Cell Biology | National University of Singapore | 2010"

SECTION ORDER (strictly): name → contact info → SUMMARY → SKILLS → EXPERIENCE → PORTFOLIO PROJECTS → EDUCATION
  - PORTFOLIO PROJECTS section: include only if source resume or PORTFOLIO PATCH contains projects.
    Use style='header' for the section title, style='bullet' for each project (1 line each).
    Include GitHub URL inline if present in the patch text (e.g. 'github.com/zhuy16/...').
    Do NOT invent projects — only list ones explicitly in the source or patch.

Call the write_resume tool with your output. No text outside the tool call.\
"""

_COVER_SYSTEM = """\
You are an expert job application writer. Write a concise, compelling cover letter \
tailored for the new job description, based on the candidate's resume.

NO HALLUCINATION — same rule as resume: use only facts from the source resume.

CANONICAL STRUCTURE — modelled on the candidate's real submitted cover letters.
Today's date: {TODAY}
Output exactly these paragraphs in order:

  1. style="date"       — today's date spelled out: "{TODAY}"
  2. style="address"    — company + team/dept on one line (e.g. "GSK, Genomic Technologies, Translational Sciences")
  3. style="normal"     — Re: line — job title only (e.g. "Re: Principal Scientist, Genomics Analytics Engineer")
  4. style="salutation" — "Dear Hiring Manager,"
  5. style="normal"     — OPENING (2-3 sentences): Start with a specific, compelling observation about
                          the role or the company's mission — NOT "I am writing to apply" or "aligns perfectly".
                          Then state the role title and your most relevant credential in one sentence.
                          Example opener: "NIST's work establishing measurement standards for AI/ML systems
                          sits at exactly the intersection of rigorous science and real-world impact that
                          has defined my career."
  6. style="normal"     — FIT PARAGRAPH (2-3 sentences): "My background maps directly onto the core
                          requirements of this role." Name the employer, tool/method, concrete outcome.
  7. style="bullet"     — KEY CONTRIBUTION 1: one line, action verb + method + outcome (from source resume)
  8. style="bullet"     — KEY CONTRIBUTION 2: one line, action verb + method + outcome (from source resume)
  9. style="bullet"     — KEY CONTRIBUTION 3: one line, action verb + method + outcome (from source resume)
 10. style="bullet"     — KEY CONTRIBUTION 4: one line, action verb + method + outcome (from source resume)
 11. style="normal"     — WHY COMPANY + CLOSING (2-3 sentences): Name something SPECIFIC about this
                          organisation (a program, a lab, a stated mission, a standard they develop).
                          Close with a concrete forward statement — not "looking forward to discussing".
                          IMPORTANT: mention the organisation/mission only ONCE in this paragraph — no repetition.
                          Example: "Contributing to NIST's bioinformatics standards effort would let me
                          apply rigorous measurement science to problems that affect the whole field."
 12. style="closing"    — "Sincerely,"
 13. style="signature"  — candidate full name (e.g. "Yunhua Zhu, PhD")
 14. style="normal"     — phone | email (single line, no label)

CONTENT RULES:
  - Body paragraphs (items 5-6, 11): flowing prose, 2-4 sentences, max 80 words each.
  - Bullets (items 7-10): each ONE line, action verb + method + outcome, end with a period.
  - Bullets must each cover a DIFFERENT skill area — no repetition.
  - Never open any sentence with "I" — restructure to lead with the role, company, or skill.
  - Banned phrases: "aligns perfectly", "I am very excited", "I am a perfect fit", "I believe",
    "I am passionate", "Looking forward to discussing", "thrilled", "ideal candidate".
  - Use **bold** only for a single key metric per paragraph — never bold adjectives or company names.
  - The Re: line (item 3) is plain text — no bold.
  - Metrics must be consistent — if source has 90%, use 90% everywhere, never mix with 80%.
  - Years of experience: always "10+" — never write "12 years" or any specific count.
  - GSK Community of Practice: write "initiated and led" — never "founded".
  - BioNTech end date: always "09/2025" — never "Present".

Call the write_cover_letter tool with your output. No text outside the tool call.\
"""


class TailorAgent:
    """
    Query ChromaDB with the new JD, find source resume, call Claude to rewrite.
    Returns draft paragraphs for resume and cover letter, plus source text for validation.
    """

    def __init__(self, collection):
        self._collection = collection
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def _find_source_resume(self, job_folder: str, jd_path: str) -> str | None:
        """
        Locate the resume DOCX (or PDF) used for a past matched job.
        Searches the matched job's folder under RESUME_ROOT.
        """
        # job_folder may be e.g. "0_slow/0818_BAMF" or just "260511.1_GSK"
        parent = os.path.dirname(jd_path)

        # Collect all candidate resume files; prefer DOCX over PDF, newest first
        candidates: list[tuple[float, str]] = []
        for name in os.listdir(parent):
            if name.startswith("~$") or name.startswith("tailored_") or name.startswith("ZhuYunhua_"):
                continue
            lower = name.lower()
            if any(kw in lower for kw in ["resume", "cv", "application"]):
                full = os.path.join(parent, name)
                if lower.endswith((".docx", ".pdf")):
                    candidates.append((os.path.getmtime(full), full))
        if not candidates:
            return None
        # Sort newest first; DOCX ranked above PDF of same mtime
        candidates.sort(key=lambda t: (t[0], 1 if t[1].endswith(".docx") else 0), reverse=True)
        return candidates[0][1]

    def run(self, jd_path: str) -> dict:
        """
        Returns:
          {
            "resume_paragraphs": list[dict],   # [{style, text}, ...]
            "cover_paragraphs":  list[dict],
            "source_text":       str,           # for ValidatorAgent
            "top_matches":       list[dict],    # similarity info for display
          }
        """
        new_jd_text = extract_text(jd_path)
        print(f"  New JD: {len(new_jd_text)} chars")

        # ── RAG query ────────────────────────────────────────────────────────
        results = self._collection.query(
            query_texts=[new_jd_text],
            n_results=min(config.TOP_K, self._collection.count()),
            include=["metadatas", "distances", "documents"],
        )
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        documents = results["documents"][0]

        top_matches = []
        print(f"\n  Top {len(metadatas)} similar past jobs:")
        for i, (meta, dist) in enumerate(zip(metadatas, distances), 1):
            sim = 1 - dist
            print(f"    {i}. [{sim:.3f}] {meta['filename']}  outcome={meta['outcome']}")
            top_matches.append({"rank": i, "similarity": sim, **meta})

        top_doc  = documents[0]

        # ── Find source resume (best-matched folder, fall through if needed) ───
        resume_path = None
        for meta in metadatas:
            resume_path = self._find_source_resume(meta["job_folder"], meta["path"])
            if resume_path:
                if meta is not metadatas[0]:
                    print(f"  [tailor] Resume not in top match — using: {meta['job_folder']}")
                break
        if not resume_path:
            raise FileNotFoundError(
                f"No source resume found in any of the top {len(metadatas)} matched jobs."
            )
        print(f"\n  Source resume: {os.path.basename(resume_path)}")

        source_paragraphs = extract_structured_paragraphs(resume_path)
        source_text = "\n".join(p["text"] for p in source_paragraphs)
        tagged_resume = "\n".join(f"[{p['style']}] {p['text']}" for p in source_paragraphs)

        # ── Portfolio patch — extract from fallback resume if not in source ──
        portfolio_patch = ""
        source_has_portfolio = any(
            "portfolio" in p["text"].lower() or "github.com" in p["text"].lower()
            for p in source_paragraphs
        )
        if not source_has_portfolio:
            fallback_path = self._find_source_resume(
                "fallback", os.path.join(config.FALLBACK_RESUME_DIR, "placeholder")
            )
            if fallback_path:
                fallback_paras = extract_structured_paragraphs(fallback_path)
                in_portfolio = False
                portfolio_lines = []
                for p in fallback_paras:
                    t = p["text"].lower()
                    if not in_portfolio and ("portfolio" in t or "github.com" in t):
                        in_portfolio = True
                    elif in_portfolio and p["style"] == "header":
                        break  # next section — stop
                    if in_portfolio:
                        portfolio_lines.append(f"[{p['style']}] {p['text']}")
                if portfolio_lines:
                    portfolio_patch = (
                        "\n\n## PORTFOLIO PROJECTS PATCH\n"
                        "Append this section VERBATIM after EXPERIENCE, before EDUCATION.\n"
                        "CRITICAL: copy these bullet texts EXACTLY as written below. "
                        "Do NOT add, remove, rename, or invent any projects. "
                        "Only these projects exist — do not hallucinate others:\n"
                        + "\n".join(portfolio_lines)
                    )
                    print("  [tailor] Portfolio patch loaded from fallback resume.")

        user_msg = (
            f"## Source Resume\n{tagged_resume}\n\n"
            f"## Past Job Description (what this resume was written for)\n{top_doc}\n\n"
            f"## New Job Description (tailor for this)\n{new_jd_text}"
            f"{portfolio_patch}"
        )

        # ── Resume rewrite ───────────────────────────────────────────────────
        print("\n  Calling Claude (resume rewrite)...")
        resume_paragraphs = self._call_claude(
            system=_RESUME_SYSTEM,
            user=user_msg,
            tool=RESUME_TOOL,
            tool_name="write_resume",
        )
        print(f"  {len(resume_paragraphs)} resume paragraphs generated.")

        # ── Cover letter ─────────────────────────────────────────────────────
        print("  Calling Claude (cover letter)...")
        today_str = datetime.now().strftime("%B %-d, %Y")
        cover_paragraphs = self._call_claude(
            system=_COVER_SYSTEM.replace("{TODAY}", today_str),
            user=user_msg,
            tool=COVER_TOOL,
            tool_name="write_cover_letter",
        )
        print(f"  {len(cover_paragraphs)} cover letter paragraphs generated.")

        return {
            "resume_paragraphs": resume_paragraphs,
            "cover_paragraphs":  cover_paragraphs,
            "source_text":       source_text,
            "portfolio_patch":   portfolio_patch,
            "top_matches":       top_matches,
        }

    def _call_claude(self, system: str, user: str, tool: dict, tool_name: str) -> list[dict]:
        response = self._client.messages.create(
            model=config.TAILOR_MODEL,
            max_tokens=4096,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                inp = block.input
                if isinstance(inp, str):
                    inp = json.loads(inp)
                return inp.get("paragraphs", [])
        raise ValueError(f"Claude did not call the expected tool '{tool_name}'")
