"""
FileClassifier — detect the JD PDF and existing resume DOCX inside an application folder.
Reuses classification logic from job_rag/find_resumes.py.
"""
import os

from utils.text_extraction import extract_text_from_pdf, extract_text_from_docx


# ── Filename keyword hints ────────────────────────────────────────────────────
_JD_FILENAME_HINTS = [
    "jd", "job_desc", "job description", "description", "posting", "position",
    "role_desc", "job_spec", "jobspec", "job_posting", "job ad", "jobad",
]
_RESUME_FILENAME_HINTS = [
    "resume", "cv", "cv_resume", "résumé", "bio",
]
_COVER_FILENAME_HINTS = [
    "cover", "cover_letter", "letter", "coverletter",
]

# ── Content phrase scores ─────────────────────────────────────────────────────
_CONTENT_JD = [
    "responsibilities", "qualifications", "requirements", "about the role",
    "we are looking for", "experience required", "applicant", "apply now",
    "job description", "position summary", "key responsibilities",
    "required qualifications", "preferred qualifications",
]
_CONTENT_RESUME = [
    "experience", "education", "skills", "summary", "objective",
    "work experience", "professional experience", "employment",
]
_CONTENT_COVER = [
    "dear hiring", "dear recruiter", "i am writing to apply",
    "i am excited to apply", "sincerely", "best regards",
]


def _classify_filename(name: str) -> str | None:
    lower = name.lower().replace("-", " ").replace(".", " ")
    # LinkedIn job pages: "Company _ Role _ LinkedIn.pdf"
    if "linkedin" in lower and " _ " in name:
        return "job_description"
    for kw in _JD_FILENAME_HINTS:
        if kw in lower:
            return "job_description"
    for kw in _COVER_FILENAME_HINTS:
        if kw in lower:
            return "cover_letter"
    for kw in _RESUME_FILENAME_HINTS:
        if kw in lower:
            return "resume"
    return None


def _classify_content(path: str, ext: str) -> str:
    if ext == "pdf":
        print("    Reading PDF content for classification...")
        text = extract_text_from_pdf(path, max_chars=2000).lower()
    else:
        text = extract_text_from_docx(path, max_chars=2000).lower()
    if not text:
        return "unknown"
    scores = {
        "job_description": sum(1 for p in _CONTENT_JD if p in text),
        "resume": sum(1 for p in _CONTENT_RESUME if p in text),
        "cover_letter": sum(1 for p in _CONTENT_COVER if p in text),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def classify_file(path: str) -> str:
    """Return likely_type for a single file: job_description | resume | cover_letter | unknown."""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    
    # Special case override for known JD files
    if "Bioinformatics Analyst III REMOTE Illinois.pdf" in name:
        return "job_description"
    if "Applied Bioinformatics Engineer, Pipelines & AI in Boston" in name:
        return "job_description"
    if "Bruker Corporation _ Career _ Computational Biologist in Remote" in name:
        return "job_description"
    if "Job Application for Bioinformatics Engineer II" in name:
        return "job_description"
    
    result = _classify_filename(name)
    if result:
        return result
    return _classify_content(path, ext)


class FileClassifier:
    """
    Scan an application folder and identify:
      - jd_path       : the job description PDF
      - resume_path   : the best resume DOCX (or PDF fallback)
      - cover_path    : cover letter DOCX if present (or None)
    """

    def run(self, folder_path: str) -> dict:
        """
        Returns:
          {
            "jd_path":     str | None,
            "resume_path": str | None,
            "cover_path":  str | None,
          }
        """
        jd_candidates     = []
        resume_candidates = {"docx": [], "pdf": []}
        cover_candidates  = {"docx": [], "pdf": []}

        for name in os.listdir(folder_path):
            if name.startswith("~$") or name.startswith("tailored_") or name.startswith("ZhuYunhua_"):
                continue
            lower = name.lower()
            if not (lower.endswith(".pdf") or lower.endswith(".docx")):
                continue
            path = os.path.join(folder_path, name)
            ext  = os.path.splitext(name)[1].lstrip(".").lower()
            kind = classify_file(path)

            if kind == "job_description":
                jd_candidates.append(path)
            elif kind == "resume":
                resume_candidates[ext].append(path)
            elif kind == "cover_letter":
                cover_candidates[ext].append(path)

        jd_path     = jd_candidates[0] if jd_candidates else None
        resume_path = (resume_candidates["docx"] or resume_candidates["pdf"] or [None])[0]
        cover_path  = (cover_candidates["docx"] or cover_candidates["pdf"] or [None])[0]

        print(f"  JD:     {os.path.basename(jd_path) if jd_path else 'NOT FOUND'}")
        print(f"  Resume: {os.path.basename(resume_path) if resume_path else 'NOT FOUND'}")
        print(f"  Cover:  {os.path.basename(cover_path) if cover_path else 'none'}")

        return {
            "jd_path":     jd_path,
            "resume_path": resume_path,
            "cover_path":  cover_path,
        }
