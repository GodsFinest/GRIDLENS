"""Unit tests for Hybrid RAG, LSA/SVD dense vector space, and Citation Verifier."""
import pytest
from services.retrieval.corpus_loader import CorpusLoader
from services.retrieval.hybrid_rag import HybridRAGEngine
from services.retrieval.citation_verifier import CitationVerifier
from domain.claims.models import Claim, ClaimType, VerificationStatus


@pytest.mark.asyncio
async def test_hybrid_rag_retrieval():
    chunks = CorpusLoader.load_documents_from_directory("data/documents")
    assert len(chunks) > 0, "Corpus documents must be chunked."

    engine = HybridRAGEngine(chunks)
    res = await engine.retrieve("ANSI 51 time overcurrent protection curve", top_k=2)
    assert len(res.chunks) == 2
    assert any("DOC-PROT-001" in ch.doc_id for ch in res.chunks)
    assert res.retrieval_method == "HYBRID_BM25_DENSE_LSA_RRF"


@pytest.mark.asyncio
async def test_dense_lsa_vector_space():
    chunks = CorpusLoader.load_documents_from_directory("data/documents")
    engine = HybridRAGEngine(chunks)

    assert engine.doc_embeddings.shape[0] == len(chunks)
    assert engine.doc_embeddings.shape[1] > 0
    assert engine.projection_matrix.shape[0] == len(engine.vocab)

    # Pure dense vector search (lexical disabled)
    res_dense = await engine.retrieve("high voltage electrical substation fault isolation", top_k=3, use_dense=True, use_lexical=False)
    assert len(res_dense.chunks) > 0
    assert any("DOC-PROT-001" in ch.doc_id or "DOC-SUB-002" in ch.doc_id for ch in res_dense.chunks)


def test_citation_verifier_valid_and_invalid():
    chunks = CorpusLoader.load_documents_from_directory("data/documents")
    import re
    source = next(c for c in chunks if c.doc_id == "DOC-PROT-001")

    valid_claim = Claim(
        claim_id="C01",
        statement=re.split(r'(?<=[.!?])\s+|\n+', source.content.strip())[0],
        claim_type=ClaimType.FACT,
        evidence_ids=["DOC-PROT-001"],
    )
    status, note = CitationVerifier.verify_document_claim(valid_claim, chunks)
    assert status == VerificationStatus.VERIFIED

    fake_claim = Claim(
        claim_id="C02",
        statement="Transformer T1 generates free solar energy without loss.",
        claim_type=ClaimType.FACT,
        evidence_ids=["DOC-PROT-001"],
    )
    fake_status, fake_note = CitationVerifier.verify_document_claim(fake_claim, chunks)
    assert fake_status == VerificationStatus.REJECTED
