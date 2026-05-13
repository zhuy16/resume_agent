"""
Standalone CLI to generate the 2D job embedding map.

Usage:
  python viz.py
  python viz.py --highlight 260512_NewCompany
  python viz.py --output /tmp/my_map.html
"""
import argparse
import os

import chromadb

import config
from agents.viz_agent import VizAgent


def resolve_jd_id(folder_name: str) -> str | None:
    """Return the ChromaDB doc_id for the JD in the given folder, or None."""
    from agents.file_classifier import FileClassifier

    # Resolve full path
    if os.path.isabs(folder_name) and os.path.isdir(folder_name):
        folder_path = folder_name
    else:
        candidate = os.path.join(config.RESUME_ROOT, folder_name)
        if not os.path.isdir(candidate):
            for sub in ["0_slow", "rejected", "interviewed", "interviewing"]:
                candidate = os.path.join(config.RESUME_ROOT, sub, folder_name)
                if os.path.isdir(candidate):
                    break
            else:
                print(f"  [viz] Folder not found: {folder_name}")
                return None
        folder_path = candidate

    files = FileClassifier().run(folder_path)
    return files["jd_path"]   # doc_id == jd_path


def main():
    parser = argparse.ArgumentParser(description="Generate 2D job embedding map.")
    parser.add_argument("--highlight", "-f", metavar="FOLDER",
                        help="Folder name to highlight as the new job (e.g. 260512_NewCompany).")
    parser.add_argument("--output", "-o", metavar="PATH",
                        help="Output HTML path (default: embedding_map.html in project folder).")
    args = parser.parse_args()

    client     = chromadb.PersistentClient(path=config.DB_PATH)
    collection = client.get_or_create_collection(name=config.DB_COLLECTION)

    highlight_id = None
    if args.highlight:
        highlight_id = resolve_jd_id(args.highlight)
        if highlight_id:
            print(f"  Highlighting: {os.path.basename(highlight_id)}")

    agent = VizAgent(collection)
    out   = agent.run(highlight_id=highlight_id, output_path=args.output)
    print(f"\nOpen in browser: file://{out}")


if __name__ == "__main__":
    main()
