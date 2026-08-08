"""The lenses a round is read through.

The runtime asks this context for :func:`required_lenses` and requests one review
per lens, then refuses to call the round reviewed until each has reported
(ADR-020: *a missing lens is not a passing lens*). So the vocabulary here decides
what "reviewed" means, and it lives in this context because Review is what owns
the question.

Why lenses at all, rather than one review
------------------------------------------
One reviewer reading for everything reads for whatever they noticed first. The
failure is not laziness -- it is that correctness and security are different
reading strategies, and a reader holding one is measurably worse at the other.
Splitting them means a security question is asked by someone who was asked
nothing else, and an unasked question is visible as a lens that never reported.

Why performance is not required
--------------------------------
A performance review of a change with no performance-sensitive path produces a
review that says nothing. A lens that is routinely empty teaches its reviewers
that approving without reading is the normal outcome, and that habit does not
stay inside the lens it was learned in. It is requested when the work warrants
it, which makes its presence informative.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from backend.contexts.review.domain.errors import UnknownLens

__all__ = ["ReviewLens", "REQUIRED_LENSES", "coerce_lens", "required_lens_values"]


class ReviewLens(str, Enum):
    """One reading stance. Each asks a question the others do not."""

    CORRECTNESS = "correctness"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    TESTING = "testing"
    PERFORMANCE = "performance"

    @property
    def is_required(self) -> bool:
        return self in REQUIRED_LENSES

    @property
    def mandate(self) -> str:
        """What this lens is answerable for.

        Carried on the enum so a reviewer is told what they were asked, rather
        than inferring it from the lens name. A lens whose mandate lives only in
        a document is a lens whose scope drifts per reviewer.
        """
        return _MANDATES[self]


#: The lenses that must report before a round counts as reviewed. Anything not
#: here is requested deliberately, per WorkOrder.
REQUIRED_LENSES: Final[frozenset] = frozenset(
    {
        ReviewLens.CORRECTNESS,
        ReviewLens.ARCHITECTURE,
        ReviewLens.SECURITY,
        ReviewLens.TESTING,
    }
)


_MANDATES: Final[dict] = {
    ReviewLens.CORRECTNESS: (
        "does the change do what the WorkOrder asked, and does it do it for the "
        "cases the implementer did not think of"
    ),
    ReviewLens.ARCHITECTURE: (
        "does the change respect the boundaries it crosses -- context isolation, "
        "layer direction, and the ADRs it cites"
    ),
    ReviewLens.SECURITY: (
        "what can a caller who is not acting in good faith do with this -- tenancy, "
        "authorisation, injection, and what the change makes reachable"
    ),
    ReviewLens.TESTING: (
        "would these tests fail if the implementation were wrong; a suite that "
        "passes against a broken implementation is worse than none"
    ),
    ReviewLens.PERFORMANCE: (
        "what happens to this at production scale, and what the change costs on "
        "the paths that run most often"
    ),
}


def coerce_lens(value) -> ReviewLens:
    """Turn a string or lens into a lens, refusing anything else.

    Refuses rather than defaulting. A misspelled lens quietly becoming
    ``correctness`` would report a lens as covered that nobody read for.
    """
    if isinstance(value, ReviewLens):
        return value
    try:
        return ReviewLens(value)
    except (ValueError, TypeError) as exc:
        raise UnknownLens(value, [lens.value for lens in ReviewLens]) from exc


def required_lens_values() -> tuple:
    """The required lenses as sorted strings, for the runtime's port."""
    return tuple(sorted(lens.value for lens in REQUIRED_LENSES))
