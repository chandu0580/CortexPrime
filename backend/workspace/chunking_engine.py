"""
Chunking Engine — splits extracted page content into overlapping chunks
suitable for embedding and retrieval.

Strategy:
  • Target ~400 tokens per chunk (≈ 1600 chars)
  • 20 % overlap between consecutive chunks
  • Preserve sentence boundaries (split on ". " / "\\n")
  • Each chunk records its source page number and character offsets
"""
from __future__ import annotations

import re
from typing import List

from backend.workspace.document_processor import PageContent
from backend.workspace.models import DocumentChunk

_CHUNK_SIZE    = 1600   # characters
_OVERLAP       = 320    # characters (20 % of chunk size)
_SENTENCE_SEPS = re.compile(r"(?<=[.!?])\s+|(?<=\n)\n+")


def _split_sentences(text: str) -> List[str]:
    """Split text into sentence-like segments."""
    parts = _SENTENCE_SEPS.split(text)
    return [p.strip() for p in parts if p.strip()]


def chunk_pages(
    pages:        List[PageContent],
    document_id:  str,
    workspace_id: str,
) -> List[DocumentChunk]:
    """
    Convert page-level content into overlapping DocumentChunk objects.
    Returns the list ordered by page, then chunk_index.
    """
    chunks:      List[DocumentChunk] = []
    chunk_index: int                 = 0

    for page in pages:
        segments = _split_sentences(page.text)
        buffer   = ""
        buf_start_char = 0
        global_char_offset = 0

        for seg in segments:
            # Append segment to buffer
            if buffer:
                buffer += " " + seg
            else:
                buffer    = seg
                buf_start_char = global_char_offset

            global_char_offset += len(seg) + 1

            if len(buffer) >= _CHUNK_SIZE:
                chunks.append(DocumentChunk(
                    document_id  = document_id,
                    workspace_id = workspace_id,
                    chunk_index  = chunk_index,
                    content      = buffer[:_CHUNK_SIZE],
                    page_number  = page.page_number,
                    char_start   = buf_start_char,
                    char_end     = buf_start_char + _CHUNK_SIZE,
                    metadata     = {**page.metadata, "page": page.page_number},
                ))
                chunk_index += 1
                # Keep overlap: retain last _OVERLAP chars as new buffer start
                overlap_text = buffer[-_OVERLAP:]
                buffer       = overlap_text
                buf_start_char = global_char_offset - len(overlap_text)

        # Flush remaining buffer for this page
        if buffer.strip():
            chunks.append(DocumentChunk(
                document_id  = document_id,
                workspace_id = workspace_id,
                chunk_index  = chunk_index,
                content      = buffer,
                page_number  = page.page_number,
                char_start   = buf_start_char,
                char_end     = buf_start_char + len(buffer),
                metadata     = {**page.metadata, "page": page.page_number},
            ))
            chunk_index += 1

    return chunks
