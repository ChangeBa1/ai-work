"""Non-idempotent action kind classification (research.md §3, FR-013).

Feature 003 T050 (/speckit-converge, Constitution v1.1.0 Principle VI):
removed the `_DEFAULT_NON_IDEMPOTENT_KEYWORDS` business-vocabulary keyword
table. It was already dead code with respect to the function's return value
— both the "keyword matched" branch and the "no keyword matched" fallback
returned the same conservative `"non_idempotent"` result (see
test_action_kind_classification.py's own pre-existing tautological
assertions), so removing it changes no behavior. The conservative fail-safe
default (research.md §3: uncertain classification MUST NOT default to
"idempotent") is now expressed directly, with no keyword list — and
therefore no business vocabulary — involved at all.
"""

from __future__ import annotations

from typing import Literal

from vnc_agent.domain.action import SemanticAction

ActionKind = Literal["idempotent", "non_idempotent"]


def classify_action_kind(action: SemanticAction | str) -> ActionKind:
    """
    Return action_kind for a SemanticAction (or raw intent string).

    Priority:
    1. Explicit ``SemanticAction.action_kind`` if set
    2. Conservative fallback: ``non_idempotent`` (research.md §3 — an
       action whose idempotency is not explicitly declared MUST be treated
       as non_idempotent, never assumed safe to repeat)
    """
    if isinstance(action, SemanticAction) and action.action_kind in (
        "idempotent",
        "non_idempotent",
    ):
        return action.action_kind
    return "non_idempotent"
