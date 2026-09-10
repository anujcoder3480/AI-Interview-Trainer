"""
FastAPI Backend — AI Interview Trainer
Exposes four API routes consumed by the frontend.
All business logic is handled by the OrchestratorAgent.

Routes:
    GET  /              → serves frontend/index.html
    GET  /health        → health check
    POST /api/start     → start a new interview session
    POST /api/answer    → submit an answer, get feedback + next question
    GET  /api/report/{session_id} → get the final interview report
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.agents.orchestrator import OrchestratorAgent

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Interview Trainer",
    description="IBM Granite + RAG powered mock interview agent",
    version="1.0.0",
)

# Allow all origins during development (frontend served from same host anyway)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Module-level orchestrator — one instance shared across all requests
_orchestrator = OrchestratorAgent()


# ---------------------------------------------------------------------------
# Startup: pre-load the RAG knowledge base so the first API call is fast
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=100, example="Software Engineer")
    experience: str = Field(..., example="1-3 years")
    skills: str = Field(default="", max_length=300, example="Python, REST APIs, SQL")
    num_questions: int = Field(default=7, ge=3, le=10)
    types: list[str] = Field(default=["technical", "behavioral", "hr"])


class StartResponse(BaseModel):
    session_id: str
    question: dict
    message: str


class AnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(default="", max_length=2000)


class AnswerResponse(BaseModel):
    evaluation: dict
    next_question: dict | None
    is_complete: bool


class ReportResponse(BaseModel):
    report: dict


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the frontend setup page."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse({"message": "Frontend not built yet. Run sub-task 9."}, status_code=200)
    return FileResponse(str(index_path))


@app.get("/interview", include_in_schema=False)
async def serve_interview():
    return FileResponse(str(FRONTEND_DIR / "interview.html"))


@app.get("/report-page", include_in_schema=False)
async def serve_report_page():
    return FileResponse(str(FRONTEND_DIR / "report.html"))


@app.get("/health")
async def health_check():
    """Simple liveness check."""
    return {"status": "ok", "model": "ibm/granite-3-8b-instruct"}


@app.post("/api/start", response_model=StartResponse)
async def start_interview(body: StartRequest):
    """
    Start a new interview session.
    Returns the session ID and the first question.
    """
    # Validate types
    valid_types = {"technical", "behavioral", "hr"}
    types = [t for t in body.types if t in valid_types]
    if not types:
        types = ["technical", "behavioral", "hr"]

    profile = {
        "role": body.role.strip(),
        "experience": body.experience.strip(),
        "skills": body.skills.strip(),
    }

    try:
        session_id, first_question = _orchestrator.start_session(
            profile=profile,
            num_questions=body.num_questions,
            types=types,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(exc)}")

    return StartResponse(
        session_id=session_id,
        question=first_question,
        message="Interview session started successfully.",
    )


@app.post("/api/answer", response_model=AnswerResponse)
async def submit_answer(body: AnswerRequest):
    """
    Submit the candidate's answer to the current question.
    Returns evaluation feedback and the next question (or None if finished).
    """
    if not _orchestrator.session_exists(body.session_id):
        raise HTTPException(status_code=404, detail="Session not found. Please start a new interview.")

    try:
        evaluation, next_question = _orchestrator.submit_answer(
            session_id=body.session_id,
            answer=body.answer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(exc)}")

    return AnswerResponse(
        evaluation=evaluation,
        next_question=next_question,
        is_complete=(next_question is None),
    )


@app.get("/api/report/{session_id}", response_model=ReportResponse)
async def get_report(session_id: str):
    """
    Retrieve the final interview report for a completed session.
    """
    if not _orchestrator.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        report = _orchestrator.get_report(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(exc)}")

    return ReportResponse(report=report)


@app.get("/api/session/{session_id}/current-question")
async def get_current_question(session_id: str):
    """
    Return the current unanswered question for a session.
    Useful if the interview page is refreshed mid-session.
    """
    if not _orchestrator.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    question = _orchestrator.get_current_question(session_id)
    if question is None:
        return {"question": None, "is_complete": True}
    return {"question": question, "is_complete": False}
