"""RetrievalTool executing hybrid document retrieval with citation tracking."""
from typing import Optional, List
from domain.models.results import DocumentRetrievalResult
from services.retrieval.hybrid_rag import HybridRAGEngine
from services.retrieval.corpus_loader import CorpusLoader
from services.config import DOCUMENTS_DIR


class RetrievalTool:
    """Specialized tool for hybrid document retrieval with citation tracking."""

    def __init__(self, docs_dir: str = str(DOCUMENTS_DIR), engine: Optional[HybridRAGEngine] = None):
        if engine:
            self.engine = engine
        else:
            chunks = CorpusLoader.load_documents_from_directory(docs_dir)
            self.engine = HybridRAGEngine(chunks)

    async def execute(self, query: str, top_k: int = 3) -> DocumentRetrievalResult:
        result = await self.engine.retrieve(query=query, top_k=top_k)
        return result
