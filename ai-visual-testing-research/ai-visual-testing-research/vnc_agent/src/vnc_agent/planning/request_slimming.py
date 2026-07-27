"""Feature 019 (planner-request-slimming): serialization-time payload slimming.

`HttpPlannerClient.plan()` sends the planner a JSON text dump of
`PlannerRequest`. On a real POS frame that dump carries 30~60 OCR items (mostly
numeric-keypad noise), each with a full-precision confidence and a
`normalized_text` that duplicates `text`, plus frequently-null/empty
bookkeeping fields — pure token waste that slows planning. This module removes
that redundancy *at serialization time only*:

- the `PlannerRequest` Pydantic model is untouched, so every non-wire consumer
  (008 cache identity, audits, orchestrator, stubs) sees exactly what it saw
  before;
- no key is renamed and surviving list items keep their original relative
  (reading) order, so every statement `_PLANNER_SYSTEM_PROMPT` makes about the
  input stays true (spec FR-009 red line);
- functions are pure (input never mutated) and total (arbitrary JSON-shaped
  dicts — including the offline-test `structured_screen={}` / `expected={}`
  shapes — pass through without raising).

Rules (spec FR-002..FR-004; plan.md "Slimming rules"):

1. `structured_screen.ocr_items` capped at `ocr_items_max`; target-relevant
   text (substring match vs `step_intent` / `expected.conditions[*].value`)
   always survives, remainder by confidence descending; each surviving item is
   reduced to `text` + integer `bbox` + 2-decimal `confidence` (+
   `normalized_text` only when it differs from `text`).
2. `structured_screen.template_matches` capped at `list_items_max` (top
   confidence, original order).
3. `structured_screen.changed_regions` / `structured_screen.local_blobs` /
   `ui_index_hints` keep their first `list_items_max` entries.
4. `recent_step_summaries` keeps its *last* `list_items_max` entries.
5. Floats are rounded recursively: keys named `confidence` to 2 decimals,
   everything else to 4.
6. Dict entries whose value is `null` or `[]` are dropped recursively.

Stdlib-only on purpose: importable from `models/planner_client.py` with no
import cycle.
"""

from __future__ import annotations

from typing import Any

DEFAULT_OCR_ITEMS_MAX = 40
DEFAULT_LIST_ITEMS_MAX = 10

_CONFIDENCE_DECIMALS = 2
_FLOAT_DECIMALS = 4


def slim_planner_payload(
    payload: dict[str, Any],
    *,
    ocr_items_max: int = DEFAULT_OCR_ITEMS_MAX,
    list_items_max: int = DEFAULT_LIST_ITEMS_MAX,
) -> dict[str, Any]:
    """Return a slimmed deep copy of a ``PlannerRequest.model_dump(mode="json")``
    dict. The input is never mutated; malformed/missing sub-structures pass
    through (minus the generic rounding / null-and-empty-list cleanup)."""
    out = dict(payload)

    screen = out.get("structured_screen")
    if isinstance(screen, dict):
        screen = dict(screen)
        target_texts = _collect_target_texts(payload)
        ocr_items = screen.get("ocr_items")
        if isinstance(ocr_items, list):
            screen["ocr_items"] = _slim_ocr_items(ocr_items, ocr_items_max, target_texts)
        template_matches = screen.get("template_matches")
        if isinstance(template_matches, list):
            screen["template_matches"] = _cap_by_confidence(template_matches, list_items_max)
        for key in ("changed_regions", "local_blobs"):
            value = screen.get(key)
            if isinstance(value, list):
                screen[key] = value[:list_items_max]
        out["structured_screen"] = screen

    hints = out.get("ui_index_hints")
    if isinstance(hints, list):
        out["ui_index_hints"] = hints[:list_items_max]

    summaries = out.get("recent_step_summaries")
    if isinstance(summaries, list) and len(summaries) > list_items_max:
        # Summaries append chronologically — the tail is the most recent.
        out["recent_step_summaries"] = summaries[-list_items_max:]

    cleaned = _cleanup(out)
    return cleaned if isinstance(cleaned, dict) else out


