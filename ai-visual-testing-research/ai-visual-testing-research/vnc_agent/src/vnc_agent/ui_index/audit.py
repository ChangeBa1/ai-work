"""Index-usage audit trail (contracts §7; data-model.md §4.2, FR-013).

`IndexUsageAuditRecord` lives here (not in `domain/run.py`) so that
`domain/run.py` can import it without `ui_index` depending back on
`domain.run` at import time — the only runtime-type dependency on
`ActionIteration` is deferred behind `TYPE_CHECKING`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from vnc_agent.runtime.telemetry import log_event

if TYPE_CHECKING:
    from vnc_agent.domain.run import ActionIteration  # noqa: F401

IndexUsageOutcome = Literal["hit", "no_match", "inconsistent", "not_configured"]
NoMatchReason = Literal["no_screen_matched", "screen_content_inconsistent"]
GrounderOutcome = Literal["not_attempted", "succeeded", "failed"]


class IndexUsageAuditRecord(BaseModel):
    bundle_id: str | None = None
    schema_version: str | None = None
    outcome: IndexUsageOutcome
    matched_screen_id: str | None = None
    hint_element_ids: list[str] = Field(default_factory=list)
    candidate_transition_ids: list[str] = Field(default_factory=list)
    no_match_reason: NoMatchReason | None = None
    grounder_outcome: GrounderOutcome = "not_attempted"


def record_index_usage(iteration: Any, audit: IndexUsageAuditRecord) -> None:
    """Writing `iteration.ui_index_audit` and emitting the structured log
    event are two necessary results of the same call — never one without
    the other (contracts §7)."""
    iteration.ui_index_audit = audit
    log_event("ui_index_usage", **audit.model_dump())
