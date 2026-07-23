"""Phase 3 (T015 RED / T025 GREEN): offline fixed-screenshot dedup sequence.

10 identical full-screen captures + 1 single-pixel-changed capture must
produce 11 logical frames / 1 unique / 9 duplicate (only counting the first
10) with the 11th forming a second unique frame, and exactly 2 physical
(unmasked) files. Also covers: ROI vs full-screen scope isolation, different
resolution/pixel-format/mask-identity/private-policy boundaries, run/session
rotation, and non-adjacent frames never deduping.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnc_agent.domain.observation import Region
from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parent / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


class SequenceDriver:
    """Serves fixture PNGs in order; repeats the last one once exhausted."""

    def __init__(self, names: list[str], *, resolution: tuple[int, int] | None = None):
        self._bytes = [(FIXTURES / MANIFEST[n]["file"]).read_bytes() for n in names]
        self._i = 0
        meta = MANIFEST[names[0]]
        self._resolution = resolution or (meta["width"], meta["height"])

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution

    async def capture_screen(self) -> bytes:
        data = self._bytes[min(self._i, len(self._bytes) - 1)]
        self._i += 1
        return data

    async def capture_region(self, x: int, y: int, w: int, h: int) -> bytes:
        return await self.capture_screen()


def _service(
    driver, run_id="r1", session_id="s1", mask_regions=(), private_allowed=True, tmp_path=None
):
    return FrameCaptureService(
        driver,
        run_id=run_id,
        vnc_session_id=session_id,
        test_run=TestRun(run_id=run_id, test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
        mask_regions=mask_regions,
        private_persistence_allowed=private_allowed,
    )


@pytest.mark.asyncio
async def test_ten_identical_plus_one_changed(tmp_path: Path):
    names = ["baseline_full"] * 10 + ["single_pixel_changed"]
    driver = SequenceDriver(names)
    svc = _service(driver, tmp_path=tmp_path)

    outcomes = []
    for _ in range(11):
        outcomes.append(await svc.capture(step_id="s1", capture_source="observation"))

    frames = [o.frame for o in outcomes]
    assert len(frames) == 11
    unique = [f for f in frames if not f.deduplicated]
    duplicate = [f for f in frames if f.deduplicated]
    assert len(unique) == 2
    assert len(duplicate) == 9

    # frame ids/timestamps independent even though physical file is shared
    assert len({f.id for f in frames}) == 11
    assert len({f.capture_sequence for f in frames}) == 11

    # duplicate_of points to the immediately preceding logical frame
    for i in range(1, 10):
        assert frames[i].duplicate_of_frame_id == frames[i - 1].id

    # exactly 2 unmasked physical files on disk
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    png_files = list(bundles_dir.rglob("safe_evidence.png"))
    assert len(png_files) == 2

    # duplicates share the exact same safe path as their source
    assert frames[1].safe_image.path == frames[0].safe_image.path
    assert frames[10].safe_image.path != frames[0].safe_image.path


@pytest.mark.asyncio
async def test_roi_does_not_dedup_against_full_screen_even_with_matching_pixels(tmp_path: Path):
    driver = SequenceDriver(["baseline_full", "baseline_full"])
    svc = _service(driver, tmp_path=tmp_path)
    full = await svc.capture(step_id="s1", capture_source="observation")
    roi = await svc.capture(
        step_id="s1", capture_source="observation", roi=Region(x1=0, y1=0, x2=10, y2=10)
    )
    assert full.frame.deduplicated is False
    assert roi.frame.deduplicated is False  # different scope: full_screen vs roi


@pytest.mark.asyncio
async def test_different_resolution_pixel_format_and_mask_identity_do_not_dedup(tmp_path: Path):
    driver_res = SequenceDriver(["baseline_full", "diff_resolution"])
    svc = _service(driver_res, tmp_path=tmp_path)
    a = await svc.capture(step_id="s1", capture_source="observation")
    b = await svc.capture(step_id="s1", capture_source="observation")
    assert a.frame.deduplicated is False
    assert b.frame.deduplicated is False

    driver_gray = SequenceDriver(["baseline_full", "grayscale"])
    svc2 = _service(driver_gray, tmp_path=tmp_path / "gray")
    a2 = await svc2.capture(step_id="s1", capture_source="observation")
    b2 = await svc2.capture(step_id="s1", capture_source="observation")
    assert b2.frame.deduplicated is False
    assert a2.frame.scope.pixel_format != b2.frame.scope.pixel_format


@pytest.mark.asyncio
async def test_mask_identity_change_breaks_dedup(tmp_path: Path):
    from vnc_agent.perception.screenshot import compute_mask_identity

    driver = SequenceDriver(["baseline_full", "baseline_full"])
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
        mask_regions=[],
    )
    first = await svc.capture(step_id="s1", capture_source="observation")
    svc.mask_regions = [[0, 0, 5, 5]]
    svc._mask_identity = compute_mask_identity(svc.mask_regions)
    second = await svc.capture(step_id="s1", capture_source="observation")
    assert first.frame.scope.mask_identity != second.frame.scope.mask_identity
    assert second.frame.deduplicated is False


@pytest.mark.asyncio
async def test_private_persistence_forbidden_writes_safe_only_and_no_model_image(tmp_path: Path):
    driver = SequenceDriver(["masked", "masked"])
    svc = _service(
        driver, mask_regions=[[40, 30, 56, 40]], private_allowed=False, tmp_path=tmp_path
    )
    outcome = await svc.capture(step_id="s1", capture_source="observation")
    assert outcome.frame.model_image is None
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    private_files = list(bundles_dir.rglob("private_model.png"))
    assert private_files == []


@pytest.mark.asyncio
async def test_run_session_rotation_clears_previous(tmp_path: Path):
    driver = SequenceDriver(["baseline_full", "baseline_full"])
    svc = _service(driver, tmp_path=tmp_path)
    await svc.capture(step_id="s1", capture_source="observation")
    svc.clear()
    second = await svc.capture(step_id="s1", capture_source="observation")
    assert second.frame.deduplicated is False
    assert second.frame.comparison_available is False
    assert second.frame.changed_since_last is None


@pytest.mark.asyncio
async def test_non_adjacent_a_b_a_does_not_dedup(tmp_path: Path):
    driver = SequenceDriver(["baseline_full", "single_pixel_changed", "baseline_full"])
    svc = _service(driver, tmp_path=tmp_path)
    a1 = await svc.capture(step_id="s1", capture_source="observation")
    b = await svc.capture(step_id="s1", capture_source="observation")
    a2 = await svc.capture(step_id="s1", capture_source="observation")
    assert a1.frame.deduplicated is False
    assert b.frame.deduplicated is False
    assert a2.frame.deduplicated is False  # A is no longer adjacent to a2
    assert a2.frame.duplicate_of_frame_id is None


@pytest.mark.asyncio
async def test_five_capture_sources_all_enter_same_global_trace(tmp_path: Path):
    names = ["baseline_full"] * 5
    driver = SequenceDriver(names)
    svc = _service(driver, tmp_path=tmp_path)
    sources = ["observation", "stability_wait", "retry", "recovery", "post_action_verification"]
    for src in sources:
        await svc.capture(step_id="s1", capture_source=src)
    trace_sources = {f.capture_source for f in svc.test_run.frames}
    assert trace_sources == set(sources)
    assert [f.capture_sequence for f in svc.test_run.frames] == [1, 2, 3, 4, 5]
