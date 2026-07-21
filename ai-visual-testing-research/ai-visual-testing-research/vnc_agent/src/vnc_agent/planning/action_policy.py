"""Action Policy priority resolver (FR-012, FR-016/019)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnc_agent.domain.action import ExecutableAction, SemanticAction, TargetDescription
from vnc_agent.domain.focus_path import VerifiedFocusNavigationPath
from vnc_agent.domain.grounding import (
    GroundingCandidate,
    GroundingResult,
    filter_in_bounds,
)
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import FailureType, GroundingLowConfidenceReason

ResolveOutcome = Literal[
    "keyboard",
    "focus",
    "ocr_template",
    "grounding",
    "stop_recover",
]


@dataclass
class PolicyResult:
    outcome: ResolveOutcome
    executable: ExecutableAction | None = None
    needs_grounding: bool = False
    failure_type: FailureType | None = None
    sub_reason: GroundingLowConfidenceReason | None = None
    selected_candidate: GroundingCandidate | None = None
    grounding_result: GroundingResult | None = None


class ActionPolicy:
    """
    Priority (each iteration independently):
    1. Configured hotkey / keys on SemanticAction
    2. Focus navigation (Tab/Shift+Tab/Enter/Space)
    3. Unique OCR / template match
    4. MiMo Grounding (caller supplies result)
    5. Stop and recover
    """

    def __init__(
        self,
        *,
        overall_confidence_threshold: float = 0.55,
        top1_top2_min_gap: float = 0.08,
        known_hotkeys: dict[str, list[str]] | None = None,
    ) -> None:
        self.overall_confidence_threshold = overall_confidence_threshold
        self.top1_top2_min_gap = top1_top2_min_gap
        self.known_hotkeys = known_hotkeys or {}

    def resolve(
        self,
        action: SemanticAction,
        screen: StructuredScreen,
        *,
        grounding_result: GroundingResult | None = None,
        prefer_keyboard: bool = False,
        focus_path: VerifiedFocusNavigationPath | None = None,
        candidate_index: int = 0,
    ) -> PolicyResult:
        # 1) Explicit keys / hotkey on the semantic action
        if action.action_type in ("press_key", "hotkey") and action.keys:
            return PolicyResult(
                outcome="keyboard",
                executable=ExecutableAction(
                    method="keyboard",
                    operation=action.action_type,
                    keys=list(action.keys),
                    text=action.text_value,
                ),
            )

        if action.action_type == "type_text":
            return PolicyResult(
                outcome="keyboard",
                executable=ExecutableAction(
                    method="keyboard",
                    operation="type_text",
                    text=action.text_value,
                    keys=[],
                ),
            )

        if action.action_type == "wait":
            return PolicyResult(
                outcome="keyboard",
                executable=ExecutableAction(
                    method="keyboard", operation="wait", keys=[]
                ),
            )

        if action.action_type == "finish":
            return PolicyResult(
                outcome="keyboard",
                executable=ExecutableAction(
                    method="keyboard", operation="finish", keys=[]
                ),
            )

        # Known hotkey by intent keyword
        for keyword, keys in self.known_hotkeys.items():
            if keyword.lower() in (action.intent or "").lower():
                return PolicyResult(
                    outcome="keyboard",
                    executable=ExecutableAction(
                        method="keyboard",
                        operation="hotkey",
                        keys=list(keys),
                    ),
                )

        # 2) Focus navigation only with VerifiedFocusNavigationPath (FR-020~024)
        # prefer_keyboard without focus_path MUST NOT emit blind tab — fall through
        # to OCR/template/grounding/stop_recover instead (US5).
        if (
            prefer_keyboard
            and focus_path is not None
            and action.action_type in ("click", "double_click", "right_click")
        ):
            keys = list(focus_path.tab_sequence) or ["tab"]
            return PolicyResult(
                outcome="focus",
                executable=ExecutableAction(
                    method="keyboard",
                    operation="press_key",
                    keys=keys,
                ),
            )

        # Explicit focus keys on the semantic action itself (not recovery-driven)
        if action.action_type == "press_key" or (
            action.keys
            and set(k.lower() for k in action.keys)
            <= {"tab", "shift", "enter", "space", "escape", "esc"}
        ):
            keys = action.keys or ["tab"]
            return PolicyResult(
                outcome="focus",
                executable=ExecutableAction(
                    method="keyboard", operation="press_key", keys=keys
                ),
            )

        # 3) Unique OCR / template localization
        unique = self._unique_ocr_or_template(action.target, screen)
        if unique is not None:
            x, y, region = unique
            op = action.action_type
            if op not in ("click", "double_click", "right_click", "drag", "scroll"):
                op = "click"
            from vnc_agent.domain.observation import Region

            return PolicyResult(
                outcome="ocr_template",
                executable=ExecutableAction(
                    method="mouse",
                    operation=op,
                    coordinates=(x, y),
                    target_region=Region(
                        x1=region[0], y1=region[1], x2=region[2], y2=region[3]
                    ),
                ),
            )

        # 4) Grounding path
        if grounding_result is None:
            return PolicyResult(outcome="grounding", needs_grounding=True)

        return self._from_grounding(
            action, screen, grounding_result, candidate_index=candidate_index
        )

    def _unique_ocr_or_template(
        self,
        target: TargetDescription | None,
        screen: StructuredScreen,
    ) -> tuple[int, int, tuple[int, int, int, int]] | None:
        if target is None:
            return None
        needle = (target.text or target.description or "").strip().lower()
        if not needle:
            return None

        ocr_hits = [
            i
            for i in screen.ocr_items
            if needle in i.normalized_text or needle in i.text.lower()
        ]
        tmpl_hits = [
            m
            for m in screen.template_matches
            if needle in m.template_id.lower()
            or (target.text and target.text.lower() in m.template_id.lower())
        ]

        if len(ocr_hits) == 1 and not tmpl_hits:
            b = ocr_hits[0].bbox
            return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2, b)
        if len(tmpl_hits) == 1 and not ocr_hits:
            b = tmpl_hits[0].bbox
            return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2, b)
        if len(ocr_hits) == 1 and len(tmpl_hits) == 1:
            # Prefer higher confidence
            o, t = ocr_hits[0], tmpl_hits[0]
            pick = o.bbox if o.confidence >= t.confidence else t.bbox
            return ((pick[0] + pick[2]) // 2, (pick[1] + pick[3]) // 2, pick)
        return None

    def _from_grounding(
        self,
        action: SemanticAction,
        screen: StructuredScreen,
        result: GroundingResult,
        *,
        candidate_index: int = 0,
    ) -> PolicyResult:
        w, h = screen.resolution
        in_bounds = filter_in_bounds(result.candidates, w, h)
        filtered = GroundingResult(
            found=result.found and bool(in_bounds),
            candidates=in_bounds,
            model_name=result.model_name,
            raw_response_ref=result.raw_response_ref,
        )

        if not result.found or not in_bounds:
            return PolicyResult(
                outcome="stop_recover",
                failure_type=FailureType.TARGET_NOT_FOUND,
                grounding_result=filtered,
            )

        # After recovery escalated to second_candidate (candidate_index > 0), honour
        # that upgrade instead of re-blocking on the same confidence heuristics.
        if candidate_index > 0:
            return self._executable_from_candidate(
                action, in_bounds, candidate_index, filtered
            )

        # Confidence classification (first attempt only)
        top = in_bounds[0]
        if top.confidence < self.overall_confidence_threshold:
            return PolicyResult(
                outcome="stop_recover",
                failure_type=FailureType.GROUNDING_LOW_CONFIDENCE,
                sub_reason="overall_low_confidence",
                grounding_result=filtered,
            )
        if len(in_bounds) >= 2:
            gap = in_bounds[0].confidence - in_bounds[1].confidence
            if gap < self.top1_top2_min_gap:
                return PolicyResult(
                    outcome="stop_recover",
                    failure_type=FailureType.GROUNDING_LOW_CONFIDENCE,
                    sub_reason="top1_top2_close",
                    grounding_result=filtered,
                )

        return self._executable_from_candidate(
            action, in_bounds, candidate_index, filtered
        )

    def _executable_from_candidate(
        self,
        action: SemanticAction,
        in_bounds: list[GroundingCandidate],
        candidate_index: int,
        filtered: GroundingResult,
    ) -> PolicyResult:
        idx = min(candidate_index, len(in_bounds) - 1)
        cand = in_bounds[idx]
        cx, cy = cand.center()
        op = action.action_type
        if op not in ("click", "double_click", "right_click", "drag", "scroll"):
            op = "click"
        from vnc_agent.domain.observation import Region

        return PolicyResult(
            outcome="grounding",
            executable=ExecutableAction(
                method="mouse",
                operation=op,
                coordinates=(cx, cy),
                target_region=Region(
                    x1=cand.bbox[0],
                    y1=cand.bbox[1],
                    x2=cand.bbox[2],
                    y2=cand.bbox[3],
                ),
            ),
            selected_candidate=cand,
            grounding_result=filtered,
        )
