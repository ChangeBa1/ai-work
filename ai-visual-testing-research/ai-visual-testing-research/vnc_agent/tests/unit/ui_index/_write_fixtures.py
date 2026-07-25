"""One-shot fixture writer for ui_index tests (not a pytest module)."""

from __future__ import annotations

import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"


def write(rel: str, files: dict[str, str]) -> None:
    d = BASE / rel
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for name, content in files.items():
        (d / name).write_text(content, encoding="utf-8", newline="\n")


def copy_valid(rel: str) -> Path:
    src = BASE / "valid_minimal"
    dst = BASE / rel
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def main() -> None:
    write(
        "valid_minimal",
        {
            "manifest.yaml": """\
schema_version: "1.0"
bundle_id: "bundle-valid-minimal"
project_id: "demo-project"
generated_at: "2026-07-25T09:00:00Z"
producer:
  name: "fixture-generator"
  version: "0.1.0"
source_revision: "fixture:v1"
frameworks: []
coordinate_spaces: ["normalized_1000"]
default_viewports:
  - name: "desktop"
    width: 1920
    height: 1080
content_files:
  manifest.yaml: {required: true, sha256: null, record_count: null}
  screens.jsonl: {required: true, sha256: null, record_count: null}
  elements.jsonl: {required: true, sha256: null, record_count: null}
  transitions.jsonl: {required: true, sha256: null, record_count: null}
metadata: {}
""",
            "screens.jsonl": (
                '{"screen_id": "screen.home", "name": "Home", "screen_type": "page", '
                '"visible_titles": ["Home"], "aliases": [], "parent_screen_id": null, '
                '"confidence": {"level": "confirmed", "score": 0.95}}\n'
            ),
            "elements.jsonl": (
                '{"element_id": "el.home.ok", "screen_id": "screen.home", '
                '"parent_element_id": null, "name": "OK", "role": "button", '
                '"visible_texts": ["OK"], "aliases": [], "supported_actions": ["click"], '
                '"region": "body", "normalized_bounds": {"coordinate_space": "normalized_1000", '
                '"x1": 400, "y1": 400, "x2": 600, "y2": 500}, "anchors": [], "neighbors": [], '
                '"confidence": {"level": "visually_confirmed", "score": 0.8}}\n'
            ),
            "transitions.jsonl": (
                '{"transition_id": "tr.home.self", "from_screen_id": "screen.home", '
                '"trigger_element_id": "el.home.ok", "trigger_action": "click", "guards": [], '
                '"to_screen_id": "screen.home", "transition_type": "state_change", '
                '"expected_visible": [], "expected_hidden": [], "expected_state_changes": [], '
                '"confidence": {"level": "confirmed", "score": 0.9}}\n'
            ),
        },
    )

    write(
        "fixture_form_input",
        {
            "manifest.yaml": """\
schema_version: "1.0"
bundle_id: "bundle-form-input"
project_id: "form-demo"
generated_at: "2026-07-25T10:00:00Z"
producer:
  name: "fixture-generator"
  version: "0.1.0"
source_revision: "fixture:form"
frameworks: ["generic_web"]
coordinate_spaces: ["normalized_1000"]
content_files:
  manifest.yaml: {required: true, sha256: null, record_count: null}
  screens.jsonl: {required: true, sha256: null, record_count: 2}
  elements.jsonl: {required: true, sha256: null, record_count: 3}
  transitions.jsonl: {required: true, sha256: null, record_count: 1}
  flows.jsonl: {required: false, sha256: null, record_count: 1}
metadata: {}
""",
            "screens.jsonl": (
                '{"screen_id": "screen.form_edit", "name": "Edit Form", "screen_type": "page", '
                '"visible_titles": ["Contact Form", "Edit Details"], "aliases": ["Form Page"], '
                '"parent_screen_id": null, "confidence": {"level": "confirmed", "score": 0.9}}\n'
                '{"screen_id": "screen.form_done", "name": "Submitted", "screen_type": "page", '
                '"visible_titles": ["Thank You", "Submission Complete"], "aliases": [], '
                '"parent_screen_id": null, "confidence": {"level": "confirmed", "score": 0.9}}\n'
            ),
            "elements.jsonl": (
                '{"element_id": "el.form.name_field", "screen_id": "screen.form_edit", '
                '"parent_element_id": null, "name": "Name", "role": "text_field", '
                '"visible_texts": ["Name", "Full name"], "aliases": ["Your name"], '
                '"supported_actions": ["type_text", "focus"], "region": "body", '
                '"normalized_bounds": {"coordinate_space": "normalized_1000", "x1": 200, '
                '"y1": 300, "x2": 800, "y2": 360}, "anchors": [], '
                '"neighbors": [{"direction": "down", "element_id": "el.form.submit_btn"}], '
                '"confidence": {"level": "visually_confirmed", "score": 0.85}}\n'
                '{"element_id": "el.form.submit_btn", "screen_id": "screen.form_edit", '
                '"parent_element_id": null, "name": "Submit", "role": "button", '
                '"visible_texts": ["Submit", "Send"], "aliases": [], '
                '"supported_actions": ["click"], "region": "footer", '
                '"normalized_bounds": {"coordinate_space": "normalized_1000", "x1": 620, '
                '"y1": 900, "x2": 780, "y2": 960}, "anchors": ["el.form.name_field"], '
                '"neighbors": [{"direction": "up", "element_id": "el.form.name_field"}], '
                '"confidence": {"level": "confirmed", "score": 0.95}}\n'
                '{"element_id": "el.done.close", "screen_id": "screen.form_done", '
                '"parent_element_id": null, "name": "Close", "role": "button", '
                '"visible_texts": ["Close"], "aliases": [], "supported_actions": ["click"], '
                '"region": "footer", "confidence": {"level": "visually_confirmed", "score": 0.7}}\n'
            ),
            "transitions.jsonl": (
                '{"transition_id": "tr.form.submit", "from_screen_id": "screen.form_edit", '
                '"trigger_element_id": "el.form.submit_btn", "trigger_action": "click", '
                '"guards": [{"element_id": "el.form.submit_btn", "condition": "enabled"}], '
                '"to_screen_id": "screen.form_done", "transition_type": "replace", '
                '"expected_visible": ["Thank You"], "expected_hidden": ["Contact Form"], '
                '"expected_state_changes": [], "confidence": {"level": "confirmed", "score": 0.9}}\n'
            ),
            "flows.jsonl": (
                '{"flow_id": "flow.form_submit", "name": "Submit contact form", '
                '"start_screen_id": "screen.form_edit", '
                '"steps": [{"transition_id": "tr.form.submit"}], '
                '"completion_screen_id": "screen.form_done", "preconditions": [], '
                '"confidence": {"level": "statically_inferred", "score": 0.6}}\n'
            ),
        },
    )

    write(
        "fixture_icon_overlay",
        {
            "manifest.yaml": """\
schema_version: "1.0"
bundle_id: "bundle-icon-overlay"
project_id: "desktop-shell"
generated_at: "2026-07-25T11:00:00Z"
producer:
  name: "fixture-generator"
  version: "0.1.0"
source_revision: "fixture:icon"
frameworks: ["generic_desktop"]
coordinate_spaces: ["normalized_1000"]
content_files:
  manifest.yaml: {required: true, sha256: null, record_count: null}
  screens.jsonl: {required: true, sha256: null, record_count: 2}
  elements.jsonl: {required: true, sha256: null, record_count: 3}
  transitions.jsonl: {required: true, sha256: null, record_count: 1}
metadata: {}
""",
            "screens.jsonl": (
                '{"screen_id": "screen.workspace", "name": "Workspace", "screen_type": "page", '
                '"visible_titles": ["Workspace", "Main Canvas"], "aliases": ["Desk"], '
                '"parent_screen_id": null, "confidence": {"level": "confirmed", "score": 0.9}}\n'
                '{"screen_id": "screen.help_modal", "name": "Help Overlay", "screen_type": "modal", '
                '"visible_titles": ["Quick Help"], "aliases": [], '
                '"parent_screen_id": "screen.workspace", '
                '"confidence": {"level": "visually_confirmed", "score": 0.8}}\n'
            ),
            "elements.jsonl": (
                '{"element_id": "el.ws.help_icon", "screen_id": "screen.workspace", '
                '"parent_element_id": null, "name": "Help", "role": "icon_button", '
                '"visible_texts": [], "aliases": ["help"], '
                '"supported_actions": ["click", "hover"], "region": "toolbar", '
                '"normalized_bounds": {"coordinate_space": "normalized_1000", "x1": 920, '
                '"y1": 20, "x2": 980, "y2": 80}, "anchors": [], '
                '"neighbors": [{"direction": "left", "element_id": "el.ws.settings_icon"}], '
                '"confidence": {"level": "visually_confirmed", "score": 0.75}}\n'
                '{"element_id": "el.ws.settings_icon", "screen_id": "screen.workspace", '
                '"parent_element_id": null, "name": "Settings", "role": "icon_button", '
                '"visible_texts": [], "aliases": ["gear"], "supported_actions": ["click"], '
                '"region": "toolbar", "anchors": ["el.ws.help_icon"], '
                '"neighbors": [{"direction": "right", "element_id": "el.ws.help_icon"}], '
                '"confidence": {"level": "confirmed", "score": 0.8}}\n'
                '{"element_id": "el.help.dismiss", "screen_id": "screen.help_modal", '
                '"parent_element_id": null, "name": "Dismiss", "role": "button", '
                '"visible_texts": ["Got it"], "aliases": [], "supported_actions": ["click"], '
                '"region": "modal", "confidence": {"level": "confirmed", "score": 0.9}}\n'
            ),
            "transitions.jsonl": (
                '{"transition_id": "tr.ws.open_help", "from_screen_id": "screen.workspace", '
                '"trigger_element_id": "el.ws.help_icon", "trigger_action": "click", '
                '"guards": [], "to_screen_id": "screen.help_modal", '
                '"transition_type": "overlay", "expected_visible": ["Quick Help"], '
                '"expected_hidden": [], "expected_state_changes": [], '
                '"confidence": {"level": "confirmed", "score": 0.85}}\n'
            ),
        },
    )

    # Invalid fixtures T013-T021
    d = copy_valid("invalid/unsupported_version")
    text = (d / "manifest.yaml").read_text(encoding="utf-8")
    (d / "manifest.yaml").write_text(
        text.replace('schema_version: "1.0"', 'schema_version: "2.0"'), encoding="utf-8"
    )

    d = copy_valid("invalid/missing_file")
    (d / "elements.jsonl").unlink()

    d = copy_valid("invalid/jsonl_syntax_error")
    with (d / "screens.jsonl").open("a", encoding="utf-8") as f:
        f.write("NOT_JSON\n")

    d = copy_valid("invalid/duplicate_id")
    with (d / "elements.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            '{"element_id": "el.home.ok", "screen_id": "screen.home", '
            '"parent_element_id": null, "name": "Dup", "role": "button", '
            '"visible_texts": ["Dup"], "aliases": [], "supported_actions": ["click"], '
            '"region": "body", "confidence": {"level": "confirmed", "score": 0.5}}\n'
        )

    d = copy_valid("invalid/missing_reference")
    (d / "transitions.jsonl").write_text(
        '{"transition_id": "tr.home.self", "from_screen_id": "screen.home", '
        '"trigger_element_id": "el.home.ok", "trigger_action": "click", "guards": [], '
        '"to_screen_id": "screen.missing", "transition_type": "state_change", '
        '"expected_visible": [], "expected_hidden": [], "expected_state_changes": [], '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )

    d = copy_valid("invalid/invalid_coordinates")
    (d / "elements.jsonl").write_text(
        '{"element_id": "el.home.ok", "screen_id": "screen.home", '
        '"parent_element_id": null, "name": "OK", "role": "button", '
        '"visible_texts": ["OK"], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "normalized_bounds": {"x1": 400, "y1": 400, "x2": 600, "y2": 500}, '
        '"anchors": [], "neighbors": [], '
        '"confidence": {"level": "visually_confirmed", "score": 0.8}}\n'
        '{"element_id": "el.home.bad", "screen_id": "screen.home", '
        '"parent_element_id": null, "name": "Bad", "role": "button", '
        '"visible_texts": ["Bad"], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "normalized_bounds": {"coordinate_space": "normalized_1000", '
        '"x1": 600, "y1": 400, "x2": 400, "y2": 500}, "anchors": [], "neighbors": [], '
        '"confidence": {"level": "visually_confirmed", "score": 0.8}}\n',
        encoding="utf-8",
    )

    d = copy_valid("invalid/invalid_confidence")
    (d / "elements.jsonl").write_text(
        '{"element_id": "el.home.ok", "screen_id": "screen.home", '
        '"parent_element_id": null, "name": "OK", "role": "button", '
        '"visible_texts": ["OK"], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "confidence": {"level": "not_a_level", "score": 0.5}}\n'
        '{"element_id": "el.home.hi", "screen_id": "screen.home", '
        '"parent_element_id": null, "name": "Hi", "role": "button", '
        '"visible_texts": ["Hi"], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "confidence": {"level": "confirmed", "score": 1.5}}\n',
        encoding="utf-8",
    )

    d = copy_valid("invalid/checksum_mismatch")
    text = (d / "manifest.yaml").read_text(encoding="utf-8")
    (d / "manifest.yaml").write_text(
        text.replace(
            "screens.jsonl: {required: true, sha256: null, record_count: null}",
            'screens.jsonl: {required: true, sha256: '
            '"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", '
            "record_count: null}",
        ),
        encoding="utf-8",
    )

    d = copy_valid("invalid/path_traversal")
    text = (d / "manifest.yaml").read_text(encoding="utf-8")
    (d / "manifest.yaml").write_text(
        text.replace(
            "transitions.jsonl: {required: true, sha256: null, record_count: null}",
            "transitions.jsonl: {required: true, sha256: null, record_count: null}\n"
            '  "../outside.jsonl": {required: false, sha256: null, record_count: null}',
        ),
        encoding="utf-8",
    )
    (BASE.parent / "outside.jsonl").write_text("{}\n", encoding="utf-8")

    print("wrote fixtures under", BASE)


if __name__ == "__main__":
    main()
