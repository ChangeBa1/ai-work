"""E2E: sensitive region masking for local artifacts only (FR-049 / T099)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.storage.artifact_store import ArtifactStore
from tests.e2e.conftest import FakeVNC, build_runtime


def test_mask_blacks_out_region(tmp_path: Path):
    img = np.full((50, 50, 3), 255, dtype=np.uint8)
    src = tmp_path / "raw.png"
    cv2.imwrite(str(src), img)
    store = ArtifactStore(tmp_path / "art", mask_regions=[[10, 10, 30, 30]])
    masked_path = store.mask_image_file(src, tmp_path / "masked.png")
    masked = cv2.imread(masked_path)
    # Center of mask should be black
    assert list(masked[20, 20]) == [0, 0, 0]
    # Outside remains white
    assert list(masked[0, 0]) == [255, 255, 255]
    # Original untouched
    orig = cv2.imread(str(src))
    assert list(orig[20, 20]) == [255, 255, 255]


@pytest.mark.asyncio
async def test_frames_dir_is_masked_model_path_is_not(
    tmp_path: Path, app_config, simple_case
):
    """T099: frames/ local persistence is masked; frames_model/ stays unmasked."""
    # White frame so black mask is obvious
    white = np.full((100, 100, 3), 255, dtype=np.uint8)
    drv = FakeVNC([white])
    # Inject mask into config-driven path via pipeline (build_runtime must accept it)
    from vnc_agent.models.planner_client import StubPlanner
    from vnc_agent.models.mimo_grounder import StubGrounder
    from vnc_agent.domain.action import SemanticAction
    from vnc_agent.perception.pipeline import ObservationPipeline
    from vnc_agent.perception.stability import StabilityEngine
    from vnc_agent.reporting.report_builder import ReportBuilder
    from vnc_agent.runtime.agent_runtime import AgentRuntime
    from vnc_agent.storage.artifact_store import ArtifactStore
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory
    from vnc_agent.storage.repositories import RunRepository

    mask = [[10, 10, 40, 40]]
    engine = make_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    store = ArtifactStore(tmp_path / "artifacts", mask_regions=mask)
    pipeline = ObservationPipeline(
        drv,
        artifacts_dir=tmp_path / "artifacts",
        planner=StubPlanner(
            action=SemanticAction(
                action_id="a", intent="esc", action_type="press_key", keys=["escape"]
            )
        ),
        ocr_enabled=False,
        template_enabled=False,
        vision_fallback=False,
        mask_regions=mask,
    )
    stability = StabilityEngine(
        drv,
        artifacts_dir=tmp_path / "artifacts",
        min_delay_ms=5,
        max_delay_ms=40,
        capture_interval_ms=5,
        stable_frame_count=2,
        pixel_diff_threshold=0.5,
        security_mask_regions=mask,
    )
    runtime = AgentRuntime(
        config=app_config,
        driver=drv,
        planner=StubPlanner(
            action=SemanticAction(
                action_id="a", intent="esc", action_type="press_key", keys=["escape"]
            )
        ),
        grounder=StubGrounder(),
        pipeline=pipeline,
        stability=stability,
        repo=repo,
        report_builder=ReportBuilder(store),
    )
    ctx = await runtime.run(simple_case)
    frames = list((tmp_path / "artifacts" / "runs" / ctx.run_id / "frames").glob("*.png"))
    model_frames = list(
        (tmp_path / "artifacts" / "runs" / ctx.run_id / "frames_model").glob("*.png")
    )
    assert frames, "expected masked local frames/"
    assert model_frames, "expected unmasked frames_model/ for model API"
    local = cv2.imread(str(frames[0]))
    model = cv2.imread(str(model_frames[0]))
    # Masked region black in frames/
    assert list(local[20, 20]) == [0, 0, 0]
    # Same region still white in frames_model/
    assert list(model[20, 20]) == [255, 255, 255]
