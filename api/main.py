"""
FastAPI application for resume generation API.
Provides REST endpoints for job processing with human-in-the-loop workflow.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
import shutil
import tempfile

from core.logging_config import setup_logging
from agents.orchestrator import ResumeOrchestrator, WorkflowState

# Setup logging
logger = setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("JSON_LOGS", "false").lower() == "true",
)

# Create FastAPI app
app = FastAPI(
    title="Resume Agent API",
    description="AI-powered resume and cover letter generation with human approval",
    version="2.0.0",
)

# CORS for React dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (replace with Redis/DB in production)
jobs: Dict[str, dict] = {}


# Pydantic models
class JobRequest(BaseModel):
    """Request to start a new resume generation job."""
    job_folder: str = Field(..., description="Folder name containing JD PDF")
    auto_approve: bool = Field(default=False, description="Skip human checkpoints")
    

class JobResponse(BaseModel):
    """Response with job ID and status."""
    job_id: str
    status: str
    created_at: str
    message: str


class JobStatus(BaseModel):
    """Detailed job status."""
    job_id: str
    status: str
    state: Optional[str] = None
    progress: float = Field(0.0, ge=0.0, le=1.0)
    created_at: str
    updated_at: str
    resume_path: Optional[str] = None
    cover_path: Optional[str] = None
    qc_score: Optional[float] = None
    review_scores: Optional[dict] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request to approve a checkpoint."""
    approved: bool
    feedback: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    jobs_in_queue: int


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat(),
        jobs_in_queue=len([j for j in jobs.values() if j["status"] == "pending"]),
    )


@app.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    # Check if ChromaDB is accessible
    try:
        import chromadb
        client = chromadb.PersistentClient(path="db")
        collection = client.get_or_create_collection("job_descriptions")
        count = collection.count()
        return {"status": "ready", "db_connected": True, "jd_count": count}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Database not ready: {e}")


@app.post("/jobs", response_model=JobResponse)
async def create_job(request: JobRequest, background_tasks: BackgroundTasks):
    """Create a new resume generation job."""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "job_id": job_id,
        "job_folder": request.job_folder,
        "status": "pending",
        "state": WorkflowState.IDLE.value,
        "auto_approve": request.auto_approve,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "progress": 0.0,
        "context": None,
    }
    
    logger.info(f"Created job {job_id} for folder {request.job_folder}")
    
    # Start background processing
    background_tasks.add_task(process_job, job_id, request.auto_approve)
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        created_at=jobs[job_id]["created_at"],
        message=f"Job created. Status: /jobs/{job_id}/status",
    )


@app.get("/jobs/{job_id}/status", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get detailed status of a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    ctx = job.get("context")
    
    # Extract review scores if available
    review_scores = None
    if ctx and ctx.resume_review:
        review_scores = {
            "overall": ctx.resume_review.overall_score,
            "style": ctx.resume_review.style_score,
            "fit": ctx.resume_review.fit_score,
        }
    
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        state=job.get("state"),
        progress=job.get("progress", 0.0),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        resume_path=ctx.resume_path if ctx else None,
        cover_path=ctx.cover_path if ctx else None,
        qc_score=ctx.qc_result.score if ctx and ctx.qc_result else None,
        review_scores=review_scores,
        error=job.get("error"),
    )


