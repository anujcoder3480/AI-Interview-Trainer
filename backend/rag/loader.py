"""
RAG Knowledge Base Loader
Reads all four JSON knowledge base files, embeds each chunk using
sentence-transformers, and stores them in a ChromaDB in-memory collection.

Called once at FastAPI startup via get_collection().
"""

import json
import os
import chromadb
from chromadb.utils import embedding_functions

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_KB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")
_KB_FILES = ["technical.json", "behavioral.json", "hr.json", "roles.json"]

# ---------------------------------------------------------------------------
# Singleton collection — built once, reused by all agent calls
# ---------------------------------------------------------------------------
_collection = None


def get_collection() -> chromadb.Collection:
    """
    Return the ChromaDB collection, initialising it on first call.
    Subsequent calls return the cached collection instantly.
    """
    global _collection
    if _collection is not None:
        return _collection

    # Built here, not at module scope — avoids blocking the Python import
    # for ~24 s while torch/transformers/sentence_transformers load.
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.Client()  # in-memory, no persistence needed

    # Use get_or_create so re-imports don't raise a duplicate error
    _collection = client.get_or_create_collection(
        name="interview_kb",
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    _load_knowledge_base(_collection)
    return _collection


def _load_knowledge_base(collection: chromadb.Collection) -> None:
    """Read all KB JSON files and upsert chunks into the collection."""
    ids, documents, metadatas = [], [], []

    for filename in _KB_FILES:
        filepath = os.path.join(_KB_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            entries = json.load(f)

        for entry in entries:
            ids.append(entry["id"])
            documents.append(entry["content"])
            metadatas.append({
                "category": entry["category"],
                "topic": entry["topic"],
                "source_file": filename,
            })

    # Upsert (insert or update) — safe to call multiple times
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"[RAG] Loaded {len(ids)} chunks into ChromaDB.")
