"""
Answer Evaluation Agent
Uses RAG + IBM Granite to score a candidate's answer to an interview question
and return structured feedback with improvement suggestions.

Public interface:
    from backend.agents.evaluation_agent import EvaluationAgent
    agent = EvaluationAgent()
    result = agent.evaluate(question, answer, profile)
    # result → {"score": 7, "strengths": [...], "improvement": "...", "category": "..."}
"""

import re
import json
from backend.rag.retriever import search
from backend.llm.granite_client import generate


# ---------------------------------------------------------------------------
# Score rubric injected into every evaluation prompt
# ---------------------------------------------------------------------------
_RUBRIC = """
Score rubric (1–10):
1–3 : Off-topic, very incomplete, or shows fundamental misunderstanding.
4–5 : Partially correct but missing key elements or too vague.
6–7 : Good answer with minor gaps; mostly clear and relevant.
8–9 : Strong answer — specific, well-structured, and demonstrates clear understanding.
10  : Exceptional — specific examples, quantified outcomes, textbook-perfect structure.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prompt(
    question: dict,
    answer: str,
    profile: dict,
    context_chunks: list[str],
) -> str:
    """Construct the evaluation prompt for Granite."""
    role = profile.get("role", "software engineer")
    experience = profile.get("experience", "fresher")
    category = question.get("category", "general")
    difficulty = question.get("difficulty", "medium")
    question_text = question.get("text", "")

    context_str = "\n\n".join(context_chunks[:3])  # cap at 3 chunks

    prompt = f"""<|system|>
You are a strict but fair interview evaluator. Evaluate the candidate's answer below.
You must output ONLY a valid JSON object. Do not include any explanation or text outside the JSON.

Candidate Profile:
- Job Role: {role}
- Experience Level: {experience}

Interview Question ({category}, {difficulty}):
{question_text}

Candidate's Answer:
{answer.strip() if answer.strip() else "(no answer provided)"}

Reference Knowledge (ideal answer patterns):
{context_str}

{_RUBRIC}

Output a JSON object with exactly these fields:
- "score": integer 1–10
- "strengths": list of 1–3 short strings (what the candidate did well)
- "improvement": single string (the single most important thing to improve)
- "ideal_points": list of 1–3 short strings (key points a great answer would include)

Example output:
{{"score": 7, "strengths": ["Used STAR format", "Gave a specific example"], "improvement": "Quantify the outcome with a metric or number.", "ideal_points": ["Mention team size", "State the measurable result", "Describe your specific role"]}}
<|assistant|>
"""
    return prompt


def _parse_evaluation(raw: str) -> dict:
    """
    Extract the evaluation JSON object from Granite's response.
    Falls back to a safe default if parsing fails.
    """
    # Try regex extraction of a JSON object
    match = re.search(r'\{[^{}]*"score"[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            return _normalise(result)
        except json.JSONDecodeError:
            pass

    # Try parsing the entire stripped response
    try:
        result = json.loads(raw.strip())
        if isinstance(result, dict) and "score" in result:
            return _normalise(result)
    except json.JSONDecodeError:
        pass

    # Last resort fallback
    return _fallback_evaluation()


def _normalise(result: dict) -> dict:
    """Validate and coerce evaluation fields to expected types."""
    # Score: clamp to 1–10
    try:
        score = int(result.get("score", 5))
        score = max(1, min(10, score))
    except (ValueError, TypeError):
        score = 5

    # Strengths: list of strings
    strengths = result.get("strengths", [])
    if not isinstance(strengths, list):
        strengths = [str(strengths)]
    strengths = [str(s) for s in strengths[:3]]
    if not strengths:
        strengths = ["Answer provided"]

    # Improvement: single string
    improvement = str(result.get("improvement", "Try to be more specific and structured."))

    # Ideal points: list of strings
    ideal_points = result.get("ideal_points", [])
    if not isinstance(ideal_points, list):
        ideal_points = [str(ideal_points)]
    ideal_points = [str(p) for p in ideal_points[:3]]

    return {
        "score": score,
        "strengths": strengths,
        "improvement": improvement,
        "ideal_points": ideal_points,
    }


def _fallback_evaluation() -> dict:
    """Safe default when Granite response cannot be parsed."""
    return {
        "score": 5,
        "strengths": ["Answer was provided"],
        "improvement": "Try to structure your answer more clearly with specific examples.",
        "ideal_points": ["Be specific", "Use the STAR method for behavioral questions", "Quantify outcomes where possible"],
    }


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class EvaluationAgent:
    """
    Answer Evaluation Agent.

    Responsibilities:
    - Query RAG for ideal-answer patterns relevant to the question.
    - Build a structured evaluation prompt for IBM Granite.
    - Parse Granite's JSON response into a structured evaluation object.
    - Return score (1–10), strengths, improvement tip, and ideal key points.
    """

    def evaluate(
        self,
        question: dict,
        answer: str,
        profile: dict,
    ) -> dict:
        """
        Evaluate a single interview answer.

        Args:
            question: Question dict {id, text, category, difficulty}.
            answer:   The candidate's raw answer string.
            profile:  User profile {role, experience, skills}.

        Returns:
            dict with keys: score, strengths, improvement, ideal_points, category.
        """
        category = question.get("category", "general")
        question_text = question.get("text", "")

        # Step 1: RAG — retrieve ideal-answer context for this question
        rag_query = f"{question_text} ideal answer {category} interview"
        context_chunks = search(rag_query, k=3, category=category if category in ("technical", "behavioral", "hr") else None)

        # Step 2: Build prompt
        prompt = _build_prompt(question, answer, profile, context_chunks)

        # Step 3: Call Granite
        raw_response = generate(prompt, max_new_tokens=512, temperature=0.3)
        # Lower temperature (0.3) for evaluation — we want consistent, deterministic scoring

        # Step 4: Parse and enrich
        result = _parse_evaluation(raw_response)
        result["category"] = category  # attach category for report aggregation

        return result
