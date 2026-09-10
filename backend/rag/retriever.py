"""
RAG Retriever
Provides a single search() function that agents call to get relevant
context chunks before building their LLM prompts.
"""

from typing import Optional
from backend.rag.loader import get_collection


def search(query: str, k: int = 5, category: Optional[str] = None) -> list[str]:
    """
    Perform a semantic similarity search over the knowledge base.

    Args:
        query:    The search string (e.g. "Python data structures interview questions").
        k:        Number of top results to return (default 5).
        category: Optional filter — "technical", "behavioral", "hr", "role-specific".
                  If None, searches across all categories.

    Returns:
        A list of up to k content strings, most relevant first.
    """
    collection = get_collection()

    where_filter = {"category": category} if category else None

    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    # results["documents"] is a list-of-lists (one per query_text)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    # Prefix each chunk with its topic for richer LLM context
    enriched = []
    for doc, meta in zip(documents, metadatas):
        enriched.append(f"[{meta['category']} / {meta['topic']}]\n{doc}")

    return enriched


def search_multi(queries: list[str], k: int = 3) -> list[str]:
    """
    Run multiple queries and return a deduplicated, merged result list.
    Useful when an agent wants to retrieve context for several aspects at once.

    Args:
        queries: List of query strings.
        k:       Results per query before deduplication.

    Returns:
        Deduplicated list of content strings.
    """
    seen = set()
    combined = []
    for query in queries:
        for chunk in search(query, k=k):
            if chunk not in seen:
                seen.add(chunk)
                combined.append(chunk)
    return combined
