"""Runtime bridge from a loaded bundle to Planner hints / Grounder candidates
(contracts §6; research.md §9; FR-007/008/009/010/011/014).

`build_hints()` never touches `ExecutableAction`/the VNC driver — it only
produces hint/candidate *proposals*; coordinate resolution and action
execution stay entirely in the existing Grounder/Action-Policy code paths.
"""

from __future__ import annotations

from typing import Any

from vnc_agent.config import UiIndexConfig
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.ui_index.audit import IndexUsageAuditRecord
from vnc_agent.ui_index.repository import UiIndexBundle, normalize_text
from vnc_agent.ui_index.sanitizer import VisibleElementHint, to_visible_hint


def _screen_text_universe(bundle: UiIndexBundle, screen_id: str) -> set[str]:
    screen = bundle.screens[screen_id]
    texts = {normalize_text(t) for t in (*screen.visible_titles, *screen.aliases)}
    for element_id in bundle.screen_elements_index.get(screen_id, []):
        element = bundle.elements[element_id]
        texts.update(normalize_text(t) for t in (*element.visible_texts, *element.aliases))
    texts.discard("")
    return texts


def _match_screen(
    bundle: UiIndexBundle,
    ocr_texts: set[str],
    min_score: float,
) -> tuple[str | None, float]:
    best_screen_id: str | None = None
    best_score = -1.0
    for screen_id in sorted(bundle.screens):
        universe = _screen_text_universe(bundle, screen_id)
        if not universe:
            continue
        score = len(universe & ocr_texts) / len(universe)
        if score > best_score:
            best_score = score
            best_screen_id = screen_id
    if best_screen_id is None or best_score < min_score:
        return None, best_score
    return best_screen_id, best_score


def _missing_ratio(bundle: UiIndexBundle, screen_id: str, ocr_texts: set[str]) -> float:
    checked = 0
    missing = 0
    for element_id in bundle.screen_elements_index.get(screen_id, []):
        element = bundle.elements[element_id]
        if element.confidence.level not in ("confirmed", "visually_confirmed"):
            continue
        texts = {normalize_text(t) for t in (*element.visible_texts, *element.aliases)}
        texts.discard("")
        if not texts:
            continue
        checked += 1
        if not (texts & ocr_texts):
            missing += 1
    return (missing / checked) if checked else 0.0


def _element_to_candidate(element: Any) -> dict[str, Any] | None:
    bounds = element.normalized_bounds
    if bounds is None:
        return None
    return {
        "bbox": [bounds.x1, bounds.y1, bounds.x2, bounds.y2],
        "coordinate_space": "normalized_1000",
        "confidence": element.confidence.score if element.confidence.score is not None else 0.5,
        "label": element.name,
        "reason": ", ".join(element.visible_texts) or element.role,
        "source": "ui_index",
    }


def build_hints(
    bundle: UiIndexBundle | None,
    current_screen: StructuredScreen,
    config: UiIndexConfig,
) -> tuple[list[VisibleElementHint], list[dict[str, Any]], IndexUsageAuditRecord]:
    if bundle is None:
        return [], [], IndexUsageAuditRecord(outcome="not_configured")

    ocr_texts = {
        normalize_text(item.text) for item in current_screen.ocr_items if item.text.strip()
    }

    matched_screen_id, _score = _match_screen(bundle, ocr_texts, config.screen_match_min_score)
    if matched_screen_id is None:
        return (
            [],
            [],
            IndexUsageAuditRecord(
                bundle_id=bundle.manifest.bundle_id,
                schema_version=bundle.manifest.schema_version,
                outcome="no_match",
                no_match_reason="no_screen_matched",
            ),
        )

    missing_ratio = _missing_ratio(bundle, matched_screen_id, ocr_texts)
    if missing_ratio > config.screen_inconsistency_max_missing_ratio:
        return (
            [],
            [],
            IndexUsageAuditRecord(
                bundle_id=bundle.manifest.bundle_id,
                schema_version=bundle.manifest.schema_version,
                outcome="inconsistent",
                matched_screen_id=matched_screen_id,
                no_match_reason="screen_content_inconsistent",
            ),
        )

    element_ids = sorted(bundle.screen_elements_index.get(matched_screen_id, []))
    hints = [to_visible_hint(bundle.elements[eid], bundle) for eid in element_ids]
    candidates: list[dict[str, Any]] = []
    for eid in element_ids:
        candidate = _element_to_candidate(bundle.elements[eid])
        if candidate is not None:
            candidates.append(candidate)

    candidate_transition_ids = sorted(bundle.transitions_from_index.get(matched_screen_id, []))

    audit = IndexUsageAuditRecord(
        bundle_id=bundle.manifest.bundle_id,
        schema_version=bundle.manifest.schema_version,
        outcome="hit",
        matched_screen_id=matched_screen_id,
        hint_element_ids=[hint.element_id for hint in hints],
        candidate_transition_ids=candidate_transition_ids,
    )
    return hints, candidates, audit
