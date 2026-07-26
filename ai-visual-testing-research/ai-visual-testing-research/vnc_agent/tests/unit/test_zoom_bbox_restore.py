"""Feature 014 (FR-004 / SC-002): strict zoomed-bbox restoration to original
frame pixel coordinates — scale+offset combos, boundary rejection, identity."""

from __future__ import annotations

import pytest

from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.coordinate_space import restore_original_bbox
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.provider import GroundingRequest


class TestRestoreOriginalBbox:
    def test_identity_when_scale_one_offset_zero(self):
        assert restore_original_bbox((10, 20, 30, 40)) == (10, 20, 30, 40)

    def test_scale_and_offset_combined(self):
        # zoomed bbox (50, 60, 90, 100) at 2x from crop origin (100, 50)
        assert restore_original_bbox(
            (50, 60, 90, 100), scale_factor=2.0, crop_offset=(100, 50)
        ) == (125, 80, 145, 100)

    def test_offset_only(self):
        assert restore_original_bbox(
            (5, 5, 15, 15), crop_offset=(100, 50)
        ) == (105, 55, 115, 65)

    def test_scale_only_with_rounding(self):
        # 3 / 2 = 1.5 → banker-independent round() → 2; 7 / 2 = 3.5 → 4
        assert restore_original_bbox((3, 3, 7, 7), scale_factor=2.0) == (2, 2, 4, 4)

    def test_non_integer_scale(self):
        assert restore_original_bbox((15, 15, 45, 45), scale_factor=1.5) == (
            10,
            10,
            30,
            30,
        )

    def test_degenerate_after_rounding_rejected(self):
        # 1px-wide zoomed box collapses at 4x downscale → reject, never invent
        assert (
            restore_original_bbox((8, 8, 9, 9), scale_factor=4.0) is None
        )

    def test_out_of_original_bounds_rejected_not_clamped(self):
        assert (
            restore_original_bbox(
                (50, 60, 90, 100),
                scale_factor=2.0,
                crop_offset=(280, 180),
                original_resolution=(300, 200),
            )
            is None
        )

    def test_within_original_bounds_accepted(self):
        assert restore_original_bbox(
            (0, 0, 40, 40),
            scale_factor=2.0,
            crop_offset=(280, 180),
            original_resolution=(300, 200),
        ) == (280, 180, 300, 200)

    def test_invalid_scale_rejected(self):
        assert restore_original_bbox((0, 0, 10, 10), scale_factor=0.0) is None
        assert restore_original_bbox((0, 0, 10, 10), scale_factor=-2.0) is None

    def test_negative_result_rejected_by_original_resolution(self):
        # crop_offset cannot be negative in practice, but strictness holds
        assert (
            restore_original_bbox(
                (0, 0, 10, 10),
                scale_factor=1.0,
                crop_offset=(-5, -5),
                original_resolution=(100, 100),
            )
            is None
        )


class TestGrounderLevelRestore:
    """End-to-end through the shared StubGrounder/MimoGrounder finalize path."""

    @pytest.mark.asyncio
    async def test_pixel_space_zoomed_candidate_restored(self):
        stub = StubGrounder(
            GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=(50, 60, 90, 100),
                        coordinate_space="pixel",
                        confidence=0.9,
                    )
                ],
                model_name="stub",
            )
        )
        res = await stub.ground(
            GroundingRequest(
                image_ref="zoom.png",
                crop_offset=(100, 50),
                scale_factor=2.0,
                resolution=(200, 160),  # zoomed image dims
                original_resolution=(300, 200),
                target={"description": "x"},
            )
        )
        assert res.found is True
        assert res.candidates[0].bbox == (125, 80, 145, 100)

    @pytest.mark.asyncio
    async def test_normalized_1000_resolved_against_zoomed_resolution(self):
        # normalized coords are relative to the image the model saw (the zoom)
        stub = StubGrounder(
            GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=(250, 375, 450, 625),
                        coordinate_space="normalized_1000",
                        confidence=0.9,
                    )
                ],
                model_name="stub",
            )
        )
        res = await stub.ground(
            GroundingRequest(
                image_ref="zoom.png",
                crop_offset=(100, 50),
                scale_factor=2.0,
                resolution=(200, 160),
                original_resolution=(300, 200),
                target={"description": "x"},
            )
        )
        # normalized → zoomed pixels: (50, 60, 90, 100) → restore → original
        assert res.found is True
        assert res.candidates[0].bbox == (125, 80, 145, 100)

    @pytest.mark.asyncio
    async def test_restored_out_of_original_bounds_is_rejected(self):
        stub = StubGrounder(
            GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=(180, 140, 200, 160),
                        coordinate_space="pixel",
                        confidence=0.9,
                    )
                ],
                model_name="stub",
            )
        )
        res = await stub.ground(
            GroundingRequest(
                image_ref="zoom.png",
                crop_offset=(250, 150),  # restored x2 = 250+100 > 300
                scale_factor=2.0,
                resolution=(200, 160),
                original_resolution=(300, 200),
                target={"description": "x"},
            )
        )
        assert res.found is False
        assert res.candidates == []
        # audit records the strict rejection
        assert any(
            entry.get("stage") == "zoom_restore" and entry.get("accepted") is False
            for entry in res.coordinate_space_audit
        )

    @pytest.mark.asyncio
    async def test_out_of_zoom_image_bounds_rejected_before_restore(self):
        # bbox exceeding the zoomed image dims is rejected by the existing
        # resolve_pixel_bbox strictness (never reaches restore)
        stub = StubGrounder(
            GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=(150, 150, 260, 170),
                        coordinate_space="pixel",
                        confidence=0.9,
                    )
                ],
                model_name="stub",
            )
        )
        res = await stub.ground(
            GroundingRequest(
                image_ref="zoom.png",
                crop_offset=(0, 0),
                scale_factor=2.0,
                resolution=(200, 160),
                original_resolution=(300, 200),
                target={"description": "x"},
            )
        )
        assert res.found is False

    @pytest.mark.asyncio
    async def test_legacy_full_screen_path_unchanged(self):
        stub = StubGrounder(
            GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=(100, 80, 200, 120),
                        coordinate_space="pixel",
                        confidence=0.9,
                    )
                ],
                model_name="stub",
            )
        )
        res = await stub.ground(
            GroundingRequest(
                image_ref="full.png",
                resolution=(300, 200),
                target={"description": "x"},
            )
        )
        assert res.candidates[0].bbox == (100, 80, 200, 120)
