"""Tests for the replaceable vector retrieval boundary."""
import pytest
from services.retrieval.corpus_loader import CorpusLoader
from services.retrieval.vector_store import LocalVectorStore


@pytest.mark.asyncio
async def test_local_vector_store_returns_ranked_chunks():
    chunks = CorpusLoader.load_documents_from_directory()
    store = LocalVectorStore(chunks)

    results = await store.similarity_search("ANSI 51 time overcurrent protection", top_k=2)

    assert len(results) == 2
    assert all(result.relevance_reason for result in results)
    assert results[0].score >= results[1].score
