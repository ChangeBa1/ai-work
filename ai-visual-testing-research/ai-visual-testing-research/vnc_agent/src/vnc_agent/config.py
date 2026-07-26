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


class PlanningConfig(BaseModel):
    ocr_sanity_check_ratio: float = Field(gt=0.0, le=1.0)
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
    ui_index: UiIndexConfig = Field(default_factory=UiIndexConfig)


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
