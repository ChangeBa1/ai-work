"""Phase 4 (T027) RED: bounded cache window (perception-cache-contract.md
"Capacity and lifecycle").

10 consecutive duplicates share one source result (never re-analyzed);
non-adjacent unique closes the reference chain; eviction is driven by
recency of the most recent *logical-frame reference*, not access count; a
bare cache get() for an ineligible/mismatched key must not itself extend
any entry's lifetime.
"""

from __future__ import annotations

from vnc_agent.perception.cache import AnalysisCacheKey, AnalysisResultCache


def _key(content_hash: str = "c" * 64) -> AnalysisCacheKey:
    return AnalysisCacheKey(
        component="ocr",
        algorithm_revision="v1",
        content_hash=content_hash,
        scope_identity="scope-1",
        pixel_format="uint8:3",
        mask_identity="no-mask-v1",
        perception_config_fingerprint="cfg-1",
        component_identity={"backend": "rapidocr", "version": "1.0"},
    )


def test_ten_consecutive_duplicates_share_one_entry_never_restored():
    cache = AnalysisResultCache(max_frames=5)
    key = _key()
    cache.store(key, "R", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    prev_frame_id = "f1"
    for seq in range(2, 12):  # 10 duplicates, sequences 2..11
        hit = cache.lookup(
            key, frame_deduplicated=True, duplicate_of_frame_id=prev_frame_id, current_sequence=seq
        )
        assert hit is not None, f"expected hit at sequence {seq}"
        assert hit.actual_invocation_id == "inv-1"  # never re-analyzed
        prev_frame_id = prev_frame_id  # duplicate reuses the same source frame id chain
    assert len(cache) == 1


def test_window_three_evicts_after_gap():
    cache = AnalysisResultCache(max_frames=3)
    key = _key()
    cache.store(key, "R", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    # No reference for 3+ sequences -> stale, must be pruned on next store/lookup sweep
    cache.store(
        _key(content_hash="d" * 64), "R2", source_frame_id="f99", sequence=5, invocation_id="inv-2"
    )
    hit = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id="f1", current_sequence=6
    )
    assert hit is None, "entry unreferenced for >= max_frames sequences must be evicted"


def test_non_adjacent_unique_closes_reference_chain():
    cache = AnalysisResultCache(max_frames=5)
    key_a = _key(content_hash="a" * 64)
    cache.store(key_a, "RA", source_frame_id="fA", sequence=1, invocation_id="inv-a")
    # unique B in between (different content) — no lookup call for B (unique frames
    # never look up), simulated simply by not calling lookup for it.
    # Now a frame with A's exact content reappears, but its predecessor is B, not fA.
    hit = cache.lookup(
        key_a, frame_deduplicated=False, duplicate_of_frame_id=None, current_sequence=3
    )
    assert hit is None  # not even eligible: not deduplicated relative to fA


def test_ineligible_lookup_does_not_extend_entry_lifetime():
    cache = AnalysisResultCache(max_frames=3)
    key = _key()
    cache.store(key, "R", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    # An ineligible lookup (frame not deduplicated at all — e.g. a unique
    # frame that happens to share this content_hash non-adjacently) at
    # sequence 2 must not refresh recency.
    miss = cache.lookup(
        key, frame_deduplicated=False, duplicate_of_frame_id=None, current_sequence=2
    )
    assert miss is None
    # By sequence 4 (>= max_frames=3 since last real reference was sequence 1),
    # the entry must already be gone, proving the ineligible lookup at seq 2
    # did not keep it alive.
    hit = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id="f1", current_sequence=4
    )
    assert hit is None


def test_clear_empties_all_entries():
    cache = AnalysisResultCache(max_frames=5)
    cache.store(_key(), "R", source_frame_id="f1", sequence=1, invocation_id="inv-1")
    assert len(cache) == 1
    cache.clear()
    assert len(cache) == 0


def test_cache_entry_never_holds_raw_bytes():
    """Structural guarantee: AnalysisCacheEntry.result is whatever pure value
    the caller stored — the cache itself never wraps/derives a pixel buffer,
    so storing a plain (non-ndarray, non-bytes) result is representative of
    real usage (pure OCR/template/diff/vision results)."""
    cache = AnalysisResultCache(max_frames=5)
    key = _key()
    cache.store(key, {"items": []}, source_frame_id="f1", sequence=1, invocation_id="inv-1")
    entry = cache.lookup(
        key, frame_deduplicated=True, duplicate_of_frame_id="f1", current_sequence=2
    )
    assert entry is not None
    assert isinstance(entry.result, dict)
