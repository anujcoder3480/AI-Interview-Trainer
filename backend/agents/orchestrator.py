"""
Interview Orchestrator Agent
The central coordinator for an interview session.
All FastAPI routes talk exclusively to this agent.

Responsibilities:
- Create and manage session state (in-memory dict keyed by UUID).
- Delegate question generation to QuestionAgent.
- Delegate answer evaluation to EvaluationAgent.
- Assemble the final report.

Public interface:
    from backend.agents.orchestrator import OrchestratorAgent
    agent = OrchestratorAgent()

    session_id, first_question = agent.start_session(profile, num_questions, types)
    feedback, next_question    = agent.submit_answer(session_id, answer)
    report                     = agent.get_report(session_id)
"""

import uuid
from datetime import datetime
from backend.agents.question_agent import QuestionAgent
from backend.agents.evaluation_agent import EvaluationAgent


# ---------------------------------------------------------------------------
# Module-level singletons — one instance shared across all API requests
# ---------------------------------------------------------------------------
_question_agent = QuestionAgent()
_evaluation_agent = EvaluationAgent()

# Session store: {session_id: session_dict}
# Each session dict is defined in _new_session() below.
_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _new_session(profile: dict, questions: list[dict]) -> dict:
    """Create a blank session object."""
    return {
        "profile": profile,
        "questions": questions,           # full list [{id, text, category, difficulty}]
        "current_index": 0,               # index of the question currently being answered
        "evaluations": [],                # list of evaluation dicts, one per answered question
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }


def _build_report(session: dict) -> dict:
    """Assemble the final report object from a completed session."""
    profile = session["profile"]
    questions = session["questions"]
    evaluations = session["evaluations"]

    # Per-question rows
    rows = []
    for q, ev in zip(questions, evaluations):
        rows.append({
            "question_id": q["id"],
            "question": q["text"],
            "category": q["category"],
            "difficulty": q["difficulty"],
            "score": ev["score"],
            "strengths": ev["strengths"],
            "improvement": ev["improvement"],
            "ideal_points": ev.get("ideal_points", []),
        })

    # Overall average score
    scores = [r["score"] for r in rows]
    overall_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Per-category averages
    category_scores: dict[str, list[int]] = {}
    for r in rows:
        category_scores.setdefault(r["category"], []).append(r["score"])
    category_averages = {
        cat: round(sum(vals) / len(vals), 1)
        for cat, vals in category_scores.items()
    }

    # Top 3 strengths (most-mentioned across all evaluations)
    all_strengths: list[str] = []
    for ev in evaluations:
        all_strengths.extend(ev.get("strengths", []))
    top_strengths = list(dict.fromkeys(all_strengths))[:3]  # deduplicated, order-preserved

    # Top 3 improvement areas (one per answered question, deduplicated)
    all_improvements = list(dict.fromkeys(
        ev.get("improvement", "") for ev in evaluations if ev.get("improvement")
    ))[:3]

    return {
        "session_id": session.get("session_id", ""),
        "profile": profile,
        "overall_score": overall_score,
        "category_averages": category_averages,
        "top_strengths": top_strengths,
        "top_improvements": all_improvements,
        "questions_answered": len(rows),
        "questions_total": len(questions),
        "rows": rows,
        "started_at": session["started_at"],
        "finished_at": session["finished_at"],
    }


# ---------------------------------------------------------------------------
# Orchestrator Agent
# ---------------------------------------------------------------------------

class OrchestratorAgent:
    """
    Interview Orchestrator Agent.

    All state is stored in the module-level _sessions dict.
    Methods are intentionally synchronous — FastAPI will run them in a
    thread pool via run_in_executor if async is needed later.
    """

    # ------------------------------------------------------------------
    # 1. Start a new session
    # ------------------------------------------------------------------

    def start_session(
        self,
        profile: dict,
        num_questions: int = 7,
        types: list[str] | None = None,
    ) -> tuple[str, dict]:
        """
        Initialise a new interview session.

        Args:
            profile:       {role, experience, skills}
            num_questions: How many questions to generate.
            types:         ["technical", "behavioral", "hr"] (default all three).

        Returns:
            (session_id, first_question_dict)
        """
        if types is None:
            types = ["technical", "behavioral", "hr"]

        # Delegate to Question Generation Agent
        questions = _question_agent.generate(profile, num_questions, types)

        session_id = str(uuid.uuid4())
        session = _new_session(profile, questions)
        session["session_id"] = session_id
        _sessions[session_id] = session

        first_question = {
            **questions[0],
            "question_number": 1,
            "total_questions": len(questions),
        }
        return session_id, first_question

    # ------------------------------------------------------------------
    # 2. Submit an answer and get feedback + next question
    # ------------------------------------------------------------------

    def submit_answer(
        self,
        session_id: str,
        answer: str,
    ) -> tuple[dict, dict | None]:
        """
        Evaluate the current question's answer and advance the session.

        Args:
            session_id: Active session UUID.
            answer:     The candidate's answer string.

        Returns:
            (evaluation_dict, next_question_dict or None if last question)

        Raises:
            KeyError: If session_id is not found.
            ValueError: If the session is already complete.
        """
        if session_id not in _sessions:
            raise KeyError(f"Session '{session_id}' not found.")

        session = _sessions[session_id]
        idx = session["current_index"]
        questions = session["questions"]

        if idx >= len(questions):
            raise ValueError("All questions have already been answered.")

        current_question = questions[idx]
        profile = session["profile"]

        # Delegate to Evaluation Agent
        evaluation = _evaluation_agent.evaluate(current_question, answer, profile)
        session["evaluations"].append(evaluation)

        # Advance index
        session["current_index"] += 1
        next_idx = session["current_index"]

        # Prepare next question (or None if done)
        next_question = None
        if next_idx < len(questions):
            next_question = {
                **questions[next_idx],
                "question_number": next_idx + 1,
                "total_questions": len(questions),
            }
        else:
            # Session complete — record finish time
            session["finished_at"] = datetime.utcnow().isoformat()

        return evaluation, next_question

    # ------------------------------------------------------------------
    # 3. Get the final report
    # ------------------------------------------------------------------

    def get_report(self, session_id: str) -> dict:
        """
        Assemble and return the final interview report.

        Args:
            session_id: Active or completed session UUID.

        Returns:
            Report dict (see _build_report for structure).

        Raises:
            KeyError: If session_id is not found.
        """
        if session_id not in _sessions:
            raise KeyError(f"Session '{session_id}' not found.")

        session = _sessions[session_id]

        # Mark finished if not already (handles partial reports)
        if not session["finished_at"]:
            session["finished_at"] = datetime.utcnow().isoformat()

        return _build_report(session)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def session_exists(self, session_id: str) -> bool:
        return session_id in _sessions

    def get_current_question(self, session_id: str) -> dict | None:
        """Return the current unanswered question, or None if session is complete."""
        if session_id not in _sessions:
            return None
        session = _sessions[session_id]
        idx = session["current_index"]
        questions = session["questions"]
        if idx >= len(questions):
            return None
        return {
            **questions[idx],
            "question_number": idx + 1,
            "total_questions": len(questions),
        }
