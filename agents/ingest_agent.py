"""
IngestAgent — embed a JD PDF into ChromaDB if not already present.
Reuses incremental upsert logic from job_rag/build_db.py.
Also supports bulk re-ingest of all folders under RESUME_ROOT from a given date prefix.
"""
import os
import re

import chromadb

import config
from utils.text_extraction import extract_text_from_pdf


def _company_from_folder(folder_name: str) -> str:
    """'260511.1_GSK' → 'GSK'"""
    name = re.sub(r"^\d[\d.]*_?", "", folder_name)
    return name if name else folder_name


def _date_prefix_from_folder(folder_name: str) -> str:
    """'260511.1_GSK' → '260511'"""
    m = re.match(r"^(\d+)", folder_name)
    return m.group(1) if m else ""


class IngestAgent:
    """
    Check whether a JD is already in ChromaDB; embed and upsert if not.
    Uses the full file path as the stable document ID.
    """

    def __init__(self):
        os.makedirs(config.DB_PATH, exist_ok=True)
        self._client = chromadb.PersistentClient(path=config.DB_PATH)
        self._collection = self._client.get_or_create_collection(
            name=config.DB_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def run(self, jd_path: str, folder_path: str) -> str:
        """
        Ensure jd_path is embedded in ChromaDB.
        Returns the doc_id (== jd_path).
        """
        doc_id = jd_path
        existing = set(self._collection.get(include=[])["ids"])

        if doc_id in existing:
            print(f"  [ingest] Already in DB: {os.path.basename(jd_path)}")
            return doc_id

        print(f"  [ingest] Embedding: {os.path.basename(jd_path)}")
        text = extract_text_from_pdf(jd_path)
        if not text:
            print(f"  [ingest] WARNING: no text extracted from {os.path.basename(jd_path)}")
            return doc_id

        folder_name = os.path.basename(folder_path)
        outcome_dir = os.path.basename(os.path.dirname(folder_path))
        outcome = outcome_dir if outcome_dir in {"0_slow", "rejected", "interviewed", "interviewing"} else "applied"
        company = _company_from_folder(folder_name)

        self._collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[{
                "filename":   os.path.basename(jd_path),
                "path":       jd_path,
                "job_folder": folder_name,
                "outcome":    outcome,
                "company":    company,
            }],
        )
        print(f"  [ingest] Added to DB. Total: {self._collection.count()}")
        return doc_id

    def bulk_ingest_from_date(self, date_prefix: str) -> None:
        """
        Re-ingest all JD PDFs in RESUME_ROOT whose folder name starts with date_prefix or later.
        Useful for refreshing the DB from a cutoff date.
        Example: bulk_ingest_from_date("260101") ingests everything from 2026-01-01 onward.
        """
        from agents.file_classifier import FileClassifier
        classifier = FileClassifier()
        ingested = skipped = 0

        for entry in sorted(os.scandir(config.RESUME_ROOT), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            prefix = _date_prefix_from_folder(entry.name)
            if prefix < date_prefix:
                continue
            print(f"\n[bulk ingest] {entry.name}")
            result = classifier.run(entry.path)
            if result["jd_path"]:
                self.run(result["jd_path"], entry.path)
                ingested += 1
            else:
                print(f"  [skip] No JD found in {entry.name}")
                skipped += 1

        # Also walk outcome subfolders
        for outcome_dir in ["0_slow", "rejected", "interviewed", "interviewing"]:
            outcome_path = os.path.join(config.RESUME_ROOT, outcome_dir)
            if not os.path.isdir(outcome_path):
                continue
            for entry in sorted(os.scandir(outcome_path), key=lambda e: e.name):
                if not entry.is_dir():
                    continue
                prefix = _date_prefix_from_folder(entry.name)
                if prefix < date_prefix:
                    continue
                print(f"\n[bulk ingest] {outcome_dir}/{entry.name}")
                result = classifier.run(entry.path)
                if result["jd_path"]:
                    self.run(result["jd_path"], entry.path)
                    ingested += 1
                else:
                    print("  [skip] No JD found.")
                    skipped += 1

        print(f"\n[bulk ingest] Done. Ingested: {ingested} | Skipped (no JD): {skipped}")
        print(f"  Total in DB: {self._collection.count()}")

    @property
    def collection(self):
        return self._collection