def _collect_target_texts(payload: dict[str, Any]) -> list[str]:
    """Normalized target-description strings present in the request itself:
    the step intent and every expected-condition value (spec FR-002)."""
    texts: list[str] = []
    intent = payload.get("step_intent")
    if isinstance(intent, str) and intent.strip():
        texts.append(intent.strip().lower())
    expected = payload.get("expected")
    if isinstance(expected, dict):
        conditions = expected.get("conditions")
        if isinstance(conditions, list):
            for condition in conditions:
                if isinstance(condition, dict):
                    value = condition.get("value")
                    if isinstance(value, str) and value.strip():
                        texts.append(value.strip().lower())
    return texts


def _item_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip().lower()
    normalized = item.get("normalized_text")
    if isinstance(normalized, str):
        return normalized.strip().lower()
    return ""


def _is_target_hit(item: Any, target_texts: list[str]) -> bool:
    text = _item_text(item)
    if not text:
        return False
    return any(text in target or target in text for target in target_texts)


def _confidence_of(item: Any) -> float:
    if isinstance(item, dict):
        value = item.get("confidence")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _slim_ocr_items(
    items: list[Any], ocr_items_max: int, target_texts: list[str]
) -> list[Any]:
    if len(items) <= ocr_items_max:
        selected = list(items)
    else:
        hit_indices = [i for i, item in enumerate(items) if _is_target_hit(item, target_texts)]
        if len(hit_indices) >= ocr_items_max:
            # More hits than budget: highest-confidence hits fill it entirely.
            keep = set(
                sorted(hit_indices, key=lambda i: _confidence_of(items[i]), reverse=True)[
                    :ocr_items_max
                ]
            )
        else:
            keep = set(hit_indices)
            rest = [i for i in range(len(items)) if i not in keep]
            rest.sort(key=lambda i: _confidence_of(items[i]), reverse=True)
            keep.update(rest[: ocr_items_max - len(keep)])
        # Emit survivors in original (reading) order — order is layout
        # information the planner may rely on (FR-009).
        selected = [items[i] for i in sorted(keep)]
    return [_slim_ocr_item(item) for item in selected]


def _slim_ocr_item(item: Any) -> Any:
    """Reduce one OCR item to `text` / integer `bbox` / 2-decimal `confidence`,
    keeping `normalized_text` only when it differs from `text` (FR-002)."""
    if not isinstance(item, dict):
        return item
    slimmed: dict[str, Any] = {}
    if "text" in item:
        slimmed["text"] = item["text"]
    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)):
        slimmed["bbox"] = [
            int(round(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
            for v in bbox
        ]
    elif "bbox" in item:
        slimmed["bbox"] = bbox
    if "confidence" in item:
        confidence = item["confidence"]
        slimmed["confidence"] = (
            round(float(confidence), _CONFIDENCE_DECIMALS)
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
            else confidence
        )
    normalized = item.get("normalized_text")
    if isinstance(normalized, str) and normalized != item.get("text"):
        slimmed["normalized_text"] = normalized
    return slimmed


def _cap_by_confidence(items: list[Any], max_items: int) -> list[Any]:
    """Keep the `max_items` highest-confidence entries, in original order."""
    if len(items) <= max_items:
        return list(items)
    indices = sorted(
        range(len(items)), key=lambda i: _confidence_of(items[i]), reverse=True
    )[:max_items]
    return [items[i] for i in sorted(indices)]


def _cleanup(value: Any, key: str | None = None) -> Any:
    """Recursive final pass: round floats (confidence → 2 dp, others → 4 dp)
    and drop dict entries whose value is null or an empty list (FR-004)."""
    if isinstance(value, bool):  # bool before float/int: bool subclasses int
        return value
    if isinstance(value, float):
        decimals = _CONFIDENCE_DECIMALS if key == "confidence" else _FLOAT_DECIMALS
        return round(value, decimals)
    if isinstance(value, dict):
        return {
            k: _cleanup(v, k)
            for k, v in value.items()
            if v is not None and v != []
        }
    if isinstance(value, list):
        return [_cleanup(v) for v in value]
    return value
