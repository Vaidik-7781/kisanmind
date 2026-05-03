"""
RAG tool — ChromaDB (local, free) over ICAR agricultural knowledge base.
Semantic search over crop manuals, pesticide guides, subsidy scheme docs.
"""

import os
import chromadb
from chromadb.utils import embedding_functions
from config.settings import CHROMA_PERSIST_DIR, CHROMA_COLLECTION

# Use free sentence-transformers embedding (downloads ~90MB on first run)
_EMBED_MODEL = "all-MiniLM-L6-v2"

_client     = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=_EMBED_MODEL
        )
        _collection = _client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def search_knowledge(query: str, n_results: int = 3, category: str = None) -> list[dict]:
    """
    Search agricultural knowledge base for relevant information.

    Args:
        query:     Natural language query
        n_results: Number of results to return
        category:  Optional filter: 'disease' | 'pesticide' | 'subsidy' | 'crop' | 'soil'

    Returns:
        List of {"text": ..., "source": ..., "score": ...}
    """
    try:
        col = _get_collection()
        count = col.count()
        if count == 0:
            return [{"text": "Knowledge base empty. Run knowledge_base/ingest.py first.", "source": "system", "score": 0}]

        where = {"category": category} if category else None
        results = col.query(
            query_texts=[query],
            n_results=min(n_results, count),
            where=where,
        )

        output = []
        for i, doc in enumerate(results["documents"][0]):
            meta  = results["metadatas"][0][i] if results["metadatas"] else {}
            dist  = results["distances"][0][i] if results["distances"] else 1.0
            score = round(1 - dist, 3)
            output.append({
                "text":     doc,
                "source":   meta.get("source", "ICAR"),
                "category": meta.get("category", "general"),
                "score":    score,
            })
        return output

    except Exception as e:
        return [{"text": f"RAG error: {e}", "source": "error", "score": 0}]


def add_documents(texts: list[str], metadatas: list[dict], ids: list[str]):
    """Add documents to the knowledge base."""
    col = _get_collection()
    col.add(documents=texts, metadatas=metadatas, ids=ids)
    return len(texts)


def get_collection_stats() -> dict:
    col = _get_collection()
    return {"total_documents": col.count(), "collection": CHROMA_COLLECTION}
