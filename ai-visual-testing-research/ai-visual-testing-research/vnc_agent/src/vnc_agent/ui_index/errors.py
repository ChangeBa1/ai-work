"""Validation error model (data-model.md §2)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from vnc_agent.ui_index.models import BundleManifest


class UiIndexErrorCode(StrEnum):
    BUNDLE_DIR_NOT_FOUND = "bundle_dir_not_found"
    SCHEMA_UNSUPPORTED_MAJOR = "schema_unsupported_major"
    MANIFEST_MISSING = "manifest_missing"
    CONTENT_FILE_MISSING = "content_file_missing"
    JSONL_SYNTAX_ERROR = "jsonl_syntax_error"
    FIELD_TYPE_ERROR = "field_type_error"
    DUPLICATE_ID = "duplicate_id"
    DANGLING_REFERENCE = "dangling_reference"
    PARENT_CYCLE = "parent_cycle"
    DANGLING_GUARD_REFERENCE = "dangling_guard_reference"
    MISSING_COORDINATE_SPACE = "missing_coordinate_space"
    COORDINATE_OUT_OF_RANGE = "coordinate_out_of_range"
    INVALID_CONFIDENCE = "invalid_confidence"
    INVALID_DIAGNOSTIC_CONFIDENCE = "invalid_diagnostic_confidence"
    PATH_TRAVERSAL = "path_traversal"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    CHECKSUM_MISMATCH = "checksum_mismatch"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: UiIndexErrorCode
    file: str | None = None
    line: int | None = None
    field_path: str | None = None
    message: str


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    bundle_dir: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    manifest: BundleManifest | None = None
