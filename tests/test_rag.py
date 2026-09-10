"""
Test: RAG Knowledge Base Loader and Retriever
Run from the project root:
    python tests/test_rag.py

No .env or API keys required — this test is purely local.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag.retriever import search, search_multi


def test_load_and_basic_search():
    print("Initialising ChromaDB and loading knowledge base...")
    results = search("binary search time complexity", k=3)
    assert len(results) > 0, "Should return at least one result"
    print(f"\n--- Query: 'binary search time complexity' (top {len(results)}) ---")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r[:200]}...")
    print("\n✓ test_load_and_basic_search passed")


def test_behavioral_search():
    results = search("tell me about a time you led a team", k=3, category="behavioral")
    assert len(results) > 0, "Should return behavioral results"
    print(f"\n--- Query: behavioral leadership (top {len(results)}) ---")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r[:200]}...")
    print("\n✓ test_behavioral_search passed")


def test_hr_search():
    results = search("salary expectations negotiation", k=3, category="hr")
    assert len(results) > 0, "Should return HR results"
    print(f"\n--- Query: HR salary (top {len(results)}) ---")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r[:200]}...")
    print("\n✓ test_hr_search passed")


def test_role_specific_search():
    results = search("data scientist machine learning interview", k=3)
    assert len(results) > 0, "Should return role-specific results"
    print(f"\n--- Query: 'data scientist machine learning interview' (top {len(results)}) ---")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r[:200]}...")
    print("\n✓ test_role_specific_search passed")


def test_search_multi():
    results = search_multi(
        ["Python skills interview", "OOP design patterns"],
        k=2,
    )
    assert len(results) > 0, "search_multi should return results"
    print(f"\n--- search_multi: Python + OOP ({len(results)} deduplicated chunks) ---")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r[:200]}...")
    print("\n✓ test_search_multi passed")


if __name__ == "__main__":
    try:
        test_load_and_basic_search()
        test_behavioral_search()
        test_hr_search()
        test_role_specific_search()
        test_search_multi()
        print("\nAll RAG tests passed.")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
