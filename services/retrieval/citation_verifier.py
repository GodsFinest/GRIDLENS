"""Verify exact source quotations, not textual overlap or source truth."""
import re
from domain.claims.models import VerificationStatus as V


class CitationVerifier:
    @classmethod
    def verify_document_claim(cls, claim, retrieved_chunks):
        if not claim.evidence_ids:
            return V.REJECTED, "No source citation."
        matches = [ch for ch in retrieved_chunks if any(
            eid in {ch.doc_id, ch.chunk_id, "EV_DOC_" + ch.chunk_id} for eid in claim.evidence_ids)]
        for chunk in matches:
            sentences = re.split(r'(?<=[.!?])\s+|\n+', chunk.content.strip())
            if claim.statement and claim.statement in sentences:
                return V.VERIFIED, f"Exact source quotation from {chunk.doc_id}; source truth is not certified."
        return V.REJECTED, "An exact complete sentence and exact retrieved source ID are required."
