"""
Evaluation runner for resume generation pipeline.
Executes test suites and generates quality reports.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_all_evaluations() -> bool:
    """
    Run complete evaluation suite.
    
    Returns:
        True if all tests pass, False otherwise
    """
    print("=" * 60)
    print("RESUME GENERATION EVALUATION SUITE")
    print("=" * 60)
    
    results = []
    
    # Delay imports to avoid loading heavy dependencies at module level
    from evals.test_hallucination import run_hallucination_tests
    from evals.test_structure import run_structure_tests
    
    # Run hallucination tests
    try:
        hallucination_passed = run_hallucination_tests()
        results.append(("Hallucination Detection", hallucination_passed))
    except Exception as e:
        print(f"\n❌ Hallucination tests failed with error: {e}")
        results.append(("Hallucination Detection", False))
    
    # Run structure tests
    try:
        structure_passed = run_structure_tests()
        results.append(("Structure Validation", structure_passed))
    except Exception as e:
        print(f"\n❌ Structure tests failed with error: {e}")
        results.append(("Structure Validation", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    for name, passed_test in results:
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nOverall: {passed}/{total} test suites passed")
    print("=" * 60)
    
    return passed == total


def evaluate_single_generation(
    resume_paragraphs: List[Dict[str, Any]],
    cover_paragraphs: List[Dict[str, Any]],
    source_text: str,
    jd_text: str,
) -> Dict[str, Any]:
    """
    Evaluate a single generation against quality criteria.
    
    Args:
        resume_paragraphs: Generated resume
        cover_paragraphs: Generated cover letter
        source_text: Source resume text
        jd_text: Job description text
        
    Returns:
        Evaluation results dict
    """
    from agents.reviewer_agent import ReviewerAgent
    from agents.validator_agent import ValidatorAgent
    from services.llm_client import LLMClient
    
    results = {
        "resume_review": None,
        "cover_review": None,
        "validation_violations": [],
        "passed": False,
    }
    
    # Run reviewer agent
    try:
        reviewer = ReviewerAgent(llm_client=LLMClient())
        results["resume_review"] = reviewer.review_resume(
            resume_paragraphs, jd_text, source_text
        )
        results["cover_review"] = reviewer.review_cover_letter(
            cover_paragraphs, jd_text
        )
    except Exception as e:
        print(f"  [eval] Reviewer failed: {e}")
    
    # Run validator
    try:
        validator = ValidatorAgent(llm_client=LLMClient())
        resume_text = "\n".join(p["text"] for p in resume_paragraphs)
        results["validation_violations"] = validator.validate_claims(
            resume_text, source_text
        )
    except Exception as e:
        print(f"  [eval] Validator failed: {e}")
    
    # Determine pass/fail
    critical_violations = sum(
        1 for v in results["validation_violations"]
        if "critical" in v.get("severity", "").lower()
    )
    
    results["passed"] = (
        critical_violations == 0
        and (results["resume_review"] is None or not results["resume_review"].action_required)
        and (results["cover_review"] is None or not results["cover_review"].action_required)
    )
    
    return results


if __name__ == "__main__":
    success = run_all_evaluations()
    sys.exit(0 if success else 1)
