"""Loaded, queryable bundle (contracts §4; data-model.md §3).

`UiIndexBundle.load()` is the only way to obtain an instance — validation
failure raises `UiIndexValidationError` and never returns a "partially
usable" object. Once constructed, every query surface is read-only,
idempotent and side-effect free.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from vnc_agent.config import UiIndexConfig
from vnc_agent.ui_index.errors import ValidationReport
from vnc_agent.ui_index.models import BundleManifest, Diagnostic, Element, Flow, Screen, Transition
from vnc_agent.ui_index.validator import validate_bundle_with_records


class UiIndexValidationError(Exception):
    """Raised by `UiIndexBundle.load()` when `validate_bundle()` fails."""

    def __init__(self, report: ValidationReport) -> None:
        super().__init__(
            f"UI index bundle at {report.bundle_dir!r} failed validation "
            f"with {len(report.issues)} issue(s)"
        )
        self.report = report


def normalize_text(text: str) -> str:
    """Shared text-normalization rule (lowercase + strip) reused by
    `query.py` inverted indexes and `runtime_adapter.py` screen matching."""
    return text.strip().lower()


class UiIndexBundle:
    def __init__(
        self,
        *,
        bundle_dir: Path,
        manifest: BundleManifest,
        screens: dict[str, Screen],
        elements: dict[str, Element],
        transitions: dict[str, Transition],
        flows: dict[str, Flow],
        diagnostics: dict[str, Diagnostic],
    ) -> None:
        self.bundle_dir = bundle_dir
        self.manifest = manifest
        self.screens = screens
        self.elements = elements
        self.transitions = transitions
        self.flows = flows
        self.diagnostics = diagnostics

        # Inverted indexes (data-model.md §3.1) consumed by query.py.
        self.text_index: dict[str, list[str]] = defaultdict(list)
        self.alias_index: dict[str, list[str]] = defaultdict(list)
        self.role_index: dict[str, list[str]] = defaultdict(list)
        self.screen_elements_index: dict[str, list[str]] = defaultdict(list)
        self.transitions_from_index: dict[str, list[str]] = defaultdict(list)
        self.transitions_trigger_index: dict[str, list[str]] = defaultdict(list)
        self.transitions_to_index: dict[str, list[str]] = defaultdict(list)
        self._build_indexes()

    def _build_indexes(self) -> None:
        for element_id, element in self.elements.items():
            for text in element.visible_texts:
                normalized = normalize_text(text)
                if normalized:
                    self.text_index[normalized].append(element_id)
            for alias in element.aliases:
                normalized = normalize_text(alias)
                if normalized:
                    self.alias_index[normalized].append(element_id)
            self.role_index[element.role].append(element_id)
            self.screen_elements_index[element.screen_id].append(element_id)

        for transition_id, transition in self.transitions.items():
            self.transitions_from_index[transition.from_screen_id].append(transition_id)
            self.transitions_trigger_index[transition.trigger_element_id].append(transition_id)
            self.transitions_to_index[transition.to_screen_id].append(transition_id)

        for index in (
            self.text_index,
            self.alias_index,
            self.role_index,
            self.screen_elements_index,
            self.transitions_from_index,
            self.transitions_trigger_index,
            self.transitions_to_index,
        ):
            for ids in index.values():
                ids.sort()

    @classmethod
    def load(
        cls,
        bundle_dir: str | Path,
        config: UiIndexConfig | None = None,
    ) -> UiIndexBundle:
        """Validate then load; raises `UiIndexValidationError` on any issue —
        never returns a partially-usable instance."""
        cfg = config or UiIndexConfig()
        bundle_path = Path(bundle_dir)
        report, records = validate_bundle_with_records(bundle_path, cfg)
        if not report.ok:
            raise UiIndexValidationError(report)
        assert report.manifest is not None  # ok=True implies manifest parsed
        return cls(
            bundle_dir=bundle_path,
            manifest=report.manifest,
            screens=records.screens,
            elements=records.elements,
            transitions=records.transitions,
            flows=records.flows,
            diagnostics=records.diagnostics,
        )
