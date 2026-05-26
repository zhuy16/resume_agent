"""
Interactive resume generation with human-in-the-loop approval.
Provides CLI interface for reviewing and approving generated content.
"""

import sys
import argparse
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import ResumeOrchestrator, WorkflowContext, WorkflowState
from services.retrieval import RetrievalService
from utils.docx_utils import build_document
import config


def print_header(text: str):
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def print_section(title: str, content: str, max_length: int = 500):
    """Print a content section with title."""
    print(f"\n📄 {title}")
    print("-" * 40)
    preview = content[:max_length] + "..." if len(content) > max_length else content
    print(preview)


def get_yes_no_input(prompt: str, default: bool = False) -> bool:
    """Get yes/no input from user."""
    default_str = "Y/n" if default else "y/N"
    user_input = input(f"{prompt} [{default_str}]: ").strip().lower()
    
    if not user_input:
        return default
    
    return user_input in ['y', 'yes', 'true', '1']


def review_resume_interactive(ctx: WorkflowContext) -> bool:
    """
    Interactive resume review with user approval.
    
    Returns:
        True if approved, False if rejected
    """
    print_header("📝 RESUME REVIEW")
    
    # Show source info
    print(f"\n📊 Source Quality: {ctx.qc_result.score:.2f}/1.0" if ctx.qc_result else "\n📊 Source Quality: N/A")
    if ctx.qc_result and ctx.qc_result.issues:
        print(f"   ⚠️  Issues: {', '.join(ctx.qc_result.issues)}")
    
    # Show AI review
    if ctx.resume_review:
        print("\n🤖 AI Review:")
        print(f"   Overall Score: {ctx.resume_review.overall_score}/100")
        print(f"   Style Score: {ctx.resume_review.style_score}/100")
        print(f"   Fit Score: {ctx.resume_review.fit_score}/100")
        
        if ctx.resume_review.strengths:
            print("\n   ✅ Strengths:")
            for s in ctx.resume_review.strengths[:3]:
                print(f"      • {s}")
        
        if ctx.resume_review.weaknesses:
            print("\n   ⚠️  Weaknesses:")
            for w in ctx.resume_review.weaknesses[:3]:
                print(f"      • {w}")
        
        if ctx.resume_review.action_required:
            print("\n   🚨 ACTION REQUIRED: Critical issues detected!")
    
    # Show content preview
    resume_text = "\n".join(f"[{p['style']}] {p['text']}" for p in ctx.resume_paragraphs[:10])
    print_section("Generated Resume (first 10 paragraphs)", resume_text)
    
    # Get approval
    print("\n" + "-" * 60)
    approved = get_yes_no_input("✅ Approve this resume?", default=True)
    
    if not approved:
        print("\n❌ Resume rejected.")
        return False
    
    print("\n✅ Resume approved!")
    return True


def review_cover_interactive(ctx: WorkflowContext) -> bool:
    """
    Interactive cover letter review with user approval.
    
    Returns:
        True if approved, False if rejected
    """
    print_header("💌 COVER LETTER REVIEW")
    
    # Show AI review
    if ctx.cover_review:
        print("\n🤖 AI Review:")
        print(f"   Overall Score: {ctx.cover_review.overall_score}/100")
        
        if ctx.cover_review.strengths:
            print("\n   ✅ Strengths:")
            for s in ctx.cover_review.strengths[:2]:
                print(f"      • {s}")
        
        if ctx.cover_review.weaknesses:
            print("\n   ⚠️  Weaknesses:")
            for w in ctx.cover_review.weaknesses[:2]:
                print(f"      • {w}")
    
    # Show content
    cover_text = "\n".join(f"[{p['style']}] {p['text']}" for p in ctx.cover_paragraphs)
    print_section("Generated Cover Letter", cover_text, max_length=800)
    
    # Get approval
    print("\n" + "-" * 60)
    approved = get_yes_no_input("✅ Approve this cover letter?", default=True)
    
    if not approved:
        print("\n❌ Cover letter rejected.")
        return False
    
    print("\n✅ Cover letter approved!")
    return True


def state_change_callback(old_state: WorkflowState, new_state: WorkflowState, ctx: WorkflowContext):
    """Callback for workflow state changes."""
    state_names = {
        WorkflowState.IDLE: "Idle",
        WorkflowState.RETRIEVING: "🔍 Retrieving similar jobs",
        WorkflowState.SELECTING_SOURCE: "📂 Selecting source resume",
        WorkflowState.GENERATING_RESUME: "✍️  Generating resume",
        WorkflowState.REVIEWING_RESUME: "🔍 Reviewing resume",
        WorkflowState.AWAITING_RESUME_APPROVAL: "⏸️  Awaiting resume approval",
        WorkflowState.GENERATING_COVER: "✍️  Generating cover letter",
        WorkflowState.REVIEWING_COVER: "🔍 Reviewing cover letter",
        WorkflowState.AWAITING_COVER_APPROVAL: "⏸️  Awaiting cover approval",
        WorkflowState.VALIDATING: "✅ Validating final output",
        WorkflowState.COMPLETED: "🎉 Completed",
        WorkflowState.REJECTED: "❌ Rejected",
    }
    
    if new_state in [WorkflowState.COMPLETED, WorkflowState.REJECTED]:
        return
    
    print(f"\n  → {state_names.get(new_state, str(new_state))}")


