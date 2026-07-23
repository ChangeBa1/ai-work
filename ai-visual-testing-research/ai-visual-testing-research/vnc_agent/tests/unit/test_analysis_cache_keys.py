"""Phase 4 (T026) RED: AnalysisCacheKey + lookup eligibility
(data-model.md §5-6, perception-cache-contract.md "Lookup contract").

Lookup requires: current frame `deduplicated=true`, `duplicate_of_frame_id`
is the direct predecessor, AND the stored entry's `source_frame_id` matches
that predecessor. Full key fields (content hash, scope, pixel format, mask
identity, perception config fingerprint, component identity) must all match
— any single field mismatch is a miss, even when the frame is otherwise an
eligible adjacent duplicate.
"""

from __future__ import annotations

import pytest

from vnc_agent.perception.cache import AnalysisCacheKey, AnalysisResultCache


def _key(**overrides) -> AnalysisCacheKey:
    base = dict(
        component="ocr",
        algorithm_revision="v1",
        content_hash="c" * 64,
        scope_identity="scope-1",
        pixel_format="uint8:3",
        mask_identity="no-mask-v1",
        perception_config_fingerprint="cfg-1",
        component_identity={"backend": "rapidocr", "version": "1.0", "language": "en"},
    )
    base.update(overrides)
    return AnalysisCacheKey(**base)


def test_same_fields_produce_same_fingerprint():
    a = _key()
    b = _key()
    assert a.fingerprint() == b.fingerprint()


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_hash": "d" * 64},
        {"scope_identity": "scope-2"},
        {"pixel_format": "uint8:1"},
        {"mask_identity": "mask-v2"},
        {"perception_config_fingerprint": "cfg-2"},
        {"component_identity": {"backend": "rapidocr", "version": "2.0", "language": "en"}},
        {"algorithm_revision": "v2"},
        {"component": "template"},
    ],
)
def test_any_field_change_changes_fingerprint(overrides):
    a = _key()
    b = _key(**overrides)
    assert a.fingerprint() != b.fingerprint()


def test_lookup_miss_when_frame_not_deduplicated():
    cache = AnalysisResultCache(max_frames=5)
    key = _key()
    cache.store(key, "result", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    hit = cache.lookup(
        key, frame_deduplicated=False, duplicate_of_frame_id=None, current_sequence=2
    )
    assert hit is None


def test_lookup_miss_when_duplicate_of_frame_id_is_none():
    """Even with `frame_deduplicated=True`, a null `duplicate_of_frame_id`
    is not a valid eligibility signal — ScreenFrame's own invariants never
    produce this combination, but the cache must not trust a partial gate."""
    cache = AnalysisResultCache(max_frames=5)
    key = _key()
    cache.store(key, "result", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    hit = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id=None, current_sequence=2
    )
    assert hit is None


def test_lookup_hit_reuses_original_source_across_a_multi_hop_chain():
    """Frame 3's direct predecessor is frame 2, not the original frame 1 —
    but all three share one identical-pixel key, so frame 3 must still hit
    the entry frame 1 created (perception-cache-contract.md "10 个连续
    duplicate 只保留一份结果")."""
    cache = AnalysisResultCache(max_frames=5)
    key = _key()
    cache.store(key, "result", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    hit_at_2 = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id="f1", current_sequence=2
    )
    assert hit_at_2 is not None
    hit_at_3 = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id="f2", current_sequence=3
    )
    assert hit_at_3 is not None
    assert hit_at_3.source_frame_id == "f1"
    assert hit_at_3.actual_invocation_id == "inv-1"


def test_lookup_hit_when_eligible_and_key_matches():
    cache = AnalysisResultCache(max_frames=5)
    key = _key()
    cache.store(key, "result-value", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    hit = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id="f1", current_sequence=2
    )
    assert hit is not None
    assert hit.result == "result-value"
    assert hit.source_frame_id == "f1"
    assert hit.actual_invocation_id == "inv-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_hash": "d" * 64},
        {"scope_identity": "scope-2"},
        {"pixel_format": "uint8:1"},
        {"mask_identity": "mask-v2"},
        {"perception_config_fingerprint": "cfg-2"},
        {"component_identity": {"backend": "rapidocr", "version": "2.0", "language": "en"}},
    ],
)
def test_lookup_miss_when_any_key_field_differs_despite_eligible_frame(overrides):
    cache = AnalysisResultCache(max_frames=5)
    stored_key = _key()
    cache.store(stored_key, "result", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    query_key = _key(**overrides)
    hit = cache.lookup(
        query_key, frame_deduplicated=True, duplicate_of_frame_id="f1", current_sequence=2
    )
    assert hit is None


def test_cache_max_frames_must_be_three_to_five():
    with pytest.raises(ValueError):
        AnalysisResultCache(max_frames=2)
    with pytest.raises(ValueError):
        AnalysisResultCache(max_frames=6)
    AnalysisResultCache(max_frames=3)
    AnalysisResultCache(max_frames=5)
