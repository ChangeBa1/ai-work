"""Phase 6 (T054): report-level zero-copy safe evidence — rebuilding a
report (simulating the offline/compat re-render entry point) never creates
a new evidence file; tampered/missing evidence renders as an unavailable
notice, never a broken/guessed link; a private model image is never
referenced anywhere in JSON or HTML output.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parent / "images" / "frame_dedup"
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


async def _run_with_iteration(tmp_path: Path, *, mask_regions=(), private_allowed=True):
    test_run = TestRun(
        run_id="dedup-r1", test_case_id="tc", status="passed",
        started_at=datetime.now(UTC), ended_at=datetime.now(UTC),
    )
    store = ArtifactStore(tmp_path)
    svc = FrameCaptureService(
        SequenceDriver(["masked"]), run_id="dedup-r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=store,
        mask_regions=list(mask_regions), private_persistence_allowed=private_allowed,
    )
    o1 = await svc.capture(step_id="s1", capture_source="observation")
    step = StepRecord(step_id="s1", final_status="passed")
    step.iterations.append(
        ActionIteration(
            iteration_index=0, before_frame_id=o1.frame.image_path,
            after_frame_id=o1.frame.image_path,
            verification_result=VerificationResult(status="passed"),
        )
    )
    test_run.steps.append(step)
    return store, test_run, o1.frame


@pytest.mark.asyncio
async def test_rebuilding_report_never_creates_new_evidence_files(tmp_path: Path):
    """Simulates the offline/compat re-render entry point: build twice."""
    store, run, _frame = await _run_with_iteration(tmp_path)
    builder = ReportBuilder(store)
    builder.build(run, formats=("json", "html"))

    bundles_dir = tmp_path / "runs" / "dedup-r1" / "bundles"
    before_files = sorted(p.name for p in bundles_dir.rglob("*.png"))

    builder2 = ReportBuilder(store)
    builder2.build(run, formats=("json", "html"))
    after_files = sorted(p.name for p in bundles_dir.rglob("*.png"))

    assert before_files == after_files
    assert not (tmp_path / "runs" / "dedup-r1" / "report_frames").exists()


@pytest.mark.asyncio
async def test_missing_evidence_renders_unavailable_not_broken_link(tmp_path: Path):
    store, run, frame = await _run_with_iteration(tmp_path)
    Path(frame.safe_image.path).unlink()  # simulate lost evidence

    builder = ReportBuilder(store)
    builder.build(run, formats=("json", "html"))

    data = json.loads(Path(run.report_json_path).read_text(encoding="utf-8"))
    it = data["steps"][0]["iterations"][0]
    assert it["before_frame_path"] is None
    assert it["after_frame_path"] is None
    for f in data["frames"]:
        assert f["safe_image_path"] is None

    html = Path(run.report_html_path).read_text(encoding="utf-8")
    assert 'data-marker="evidence_unavailable"' in html
    assert "<a href=" not in html or "safe_evidence.png" not in html


@pytest.mark.asyncio
async def test_private_model_image_never_appears_in_json_or_html(tmp_path: Path):
    store, run, frame = await _run_with_iteration(
        tmp_path, mask_regions=[[40, 30, 56, 40]], private_allowed=True
    )
    assert frame.model_image is not None
    private_path = frame.model_image.path
    assert "private_model" in private_path

    builder = ReportBuilder(store)
    builder.build(run, formats=("json", "html"))

    json_text = Path(run.report_json_path).read_text(encoding="utf-8")
    html_text = Path(run.report_html_path).read_text(encoding="utf-8")
    assert private_path not in json_text
    assert private_path not in html_text
    # "private_model" alone IS legitimate as an aggregate count key
    # (performance_summary.physical_images_by_purpose) — what must never
    # appear is a private_model.png *path* reference.
    assert "private_model.png" not in json_text
    assert "private_model.png" not in html_text

    data = json.loads(json_text)
    it = data["steps"][0]["iterations"][0]
    assert it["before_frame_path"] is not None
    assert Path(it["before_frame_path"]).name != "private_model.png"
    assert it["after_frame_path"] is not None
    assert Path(it["after_frame_path"]).name != "private_model.png"
    for f in data["frames"]:
        assert (
            f["safe_image_path"] is None
            or Path(f["safe_image_path"]).name != "private_model.png"
        )
    assert data["performance_summary"]["physical_images_by_purpose"].get("private_model") == 1


@pytest.mark.asyncio
async def test_no_private_persistence_reports_null_model_image_and_valid_safe_evidence(
    tmp_path: Path,
):
    store, run, frame = await _run_with_iteration(
        tmp_path, mask_regions=[[40, 30, 56, 40]], private_allowed=False
    )
    assert frame.model_image is None

    builder = ReportBuilder(store)
    builder.build(run, formats=("json",))
    data = json.loads(Path(run.report_json_path).read_text(encoding="utf-8"))
    it = data["steps"][0]["iterations"][0]
    assert it["before_frame_path"] is not None
    assert Path(it["before_frame_path"]).is_file()
