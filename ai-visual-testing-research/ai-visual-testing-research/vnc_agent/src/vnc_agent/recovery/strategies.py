"""Recovery strategy set (FR-037/038 + T069 focus-path derivation)."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vnc_agent.domain.focus_path import VerifiedFocusNavigationPath
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import FailureType, RecoveryStrategy

if TYPE_CHECKING:
    pass

StrategyFn = Callable[..., Awaitable[bool]]

# Refuse inventing very long tab walks (likely wrong anchor ordering)
_MAX_TAB_SEQUENCE_LEN = 30


def normalize_focus_hint(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def _ordered_anchor_labels(screen: StructuredScreen) -> list[str]:
    """
    Focusable-like anchors in reading order (top-to-bottom, left-to-right).

    Uses OCR text and template ids as black-box stand-ins for tab order. This is
    an approximation — when match is ambiguous we refuse to build a path (FR-022).
    """
    entries: list[tuple[int, int, str]] = []
    for item in screen.ocr_items:
        label = (item.normalized_text or item.text or "").strip()
        if not label:
            continue
        x1, y1, _x2, _y2 = item.bbox
        entries.append((y1, x1, label))
    for match in screen.template_matches:
        label = (match.template_id or "").strip()
        if not label:
            continue
        x1, y1, _x2, _y2 = match.bbox
        entries.append((y1, x1, label))
    entries.sort(key=lambda t: (t[0], t[1]))
    return [label for _y, _x, label in entries]


def _unique_anchor_index(labels: list[str], hint: str) -> int | None:
    needle = normalize_focus_hint(hint)
    if not needle:
        return None
    hits = [
        i
        for i, lab in enumerate(labels)
        if needle in normalize_focus_hint(lab) or normalize_focus_hint(lab) in needle
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _clean_tab_sequence(tab_sequence: list[str]) -> list[str]:
    cleaned: list[str] = []
    for k in tab_sequence:
        kl = k.lower().replace(" ", "")
        if kl == "tab":
            cleaned.append("tab")
        elif kl in ("shift+tab", "shift-tab"):
            cleaned.append("shift+tab")
    return cleaned


def derive_tab_sequence_from_structure(
    screen: StructuredScreen,
    *,
    from_hint: str,
    to_hint: str,
) -> list[str] | None:
    """
    Derive tab/shift+tab sequence from OCR/template anchor ordering.

    Requires both from_hint and to_hint to uniquely resolve to different anchors.
    Returns None when evidence is insufficient (never invents a default single Tab).
    """
    labels = _ordered_anchor_labels(screen)
    if len(labels) < 2:
        return None
    from_idx = _unique_anchor_index(labels, from_hint)
    to_idx = _unique_anchor_index(labels, to_hint)
    if from_idx is None or to_idx is None:
        return None
    if from_idx == to_idx:
        return None
    delta = to_idx - from_idx
    if delta > 0:
        seq = ["tab"] * delta
    else:
        seq = ["shift+tab"] * (-delta)
    if not seq or len(seq) > _MAX_TAB_SEQUENCE_LEN:
        return None
    return seq


def try_build_focus_path(
    screen: StructuredScreen | None,
    *,
    to_hint: str = "",
    from_hint: str = "",
    tab_sequence: list[str] | None = None,
    method: str = "structural_diff_confirmed",
) -> VerifiedFocusNavigationPath | None:
    """
    Construct a VerifiedFocusNavigationPath for switch_to_keyboard.

    Returns None when evidence is insufficient — ActionPolicy then must not emit Tab.

    Sources (in order when called via RecoveryEngine):
    1. Explicit non-empty ``tab_sequence`` (prior_successful_replay or precomputed)
    2. Structural derivation from OCR/template reading order when both from/to
       hints uniquely match anchors on ``screen`` (structural_diff_confirmed)

    Without a real sequence we refuse (FR-022: no blind Tab).
    """
    cleaned = _clean_tab_sequence(tab_sequence) if tab_sequence else []

    if not cleaned and method != "prior_successful_replay" and screen is not None:
        # Structural derivation when no explicit sequence was supplied
        derived = derive_tab_sequence_from_structure(
            screen, from_hint=from_hint, to_hint=to_hint
        )
        if derived:
            cleaned = derived
            method = "structural_diff_confirmed"

    if not cleaned:
        return None
    if screen is None and method != "prior_successful_replay":
        return None

    return VerifiedFocusNavigationPath(
        from_hint=from_hint or "current_focus",
        to_hint=to_hint or "target",
        tab_sequence=cleaned,  # type: ignore[arg-type]
        verification_method=(
            "prior_successful_replay"
            if method == "prior_successful_replay"
            else "structural_diff_confirmed"
        ),
        verified_at_frame_id=screen.frame_id if screen is not None else "",
    )


# Preferred then fallback strategies (data-model.md §8; feature 014 FR-001
# inserts zoom_reground as the escalation tier after the first strategy for
# target_not_found / grounding_low_confidence, keeping re_ground terminal).
ROUTING: dict[FailureType, list[RecoveryStrategy]] = {
    FailureType.VNC_CONNECT_FAILED: ["recapture"],
    FailureType.VNC_DISCONNECTED: ["restart_step"],
    FailureType.BLACK_SCREEN: ["recapture", "extra_wait"],
    FailureType.PAGE_NOT_STABLE: ["extra_wait", "recapture"],
    FailureType.TARGET_NOT_FOUND: ["recapture", "zoom_reground", "re_ground"],
    FailureType.GROUNDING_LOW_CONFIDENCE: ["second_candidate", "zoom_reground", "re_ground"],
    FailureType.ACTION_NO_EFFECT: ["second_candidate", "switch_to_keyboard"],
    FailureType.FOCUS_ERROR: ["press_escape", "switch_to_keyboard"],
    FailureType.INPUT_METHOD_ERROR: ["release_modifiers", "switch_to_keyboard"],
    FailureType.UNEXPECTED_DIALOG: ["press_escape", "win_d_reset"],
    FailureType.VERIFICATION_FAILED: ["recapture", "extra_wait"],
    FailureType.TIMEOUT: ["re_ground", "release_modifiers"],
    # Feature 022: the action was never sent — a fresh observation (next
    # ActionIteration re-observes + re-grounds by construction) is the whole
    # remedy; no path change needed.
    FailureType.STALE_FRAME: ["recapture"],
    # Feature 022: click landed beside the target — same re-observe/re-locate
    # escalation chain as target_not_found (recapture → zoom_reground →
    # re_ground), reusing the feature-014 zoom plumbing unchanged.
    FailureType.WRONG_TARGET: ["recapture", "zoom_reground", "re_ground"],
}


@dataclass
class StrategyContext:
    driver: Any | None = None
    executor: Any | None = None
    extra_wait_ms: int = 1000
    strong_model_available: bool = False
    human_confirmation_granted: bool = False
    # Feature 014 (FR-002): evidence for zoom_reground ROI derivation. All
    # optional — when absent the engine skips the escalation and substitutes
    # the next strategy in the sequence.
    screen: StructuredScreen | None = None
    grounding_result: Any | None = None
    target: dict[str, Any] | None = None


async def execute_strategy(
    strategy: RecoveryStrategy,
    ctx: StrategyContext,
    *,
    timeout_seconds: float = 10.0,
) -> bool:
    """
    Run a recovery strategy under action-level timeout.
    Returns True if strategy completed without error (not necessarily 'resolved').
    """
    try:
        await asyncio.wait_for(_run(strategy, ctx), timeout=timeout_seconds)
        return True
    except Exception:
        return False


async def _run(strategy: RecoveryStrategy, ctx: StrategyContext) -> None:
    driver = ctx.driver
    if strategy == "recapture":
        if driver is not None:
            await driver.capture_screen()
        return
    if strategy == "extra_wait":
        await asyncio.sleep(ctx.extra_wait_ms / 1000.0)
        return
    if strategy == "second_candidate":
        return  # policy layer bumps candidate_index
    if strategy == "re_ground":
        return  # policy/runtime re-invokes grounder
    if strategy == "zoom_reground":
        # Feature 014: the actual crop+upscale observation happens in the next
        # ActionIteration's grounding branch (engine sets the one-shot plan).
        return
    if strategy == "switch_to_keyboard":
        return  # policy prefer_keyboard flag
    if strategy == "release_modifiers":
        if driver is not None and hasattr(driver, "release_modifiers"):
            await driver.release_modifiers()
        return
    if strategy == "press_escape":
        if driver is not None:
            await driver.send_key("escape")
        return
    if strategy == "win_d_reset":
        if driver is not None:
            await driver.send_hotkey(["win", "d"])
        return
    if strategy == "restart_step":
        if driver is not None:
            await driver.reconnect()
        return
