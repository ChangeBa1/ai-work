"""Phase 5 (T041) RED->GREEN: PerformanceSummary derivation from
TestRun.frames + counter_events (data-model.md §11, telemetry-contract.md
"Counter definitions" + "Conservation checks").

`physical_image_count` only counts `physical_image_written` events that
belong to a REFERENCED bundle (i.e. whose frame successfully committed in
the same TestRun update); staging/quarantined/orphan bundles never
contribute, even if a physical_image_written-shaped event exists for them.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.runtime.telemetry import derive_performance_summary
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


class SequenceDriver:
    def __init__(self, names: list[str]):
        self._bytes = [(FIXTURES / MANIFEST[n]["file"]).read_bytes() for n in names]
        self._i = 0
        meta = MANIFEST[names[0]]
        self._resolution = (meta["width"], meta["height"])

    @property
    def resolution(self):
        return self._resolution

    async def capture_screen(self) -> bytes:
        data = self._bytes[min(self._i, len(self._bytes) - 1)]
        self._i += 1
        return data

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


@pytest.mark.asyncio
async def test_ten_identical_plus_one_changed_summary_conservation(tmp_path: Path):
    names = ["baseline_full"] * 10 + ["single_pixel_changed"]
    driver = SequenceDriver(names)
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1", test_run=test_run,
        artifact_store=ArtifactStore(tmp_path),
    )
    for _ in range(11):
        await svc.capture(step_id="s1", capture_source="observation")

    summary = derive_performance_summary(test_run)
    assert summary.total_capture_count == 11
    assert summary.unique_frame_count == 2
    assert summary.duplicate_frame_count == 9
    assert summary.dedup_ratio == pytest.approx(9 / 11)
    assert summary.physical_image_count == 2
    assert summary.physical_images_by_purpose.get("safe_evidence") == 2
    assert summary.physical_images_by_purpose.get("report_copy", 0) == 0
    assert summary.avoided_write_count == 9
    assert summary.avoided_write_bytes > 0
    assert not summary.check_conservation()
    assert summary.completeness == "complete"


def test_dedup_ratio_null_and_conservation_ok_for_zero_captures():
    test_run = TestRun(run_id="r1", test_case_id="tc")
    summary = derive_performance_summary(test_run)
    assert summary.total_capture_count == 0
    assert summary.dedup_ratio is None
    assert summary.physical_image_count == 0
    assert not summary.check_conservation()


@pytest.mark.asyncio
async def test_quarantined_orphan_bundle_never_counted_as_physical(tmp_path: Path):
    """A published-but-never-referenced bundle (simulated recovery
    scenario) must not contribute to physical_image_count even though a
    physical_image_written-shaped event could theoretically exist for it —
    here we prove the derivation only trusts events tied to a frame that
    is actually present in TestRun.frames."""
    from vnc_agent.runtime.telemetry import CounterEvent

    test_run = TestRun(run_id="r1", test_case_id="tc")
    # A forged physical_image_written event with no corresponding frame in
    # TestRun.frames — simulating an orphaned/quarantined bundle's ghost event.
    test_run.counter_events.append(
        CounterEvent(
            kind="physical_image_written",
            occurred_at=datetime.now(UTC),
            payload={
                "physical_image_id": "ghost-1",
                "purpose": "safe_evidence",
                "byte_size": 999,
                "frame_id": "frame-that-does-not-exist",
            },
        )
    )
    summary = derive_performance_summary(test_run)
    assert summary.physical_image_count == 0
    assert summary.consistency_errors, "an unreferenced physical event must be flagged"
    assert summary.completeness == "partial"
