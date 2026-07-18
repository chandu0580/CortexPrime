"""
Citation Engine — builds formatted citations from ranked research sources.

Produces:
  - In-line citation markers: [1], [2], …
  - Full citation list with title, url, domain, date, snippet
  - Plain-text reference block for LLM prompt injection
  - JSON citation store for frontend rendering
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Citation:
    index:     int
    title:     str
    url:       str
    domain:    str
    snippet:   str
    published: Optional[str]
    score:     float

    @property
    def marker(self) -> str:
        return f"[{self.index}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index":     self.index,
            "marker":    self.marker,
            "title":     self.title,
            "url":       self.url,
            "domain":    self.domain,
            "snippet":   self.snippet[:300],
            "published": self.published,
            "score":     self.score,
        }

    def to_reference_line(self) -> str:
        """One-line APA-ish reference for LLM prompt injection."""
        date_part = f" ({self.published})" if self.published else ""
        return f"[{self.index}] {self.title}{date_part}. {self.url}"


class CitationEngine:
    """
    Builds a citation list from ranked source dicts returned by SourceRanker.

    Usage::

        engine    = CitationEngine()
        citations = engine.build(ranked_sources)
        prompt    = engine.format_for_prompt(citations)
        annotated = engine.annotate_response(text, citations)
    """

    def build(self, ranked_sources: List[Dict[str, Any]]) -> List[Citation]:
        """
        Convert ranked source dicts into Citation objects with 1-based indices.
        """
        citations = []
        for i, src in enumerate(ranked_sources, start=1):
            citations.append(Citation(
                index     = i,
                title     = src.get("title", "Untitled"),
                url       = src.get("url", ""),
                domain    = src.get("domain", ""),
                snippet   = src.get("snippet", ""),
                published = src.get("published"),
                score     = src.get("final_score", src.get("score", 0.0)),
            ))
        return citations

    def format_for_prompt(self, citations: List[Citation]) -> str:
        """
        Format citations as a numbered source block to inject into an LLM prompt.

        Example output::

            [1] OpenAI announces GPT-5 (2025-03-10). https://openai.com/blog/gpt-5
                "GPT-5 is a major step forward..."

        """
        if not citations:
            return "No external sources retrieved."

        lines = ["VERIFIED SOURCES (cite these in your response using [N] markers):"]
        for c in citations:
            lines.append(c.to_reference_line())
            if c.snippet:
                lines.append(f'   "{c.snippet[:200]}"')
        return "\n".join(lines)

    def annotate_response(self, text: str, citations: List[Citation]) -> str:
        """
        Append a References section to the response text.  Does not modify
        existing in-line markers — those are placed by the LLM.
        """
        if not citations:
            return text

        refs = ["\n\n---\n**Sources:**"]
        for c in citations:
            date_part = f" · {c.published}" if c.published else ""
            refs.append(f"{c.marker} [{c.title}]({c.url}){date_part}")
        return text + "\n".join(refs)

    def extract_used_indices(self, text: str) -> List[int]:
        """Return the citation indices actually referenced in the response text."""
        return [int(m) for m in re.findall(r"\[(\d+)\]", text)]

    def filter_used(
        self, text: str, citations: List[Citation]
    ) -> List[Citation]:
        """Return only citations referenced in the text."""
        used = set(self.extract_used_indices(text))
        return [c for c in citations if c.index in used]


citation_engine = CitationEngine()
