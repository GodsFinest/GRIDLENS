"""Corpus loader and chunking engine for technical engineering documents."""
import os
import glob
from typing import List
from domain.models.results import RetrievedDocumentChunk
from services.config import DOCUMENTS_DIR


class CorpusLoader:
    """Loads and chunks technical engineering documents with section-level granularity."""

    @classmethod
    def load_documents_from_directory(cls, docs_dir: str = str(DOCUMENTS_DIR)) -> List[RetrievedDocumentChunk]:
        chunks: List[RetrievedDocumentChunk] = []
        if not os.path.exists(docs_dir):
            return chunks

        md_files = glob.glob(os.path.join(docs_dir, "*.md"))
        for file_path in sorted(md_files):
            doc_id = os.path.basename(file_path).replace(".md", "")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            doc_chunks = cls.chunk_document(doc_id, content)
            chunks.extend(doc_chunks)
        return chunks

    @classmethod
    def chunk_document(cls, doc_id: str, content: str) -> List[RetrievedDocumentChunk]:
        chunks: List[RetrievedDocumentChunk] = []
        lines = content.splitlines()

        doc_title = lines[0].lstrip("# ").strip() if lines else doc_id
        current_section = "General"
        current_lines: List[str] = []
        chunk_idx = 1

        for line in lines[1:]:
            if line.startswith("## "):
                # Save previous chunk
                if current_lines:
                    chunk_text = "\n".join(current_lines).strip()
                    if chunk_text:
                        chunks.append(RetrievedDocumentChunk(
                            doc_id=doc_id,
                            title=doc_title,
                            section=current_section,
                            chunk_id=f"{doc_id}_chk_{chunk_idx:02d}",
                            content=chunk_text,
                            score=0.0,
                        ))
                        chunk_idx += 1
                    current_lines = []
                current_section = line.lstrip("# ").strip()
            else:
                current_lines.append(line)

        # Append final chunk
        if current_lines:
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                chunks.append(RetrievedDocumentChunk(
                    doc_id=doc_id,
                    title=doc_title,
                    section=current_section,
                    chunk_id=f"{doc_id}_chk_{chunk_idx:02d}",
                    content=chunk_text,
                    score=0.0,
                ))
        return chunks
