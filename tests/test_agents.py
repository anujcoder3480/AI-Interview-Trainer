"""
Test: End-to-end agent pipeline (no browser required)
Run from the project root:
    python tests/test_agents.py

Requires a valid .env file with WATSONX_API_KEY and WATSONX_PROJECT_ID.
This test makes real Granite API calls.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.orchestrator import OrchestratorAgent

# ---------------------------------------------------------------------------
# Mock profile
# ---------------------------------------------------------------------------
PROFILE = {
    "role": "Software Engineer",
    "experience": "1-3 years",
    "skills": "Python, data structures, REST APIs",
}
NUM_QUESTIONS = 3   # keep small for the test to run quickly
TYPES = ["technical", "behavioral", "hr"]

# Mock answers — realistic enough to produce meaningful scores
MOCK_ANSWERS = [
    "A stack follows LIFO order — last in, first out. It supports push and pop operations, both O(1). I use stacks for DFS graph traversal and expression parsing in compilers.",
    "In my last internship, two teammates disagreed on the database design. I organised a short meeting where each person explained their reasoning, then we mapped both options against our requirements. We chose the hybrid approach — it shipped on time and had no schema issues.",
    "I want to keep growing my backend skills, take on ownership of a full feature end-to-end, and eventually mentor junior engineers. This role seems like a great step toward that because of the scale of the systems involved.",
]


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def test_full_session():
    orchestrator = OrchestratorAgent()

    # ---- Step 1: Start session ----
    separator("STEP 1: Start Session")
    session_id, first_question = orchestrator.start_session(PROFILE, NUM_QUESTIONS, TYPES)
    print(f"Session ID : {session_id}")
    print(f"First Q    : [{first_question['category']}] {first_question['text']}")
    print(f"Difficulty : {first_question['difficulty']}")
    print(f"Progress   : {first_question['question_number']} / {first_question['total_questions']}")

    assert session_id, "Session ID should not be empty"
    assert "text" in first_question, "First question should have text"

    # ---- Step 2: Answer each question ----
    current_question = first_question
    for i, answer in enumerate(MOCK_ANSWERS):
        separator(f"STEP 2.{i+1}: Submit Answer for Q{i+1}")
        print(f"Question : {current_question['text']}")
        print(f"Answer   : {answer[:80]}...")

        evaluation, next_question = orchestrator.submit_answer(session_id, answer)

        print(f"\nScore      : {evaluation['score']} / 10")
        print(f"Strengths  : {evaluation['strengths']}")
        print(f"Improvement: {evaluation['improvement']}")
        print(f"Ideal pts  : {evaluation.get('ideal_points', [])}")

        assert 1 <= evaluation["score"] <= 10, "Score must be between 1 and 10"
        assert isinstance(evaluation["strengths"], list), "Strengths must be a list"
        assert isinstance(evaluation["improvement"], str), "Improvement must be a string"

        if next_question:
            print(f"\nNext Q : [{next_question['category']}] {next_question['text']}")
            current_question = next_question
        else:
            print("\n(No more questions — session complete)")

    # ---- Step 3: Get report ----
    separator("STEP 3: Final Report")
    report = orchestrator.get_report(session_id)

    print(f"Overall Score      : {report['overall_score']} / 10")
    print(f"Questions Answered : {report['questions_answered']} / {report['questions_total']}")
    print(f"Category Averages  : {json.dumps(report['category_averages'], indent=2)}")
    print(f"Top Strengths      : {report['top_strengths']}")
    print(f"Top Improvements   : {report['top_improvements']}")

    print("\nPer-question breakdown:")
    for row in report["rows"]:
        print(f"  [{row['category']}] Q: {row['question'][:50]}... → Score: {row['score']}/10")

    assert report["overall_score"] > 0, "Overall score should be positive"
    assert report["questions_answered"] == NUM_QUESTIONS, "All questions should be answered"
    assert len(report["rows"]) == NUM_QUESTIONS, "Report rows should match question count"

    print("\n✓ test_full_session passed")


if __name__ == "__main__":
    try:
        test_full_session()
        print("\nAll agent pipeline tests passed.")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
