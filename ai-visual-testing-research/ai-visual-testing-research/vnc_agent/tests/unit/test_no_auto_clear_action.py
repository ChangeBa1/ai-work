"""Static prohibition on program-created clear-cart actions (T054)."""

import re
from pathlib import Path


def test_no_auto_clear_executable_action_exists() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "vnc_agent"
    offenders = []
    for path in source_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"ExecutableAction\s*\(", source):
            construction = source[match.start() : match.start() + 500].lower()
            if any(
                marker in construction
                for marker in ("クリア", "clear_cart", "clear cart")
            ):
                offenders.append(str(path))
    assert offenders == []
