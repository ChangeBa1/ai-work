"""Configuration loading (data-model.md §11, FR-045/047)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RecoveryPolicy(BaseModel):
    max_retries: int = Field(ge=1, default=2)
    cooldown_ms: int = Field(ge=0, default=300)


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
    # 002-action-effect-verification: error popup OCR keywords + local blob min area ratio
    error_keywords: list[str] = Field(
        default_factory=lambda: ["错误", "エラー", "Error", "失败", "失敗", "Failed"]
    )
    local_blob_min_ratio: float = 0.0005


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


class ActionConfig(BaseModel):
    default_timeout_seconds: int = 10


class AgentConfig(BaseModel):
    step: StepConfig = Field(default_factory=StepConfig)
    wait: WaitConfig = Field(default_factory=WaitConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    grounding: GroundingConfig = Field(default_factory=GroundingConfig)
    action: ActionConfig = Field(default_factory=ActionConfig)
    recovery: dict[str, RecoveryPolicy] = Field(default_factory=dict)


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
        return self.agent.recovery.get(failure_type, RecoveryPolicy())


def load_config(config_dir: str | Path = "config") -> AppConfig:
    config_dir = Path(config_dir)
    return AppConfig(
        agent=load_agent_config(config_dir),
        models=load_models_config(config_dir),
        vnc_targets=load_vnc_targets(config_dir),
        config_dir=str(config_dir),
    )
