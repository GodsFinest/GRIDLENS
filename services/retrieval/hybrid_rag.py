"""Hybrid RAG retrieval engine combining BM25 lexical search, LSA dense vector embeddings, and RRF ranking."""
import re
import math
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from rank_bm25 import BM25Okapi
from domain.models.results import DocumentRetrievalResult, RetrievedDocumentChunk


class HybridRAGEngine:
    """Lightweight hybrid retrieval engine combining BM25 with LSA/SVD dense vectors."""

    def __init__(self, chunks: Optional[List[RetrievedDocumentChunk]] = None):
        self.chunks = chunks or []
        self.bm25: Optional[BM25Okapi] = None
        self.vocab: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([])
        self.doc_embeddings: np.ndarray = np.array([])
        self.projection_matrix: np.ndarray = np.array([])
        self.latent_dim: int = 16
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        if not self.chunks:
            return

        # 1. Tokenize corpus preserving power engineering terms (e.g. 50P, 51N, OGS-01)
        tokenized_corpus = [
            self._tokenize(chunk.content + " " + chunk.title + " " + chunk.section)
            for chunk in self.chunks
        ]

        # Initialize BM25 lexical retriever
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 2. Build Vocabulary and TF-IDF for Latent Semantic Analysis (LSA) dense vectors
        vocab_set = set()
        for doc_tokens in tokenized_corpus:
            vocab_set.update(doc_tokens)

        self.vocab = {term: idx for idx, term in enumerate(sorted(vocab_set))}
        vocab_size = len(self.vocab)
        num_docs = len(self.chunks)

        if vocab_size == 0 or num_docs == 0:
            return

        # Document frequencies
        df = np.zeros(vocab_size)
        for doc_tokens in tokenized_corpus:
            for term in set(doc_tokens):
                if term in self.vocab:
                    df[self.vocab[term]] += 1

        # Smooth IDF calculation: ln((1 + N) / (1 + df)) + 1
        self.idf = np.log((1.0 + num_docs) / (1.0 + df)) + 1.0

        # Term-document TF-IDF matrix: shape (num_docs, vocab_size)
        tfidf_matrix = np.zeros((num_docs, vocab_size), dtype=np.float64)
        for doc_idx, doc_tokens in enumerate(tokenized_corpus):
            if not doc_tokens:
                continue
            doc_len = len(doc_tokens)
            term_counts: Dict[int, int] = {}
            for t in doc_tokens:
                t_id = self.vocab[t]
                term_counts[t_id] = term_counts.get(t_id, 0) + 1
            for t_id, cnt in term_counts.items():
                tf = cnt / doc_len
                tfidf_matrix[doc_idx, t_id] = tf * self.idf[t_id]

        # L2-normalize TF-IDF rows
        row_norms = np.linalg.norm(tfidf_matrix, axis=1, keepdims=True)
        row_norms[row_norms == 0] = 1.0
        tfidf_normalized = tfidf_matrix / row_norms

        # Compute Singular Value Decomposition (SVD) for low-rank semantic projection: X = U * S * V^T
        k = min(self.latent_dim, num_docs, vocab_size - 1) if vocab_size > 1 else 1
        k = max(k, 1)

        try:
            u, s, vt = np.linalg.svd(tfidf_normalized, full_matrices=False)
            # Dense document embeddings in latent space: shape (num_docs, k)
            dense_docs = u[:, :k] * s[:k]
            # Projection matrix to map queries into the same k-dimensional space: shape (vocab_size, k)
            self.projection_matrix = vt[:k, :].T
        except Exception:
            # Fallback to PCA-style covariance projection
            dense_docs = tfidf_normalized[:, :k]
            self.projection_matrix = np.eye(vocab_size, k)

        # L2-normalize dense document vectors
        dense_norms = np.linalg.norm(dense_docs, axis=1, keepdims=True)
        dense_norms[dense_norms == 0] = 1.0
        self.doc_embeddings = dense_docs / dense_norms

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", " ", text.lower())
        return [tok.strip() for tok in cleaned.split() if len(tok.strip()) > 1]

    def _encode_query_dense(self, query_tokens: List[str]) -> np.ndarray:
        """Projects a tokenized query into the k-dimensional latent semantic vector space."""
        if not self.vocab or self.projection_matrix.size == 0:
            return np.array([])

        q_vec = np.zeros(len(self.vocab), dtype=np.float64)
        if not query_tokens:
            return q_vec

        q_len = len(query_tokens)
        for t in query_tokens:
            if t in self.vocab:
                q_vec[self.vocab[t]] += 1.0 / q_len

        # Weight by corpus IDF
        q_tfidf = q_vec * self.idf
        norm = np.linalg.norm(q_tfidf)
        if norm > 0:
            q_tfidf /= norm

        # Project into latent semantic space: (1, vocab_size) @ (vocab_size, k) -> (k,)
        q_dense = q_tfidf @ self.projection_matrix
        dense_norm = np.linalg.norm(q_dense)
        if dense_norm > 0:
            q_dense /= dense_norm
        return q_dense

    async def retrieve(
        self,
        query: str,
        top_k: int = 4,
        category_filter: Optional[str] = None,
        use_dense: bool = True,
        use_lexical: bool = True,
    ) -> DocumentRetrievalResult:
        if not self.chunks:
            return DocumentRetrievalResult(query=query, chunks=[], total_chunks_found=0)

        tokens = self._tokenize(query)

        # 1. Lexical retrieval (BM25)
        bm25_ranks: Dict[str, int] = {}
        if use_lexical and self.bm25:
            scores = self.bm25.get_scores(tokens)
            sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            for rank, idx in enumerate(sorted_indices):
                bm25_ranks[self.chunks[idx].chunk_id] = rank + 1

        # 2. Dense Semantic Vector Retrieval (Cosine Similarity in LSA/SVD Latent Space)
        dense_ranks: Dict[str, int] = {}
        if use_dense and self.doc_embeddings.size > 0:
            q_dense = self._encode_query_dense(tokens)
            if q_dense.size > 0:
                # Dot product of unit vectors equals cosine similarity
                cosine_similarities = self.doc_embeddings @ q_dense
                sorted_dense_indices = sorted(
                    range(len(cosine_similarities)),
                    key=lambda i: cosine_similarities[i],
                    reverse=True,
                )
                for rank, idx in enumerate(sorted_dense_indices):
                    dense_ranks[self.chunks[idx].chunk_id] = rank + 1

        # 3. Reciprocal Rank Fusion (RRF with k=60)
        rrf_k = 60
        fused_scores: Dict[str, float] = {}
        for ch in self.chunks:
            c_id = ch.chunk_id
            score = 0.0
            if c_id in bm25_ranks:
                score += 1.0 / (rrf_k + bm25_ranks[c_id])
            if c_id in dense_ranks:
                score += 1.0 / (rrf_k + dense_ranks[c_id])
            fused_scores[c_id] = score

        # Sort by fused score descending
        sorted_chunks = sorted(self.chunks, key=lambda c: fused_scores.get(c.chunk_id, 0.0), reverse=True)

        result_chunks: List[RetrievedDocumentChunk] = []
        for ch in sorted_chunks[:top_k]:
            cloned = ch.model_copy() if hasattr(ch, "model_copy") else ch.copy(deep=True)
            cloned.score = round(fused_scores.get(ch.chunk_id, 0.0) * 100.0, 3)
            cloned.relevance_reason = f"Ranked via Hybrid BM25 + LSA/SVD Dense Vector RRF (Score: {cloned.score})"
            result_chunks.append(cloned)

        return DocumentRetrievalResult(
            query=query,
            retrieval_method="HYBRID_BM25_DENSE_LSA_RRF",
            chunks=result_chunks,
            total_chunks_found=len(result_chunks),
        )
