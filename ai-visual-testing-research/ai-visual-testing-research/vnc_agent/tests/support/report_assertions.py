"""Snapshot-stabilization + DOM visible-text helpers for report tests.

Used by feature 004 HTML/JSON snapshot and localization tests: strips the
run-specific noise (UUIDs, timestamps, absolute paths) that would otherwise
make golden snapshots flaky, and extracts the DOM's visible text so English
UI-leak scans do not have to hand-parse HTML.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ISO_DATETIME_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_SHA256_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")

_NO_TAG_CONTENT_ELEMENTS = {"script", "style"}
_BLOCK_ELEMENTS = {
    "p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "table", "ul", "ol", "br",
}


def normalize_report_snapshot(
    text: str,
    *,
    run_root: str | Path | None = None,
    extra_paths: list[str | Path] | None = None,
) -> str:
    """Replace UUIDs, ISO timestamps, SHA-256 hex digests and absolute paths
    with stable placeholders so golden snapshots do not churn per-run."""
    normalized = text
    if run_root is not None:
        normalized = normalized.replace(str(Path(run_root)), "<RUN_ROOT>")
        normalized = normalized.replace(str(Path(run_root)).replace("\\", "/"), "<RUN_ROOT>")
    for extra in extra_paths or []:
        normalized = normalized.replace(str(Path(extra)), "<PATH>")
    normalized = _SHA256_RE.sub("<SHA256>", normalized)
    normalized = _ISO_DATETIME_RE.sub("<TIMESTAMP>", normalized)
    normalized = _UUID_RE.sub("<UUID>", normalized)
    return normalized


class _VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _NO_TAG_CONTENT_ELEMENTS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _NO_TAG_CONTENT_ELEMENTS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self.chunks.append(data.strip())


def extract_visible_text(html: str) -> list[str]:
    """Return the DOM's visible text nodes (script/style excluded), in order."""
    parser = _VisibleTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.chunks


def extract_visible_text_joined(html: str, *, sep: str = "\n") -> str:
    return sep.join(extract_visible_text(html))
