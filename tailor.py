"""
resume_agent — main orchestrator.

Usage:
  # Tailor resume + cover letter for a new job (folder name or full path)
  python tailor.py --folder 260511.1_GSK

  # Re-ingest all applications from a date cutoff, then exit
  python tailor.py --reingest-from 260101

  # Show top-K similar past jobs (default 3)
  python tailor.py --folder 260511.1_GSK --top-k 5
"""
import argparse
import os
import sys

import config
from agents.file_classifier import FileClassifier
from agents.formatter_agent import FormatterAgent
from agents.ingest_agent import IngestAgent
from agents.tailor_agent import TailorAgent
from agents.validator_agent import ValidatorAgent
from agents.viz_agent import VizAgent


def resolve_folder(raw: str) -> str:
    """
    Accept either a full path or a short folder name (resolved under RESUME_ROOT).
    Also searches one level into outcome subdirs (0_slow/, rejected/, etc.).
    """
    if os.path.isabs(raw) and os.path.isdir(raw):
        return raw

    # Direct match under RESUME_ROOT
    candidate = os.path.join(config.RESUME_ROOT, raw)
    if os.path.isdir(candidate):
        return candidate

    # Search inside outcome subdirs
    for subdir in ["0_slow", "rejected", "interviewed", "interviewing"]:
        candidate = os.path.join(config.RESUME_ROOT, subdir, raw)
        if os.path.isdir(candidate):
            return candidate

    sys.exit(
        f"Folder not found: '{raw}'\n"
        f"Checked under RESUME_ROOT: {config.RESUME_ROOT}\n"
        f"Make sure the folder name matches exactly, e.g. '260511.1_GSK'"
    )


def main():
    parser = argparse.ArgumentParser(description="Tailor resume + cover letter for a new job.")
    parser.add_argument(
        "--folder", "-f",
        help="Application folder name (e.g. 260511.1_GSK) or full path.",
    )
    parser.add_argument(
        "--top-k", type=int, default=config.TOP_K,
        help=f"Number of similar past JDs to retrieve (default {config.TOP_K}).",
    )
    parser.add_argument(
        "--reingest-from",
        metavar="YYYYMMDD",
        help="Bulk re-ingest all application folders from this date prefix onward, then exit.",
    )
    parser.add_argument(
        "--viz", action="store_true",
        help="After tailoring, generate a 2D UMAP embedding map (embedding_map.html).",
    )
    args = parser.parse_args()

    if not config.ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set — add it to .env")

    # ── Bulk re-ingest mode ───────────────────────────────────────────────────
    if args.reingest_from:
        print(f"[reingest] Re-ingesting all folders from date prefix '{args.reingest_from}' onward...")
        agent = IngestAgent()
        agent.bulk_ingest_from_date(args.reingest_from)
        return

    # ── Normal tailor mode ────────────────────────────────────────────────────
    if not args.folder:
        parser.error("--folder is required unless using --reingest-from")

    folder_path = resolve_folder(args.folder)
    folder_name = os.path.basename(folder_path)
    print(f"\n{'='*60}")
    print(f"Processing: {folder_name}")
    print(f"Path: {folder_path}")
    print(f"{'='*60}")

    # 1. Classify files in folder
    print("\n[1/5] Classifying files...")
    classifier = FileClassifier()
    files = classifier.run(folder_path)

    if not files["jd_path"]:
        sys.exit(
            f"\nNo job description PDF found in: {folder_path}\n"
            "Expected a PDF file (e.g. a LinkedIn job posting)."
        )

    # 2. Ingest JD into ChromaDB if needed
    print("\n[2/5] Checking / updating vector DB...")
    ingest = IngestAgent()
    ingest.run(files["jd_path"], folder_path)
    collection = ingest.collection

    # 3. Tailor resume + cover letter via RAG + Claude
    print("\n[3/5] Generating tailored resume and cover letter...")
    config.TOP_K = args.top_k
    tailor = TailorAgent(collection)
    result = tailor.run(files["jd_path"])

    # 4. Validate — flag any hallucinated claims
    print("\n[4/5] Validating claims...")
    validator = ValidatorAgent()
    validation = validator.run(
        resume_paragraphs=result["resume_paragraphs"],
        cover_paragraphs=result["cover_paragraphs"],
        source_text=result["source_text"],
        supplemental_facts=result.get("portfolio_patch", ""),
    )

    # 5. Render to DOCX
    print("\n[5/5] Writing output files...")
    formatter = FormatterAgent()
    output = formatter.run(
        folder_path=folder_path,
        resume_paragraphs=result["resume_paragraphs"],
        cover_paragraphs=result["cover_paragraphs"],
        violations=validation["violations"] if not validation["valid"] else None,
    )

    # 6. (Optional) Embedding map
    map_path = None
    if args.viz:
        print("\n[6/6] Generating embedding map...")
        viz = VizAgent(collection)
        map_path = viz.run(highlight_id=files["jd_path"])

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("DONE")
    print(f"  Resume:      {output['resume_path']}")
    if output["cover_path"]:
        print(f"  Cover letter:{output['cover_path']}")
    if map_path:
        print(f"  Map:         file://{map_path}")
    if not validation["valid"]:
        print(f"\n  ⚠  {len(validation['violations'])} violation(s) flagged — review before sending.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
