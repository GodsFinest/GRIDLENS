"""Vector-store boundary with a deterministic local implementation.

The interface is intentionally small so pgvector, a managed vector service,
or an offline index can be substituted without changing the investigation
pipeline.
"""
from abc import ABC, abstractmethod
from typing import Iterable, List
from domain.models.results import RetrievedDocumentChunk
from services.retrieval.hybrid_rag import HybridRAGEngine


class VectorStore(ABC):
    @abstractmethod
    async def similarity_search(self, query: str, top_k: int = 4) -> List[RetrievedDocumentChunk]:
        raise NotImplementedError


class LocalVectorStore(VectorStore):
    """Local retrieval adapter used by the application and CI."""

    def __init__(self, chunks: Iterable[RetrievedDocumentChunk]):
        self.engine = HybridRAGEngine(list(chunks))

    async def similarity_search(self, query: str, top_k: int = 4) -> List[RetrievedDocumentChunk]:
        result = await self.engine.retrieve(query=query, top_k=top_k)
        return result.chunks
