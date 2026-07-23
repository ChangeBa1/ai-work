"""Bounded per-component analysis result cache (data-model.md §5-6,
perception-cache-contract.md).

Lookup is gated on the *current* ScreenFrame: only a strictly-adjacent
exact duplicate is eligible (`deduplicated=true` and `duplicate_of_frame_id`
is the direct predecessor), and only when the cached entry's
`source_frame_id` matches that predecessor. A→B→A never hits because A's
second occurrence is not adjacent to its own first occurrence —
`FrameCaptureService`'s own dedup decision already enforces strict
adjacency; this cache key additionally re-derives content/scope/config
identity so an eligible-looking duplicate whose analysis configuration
changed still misses.

Entries never hold raw pixels, PNG bytes, evidence paths, or a full
StructuredScreen — only pure per-component results.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

Component = Literal["ocr", "template", "diff", "vision_describe"]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@dataclass(frozen=True)
class AnalysisCacheKey:
    component: Component
    algorithm_revision: str
    content_hash: str
    scope_identity: str
    pixel_format: str
    mask_identity: str
    perception_config_fingerprint: str
    component_identity: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        payload = {
            "component": self.component,
            "algorithm_revision": self.algorithm_revision,
            "content_hash": self.content_hash,
            "scope_identity": self.scope_identity,
            "pixel_format": self.pixel_format,
            "mask_identity": self.mask_identity,
            "perception_config_fingerprint": self.perception_config_fingerprint,
            "component_identity": self.component_identity,
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass
class AnalysisCacheEntry:
    key: AnalysisCacheKey
    result: Any
    source_frame_id: str
    created_sequence: int
    referencing_sequences: deque[int]
    actual_invocation_id: str


class AnalysisResultCache:
    """Per-run/session bounded cache; `perception.cache_max_frames` (3..5)."""

    def __init__(self, *, max_frames: int = 5) -> None:
        if not (3 <= max_frames <= 5):
            raise ValueError("cache_max_frames must be within 3..5")
        self.max_frames = max_frames
        self._entries: dict[str, AnalysisCacheEntry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        """Run/session reset, disconnect, close: drop everything."""
        self._entries.clear()

    def lookup(
        self,
        key: AnalysisCacheKey,
        *,
        frame_deduplicated: bool,
        duplicate_of_frame_id: str | None,
        current_sequence: int,
    ) -> AnalysisCacheEntry | None:
        """`frame_deduplicated`/`duplicate_of_frame_id` are the eligibility
        gate: only a `ScreenFrame` that `FrameCaptureService` has already
        rigorously proven pixel-identical to its direct predecessor may look
        up at all. The entry's `source_frame_id` is audit metadata (which
        frame actually ran the analysis) — it is intentionally NOT compared
        against `duplicate_of_frame_id`: for a chain of N consecutive
        duplicates, frame 3's predecessor is frame 2, not the original
        source, yet all N share one identical-pixel key and must reuse the
        same entry (perception-cache-contract.md "10 个连续 duplicate")."""
        if not frame_deduplicated or duplicate_of_frame_id is None:
            return None
        fp = key.fingerprint()
        entry = self._entries.get(fp)
        if entry is None:
            return None
        if current_sequence - entry.referencing_sequences[-1] >= self.max_frames:
            # Stale before this lookup could extend it — evict, don't hit.
            del self._entries[fp]
            return None
        entry.referencing_sequences.append(current_sequence)
        return entry

    def store(
        self,
        key: AnalysisCacheKey,
        result: Any,
        *,
        source_frame_id: str,
        sequence: int,
        invocation_id: str,
    ) -> None:
        self._entries[key.fingerprint()] = AnalysisCacheEntry(
            key=key,
            result=result,
            source_frame_id=source_frame_id,
            created_sequence=sequence,
            referencing_sequences=deque([sequence], maxlen=self.max_frames),
            actual_invocation_id=invocation_id,
        )
        self._prune(sequence)

    def _prune(self, current_sequence: int) -> None:
        stale = [
            fp
            for fp, entry in self._entries.items()
            if current_sequence - entry.referencing_sequences[-1] >= self.max_frames
        ]
        for fp in stale:
            del self._entries[fp]
