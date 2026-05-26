"""
Source resume selection service with quality control and fallback logic.
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import config
from utils.text_extraction import extract_structured_paragraphs


@dataclass
class QualityResult:
    """Result of quality check on a resume."""
    passes_qc: bool
    issues: List[str]
    score: float
    

def _quality_check_resume(paragraphs: List[Dict[str, Any]]) -> QualityResult:
    """
    Evaluate resume quality and return QC results.
    
    Returns:
        QualityResult with passes_qc flag, list of issues, and score (0-1)
    """
    issues = []
    score = 1.0
    
    # Check minimum content length
    total_chars = sum(len(p["text"]) for p in paragraphs)
    if total_chars < 500:
        issues.append(f"Resume too short: {total_chars} chars (minimum 500)")
        score -= 0.4
    
    # Check for proper sections
    has_name = any(p["style"] == "name" for p in paragraphs)
    has_header = any(p["style"] == "header" for p in paragraphs)
    has_bullet = any(p["style"] == "bullet" for p in paragraphs)
    
    if not has_name:
        issues.append("Missing name section")
        score -= 0.2
    if not has_header:
        issues.append("Missing section headers")
        score -= 0.1
    if not has_bullet:
        issues.append("Missing bullet points")
        score -= 0.2
    
    # Check for job descriptions (bad source material)
    text_content = " ".join(p["text"].lower() for p in paragraphs)
    jd_indicators = ["job description", "requirements", "qualifications", "responsibilities", "salary"]
    jd_score = sum(1 for indicator in jd_indicators if indicator in text_content)
    if jd_score >= 2:
        issues.append("Appears to be a job description, not a resume")
        score -= 0.5
    
    # Check for placeholder content
    placeholder_indicators = ["<unknown>", "tbd", "to be determined", "placeholder"]
    placeholder_count = sum(1 for indicator in placeholder_indicators if indicator in text_content)
    if placeholder_count > 0:
        issues.append(f"Contains {placeholder_count} placeholders")
        score -= 0.3
    
    passes_qc = score >= 0.6 and len(issues) == 0
    
    return QualityResult(
        passes_qc=passes_qc,
        issues=issues,
        score=max(0, score)
    )


class SourceSelector:
    """
    Select best source resume from matched jobs with QC and fallback.
    """
    
    def __init__(self, resume_finder_func):
        """
        Initialize with resume finder function.
        
        Args:
            resume_finder_func: Function that takes (job_folder, jd_path) and returns resume_path or None
        """
        self._find_resume = resume_finder_func
    
    def select_source(
        self,
        metadatas: List[Dict[str, Any]],
        verbose: bool = True
    ) -> Tuple[str, List[Dict[str, Any]], QualityResult]:
        """
        Select best source resume from matched jobs with QC fallback.
        
        Args:
            metadatas: List of metadata dicts from ChromaDB query
            verbose: Whether to print selection progress
            
        Returns:
            Tuple of (resume_path, paragraphs, quality_result)
            
        Raises:
            FileNotFoundError: If no valid resume found in any matched job
        """
        resume_path = None
        source_paragraphs = None
        qc_result = None
        
        for i, meta in enumerate(metadatas):
            try:
                candidate_path = self._find_resume(meta["job_folder"], meta["path"])
                if candidate_path:
                    # Extract and QC check the candidate resume
                    candidate_paragraphs = extract_structured_paragraphs(candidate_path)
                    qc_result = _quality_check_resume(candidate_paragraphs)
                    
                    if qc_result.passes_qc:
                        resume_path = candidate_path
                        source_paragraphs = candidate_paragraphs
                        if verbose and i > 0:
                            print(f"  [tailor] Resume not in top match — using: {meta['job_folder']} (QC passed)")
                        break
                    else:
                        if verbose:
                            print(f"  [tailor] {meta['job_folder']} failed QC: {', '.join(qc_result.issues)}")
                        if i == len(metadatas) - 1:
                            # Last candidate, use it anyway but warn
                            if verbose:
                                print(f"  [tailor] All candidates failed QC, using best available: {meta['job_folder']}")
                            resume_path = candidate_path
                            source_paragraphs = candidate_paragraphs
                            break
            except (FileNotFoundError, OSError) as e:
                if verbose:
                    print(f"  [tailor] {meta['job_folder']} not accessible: {str(e)[:50]}...")
                continue
        
        if not resume_path:
            # Try to use fallback resume as last resort
            fallback_path = self._find_source_resume("fallback", os.path.join(config.FALLBACK_RESUME_DIR, "placeholder"))
            if fallback_path:
                if verbose:
                    print(f"  [tailor] Using fallback resume: {fallback_path}")
                try:
                    source_paragraphs = extract_structured_paragraphs(fallback_path)
                    from services.source_selection import QualityResult
                    qc_result = QualityResult(score=0.5, passes_qc=True, issues=["Using fallback resume"])
                    return fallback_path, source_paragraphs, qc_result
                except Exception:
                    pass
            
            raise FileNotFoundError(
                f"No source resume found in any of the top {len(metadatas)} matched jobs, and no fallback available."
            )
        
        return resume_path, source_paragraphs, qc_result
