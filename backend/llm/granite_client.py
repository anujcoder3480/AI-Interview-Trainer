"""
IBM Granite LLM Client
Wraps the watsonx.ai text generation REST API.

Usage:
    from backend.llm.granite_client import generate
    response = generate("Your prompt here")
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration (read once at import time)
# ---------------------------------------------------------------------------
_API_KEY = os.getenv("WATSONX_API_KEY", "")
_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
_BASE_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

_MODEL_ID = "ibm/granite-4-h-small"
_IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
_GENERATE_URL = f"{_BASE_URL}/ml/v1/text/generation?version=2023-05-29"

# ---------------------------------------------------------------------------
# IAM token helper (fetched fresh each call — simple and reliable)
# ---------------------------------------------------------------------------

def _get_iam_token() -> str:
    """Exchange the API key for a short-lived IAM Bearer token."""
    if not _API_KEY:
        raise ValueError(
            "WATSONX_API_KEY is not set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    resp = requests.post(
        _IAM_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": _API_KEY,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"IAM token request failed ({resp.status_code}): {resp.text}"
        )
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate(prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
    """
    Send a prompt to IBM Granite and return the generated text.

    Args:
        prompt:         The full prompt string (system + user content).
        max_new_tokens: Maximum tokens to generate (default 512).
        temperature:    Sampling temperature 0.0–1.0 (default 0.7).

    Returns:
        The generated text as a plain string.

    Raises:
        ValueError:  If credentials are missing.
        RuntimeError: If the API call fails.
    """
    if not _PROJECT_ID:
        raise ValueError(
            "WATSONX_PROJECT_ID is not set. "
            "Copy .env.example to .env and fill in your credentials."
        )

    token = _get_iam_token()

    payload = {
        "model_id": _MODEL_ID,
        "input": prompt,
        "parameters": {
            "decoding_method": "sample",
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "repetition_penalty": 1.1,
        },
        "project_id": _PROJECT_ID,
    }

    resp = requests.post(
        _GENERATE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Granite API call failed ({resp.status_code}): {resp.text}"
        )

    data = resp.json()
    # Response structure: {"results": [{"generated_text": "..."}]}
    try:
        return data["results"][0]["generated_text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"Unexpected Granite response format: {data}"
        ) from exc