def human_approval_callback(checkpoint: str, ctx: WorkflowContext) -> bool:
    """Human approval callback for workflow checkpoints."""
    if checkpoint == "resume":
        return review_resume_interactive(ctx)
    elif checkpoint == "cover_letter":
        return review_cover_interactive(ctx)
    return True


def main():
    """Main interactive entry point."""
    parser = argparse.ArgumentParser(description="Interactive resume generation with human approval")
    parser.add_argument("--folder", "-f", required=True, help="Job folder (e.g., 260513.3_Parse)")
    parser.add_argument("--auto", "-a", action="store_true", help="Auto-approve (skip human checkpoints)")
    parser.add_argument("--save", "-s", action="store_true", default=True, help="Save output files")
    
    args = parser.parse_args()
    
    print_header("🚀 INTERACTIVE RESUME GENERATOR")
    print(f"Job folder: {args.folder}")
    print(f"Mode: {'Auto' if args.auto else 'Interactive (human checkpoints)'}")
    
    # Initialize services
    import chromadb
    
    print("\n📡 Connecting to vector database...")
    client = chromadb.PersistentClient(path=config.DB_PATH)
    collection = client.get_or_create_collection(name="job_descriptions")
    retrieval = RetrievalService(collection)
    
    # Create orchestrator
    orchestrator = ResumeOrchestrator(
        retrieval_service=retrieval,
        enable_tracing=True,
        trace_dir=str(config.PROJECT_ROOT / "evals" / "traces"),
    )
    
    # Register callbacks
    orchestrator.on_state_change(state_change_callback)
    
    if not args.auto:
        orchestrator.on_human_approval(human_approval_callback)
    
    # Load job description
    job_folder_path = Path(config.RESUME_ROOT) / args.folder
    jd_files = list(job_folder_path.glob("*.pdf"))
    
    if not jd_files:
        print(f"❌ No PDF files found in {job_folder_path}")
        sys.exit(1)
    
    jd_path = jd_files[0]  # Use first PDF
    print(f"\n📄 Using JD: {jd_path.name}")
    
    # Extract JD text
    from utils.text_extraction import extract_text
    jd_text = extract_text(str(jd_path))
    print(f"   JD length: {len(jd_text)} chars")
    
    # Run workflow
    print_header("⚙️  EXECUTING WORKFLOW")
    
    ctx = orchestrator.run(
        job_folder=args.folder,
        jd_path=str(jd_path),
        jd_text=jd_text,
        auto_approve=args.auto,
    )
    
    # Results
    print_header("📊 RESULTS")
    
    if ctx._state == orchestrator._get_state_from_context(ctx):
        if hasattr(ctx, '_state') and ctx._state == WorkflowState.REJECTED:
            print(f"\n❌ Workflow rejected: {ctx.rejection_reason}")
            sys.exit(1)
    
    if ctx.completed_at:
        duration = (ctx.completed_at - ctx.started_at).total_seconds()
        print(f"\n⏱️  Duration: {duration:.1f}s")
    
    print(f"✅ Resume paragraphs: {len(ctx.resume_paragraphs)}")
    print(f"✅ Cover paragraphs: {len(ctx.cover_paragraphs)}")
    
    if ctx.validation_violations:
        print(f"⚠️  Validation violations: {len(ctx.validation_violations)}")
        for v in ctx.validation_violations[:3]:
            print(f"   • {v.get('issue', 'Unknown')[:60]}...")
    
    # Save outputs
    if args.save and ctx.resume_paragraphs and ctx.cover_paragraphs:
        print_header("💾 SAVING OUTPUTS")
        
        output_dir = job_folder_path
        
        # Extract company name from folder
        company = args.folder.split("_")[-1] if "_" in args.folder else "Unknown"
        
        resume_path = output_dir / f"ZhuYunhua_{company}_resume.docx"
        cover_path = output_dir / f"ZhuYunhua_{company}_cover.docx"
        
        try:
            build_document(ctx.resume_paragraphs, str(resume_path))
            print(f"✅ Resume: {resume_path}")
        except Exception as e:
            print(f"❌ Resume save failed: {e}")
        
        try:
            build_document(ctx.cover_paragraphs, str(cover_path))
            print(f"✅ Cover: {cover_path}")
        except Exception as e:
            print(f"❌ Cover save failed: {e}")
    
    print_header("🎉 DONE!")
    print(f"\nFiles saved to: {job_folder_path}")


if __name__ == "__main__":
    main()
