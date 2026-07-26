"""Configuration loading (data-model.md §11, FR-045/047)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vnc_agent.domain.reporting_tags import ActionTagRule


class RecoveryPolicy(BaseModel):
    """Explicit recovery controls required by the project constitution."""

    max_retries: int = Field(ge=1)
    cooldown_ms: int = Field(ge=0)
    consumes_global_retry_budget: bool
    allows_action_path_change: bool
    requires_strong_model: bool
    requires_human_confirmation: bool


class ZoomRegroundConfig(BaseModel):
    """Feature 014 (FR-007): budgets/geometry for the zoom_reground escalation.

    Declared inside the yaml ``recovery:`` section as ``recovery.zoom_reground``
    (AgentConfig extracts it before the per-failure-type RecoveryPolicy dict is
    validated). ``max_per_step=0`` disables the escalation entirely.
    """

    max_per_step: int = Field(default=1, ge=0)
    scale_factor: float = Field(default=2.0, gt=1.0, le=8.0)
    roi_expand_factor: float = Field(default=2.0, ge=1.0, le=8.0)
    min_roi_size_px: int = Field(default=64, ge=16)


class StepConfig(BaseModel):
    default_timeout_seconds: int = 60
    default_max_retries: int = 3


class WaitConfig(BaseModel):
    min_delay_ms: int = 300
    max_delay_ms: int = 20000
    capture_interval_ms: int = 500
    stable_frame_count: int = 3
    pixel_diff_threshold: float = 0.02


class PerceptionConfig(BaseModel):
    ocr_enabled: bool = True
    template_enabled: bool = True
    vision_fallback_enabled: bool = True
    # Feature 010 (ocr-japanese-model): OCR recognition language / model
    # selection. All three default to None = pre-feature behavior (bundled
    # recognition model). `ocr_lang` values with a project asset mapping are
    # defined in perception/ocr/engine.py::OCR_LANG_ASSETS; an explicit
    # `ocr_rec_model_path` overrides the language mapping. Path existence is
    # validated fail-fast by configure_ocr() at composition time, not here
    # (config objects are built in offline tests with no filesystem context).
    ocr_lang: str | None = None
    ocr_rec_model_path: str | None = None
    ocr_rec_keys_path: str | None = None

    @model_validator(mode="after")
    def _ocr_lang_known_or_explicit_path(self) -> PerceptionConfig:
        if self.ocr_lang is not None and self.ocr_rec_model_path is None:
            from vnc_agent.perception.ocr.engine import OCR_LANG_ASSETS

            if self.ocr_lang not in OCR_LANG_ASSETS:
                raise ValueError(
                    f"unknown perception.ocr_lang {self.ocr_lang!r} without an "
                    "explicit ocr_rec_model_path; known languages: "
                    f"{sorted(OCR_LANG_ASSETS)}"
                )
        return self
    # 002-action-effect-verification: error popup OCR keywords + local blob min area ratio
    error_keywords: list[str] = Field(
        default_factory=lambda: ["错误", "エラー", "Error", "失败", "失敗", "Failed"]
    )
    local_blob_min_ratio: float = 0.0005
    # Feature 004: bounded analysis-cache window, most-recent-frame references
    # only (perception-cache-contract.md "Capacity and lifecycle")
    cache_max_frames: int = Field(default=5, ge=3, le=5)


class ArtifactsConfig(BaseModel):
    screenshot_policy: Literal["step", "all", "on_failure"] = "all"
    root_dir: str = "artifacts"
    db_path: str = "data/vnc_agent.db"


class SecurityConfig(BaseModel):
    mask_regions: list[list[int]] = Field(default_factory=list)
    sensitive_field_names: list[str] = Field(
        default_factory=lambda: ["password", "api_key", "secret", "token"]
    )


class GroundingConfig(BaseModel):
    overall_confidence_threshold: float = 0.55
    top1_top2_min_gap: float = 0.08


class VerificationConfig(BaseModel):
    """Feature 011 (FR-007): step-verification arbitration thresholds.

    ``visual_override_confidence_threshold`` — minimum confidence a re-checked
    ``visual_question`` "passed" answer needs before a deterministic ``failed``
    built solely from weak-negative OCR misses (``text_appears`` not found) may
    be overridden (spec 011, revised FR-010). Raising it tightens arbitration;
    1.0 effectively disables the override.
    """

    visual_override_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class ActionConfig(BaseModel):
    default_timeout_seconds: int = 10


class ClickConfig(BaseModel):
    """Feature 013 (safe-click-point): click-point geometry parameters.

    ``edge_inset_ratio`` — per-side inset ratio defining the safe zone inside
    a target bbox (overall_design.md §9.6 "避开边缘 15%"). Applies to both the
    OCR/template path and the grounding path. Values >= 0.5 are rejected
    because the safe zone would always be empty.
    """

    edge_inset_ratio: float = Field(default=0.15, ge=0.0, lt=0.5)


class PlanningConfig(BaseModel):
    ocr_sanity_check_ratio: float = Field(gt=0.0, le=1.0)
    # Feature 012 (ocr-partial-hit-grounder-fallback): minimum OCR confidence a
    # unique OCR hit needs before the Action Policy may click it directly
    # without grounding (suspicion rule R-B). Below this, resolution falls
    # through to MiMo Grounding with the hit forwarded as an ocr_candidates
    # hint. Default 0.85 — deliberately stricter than the grounding-consensus
    # threshold (grounding.overall_confidence_threshold, 0.55) because a direct
    # click trusts a single piece of OCR evidence.
    ocr_direct_click_min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    # Feature 003 (safety issue A): spatial-conflict IoU threshold — generic
    # geometry, not business-specific.
    target_region_conflict_iou_threshold: float = Field(default=0.10, gt=0.0, le=1.0)
    # Feature 003 (safety issue B): per-micro-action-category max allowed
    # risk_level. Keys are the generic UI-interaction purposes declared on
    # SemanticAction.micro_action_purpose — never business vocabulary.
    micro_action_risk_thresholds: dict[str, Literal["low", "medium", "high"]] = Field(
        default_factory=dict
    )


# Feature 004: locale resource-registry membership (report-contract.md
# "Locale configuration") — single source of truth shared with
# reporting/localization.py to avoid a circular import.
KNOWN_LOCALES: frozenset[str] = frozenset({"zh-CN"})


class ReportingConfig(BaseModel):
    # Feature 003 (FR-027/028): declarative, testcase/profile-supplied action
    # tags. Core MUST NOT hardcode any fixed business category — default is
    # an empty list.
    action_tags: list[ActionTagRule] = Field(default_factory=list)
    # Feature 004: zh-CN is the default and only required resource bundle;
    # an unregistered locale fails at config-load time, never silently falls
    # back (report-contract.md "Locale configuration").
    locale: str = "zh-CN"

    @field_validator("locale")
    @classmethod
    def _locale_must_be_registered(cls, value: str) -> str:
        if value not in KNOWN_LOCALES:
            raise ValueError(
                f"unregistered reporting.locale {value!r}; known locales: {sorted(KNOWN_LOCALES)}"
            )
        return value


class MemoryConfig(BaseModel):
    """Feature 015 (page-element-memory, FR-009): page/element memory knobs.

    ``enabled: false`` short-circuits every memory read/write — runtime
    behavior is byte-identical to the pre-015 codebase. Threshold semantics
    follow overall_design.md §13 (high => historical experience usable
    directly; medium => hint only, must re-verify via the grounder; low =>
    planner-reference tier, unused by the hot path in this MVP).
    """

    enabled: bool = True
    page_match_high: float = Field(default=0.88, gt=0.0, le=1.0)
    page_match_medium: float = Field(default=0.72, gt=0.0, le=1.0)
    page_match_low: float = Field(default=0.55, gt=0.0, le=1.0)
    # Minimum TM_CCOEFF_NORMED score for a neighborhood template match to
    # produce a direct click (spec FR-006).
    template_match_threshold: float = Field(default=0.85, gt=0.0, le=1.0)
    # Per-side search-neighborhood expansion around the remembered bbox,
    # relative to the bbox's own width/height (spec FR-006).
    bbox_expand_ratio: float = Field(default=0.5, ge=0.0, le=4.0)
    # Deterministic eviction cap (spec Clarification 8).
    max_elements_per_page: int = Field(default=64, ge=1)
    # Template image is refreshed only after this many *consecutive*
    # verified successes (spec Clarification 4).
    template_refresh_min_consecutive_successes: int = Field(default=3, ge=1)
    # None => "<artifacts.root_dir>/memory/templates" derived at wiring time.
    storage_dir: str | None = None

    @model_validator(mode="after")
    def _thresholds_ordered(self) -> MemoryConfig:
        if not (self.page_match_high > self.page_match_medium > self.page_match_low):
            raise ValueError(
                "memory thresholds must satisfy page_match_high > page_match_medium "
                f"> page_match_low, got {self.page_match_high} / "
                f"{self.page_match_medium} / {self.page_match_low}"
            )
        return self


class ReplayConfig(BaseModel):
    """Feature 016 (record-replay, FR-011): trajectory record/replay knobs.

    ``enabled: false`` disables both auto-recording and replay-mode runs
    (a mode:"replay" run then fails fast — spec Clarification 11).
    ``patch_auto_apply`` exists but is deliberately inert in this MVP: even
    ``true`` only logs a warning and never applies a patch (ADR-005 /
    spec FR-009 — self-heal candidates require human review).
    """

    enabled: bool = True
    # Auto-generate a candidate replay script after a fully-passed
    # exploration run (design §10.1 "自动产生候选回放轨迹").
    auto_generate: bool = True
    # ADR-005 red line: MUST default to false; true is a no-op + warning in MVP.
    patch_auto_apply: bool = False
    # Minimum TM_CCOEFF_NORMED score for the replay template-locate stage.
    # Independent from memory.template_match_threshold (spec Clarification 8).
    template_match_threshold: float = Field(default=0.85, gt=0.0, le=1.0)
    # Per-side search-neighborhood expansion around the recorded bbox.
    bbox_expand_ratio: float = Field(default=0.5, ge=0.0, le=4.0)
    # Minimum page-fingerprint match tier required before any direct locate
    # (design §10.2; "high" is the design default — spec Clarification 8).
    min_page_match_level: Literal["high", "medium"] = "high"
    # Max pairwise disagreement (px, per axis) between matched anchor offsets
    # for the anchor-translation locate stage (spec Clarification 2).
    anchor_offset_tolerance_px: int = Field(default=8, ge=0)
    # None => "<artifacts.root_dir>/replay/templates" derived at wiring time.
    storage_dir: str | None = None


class UiIndexConfig(BaseModel):
    """Optional external UI-analysis bundle consumption (feature 007)."""

    bundle_dir: str | None = None
    screen_match_min_score: float = 0.6
    screen_inconsistency_max_missing_ratio: float = 0.7
    max_content_file_bytes: int = 50_000_000
    max_content_file_records: int = 200_000
    max_bundle_total_bytes: int = 200_000_000


class AgentConfig(BaseModel):
    step: StepConfig = Field(default_factory=StepConfig)
    wait: WaitConfig = Field(default_factory=WaitConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    grounding: GroundingConfig = Field(default_factory=GroundingConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    action: ActionConfig = Field(default_factory=ActionConfig)
    click: ClickConfig = Field(default_factory=ClickConfig)
    planning: PlanningConfig = Field(
        default_factory=lambda: PlanningConfig(
            ocr_sanity_check_ratio=0.10,
            target_region_conflict_iou_threshold=0.10,
            micro_action_risk_thresholds={
                "dismiss_overlay": "medium",
                "scroll_reveal": "medium",
                "refocus": "medium",
                "wait": "high",
                "re_observe": "high",
            },
        )
    )
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    recovery: dict[str, RecoveryPolicy] = Field(default_factory=dict)
    # Feature 014 (FR-007): declared under the yaml `recovery:` section as
    # `recovery.zoom_reground`; extracted below so the per-failure-type
    # RecoveryPolicy dict stays homogeneous.
    zoom_reground: ZoomRegroundConfig = Field(default_factory=ZoomRegroundConfig)
    ui_index: UiIndexConfig = Field(default_factory=UiIndexConfig)
    # Feature 015 (page-element-memory, FR-009)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    # Feature 016 (record-replay, FR-011)
    replay: ReplayConfig = Field(default_factory=ReplayConfig)

    @model_validator(mode="before")
    @classmethod
    def _extract_zoom_reground_from_recovery(cls, data: Any) -> Any:
        if isinstance(data, dict):
            recovery = data.get("recovery")
            if isinstance(recovery, dict) and "zoom_reground" in recovery:
                recovery = dict(recovery)
                zoom = recovery.pop("zoom_reground")
                data = {**data, "recovery": recovery}
                # An explicit top-level `zoom_reground` (tests / programmatic
                # construction) wins over the yaml-section spelling.
                data.setdefault("zoom_reground", zoom)
        return data


class PlannerModelConfig(BaseModel):
    provider: str = "http_openai_compatible"
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "planner-v1"
    timeout_seconds: int = 60
    describe_screen_timeout_seconds: int | None = None
    api_key_env: str = "VNC_AGENT_PLANNER_API_KEY"

    def resolve_api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

    def describe_timeout(self) -> int:
        return self.describe_screen_timeout_seconds or self.timeout_seconds


class GrounderModelConfig(BaseModel):
    provider: str = "opencode-go"
    # OpenCode Go cloud endpoint (contract 2026-07-22); not a local placeholder
    base_url: str = "https://opencode.ai/zen/go/v1"
    # NEEDS VERIFICATION via GET {base_url}/models — try "mimo-v2.5" first
    model: str = "mimo-v2.5"
    timeout_seconds: int = 30
    top_k: int = 3
    api_key_env: str = "VNC_AGENT_GROUNDER_API_KEY"

    def resolve_api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


class ModelsConfig(BaseModel):
    planner: PlannerModelConfig = Field(default_factory=PlannerModelConfig)
    grounder: GrounderModelConfig = Field(default_factory=GrounderModelConfig)


class VNCTarget(BaseModel):
    id: str
    host: str
    port: int = 5900
    password_env: str = "VNC_AGENT_VNC_PASSWORD"
    connect_timeout_seconds: int = 15
    reconnect_attempts: int = 3

    def resolve_password(self) -> str | None:
        """Resolve password from env; never store plaintext in config (FR-047)."""
        return os.environ.get(self.password_env)


class VNCTargetsConfig(BaseModel):
    targets: list[VNCTarget] = Field(default_factory=list)

    def get(self, target_id: str) -> VNCTarget | None:
        for t in self.targets:
            if t.id == target_id:
                return t
        return None


class EnvSettings(BaseSettings):
    """Environment-bound secrets only — never written to yaml."""

    model_config = SettingsConfigDict(env_prefix="VNC_AGENT_", extra="ignore")

    planner_api_key: str | None = None
    grounder_api_key: str | None = None
    vnc_password: str | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_agent_config(config_dir: str | Path) -> AgentConfig:
    raw = _load_yaml(Path(config_dir) / "agent.yaml")
    return AgentConfig.model_validate(raw or {})


def load_models_config(config_dir: str | Path) -> ModelsConfig:
    raw = _load_yaml(Path(config_dir) / "models.yaml")
    return ModelsConfig.model_validate(raw or {})


def load_vnc_targets(config_dir: str | Path) -> VNCTargetsConfig:
    raw = _load_yaml(Path(config_dir) / "vnc-targets.yaml")
    return VNCTargetsConfig.model_validate(raw or {})


class AppConfig(BaseModel):
    agent: AgentConfig
    models: ModelsConfig
    vnc_targets: VNCTargetsConfig
    config_dir: str

    def recovery_for(self, failure_type: str) -> RecoveryPolicy:
        try:
            return self.agent.recovery[failure_type]
        except KeyError as exc:
            raise KeyError(f"missing explicit recovery policy for {failure_type}") from exc


def load_config(config_dir: str | Path = "config") -> AppConfig:
    config_dir = Path(config_dir)
    return AppConfig(
        agent=load_agent_config(config_dir),
        models=load_models_config(config_dir),
        vnc_targets=load_vnc_targets(config_dir),
        config_dir=str(config_dir),
    )
