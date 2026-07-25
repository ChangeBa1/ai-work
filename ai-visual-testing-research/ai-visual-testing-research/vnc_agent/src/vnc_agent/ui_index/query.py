"""Pure, read-only queries over a loaded `UiIndexBundle` (contracts §4, FR-004/005).

Every function here is a pure function: same inputs always return the same
outputs, no mutation of `bundle`, no exceptions on a miss (miss -> `[]`/`None`).
Multi-hit results are always sorted by id ascending for deterministic output.
"""

from __future__ import annotations

from vnc_agent.ui_index.models import Element, Screen, Transition
from vnc_agent.ui_index.repository import UiIndexBundle, normalize_text


def query_screen(bundle: UiIndexBundle, screen_id: str) -> Screen | None:
    return bundle.screens.get(screen_id)


def query_by_text(bundle: UiIndexBundle, text: str) -> list[Element]:
    element_ids = bundle.text_index.get(normalize_text(text), [])
    return [bundle.elements[eid] for eid in sorted(element_ids)]


def query_by_alias(bundle: UiIndexBundle, alias: str) -> list[Element]:
    element_ids = bundle.alias_index.get(normalize_text(alias), [])
    return [bundle.elements[eid] for eid in sorted(element_ids)]


def query_by_role(bundle: UiIndexBundle, role: str) -> list[Element]:
    element_ids = bundle.role_index.get(role, [])
    return [bundle.elements[eid] for eid in sorted(element_ids)]


def query_transitions(
    bundle: UiIndexBundle,
    *,
    from_screen_id: str | None = None,
    trigger_element_id: str | None = None,
    to_screen_id: str | None = None,
) -> list[Transition]:
    id_sets: list[set[str]] = []
    if from_screen_id is not None:
        id_sets.append(set(bundle.transitions_from_index.get(from_screen_id, [])))
    if trigger_element_id is not None:
        id_sets.append(set(bundle.transitions_trigger_index.get(trigger_element_id, [])))
    if to_screen_id is not None:
        id_sets.append(set(bundle.transitions_to_index.get(to_screen_id, [])))

    if not id_sets:
        return []

    matched = id_sets[0]
    for other in id_sets[1:]:
        matched &= other
    return [bundle.transitions[tid] for tid in sorted(matched)]
