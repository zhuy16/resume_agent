"""
ResumeOrchestrator — Stateful workflow with human-in-the-loop checkpoints.
Modern multi-agent orchestration with explicit state transitions.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum, auto
from datetime import datetime

from services.retrieval import RetrievalService
from services.source_selection import SourceSelector, QualityResult
from services.llm_client import LLMClient, TracedLLMClient
from agents.reviewer_agent import ReviewerAgent, ReviewResult
from agents.validator_agent import ValidatorAgent
from schemas import RESUME_TOOL, COVER_TOOL


class WorkflowState(Enum):
    """Explicit states in the resume generation workflow."""
    IDLE = auto()
    RETRIEVING = auto()
    SELECTING_SOURCE = auto()
    GENERATING_RESUME = auto()
    REVIEWING_RESUME = auto()
    AWAITING_RESUME_APPROVAL = auto()
    GENERATING_COVER = auto()
    REVIEWING_COVER = auto()
    AWAITING_COVER_APPROVAL = auto()
    VALIDATING = auto()
    COMPLETED = auto()
    REJECTED = auto()


@dataclass
class WorkflowContext:
    """Mutable context passed through workflow states."""
    job_folder: str
    jd_text: str
    jd_path: str
    
    # Retrieved data
    similar_jobs: List[Dict[str, Any]] = field(default_factory=list)
    selected_source_path: Optional[str] = None
    source_paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    source_text: str = ""
    qc_result: Optional[QualityResult] = None
    
    # Generated content
    resume_paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    cover_paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Reviews
    resume_review: Optional[ReviewResult] = None
    cover_review: Optional[ReviewResult] = None
    validation_violations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Human decisions
    resume_approved: Optional[bool] = None
    cover_approved: Optional[bool] = None
    rejection_reason: Optional[str] = None
    
    # Metadata
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    traces: List[Dict[str, Any]] = field(default_factory=list)


class ResumeOrchestrator:
    """
    Multi-agent orchestrator with stateful workflow and human checkpoints.
    
    Replaces the monolithic TailorAgent with explicit state management
    and human approval gates.
    """
    
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_client: Optional[LLMClient] = None,
        enable_tracing: bool = True,
        trace_dir: Optional[str] = None,
    ):
        """
        Initialize orchestrator with services.
        
        Args:
            retrieval_service: ChromaDB retrieval service
            llm_client: LLM client (creates default if None)
            enable_tracing: Whether to trace execution
            trace_dir: Directory to save traces
        """
        self._retrieval = retrieval_service
        self._llm = llm_client or TracedLLMClient(trace_dir=trace_dir) if enable_tracing else LLMClient()
        self._reviewer = ReviewerAgent(self._llm)
        self._validator = ValidatorAgent(self._llm)
        
        # State callbacks
        self._on_state_change: Optional[Callable[[WorkflowState, WorkflowState, WorkflowContext], None]] = None
        self._human_approval_callback: Optional[Callable[[str, WorkflowContext], bool]] = None
    
    def on_state_change(self, callback: Callable[[WorkflowState, WorkflowState, WorkflowContext], None]):
        """Register callback for state transitions."""
        self._on_state_change = callback
        return self
    
    def on_human_approval(self, callback: Callable[[str, WorkflowContext], bool]):
        """Register callback for human approval checkpoints."""
        self._human_approval_callback = callback
        return self
    
    def _transition(
        self,
        ctx: WorkflowContext,
        new_state: WorkflowState,
    ) -> WorkflowState:
        """Execute state transition with optional callback."""
        old_state = getattr(ctx, '_state', WorkflowState.IDLE)
        ctx._state = new_state
        
        if self._on_state_change:
            self._on_state_change(old_state, new_state, ctx)
        
        return new_state
    
    def _get_human_approval(self, checkpoint: str, ctx: WorkflowContext) -> bool:
        """Request human approval at checkpoint."""
        if self._human_approval_callback:
            return self._human_approval_callback(checkpoint, ctx)
        
        # Default: auto-approve if no callback registered
        print(f"  [checkpoint] {checkpoint}: Auto-approved (no human callback)")
        return True
    
    def run(
        self,
        job_folder: str,
        jd_path: str,
        jd_text: str,
        auto_approve: bool = True,
    ) -> WorkflowContext:
        """
        Execute full workflow with state management.
        
        Args:
            job_folder: Target job folder
            jd_path: Path to job description file
            jd_text: Job description text
            auto_approve: Skip human checkpoints (for batch processing)
            
        Returns:
            Final workflow context with all artifacts
        """
        ctx = WorkflowContext(
            job_folder=job_folder,
            jd_path=jd_path,
            jd_text=jd_text,
        )
        
        # Override human callback if auto-approve
        original_callback = self._human_approval_callback
        if auto_approve:
            self._human_approval_callback = lambda c, ctx: True
        
        try:
            # Phase 1: Retrieve similar jobs
            self._transition(ctx, WorkflowState.RETRIEVING)
            ctx.similar_jobs = self._retrieve_similar_jobs(jd_text)
            
            # Phase 2: Select source resume with QC
            self._transition(ctx, WorkflowState.SELECTING_SOURCE)
            self._select_source_resume(ctx)
            
            # Phase 3: Generate resume
            self._transition(ctx, WorkflowState.GENERATING_RESUME)
            ctx.resume_paragraphs = self._generate_resume(ctx)
            
            # Phase 4: Review resume
            self._transition(ctx, WorkflowState.REVIEWING_RESUME)
            ctx.resume_review = self._review_resume(ctx)
            
            # Phase 5: Human checkpoint - resume approval
            if not auto_approve:
                self._transition(ctx, WorkflowState.AWAITING_RESUME_APPROVAL)
                ctx.resume_approved = self._get_human_approval("resume", ctx)
                
                if not ctx.resume_approved:
                    ctx.rejection_reason = "Resume rejected by human"
                    self._transition(ctx, WorkflowState.REJECTED)
                    return ctx
            else:
                ctx.resume_approved = True
            
            # Phase 6: Generate cover letter
            self._transition(ctx, WorkflowState.GENERATING_COVER)
            ctx.cover_paragraphs = self._generate_cover_letter(ctx)
            
            # Phase 7: Review cover letter
            self._transition(ctx, WorkflowState.REVIEWING_COVER)
            ctx.cover_review = self._review_cover_letter(ctx)
            
            # Phase 8: Human checkpoint - cover approval
            if not auto_approve:
                self._transition(ctx, WorkflowState.AWAITING_COVER_APPROVAL)
                ctx.cover_approved = self._get_human_approval("cover_letter", ctx)
                
                if not ctx.cover_approved:
                    ctx.rejection_reason = "Cover letter rejected by human"
                    self._transition(ctx, WorkflowState.REJECTED)
                    return ctx
            else:
                ctx.cover_approved = True
            
            # Phase 9: Final validation
            self._transition(ctx, WorkflowState.VALIDATING)
            ctx.validation_violations = self._validate_final(ctx)
            
            # Complete
            ctx.completed_at = datetime.now()
            self._transition(ctx, WorkflowState.COMPLETED)
            
        finally:
            # Restore original callback
            self._human_approval_callback = original_callback
        
        return ctx
    
    def _retrieve_similar_jobs(self, jd_text: str) -> List[Dict[str, Any]]:
        """Retrieve similar jobs from vector database."""
        results = self._retrieval.query_similar_jobs(jd_text, n_results=3)
        
        jobs = []
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"],
            results["metadatas"],
            results["distances"]
        )):
            jobs.append({
                "rank": i + 1,
                "similarity": 1 - dist,  # Convert distance to similarity
                "document": doc[:200] + "..." if len(doc) > 200 else doc,
                **meta
            })
        
        return jobs
    
    def _select_source_resume(self, ctx: WorkflowContext):
        """Select best source resume with QC fallback."""
        import os
        import config
        
        def find_resume(job_folder: str, jd_path: str) -> Optional[str]:
            """Find resume file in job folder."""
            folder_path = os.path.join(config.RESUME_ROOT, job_folder)
            
            if not os.path.exists(folder_path):
                return None
            
            for file in os.listdir(folder_path):
                if file.lower().endswith('.docx') or file.lower().endswith('.pdf'):
                    # Skip cover letters
                    if 'cover' in file.lower():
                        continue
                    return os.path.join(folder_path, file)
            
            return None
        
        selector = SourceSelector(find_resume)
        
        metadatas = [{"job_folder": j.get("job_folder", "unknown"), "path": j.get("path", "")} 
                     for j in ctx.similar_jobs]
        
        ctx.selected_source_path, ctx.source_paragraphs, ctx.qc_result = selector.select_source(
            metadatas, verbose=True
        )
        
        ctx.source_text = "\n".join(p["text"] for p in ctx.source_paragraphs)
    
    def _generate_resume(self, ctx: WorkflowContext) -> List[Dict[str, Any]]:
        """Generate tailored resume using LLM."""
        from prompts.resume_system import RESUME_SYSTEM_PROMPT
        
        user_prompt = f"""\