@app.post("/jobs/{job_id}/approve/{checkpoint}")
async def approve_checkpoint(job_id: str, checkpoint: str, request: ApprovalRequest):
    """Approve a checkpoint for human-in-the-loop workflow."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Store approval decision
    if "approvals" not in job:
        job["approvals"] = {}
    
    job["approvals"][checkpoint] = {
        "approved": request.approved,
        "feedback": request.feedback,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(f"Checkpoint {checkpoint} for job {job_id}: {'approved' if request.approved else 'rejected'}")
    
    return {
        "job_id": job_id,
        "checkpoint": checkpoint,
        "approved": request.approved,
        "status": "recorded",
    }


@app.get("/jobs")
async def list_jobs(limit: int = 10, status: Optional[str] = None):
    """List recent jobs."""
    job_list = list(jobs.values())
    
    if status:
        job_list = [j for j in job_list if j["status"] == status]
    
    # Sort by created_at descending
    job_list.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "jobs": job_list[:limit],
        "total": len(jobs),
        "filtered": len(job_list),
    }


@app.post("/upload-and-generate")
async def upload_and_generate(
    file: UploadFile = File(..., description="Job description PDF"),
    company_name: str = "Company",
    auto_approve: bool = True,
):
    """
    Upload a JD PDF and immediately generate resume + cover letter.
    
    - Upload PDF
    - System processes it
    - Returns download links for generated files
    """
    import config
    from utils.text_extraction import extract_text
    from agents.tailor_agent import TailorAgent
    from agents.validator_agent import ValidatorAgent
    from agents.formatter_agent import FormatterAgent
    import asyncio
    
    try:
        # Create temporary folder
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        job_folder = f"{timestamp}_{company_name}"
        temp_dir = Path(tempfile.gettempdir()) / job_folder
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file
        jd_path = temp_dir / file.filename
        with open(jd_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Extract text
        jd_text = extract_text(str(jd_path))
        
        # Create output folder
        output_dir = Path(config.RESUME_ROOT) / job_folder
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy JD to output folder for reference
        shutil.copy(jd_path, output_dir / file.filename)
        
        # Initialize ChromaDB and agents
        import chromadb
        chroma_client = chromadb.PersistentClient(path=config.DB_PATH)
        collection = chroma_client.get_or_create_collection(config.DB_COLLECTION)
        
        tailor = TailorAgent(collection)
        validator = ValidatorAgent()
        formatter = FormatterAgent()
        
        # Run synchronous code in thread pool to not block
        loop = asyncio.get_event_loop()
        
        # Find similar jobs and generate
        result = await loop.run_in_executor(None, tailor.run, str(jd_path))
        
        # Validate
        source_text = "\n".join(p["text"] for p in result.get("source_paragraphs", []))
        validation = await loop.run_in_executor(
            None, 
            validator.run,
            result["resume_paragraphs"],
            result["cover_paragraphs"],
            source_text,
        )
        
        # Format and save
        format_result = await loop.run_in_executor(
            None,
            formatter.run,
            str(output_dir),
            result["resume_paragraphs"],
            result["cover_paragraphs"],
            validation.violations if validation else [],
        )
        
        resume_path = format_result["resume_path"]
        cover_path = format_result["cover_path"]
        
        # Prepare metadata
        metadata = {
            "job_folder": job_folder,
            "company": company_name,
            "jd_filename": file.filename,
            "jd_length": len(jd_text),
            "similar_jobs": result.get("similar_jobs", []),
            "source_resume": result.get("source_resume", "unknown"),
            "validation_violations": len(validation.violations) if validation else 0,
            "resume_paragraphs": len(result["resume_paragraphs"]),
            "cover_paragraphs": len(result["cover_paragraphs"]),
            "generated_at": datetime.utcnow().isoformat(),
            "output_files": {
                "resume": str(resume_path),
                "cover": str(cover_path),
            },
        }
        
        return {
            "success": True,
            "job_folder": job_folder,
            "company": company_name,
            "download_urls": {
                "resume": f"/download/{job_folder}/resume",
                "cover": f"/download/{job_folder}/cover",
            },
            "metadata": metadata,
            "violations": validation.violations if validation else [],
        }
        
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{job_folder}/{file_type}")
async def download_file(job_folder: str, file_type: str):
    """Download generated resume or cover letter."""
    import config
    
    output_dir = Path(config.RESUME_ROOT) / job_folder
    
    # Extract company name from folder
    company = job_folder.split("_")[-1] if "_" in job_folder else "Company"
    
    if file_type == "resume":
        file_path = output_dir / f"ZhuYunhua_{company}_resume.docx"
        filename = f"{company}_resume.docx"
    elif file_type == "cover":
        file_path = output_dir / f"ZhuYunhua_{company}_cover.docx"
        filename = f"{company}_cover.docx"
    else:
        raise HTTPException(status_code=400, detail="Invalid file_type. Use 'resume' or 'cover'")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/", response_class=HTMLResponse)
async def root():
    """Simple HTML interface for file upload."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Resume Agent</title>
        <style>
            body { font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #1A3A5C; }
            .upload-box { border: 2px dashed #ccc; padding: 40px; text-align: center; border-radius: 8px; }
            input[type="file"] { margin: 20px 0; }
            button { background: #1A3A5C; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #2d5a8f; }
            .result { margin-top: 20px; padding: 20px; background: #f0f0f0; border-radius: 4px; display: none; }
        </style>
    </head>
    <body>
        <h1>📄 Resume Agent</h1>
        <p>Upload a job description PDF to generate a tailored resume and cover letter.</p>
        
        <div class="upload-box">
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" name="file" accept=".pdf" required><br>
                <input type="text" name="company_name" placeholder="Company Name" required><br><br>
                <button type="submit">Generate Resume & Cover Letter</button>
            </form>
        </div>
        
        <div id="result" class="result"></div>
        
        <script>
            document.getElementById('uploadForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                
                document.getElementById('result').style.display = 'block';
                document.getElementById('result').innerHTML = '⏳ Processing... This may take 30-60 seconds.';
                
                try {
                    const response = await fetch('/upload-and-generate', {
                        method: 'POST',
                        body: formData
                    });
                    
                    // Check if response is OK
                    if (!response.ok) {
                        const errorText = await response.text();
                        let errorMsg = errorText;
                        try {
                            const errorData = JSON.parse(errorText);
                            errorMsg = errorData.detail || errorData.message || errorText;
                        } catch (e) {
                            // Not JSON, use text as is
                        }
                        throw new Error(`Server error (${response.status}): ${errorMsg}`);
                    }
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        let html = `<h3>✅ Generated Successfully!</h3>`;
                        html += `<p><strong>Company:</strong> ${data.company}</p>`;
                        html += `<p><strong>JD Length:</strong> ${data.metadata.jd_length} chars</p>`;
                        html += `<p><strong>Resume Paragraphs:</strong> ${data.metadata.resume_paragraphs}</p>`;
                        html += `<p><strong>Cover Paragraphs:</strong> ${data.metadata.cover_paragraphs}</p>`;
                        
                        if (data.violations && data.violations.length > 0) {
                            html += `<p style="color: orange;">⚠️ ${data.violations.length} validation warnings</p>`;
                        }
                        
                        html += `<h4>Download:</h4>`;
                        html += `<a href="${data.download_urls.resume}" download><button>📄 Download Resume</button></a> `;
                        html += `<a href="${data.download_urls.cover}" download><button>📝 Download Cover Letter</button></a>`;
                        
                        document.getElementById('result').innerHTML = html;
                    } else {
                        document.getElementById('result').innerHTML = `<p style="color: red;">❌ Error: ${data.error || 'Unknown error'}</p>`;
                    }
                } catch (error) {
                    console.error('Full error:', error);
                    document.getElementById('result').innerHTML = `<p style="color: red;">❌ Error: ${error.message}</p>`;
                }
            };
        </script>
    </body>
    </html>
    """


async def process_job(job_id: str, auto_approve: bool):
    """Background task to process a job."""
    job = jobs[job_id]
    
    try:
        # Import here to avoid circular imports
        from services.retrieval import RetrievalService
        import chromadb
        import config
        
        # Setup ChromaDB
        client = chromadb.PersistentClient(path=config.VECTOR_DB_PATH)
        collection = client.get_or_create_collection(name="job_descriptions")
        retrieval = RetrievalService(collection)
        
        # Create orchestrator
        orchestrator = ResumeOrchestrator(
            retrieval_service=retrieval,
            enable_tracing=True,
            trace_dir="evals/traces",
        )
        
        # Update job status
        job["status"] = "processing"
        job["state"] = WorkflowState.RETRIEVING.value
        job["progress"] = 0.1
        
        # Load job description
        from utils.text_extraction import extract_text
        from pathlib import Path
        
        job_folder_path = Path(config.RESUME_ROOT) / job["job_folder"]
        jd_files = list(job_folder_path.glob("*.pdf"))
        
        if not jd_files:
            raise ValueError(f"No PDF found in {job_folder_path}")
        
        jd_path = jd_files[0]
        jd_text = extract_text(str(jd_path))
        
        # Run orchestrator (with callbacks to update job status)
        def state_callback(old_state, new_state, ctx):
            job["state"] = new_state.value if hasattr(new_state, 'value') else str(new_state)
            job["context"] = ctx
            job["updated_at"] = datetime.utcnow().isoformat()
            
            # Calculate progress
            state_order = [
                WorkflowState.IDLE,
                WorkflowState.RETRIEVING,
                WorkflowState.SELECTING_SOURCE,
                WorkflowState.GENERATING_RESUME,
                WorkflowState.REVIEWING_RESUME,
                WorkflowState.AWAITING_RESUME_APPROVAL,
                WorkflowState.GENERATING_COVER,
                WorkflowState.REVIEWING_COVER,
                WorkflowState.AWAITING_COVER_APPROVAL,
                WorkflowState.VALIDATING,
                WorkflowState.COMPLETED,
            ]
            if new_state in state_order:
                idx = state_order.index(new_state)
                job["progress"] = min(1.0, idx / len(state_order))
            
            logger.info(f"Job {job_id} state: {job['state']} (progress: {job['progress']:.0%})")
        
        orchestrator.on_state_change(state_callback)
        
        # Run the workflow
        ctx = orchestrator.run(
            job_folder=job["job_folder"],
            jd_path=str(jd_path),
            jd_text=jd_text,
            auto_approve=auto_approve,
        )
        
        # Mark completed
        job["status"] = "completed"
        job["state"] = WorkflowState.COMPLETED.value
        job["progress"] = 1.0
        job["context"] = ctx
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["state"] = WorkflowState.REJECTED.value if hasattr(WorkflowState, 'REJECTED') else "failed"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
