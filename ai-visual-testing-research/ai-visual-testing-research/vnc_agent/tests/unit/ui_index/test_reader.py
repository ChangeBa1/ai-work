"""T022: reader behavior."""

from __future__ import annotations

from pathlib import Path

from vnc_agent.ui_index.errors import UiIndexErrorCode
from vnc_agent.ui_index.reader import iter_jsonl, read_manifest

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"


def test_read_manifest_valid_minimal():
    manifest, issues = read_manifest(FIXTURES / "valid_minimal")
    assert manifest is not None
    assert not any(i.error_code == UiIndexErrorCode.MANIFEST_MISSING for i in issues)
    assert manifest.bundle_id == "bundle-valid-minimal"


def test_read_manifest_dir_missing(tmp_path: Path):
    manifest, issues = read_manifest(tmp_path / "nope")
    assert manifest is None
    assert issues[0].error_code == UiIndexErrorCode.BUNDLE_DIR_NOT_FOUND


def test_read_manifest_missing_file(tmp_path: Path):
    tmp_path.mkdir(exist_ok=True)
    manifest, issues = read_manifest(tmp_path)
    assert manifest is None
    assert issues[0].error_code == UiIndexErrorCode.MANIFEST_MISSING


def test_iter_jsonl_syntax_error():
    path = FIXTURES / "invalid" / "jsonl_syntax_error" / "screens.jsonl"
    issues = [item for _, item in iter_jsonl(path, max_bytes=10_000_000, max_records=1000) if not isinstance(item, dict)]
    assert any(i.error_code == UiIndexErrorCode.JSONL_SYNTAX_ERROR for i in issues)


def test_iter_jsonl_resource_limits(tmp_path: Path):
    p = tmp_path / "big.jsonl"
    p.write_text('{"a":1}\n{"a":2}\n{"a":3}\n', encoding="utf-8")
    out = list(iter_jsonl(p, max_bytes=10_000_000, max_records=1))
    assert out[-1][1].error_code == UiIndexErrorCode.RESOURCE_LIMIT_EXCEEDED  # type: ignore[union-attr]
