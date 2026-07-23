"""Canonical normalized-pixel content hash (data-model.md §2 "Canonical hash preimage").

The preimage is::

    frame-pixels-v1 || width || height || canonical pixel_format ||
    C-contiguous unmasked normalized pixel bytes

``width``/``height`` are encoded as fixed-width big-endian 8-byte unsigned
integers; ``pixel_format`` is length-prefixed UTF-8. This module has no
dependency on capture/artifact/dedup machinery so both offline fixture
generation and the production capture path compute byte-identical hashes.
"""

from __future__ import annotations

import hashlib

import numpy as np

_HASH_VERSION_TAG = b"frame-pixels-v1"


def canonical_pixel_format(array: np.ndarray) -> str:
    """Stable format string derived from dtype + channel count.

    Two arrays with the same shape/dtype/channel-order produce the same
    string; capture kind, ROI coordinates, resolution and mask identity are
    intentionally excluded (data-model.md §2).
    """
    channels = 1 if array.ndim == 2 else array.shape[2]
    return f"{array.dtype.str}:{channels}"


def normalize_c_contiguous(array: np.ndarray) -> np.ndarray:
    """Return a read-only, C-contiguous copy of ``array``."""
    if not array.flags["C_CONTIGUOUS"]:
        array = np.ascontiguousarray(array)
    else:
        array = array.copy()
    array.setflags(write=False)
    return array


def pixel_content_hash(array: np.ndarray, *, pixel_format: str | None = None) -> str:
    """SHA-256 of the versioned, length-framed normalized-pixel preimage."""
    normalized = normalize_c_contiguous(array)
    height, width = normalized.shape[0], normalized.shape[1]
    fmt = pixel_format or canonical_pixel_format(normalized)
    fmt_bytes = fmt.encode("utf-8")

    preimage = bytearray()
    preimage += _HASH_VERSION_TAG
    preimage += b"|"
    preimage += int(width).to_bytes(8, "big", signed=False)
    preimage += b"|"
    preimage += int(height).to_bytes(8, "big", signed=False)
    preimage += b"|"
    preimage += len(fmt_bytes).to_bytes(2, "big", signed=False)
    preimage += fmt_bytes
    preimage += b"|"
    preimage += normalized.tobytes(order="C")
    return hashlib.sha256(bytes(preimage)).hexdigest()
