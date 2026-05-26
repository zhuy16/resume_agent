"""
ReviewerAgent — Style and role-fit critique for generated resumes and cover letters.
Provides structured feedback on quality, alignment, and improvement opportunities.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from services.llm_client import LLMClient


@dataclass
class ReviewResult:
    """Structured review result with scores and recommendations."""
    overall_score: float  # 0-100
    style_score: float    # 0-100
    fit_score: float      # 0-100  
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    action_required: bool
    

class ReviewerAgent:
    """
    Critique generated content for style consistency and job-fit alignment.
    Acts as a quality gate before final output.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize reviewer agent.
        
        Args:
            llm_client: LLM client for generating critiques (uses default if None)
        """
        self._llm = llm_client or LLMClient()
    
    def review_resume(
        self,
        paragraphs: List[Dict[str, Any]],
        jd_text: str,
        source_resume_text: str,
    ) -> ReviewResult:
        """
        Review a generated resume for quality and fit.
        
        Args:
            paragraphs: Generated resume paragraphs
            jd_text: Target job description
            source_resume_text: Original source resume for comparison
            
        Returns:
            ReviewResult with scores and recommendations
        """
        # Build review prompt
        resume_text = "\n".join(f"[{p['style']}] {p['text']}" for p in paragraphs)
        
        review_prompt = f"""\
You are an expert resume reviewer evaluating a tailored resume against a job description.

## Job Description
{jd_text[:1500]}

## Generated Resume
{resume_text[:2000]}

## Original Source (for comparison)
{source_resume_text[:1000]}

Evaluate on these dimensions (score 0-100):

1. **Job Fit (40%)**: How well does this resume match the JD requirements?
   - Required skills mentioned
   - Experience level appropriate
   - Domain expertise highlighted

2. **Style Quality (30%)**: Professional writing standards
   - Clear, concise bullets
   - Strong action verbs
   - Quantified achievements
   - No clichés or buzzwords

3. **Accuracy (30%)**: Fidelity to source material
   - No fabricated claims
   - Correct company attributions
   - Accurate dates and titles

Return a structured critique:
- Overall score (0-100)
- Style score (0-100)
- Fit score (0-100)
- Top 3 strengths
- Top 3 weaknesses (flag as "CRITICAL" if deal-breakers)
- 3 specific recommendations
- Action required: true if critical issues found

Format as JSON with keys: overall_score, style_score, fit_score, strengths, weaknesses, recommendations, action_required"""

        try:
            response = self._llm.generate_text(
                system="You are a strict but fair resume reviewer. Be specific and actionable.",
                user=review_prompt,
                max_tokens=1500,
                temperature=0.3,
            )
            
            # Parse JSON response
            import json
            result = json.loads(response)
            
            return ReviewResult(
                overall_score=result.get("overall_score", 70),
                style_score=result.get("style_score", 70),
                fit_score=result.get("fit_score", 70),
                strengths=result.get("strengths", []),
                weaknesses=result.get("weaknesses", []),
                recommendations=result.get("recommendations", []),
                action_required=result.get("action_required", False),
            )
        except Exception as e:
            # Fallback if LLM review fails
            print(f"  [reviewer] LLM review failed: {e}")
            return self._heuristic_review(paragraphs, jd_text)
    
    def review_cover_letter(
        self,
        paragraphs: List[Dict[str, Any]],
        jd_text: str,
    ) -> ReviewResult:
        """
        Review a generated cover letter.
        
        Args:
            paragraphs: Generated cover letter paragraphs
            jd_text: Target job description
            
        Returns:
            ReviewResult with scores and recommendations
        """
        cover_text = "\n".join(f"[{p['style']}] {p['text']}" for p in paragraphs)
        
        review_prompt = f"""\
Review this cover letter against the job description.

## Job Description
{jd_text[:1500]}

## Cover Letter
{cover_text[:1500]}

Evaluate:
1. **Opening Impact (30%)**: Compelling hook, company-specific observation
2. **Body Fit (40%)**: Clear connection between experience and JD requirements
3. **Closing Strength (30%)**: Confident forward statement, no clichés

Score 0-100 for each dimension and overall.

Flag issues:
- Generic openings ("I am writing to apply")
- Missing specific company references
- Weak closings ("looking forward to discussing")
- Title inflation (claiming higher title than earned)

Return JSON: overall_score, style_score, fit_score, strengths, weaknesses, recommendations, action_required"""

        try:
            response = self._llm.generate_text(
                system="You are a cover letter expert. Be direct about flaws.",
                user=review_prompt,
                max_tokens=1200,
                temperature=0.3,
            )
            
            import json
            result = json.loads(response)
            
            return ReviewResult(
                overall_score=result.get("overall_score", 70),
                style_score=result.get("style_score", 70),
                fit_score=result.get("fit_score", 70),
                strengths=result.get("strengths", []),
                weaknesses=result.get("weaknesses", []),
                recommendations=result.get("recommendations", []),
                action_required=result.get("action_required", False),
            )
        except Exception as e:
            print(f"  [reviewer] Cover letter review failed: {e}")
            return ReviewResult(
                overall_score=70,
                style_score=70,
                fit_score=70,
                strengths=["Generated successfully"],
                weaknesses=["Review incomplete due to error"],
                recommendations=["Manual review recommended"],
                action_required=False,
            )
    
    def _heuristic_review(
        self,
        paragraphs: List[Dict[str, Any]],
        jd_text: str,
    ) -> ReviewResult:
        """
        Fallback heuristic review when LLM fails.
        
        Args:
            paragraphs: Generated content
            jd_text: Target job description
            
        Returns:
            Basic review result
        """
        # Simple checks
        text = " ".join(p["text"] for p in paragraphs).lower()
        
        strengths = []
        weaknesses = []
        
        # Check for portfolio project attribution issues
        portfolio_projects = ["linkedin-job-scout", "job-rag", "scrna_longformer", "python-ml-reps"]
        in_experience = False
        for p in paragraphs:
            if p["style"] == "header" and "experience" in p["text"].lower():
                in_experience = True
            elif p["style"] == "header":
                in_experience = False
            elif in_experience and any(proj in p["text"].lower() for proj in portfolio_projects):
                weaknesses.append("CRITICAL: Portfolio project attributed to company experience")
        
        # Check for required sections
        has_summary = any("summary" in p["text"].lower() for p in paragraphs if p["style"] == "header")
        has_skills = any("skills" in p["text"].lower() for p in paragraphs if p["style"] == "header")
        has_experience = any("experience" in p["text"].lower() for p in paragraphs if p["style"] == "header")
        
        if has_summary and has_skills and has_experience:
            strengths.append("Complete section structure")
        else:
            weaknesses.append("Missing required sections")
        
        # Check for buzzwords
        buzzwords = ["synergy", "leverage", "passionate", "thrilled"]
        buzzword_count = sum(1 for bw in buzzwords if bw in text)
        if buzzword_count > 0:
            weaknesses.append(f"Contains {buzzword_count} buzzwords/clichés")
        
        # Calculate rough score
        score = 80
        score -= len(weaknesses) * 10
        score += len(strengths) * 5
        score = max(50, min(95, score))
        
        return ReviewResult(
            overall_score=score,
            style_score=score,
            fit_score=score,
            strengths=strengths or ["Basic structure present"],
            weaknesses=weaknesses or ["Minor formatting issues"],
            recommendations=["Consider LLM review for detailed feedback"],
            action_required=any("CRITICAL" in w for w in weaknesses),
        )
