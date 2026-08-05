"""Feature 024 (FR-002/SC-008): declarative profile schema + plugin registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vnc_agent.perception.app_plugins.detector import DeclarativeSubWindowPlugin
from vnc_agent.perception.app_plugins.profile import (
    PluginProfile,
    ProfileError,
    load_profile,
)
from vnc_agent.perception.app_plugins.registry import (
    DuplicatePluginError,
    PluginRegistry,
)

MINIMAL = {"name": "demo-window", "required_anchors": ["Alpha:", "Beta:"]}


def write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def test_minimal_profile_loads_and_defaults_to_all_anchors(tmp_path):
    profile = load_profile(write(tmp_path, "demo", MINIMAL))
    assert profile.name == "demo-window"
    assert profile.anchor_hits_required() == 2
    # No core shape defaults: unset means "no per-window constraint at all".
    assert profile.area_ratio_range is None
    assert profile.aspect_ratio_range is None
    assert profile.min_size_px is None
    assert profile.scale_override() is None


def test_min_required_anchor_hits_can_relax_the_requirement(tmp_path):
    profile = load_profile(
        write(tmp_path, "demo", {**MINIMAL, "min_required_anchor_hits": 1})
    )
    assert profile.anchor_hits_required() == 1


@pytest.mark.parametrize(
    "payload, needle",
    [
        ({**MINIMAL, "required_anchors": []}, "required_anchors"),
        ({**MINIMAL, "name": "Bad Name"}, "name"),
        ({**MINIMAL, "min_required_anchor_hits": 5}, "min_required_anchor_hits"),
        ({**MINIMAL, "area_ratio_range": [0.7, 0.2]}, "area_ratio_range"),
        ({**MINIMAL, "aspect_ratio_range": [2.0, 1.0]}, "aspect_ratio_range"),
        ({**MINIMAL, "zoom": {"scale": 0.5}}, "zoom"),
        (
            {
                **MINIMAL,
                "anchor_constraints": [
                    {"subject": "x", "relation": "between", "anchors": ["only-one"]}
                ],
            },
            "anchor",
        ),
        (
            {**MINIMAL, "source_geometry": {"client_size": [0, 10], "controls": []}},
            "client_size",
        ),
    ],
    ids=[
        "no-anchors",
        "bad-name",
        "hits-exceed-anchors",
        "inverted-area-range",
        "inverted-aspect-range",
        "scale-not-magnifying",
        "between-needs-two-anchors",
        "non-positive-client-size",
    ],
)
def test_invalid_profiles_are_rejected_at_load_time(tmp_path, payload, needle):
    path = write(tmp_path, "bad", payload)
    with pytest.raises(ProfileError) as excinfo:
        load_profile(path)
    message = str(excinfo.value)
    assert str(path) in message, "error must name the offending file"
    assert needle in message, f"error must point at the field ({needle}): {message}"


def test_missing_file_and_malformed_yaml_are_profile_errors(tmp_path):
    with pytest.raises(ProfileError):
        load_profile(tmp_path / "nope.yaml")
    broken = tmp_path / "broken.yaml"
    broken.write_text("name: [unclosed\n", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(broken)
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("just-a-string\n", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(scalar)


def test_registry_loads_directory_and_sorts_names(tmp_path):
    write(tmp_path, "b", {**MINIMAL, "name": "beta-window"})
    write(tmp_path, "a", {**MINIMAL, "name": "alpha-window"})
    registry = PluginRegistry.from_profiles_dir(tmp_path)
    assert registry.names() == ["alpha-window", "beta-window"]
    assert registry.get("alpha-window") is not None
    assert registry.get("missing") is None


def test_missing_profiles_dir_yields_empty_registry_not_an_error(tmp_path):
    """"No profiles installed on this machine" is a normal state; the whole
    feature then degrades to the unchanged full-frame path."""
    registry = PluginRegistry.from_profiles_dir(tmp_path / "does-not-exist")
    assert len(registry) == 0
    assert registry.names() == []


def test_duplicate_plugin_names_are_fatal(tmp_path):
    write(tmp_path, "one", {**MINIMAL, "name": "same-window"})
    write(tmp_path, "two", {**MINIMAL, "name": "same-window"})
    with pytest.raises(ProfileError):
        PluginRegistry.from_profiles_dir(tmp_path)

    registry = PluginRegistry()
    registry.register(DeclarativeSubWindowPlugin(PluginProfile.model_validate(MINIMAL)))
    with pytest.raises(DuplicatePluginError):
        registry.register(
            DeclarativeSubWindowPlugin(PluginProfile.model_validate(MINIMAL))
        )


def test_invalid_profile_in_directory_is_fatal_not_silently_skipped(tmp_path):
    """A broken profile must fail loudly at load time — silently skipping it
    would look exactly like a correctly undeclared step at run time."""
    write(tmp_path, "ok", MINIMAL)
    write(tmp_path, "bad", {"name": "x", "required_anchors": []})
    with pytest.raises(ProfileError):
        PluginRegistry.from_profiles_dir(tmp_path)


# --- the shipped profiles must stay valid ---------------------------------

SHIPPED = Path(__file__).resolve().parents[2] / "profiles" / "app_perception"


@pytest.mark.parametrize("path", sorted(SHIPPED.glob("*.yaml")), ids=lambda p: p.stem)
def test_shipped_profiles_are_valid(path):
    profile = load_profile(path)
    assert profile.name == path.stem, "file name should match the profile name"


def test_shipped_profiles_cover_unrelated_window_shapes():
    """Constitution VI: the generic capability is validated against two
    unrelated windows — here, deliberately opposite aspect ratios."""
    profiles = [load_profile(p) for p in sorted(SHIPPED.glob("*.yaml"))]
    with_geometry = [p for p in profiles if p.source_geometry]
    assert len(with_geometry) >= 2
    aspects = [
        p.source_geometry.client_size[0] / p.source_geometry.client_size[1]
        for p in with_geometry
    ]
    assert min(aspects) < 1.0 < max(aspects), (
        f"expected both a tall and a wide window, got aspects {aspects}"
    )