## Source Resume
{ctx.source_text[:4000]}

## Target Job Description
{ctx.jd_text[:2000]}

Generate a tailored resume that matches the job description while staying faithful to the source resume."""
        
        result = self._llm.generate_structured(
            system=RESUME_SYSTEM_PROMPT,
            user=user_prompt,
            tool=RESUME_TOOL,
            tool_name="write_resume",
        )
        
        return result
    
    def _review_resume(self, ctx: WorkflowContext) -> ReviewResult:
        """Review generated resume."""
        return self._reviewer.review_resume(
            ctx.resume_paragraphs,
            ctx.jd_text,
            ctx.source_text,
        )
    
    def _generate_cover_letter(self, ctx: WorkflowContext) -> List[Dict[str, Any]]:
        """Generate cover letter using LLM."""
        from prompts.cover_system import COVER_SYSTEM_PROMPT
        from datetime import datetime
        
        today = datetime.now().strftime("%B %d, %Y")
        
        system = COVER_SYSTEM_PROMPT.format(TODAY=today)
        
        user_prompt = f"""\
## Source Resume
{ctx.source_text[:3000]}

## Target Job Description
{ctx.jd_text[:2000]}

Generate a tailored cover letter."""
        
        result = self._llm.generate_structured(
            system=system,
            user=user_prompt,
            tool=COVER_TOOL,
            tool_name="write_cover_letter",
        )
        
        return result
    
    def _review_cover_letter(self, ctx: WorkflowContext) -> ReviewResult:
        """Review generated cover letter."""
        return self._reviewer.review_cover_letter(
            ctx.cover_paragraphs,
            ctx.jd_text,
        )
    
    def _validate_final(self, ctx: WorkflowContext) -> List[Dict[str, Any]]:
        """Final validation of generated content."""
        resume_text = "\n".join(p["text"] for p in ctx.resume_paragraphs)
        
        return self._validator.validate_claims(
            resume_text,
            ctx.source_text,
        )
