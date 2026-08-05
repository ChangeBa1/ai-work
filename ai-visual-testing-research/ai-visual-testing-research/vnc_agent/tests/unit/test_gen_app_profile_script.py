"""Feature 024 (FR-005c): the offline profile generator.

Uses a SYNTHETIC designer file — the test must not depend on an external
application source tree being present.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from vnc_agent.perception.app_plugins.profile import PluginProfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen_app_profile_from_designer.py"

SYNTHETIC = """
namespace Demo {
    partial class DemoForm {
        private void InitializeComponent() {
            this.btnGo.Anchor = ((System.Windows.Forms.AnchorStyles)(
                (System.Windows.Forms.AnchorStyles.Bottom
                | System.Windows.Forms.AnchorStyles.Right)));
            this.btnGo.Location = new System.Drawing.Point(300, 500);
            this.btnGo.Size = new System.Drawing.Size(75, 23);
            this.btnGo.Text = "Go";
            this.lblTop.Location = new System.Drawing.Point(10, 6);
            this.lblTop.Size = new System.Drawing.Size(48, 12);
            this.lblTop.Text = "Top:";
            this.lblMid.Location = new System.Drawing.Point(12, 56);
            this.lblMid.Size = new System.Drawing.Size(49, 12);
            this.lblMid.Text = "Middle:";
            this.txtInput.Location = new System.Drawing.Point(11, 25);
            this.txtInput.Size = new System.Drawing.Size(356, 19);
            this.noGeometry.Text = "Ignored";
            this.ClientSize = new System.Drawing.Size(400, 560);
            this.Text = "DemoForm";
        }
    }
}
"""


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("gen_app_profile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_app_profile"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def designer(tmp_path):
    path = tmp_path / "DemoForm.Designer.cs"
    path.write_text(SYNTHETIC, encoding="utf-8")
    return path


def test_parses_title_and_client_size(gen, designer):
    title, client_size, controls = gen.parse_designer(designer.read_text(encoding="utf-8"))
    assert title == "DemoForm"
    assert client_size == (400, 560)
    assert {c.name for c in controls} == {"btnGo", "lblTop", "lblMid", "txtInput"}


def test_rects_are_location_plus_size(gen, designer):
    _, _, controls = gen.parse_designer(designer.read_text(encoding="utf-8"))
    by_name = {c.name: c for c in controls}
    assert by_name["lblTop"].rect == (10, 6, 58, 18)
    assert by_name["btnGo"].rect == (300, 500, 375, 523)


def test_anchor_styles_are_captured(gen, designer):
    _, _, controls = gen.parse_designer(designer.read_text(encoding="utf-8"))
    by_name = {c.name: c for c in controls}
    assert set(by_name["btnGo"].anchors) == {"bottom", "right"}
    # WinForms default when no Anchor is assigned.
    assert set(by_name["lblTop"].anchors) == {"top", "left"}


def test_controls_without_geometry_are_skipped(gen, designer):
    _, _, controls = gen.parse_designer(designer.read_text(encoding="utf-8"))
    assert "noGeometry" not in {c.name for c in controls}


def test_generated_profile_validates_against_the_schema(gen, designer, tmp_path):
    out = tmp_path / "demo-window.yaml"
    exit_code = gen.main(
        [str(designer), "--name", "demo-window", "--anchors", "Top:,Middle:,Go", "-o", str(out)]
    )
    assert exit_code == 0
    payload = yaml.safe_load(out.read_text(encoding="utf-8"))
    profile = PluginProfile.model_validate(payload)
    assert profile.name == "demo-window"
    assert profile.required_anchors == ["Top:", "Middle:", "Go"]
    assert profile.source_geometry is not None
    assert profile.source_geometry.client_size == (400, 560)
    go = profile.source_geometry.by_text("Go")
    assert go is not None and set(go.anchors) == {"bottom", "right"}


def test_draft_carries_the_manual_review_checklist(gen, designer, capsys):
    assert gen.main([str(designer), "--name", "demo-window"]) == 0
    out = capsys.readouterr().out
    assert "MANUAL REVIEW REQUIRED" in out
    assert "transform is solved from the anchors OCR actually measured" in out
    assert "Controls with no Text are exported by Name" in out


def test_list_mode_does_not_emit_a_profile(gen, designer, capsys):
    assert gen.main([str(designer), "--list"]) == 0
    out = capsys.readouterr().out
    assert "client_size=400x560" in out
    assert "name:" not in out


def test_missing_client_size_is_an_error(gen, tmp_path, capsys):
    path = tmp_path / "Empty.Designer.cs"
    path.write_text("class X {}", encoding="utf-8")
    assert gen.main([str(path)]) == 2
    assert "no ClientSize" in capsys.readouterr().err


def test_unreadable_file_is_an_error(gen, tmp_path, capsys):
    assert gen.main([str(tmp_path / "nope.cs")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_script_never_writes_to_the_source_tree(gen, designer):
    """The generator is read-only w.r.t. the application sources."""
    before = designer.read_bytes()
    mtime = designer.stat().st_mtime
    gen.main([str(designer), "--name", "demo-window"])
    assert designer.read_bytes() == before
    assert designer.stat().st_mtime == mtime
    assert list(designer.parent.iterdir()) == [designer]
