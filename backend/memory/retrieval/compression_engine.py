"""
Context Compression Engine.

Trims retrieved memory context to a token budget by progressively
removing lower-priority entries.  When the OpenAI API is available,
a summarisation pass can further reduce large blobs.
"""
from __future__ import annotations

import logging
import os
from typing import List, Tuple

from backend.memory.models import EpisodicEntry, SemanticEntry

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN    = 4      # rough approximation
DEFAULT_MAX_TOKENS = 4096   # default context budget


class CompressionEngine:
    """
    Two-stage context compression:

    Stage 1 — Trim: remove lowest-priority entries until within budget.
    Stage 2 — Summarise (optional): call GPT-4o-mini to condense large
              individual entries.
    """

    async def compress_context(
        self,
        episodic:   List[EpisodicEntry],
        semantic:   List[SemanticEntry],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Tuple[List[EpisodicEntry], List[SemanticEntry], bool]:
        """
        Trim the combined context to fit within *max_tokens*.

        Returns (episodic, semantic, was_compressed).
        Removes entries from the *end* of each list (lowest relevance last).
        """
        if self._token_count(episodic, semantic) <= max_tokens:
            return episodic, semantic, False

        ep = list(episodic)
        sm = list(semantic)

        while self._token_count(ep, sm) > max_tokens:
            if ep and len(ep) >= len(sm):
                ep.pop()
            elif sm:
                sm.pop()
            elif ep:
                ep.pop()
            else:
                break

        return ep, sm, True

    async def summarize(
        self,
        text:       str,
        max_tokens: int = 300,
    ) -> str:
        """
        Summarise *text* to at most *max_tokens* tokens.
        Uses LLM when available; otherwise truncates.
        """
        char_limit = max_tokens * CHARS_PER_TOKEN
        if len(text) <= char_limit:
            return text

        if os.getenv("OPENAI_API_KEY"):
            summarised = await self._llm_summarize(text, max_tokens)
            if summarised:
                return summarised

        # Plain truncation fallback
        return text[:char_limit].rstrip() + " […]"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _llm_summarize(self, text: str, max_tokens: int) -> str:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            resp   = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role":    "system",
                        "content": (
                            "Summarise the following memory entries into a "
                            "concise paragraph. Preserve key facts and agent names."
                        ),
                    },
                    {
                        "role":    "user",
                        "content": text[:6000],
                    },
                ],
                max_tokens=max_tokens,
                temperature=0,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(f"LLM summarisation failed: {exc}")
            return ""

    @staticmethod
    def _token_count(
        episodic: List[EpisodicEntry],
        semantic: List[SemanticEntry],
    ) -> int:
        total_chars = sum(len(e.content) for e in episodic)
        total_chars += sum(len(s.content) for s in semantic)
        return total_chars // CHARS_PER_TOKEN


compression_engine = CompressionEngine()
