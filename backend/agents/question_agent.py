"""
Question Generation Agent
Uses RAG + IBM Granite to generate a personalised list of interview questions
based on the user's job role, experience level, skills, and chosen question types.

Public interface:
    from backend.agents.question_agent import QuestionAgent
    agent = QuestionAgent()
    questions = agent.generate(profile, num_questions, types)
"""

import re
import json
from backend.rag.retriever import search_multi
from backend.llm.granite_client import generate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_rag_queries(profile: dict, types: list[str]) -> list[str]:
    """Build retrieval queries from the user profile and chosen question types."""
    role = profile.get("role", "software engineer")
    skills = profile.get("skills", "")
    exp = profile.get("experience", "fresher")

    queries = [f"{role} interview questions {exp}"]
    if skills:
        queries.append(f"{skills} technical interview questions")
    if "technical" in types:
        queries.append(f"{role} technical coding system design questions")
    if "behavioral" in types:
        queries.append("behavioral STAR method interview questions leadership teamwork")
    if "hr" in types:
        queries.append("HR interview questions strengths weaknesses career goals salary")
    return queries


def _build_prompt(profile: dict, num_questions: int, types: list[str], context_chunks: list[str]) -> str:
    """Construct the full prompt sent to Granite."""
    role = profile.get("role", "software engineer")
    experience = profile.get("experience", "fresher")
    skills = profile.get("skills", "not specified")

    type_instructions = []
    if "technical" in types:
        type_instructions.append("technical (coding, system design, concepts)")
    if "behavioral" in types:
        type_instructions.append("behavioral (STAR-method, teamwork, leadership)")
    if "hr" in types:
        type_instructions.append("HR (strengths, weaknesses, career goals, motivation)")

    types_str = ", ".join(type_instructions) if type_instructions else "technical, behavioral, and HR"
    context_str = "\n\n".join(context_chunks[:5])  # cap at 5 chunks to control token usage

    prompt = f"""<|system|>
You are an expert interview coach. Your task is to generate exactly {num_questions} interview questions for a candidate.
You must output ONLY a valid JSON array. Do not include any explanation, markdown, or text outside the JSON array.

Candidate Profile:
- Job Role: {role}
- Experience Level: {experience}
- Skills: {skills}

Question Types Required: {types_str}

Reference Knowledge (use this to make questions relevant and specific):
{context_str}

Rules:
1. Generate exactly {num_questions} questions total.
2. Distribute questions across the requested types as evenly as possible.
3. Tailor technical questions to the candidate's specific skills and role.
4. Each question must have: "id", "text", "category" (one of: technical, behavioral, hr), "difficulty" (easy, medium, hard).
5. Output ONLY a JSON array, nothing else.

Example format:
[
  {{"id": "q1", "text": "Explain the difference between a stack and a queue.", "category": "technical", "difficulty": "easy"}},
  {{"id": "q2", "text": "Tell me about a time you resolved a conflict in your team.", "category": "behavioral", "difficulty": "medium"}}
]
<|assistant|>
"""
    return prompt


def _parse_questions(raw: str, num_questions: int) -> list[dict]:
    """
    Extract the JSON array from Granite's response.
    Tries strict parse first, then falls back to regex extraction.
    """
    # Try to find a JSON array anywhere in the response
    match = re.search(r'\[\s*\{.*?\}\s*\]', raw, re.DOTALL)
    if match:
        try:
            questions = json.loads(match.group())
            return _normalise(questions)
        except json.JSONDecodeError:
            pass

    # Fallback: try parsing the entire response as JSON
    try:
        questions = json.loads(raw.strip())
        if isinstance(questions, list):
            return _normalise(questions)
    except json.JSONDecodeError:
        pass

    # Last resort: return a safe placeholder so the session can still run
    return _fallback_questions(num_questions)


def _normalise(questions: list) -> list[dict]:
    """Ensure every question has the required fields with safe defaults."""
    normalised = []
    valid_categories = {"technical", "behavioral", "hr"}
    valid_difficulties = {"easy", "medium", "hard"}

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        normalised.append({
            "id": str(q.get("id", f"q{i+1}")),
            "text": str(q.get("text", q.get("question", "Tell me about yourself."))),
            "category": q.get("category", "hr") if q.get("category") in valid_categories else "hr",
            "difficulty": q.get("difficulty", "medium") if q.get("difficulty") in valid_difficulties else "medium",
        })
    return normalised


def _fallback_questions(num_questions: int) -> list[dict]:
    """Minimal safe fallback if Granite returns unparseable output."""
    pool = [
        {"id": "f1", "text": "Tell me about yourself and your background.", "category": "hr", "difficulty": "easy"},
        {"id": "f2", "text": "What are your greatest technical strengths?", "category": "technical", "difficulty": "easy"},
        {"id": "f3", "text": "Describe a challenging project you worked on.", "category": "behavioral", "difficulty": "medium"},
        {"id": "f4", "text": "Explain the difference between a process and a thread.", "category": "technical", "difficulty": "medium"},
        {"id": "f5", "text": "Where do you see yourself in 5 years?", "category": "hr", "difficulty": "easy"},
        {"id": "f6", "text": "Tell me about a time you had to learn something quickly.", "category": "behavioral", "difficulty": "medium"},
        {"id": "f7", "text": "What is the time complexity of binary search?", "category": "technical", "difficulty": "easy"},
    ]
    return pool[:num_questions]


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class QuestionAgent:
    """
    Question Generation Agent.

    Responsibilities:
    - Query the RAG knowledge base for relevant interview context.
    - Build a structured prompt for IBM Granite.
    - Parse and validate Granite's JSON response into a question list.
    """

    def generate(
        self,
        profile: dict,
        num_questions: int = 7,
        types: list[str] | None = None,
    ) -> list[dict]:
        """
        Generate a personalised interview question list.

        Args:
            profile:       {"role": str, "experience": str, "skills": str}
            num_questions: Total number of questions to generate (default 7).
            types:         List of question types: ["technical", "behavioral", "hr"].
                           Defaults to all three if not specified.

        Returns:
            List of question dicts: [{id, text, category, difficulty}, ...]
        """
        if types is None:
            types = ["technical", "behavioral", "hr"]

        # Step 1: RAG retrieval
        queries = _build_rag_queries(profile, types)
        context_chunks = search_multi(queries, k=3)

        # Step 2: Build prompt
        prompt = _build_prompt(profile, num_questions, types, context_chunks)

        # Step 3: Call Granite
        raw_response = generate(prompt, max_new_tokens=1024, temperature=0.7)

        # Step 4: Parse and return
        questions = _parse_questions(raw_response, num_questions)

        # Trim or pad to exact count
        if len(questions) > num_questions:
            questions = questions[:num_questions]
        elif len(questions) < num_questions:
            extra = _fallback_questions(num_questions - len(questions))
            questions.extend(extra)

        # Re-index IDs to be clean and sequential
        for i, q in enumerate(questions):
            q["id"] = f"q{i+1}"

        return questions
