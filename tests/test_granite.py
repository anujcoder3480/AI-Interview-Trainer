"""
Test: IBM Granite LLM Client
Run from the project root:
    python tests/test_granite.py

Requires a valid .env file with WATSONX_API_KEY and WATSONX_PROJECT_ID.
"""

import sys
import os

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm.granite_client import generate

def test_basic_generation():
    prompt = (
        "You are a helpful assistant.\n\n"
        "Question: What is the time complexity of binary search?\n"
        "Answer:"
    )
    print("Sending prompt to IBM Granite (ibm/granite-3-8b-instruct)...")
    print(f"Prompt:\n{prompt}\n")

    result = generate(prompt, max_new_tokens=128, temperature=0.5)

    print(f"Response:\n{result}\n")
    assert isinstance(result, str) and len(result) > 0, "Response should be a non-empty string"
    print("✓ test_basic_generation passed")


if __name__ == "__main__":
    try:
        test_basic_generation()
        print("\nAll Granite tests passed.")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
