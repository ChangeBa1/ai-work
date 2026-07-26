"""Action Policy priority resolver (FR-012, FR-016/019)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

from vnc_agent.domain.action import (
    BATCH_REPEAT_INTERVAL_MS_DEFAULT,
    ExecutableAction,
    SemanticAction,
    TargetDescription,
)
from vnc_agent.domain.focus_path import VerifiedFocusNavigationPath
from vnc_agent.domain.grounding import (
    GroundingCandidate,
    GroundingResult,
    filter_in_bounds,
)
from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.domain.recovery import FailureType, GroundingLowConfidenceReason

ResolveOutcome = Literal[
    "keyboard",
    "focus",
    "ocr_template",
    "grounding",
    "stop_recover",
]

logger = logging.getLogger(__name__)

# Feature 012: suspicion reason codes (generic evidence semantics, never
# business vocabulary — Constitution VI).
SUSPICION_PARTIAL_TEXT_OVERLAP = "partial_text_overlap"
SUSPICION_LOW_CONFIDENCE = "low_confidence"
SUSPICION_SHORT_TEXT = "short_text"
SUSPICION_TRUNCATED_OCR_READ = "truncated_ocr_read"

# Feature 012: generic ASCII/CJK decoration characters stripped from BOTH ends
# (only) before the exact-match comparison, so purely decorative differences
# («【ログイン】» vs «ログイン») do not demote a trustworthy hit to grounding.
# Inner characters are never touched and no business vocabulary is involved.
_DECOR_CHARS = (
    " \t\r\n"
    "\"'`“”‘’„‟"
    "()[]{}<>（）［］｛｝〈〉《》「」『』【】〔〕"
    ".,:;!?、。，：；！？"
    "·・…‥~～-—–_*※|丨"
)

# Feature 012 (rule R-C): a normalized hit of this length or shorter is never
# trusted for a direct click — single glyphs are the highest-confusion OCR
# class (+/十/†, 一/-) and the widest accidental containment-match surface.
_SHORT_TEXT_MAX_LEN = 1

# Feature 012 (rule R-A1): minimum comparable length for an OCR item to count
# as truncation evidence (a proper substring of the target text); single-char
# substrings are too noisy to attribute.
_TRUNCATION_EVIDENCE_MIN_LEN = 2


def _comparable_text(s: str) -> str:
    """Normalize for the suspicion equality check (not for matching)."""
    return s.strip().lower().strip(_DECOR_CHARS)


@dataclass
class OcrSuspicion:
    """Feature 012: why a unique OCR hit was not clicked directly.

    Attached to PolicyResult for observability whenever resolution fell
    through to grounding because the OCR evidence looked suspicious.
    """

    reasons: list[str]
    ocr_text: str
    ocr_confidence: float
    bbox: tuple[int, int, int, int]


@dataclass
class PolicyResult:
    outcome: ResolveOutcome
    executable: ExecutableAction | None = None
    needs_grounding: bool = False
    failure_type: FailureType | None = None
    sub_reason: GroundingLowConfidenceReason | None = None
    selected_candidate: GroundingCandidate | None = None
    grounding_result: GroundingResult | None = None
    # Feature 012: set when a suspicious unique OCR hit (or a unique
    # truncated partial read) diverted resolution to the grounding path.
    ocr_suspicion: OcrSuspicion | None = None


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
        ocr_sanity_check_ratio: float = 0.10,
        known_hotkeys: dict[str, list[str]] | None = None,
        # Feature 012 (rule R-B): default kept in sync with
        # config.PlanningConfig.ocr_direct_click_min_confidence (0.85).
        ocr_direct_click_min_confidence: float = 0.85,
    ) -> None:
        self.overall_confidence_threshold = overall_confidence_threshold
        self.top1_top2_min_gap = top1_top2_min_gap
        self.ocr_sanity_check_ratio = ocr_sanity_check_ratio
        self.known_hotkeys = known_hotkeys or {}
        self.ocr_direct_click_min_confidence = ocr_direct_click_min_confidence

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
        # 0) Batch repeat key (Feature 005) — always author-declared and
        # already validated (SemanticAction.validate_batch_repeat); resolves
        # unconditionally, never falls through to focus/OCR/Grounding.
        if action.action_type == "press_key_repeat":
            return PolicyResult(
                outcome="keyboard",
                executable=ExecutableAction(
                    method="keyboard",
                    operation="press_key_repeat",
                    keys=list(action.keys),
                    repeat_count=action.repeat_count,
                    repeat_interval_ms=(
                        action.repeat_interval_ms or BATCH_REPEAT_INTERVAL_MS_DEFAULT
                    ),
                ),
            )

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
        # Feature 012: explain a suspicious-OCR fallthrough (FR-005). The
        # payload also names the hit the grounder will see again through the
        # existing GroundingRequest.ocr_candidates hint channel (FR-002).
        suspicion = self._ocr_suspicion_for(action.target, screen)
        if grounding_result is None:
            if suspicion is not None:
                logger.info(
                    "unique OCR evidence deemed suspicious; deferring to "
                    "grounding: reasons=%s ocr_text=%r confidence=%.3f bbox=%s",
                    suspicion.reasons,
                    suspicion.ocr_text,
                    suspicion.ocr_confidence,
                    suspicion.bbox,
                )
            return PolicyResult(
                outcome="grounding", needs_grounding=True, ocr_suspicion=suspicion
            )

        result = self._from_grounding(
            action, screen, grounding_result, candidate_index=candidate_index
        )
        result.ocr_suspicion = suspicion
        return result

    def _find_unique_hits(
        self,
        target: TargetDescription | None,
        screen: StructuredScreen,
    ) -> tuple[str, list[OCRItem], list[TemplateMatch]] | None:
        """Feature 012: hit collection extracted verbatim from
        _unique_ocr_or_template so suspicion evaluation reuses the exact same
        matching rules. Returns (needle, ocr_hits, tmpl_hits) or None."""
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
        return needle, ocr_hits, tmpl_hits

    def _ocr_hit_suspicion_reasons(self, needle: str, item: OCRItem) -> list[str]:
        """Feature 012: suspicion rule table for a unique OCR hit.

        R-C short_text: comparable hit length <= 1 (never trusted, even when
        exact and confident — single glyphs are the highest-confusion class).
        R-A2 partial_text_overlap: containment hit but not an exact comparable
        match (OCR merged neighbouring glyphs, or the declared target is a
        truncated-echo fragment) — bbox centre may not be the target centre.
        R-B low_confidence: below the configurable direct-click threshold.
        Empty list == trusted exact hit (byte-identical legacy behavior).
        """
        reasons: list[str] = []
        comparable_hit = _comparable_text(item.normalized_text or item.text)
        comparable_target = _comparable_text(needle)
        if len(comparable_hit) <= _SHORT_TEXT_MAX_LEN:
            reasons.append(SUSPICION_SHORT_TEXT)
        if comparable_target and comparable_hit != comparable_target:
            reasons.append(SUSPICION_PARTIAL_TEXT_OVERLAP)
        if item.confidence < self.ocr_direct_click_min_confidence:
            reasons.append(SUSPICION_LOW_CONFIDENCE)
        return reasons

    def _ocr_suspicion_for(
        self,
        target: TargetDescription | None,
        screen: StructuredScreen,
    ) -> OcrSuspicion | None:
        """Feature 012: observability payload for the grounding fallthrough.

        Only meaningful when _unique_ocr_or_template returned None:
        - a unique OCR hit that was rejected by the suspicion rules;
        - no containment hit at all, but exactly one OCR item whose comparable
          text is a proper substring (length >= 2) of the target text —
          truncation evidence (OCR read fewer glyphs than the declared label,
          rule R-A1); behavior was already "fall through to grounding", this
          only explains why.
        """
        found = self._find_unique_hits(target, screen)
        if found is None:
            return None
        needle, ocr_hits, _tmpl_hits = found
        if len(ocr_hits) == 1:
            reasons = self._ocr_hit_suspicion_reasons(needle, ocr_hits[0])
            if reasons:
                item = ocr_hits[0]
                return OcrSuspicion(
                    reasons=reasons,
                    ocr_text=item.text,
                    ocr_confidence=item.confidence,
                    bbox=item.bbox,
                )
            return None
        if not ocr_hits:
            comparable_target = _comparable_text(needle)
            partial = [
                i
                for i in screen.ocr_items
                if (
                    len(_comparable_text(i.normalized_text or i.text))
                    >= _TRUNCATION_EVIDENCE_MIN_LEN
                )
                and _comparable_text(i.normalized_text or i.text) != comparable_target
                and _comparable_text(i.normalized_text or i.text) in comparable_target
            ]
            if len(partial) == 1:
                item = partial[0]
                return OcrSuspicion(
                    reasons=[SUSPICION_TRUNCATED_OCR_READ],
                    ocr_text=item.text,
                    ocr_confidence=item.confidence,
                    bbox=item.bbox,
                )
        return None

    def _unique_ocr_or_template(
        self,
        target: TargetDescription | None,
        screen: StructuredScreen,
    ) -> tuple[int, int, tuple[int, int, int, int]] | None:
        found = self._find_unique_hits(target, screen)
        if found is None:
            return None
        needle, ocr_hits, tmpl_hits = found

        if len(ocr_hits) == 1 and not tmpl_hits:
            # Feature 012: a suspicious unique hit must not be clicked —
            # fall through to the grounding path instead (FR-001).
            if self._ocr_hit_suspicion_reasons(needle, ocr_hits[0]):
                return None
            b = ocr_hits[0].bbox
            return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2, b)
        if len(tmpl_hits) == 1 and not ocr_hits:
            b = tmpl_hits[0].bbox
            return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2, b)
        if len(ocr_hits) == 1 and len(tmpl_hits) == 1:
            # Prefer higher confidence
            o, t = ocr_hits[0], tmpl_hits[0]
            # Feature 012 (FR-007): when the OCR hit is suspicious, fall back
            # to the template evidence (pixel-level, no truncation problem) —
            # still a direct click, zero extra model calls.
            if self._ocr_hit_suspicion_reasons(needle, o):
                pick = t.bbox
            else:
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
        in_bounds = [
            candidate
            for candidate in in_bounds
            if self._consistent_with_unique_ocr(action, screen, candidate)
        ]
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

    def _consistent_with_unique_ocr(
        self,
        action: SemanticAction,
        screen: StructuredScreen,
        candidate: GroundingCandidate,
    ) -> bool:
        target_text = (action.target.text if action.target else "") or ""
        needle = target_text.strip().lower()
        if not needle:
            return True
        hits = [
            item
            for item in screen.ocr_items
            if needle in item.normalized_text or needle in item.text.lower()
        ]
        if len(hits) != 1:
            return True
        anchor = hits[0].bbox
        anchor_center = ((anchor[0] + anchor[2]) // 2, (anchor[1] + anchor[3]) // 2)
        candidate_center = candidate.center()
        distance = math.dist(anchor_center, candidate_center)
        tolerance = self.ocr_sanity_check_ratio * min(screen.resolution)
        return distance <= tolerance

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
