#!/usr/bin/env python3
"""Migrate element_memories for feature 025: identity_key column + purge legacy rows."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


def ensure_identity_key_column(con: sqlite3.Connection) -> None:
    cols = {r[1] for r in con.execute("PRAGMA table_info(element_memories)")}
    if "identity_key" not in cols:
        con.execute(
            "ALTER TABLE element_memories ADD COLUMN identity_key VARCHAR(640) DEFAULT ''"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_element_memories_identity_key "
            "ON element_memories (identity_key)"
        )
        con.commit()


def migrate(
    db_path: Path,
    *,
    template_dir: Path | None,
    legacy_template_dir: Path | None,
    delete_elements: bool = True,
) -> dict:
    con = sqlite3.connect(db_path)
    ensure_identity_key_column(con)
    pages_before = con.execute("SELECT COUNT(*) FROM page_memories").fetchone()[0]
    n_el = con.execute("SELECT COUNT(*) FROM element_memories").fetchone()[0]
    template_paths: list[str] = []
    if delete_elements and n_el:
        for (payload,) in con.execute("SELECT payload FROM element_memories"):
            if not payload:
                continue
            import json

            try:
                p = json.loads(payload) if isinstance(payload, str) else payload
            except Exception:
                continue
            tp = p.get("template_path") if isinstance(p, dict) else None
            if tp:
                template_paths.append(tp)
        con.execute("DELETE FROM element_memories")
        con.commit()
    pages_after = con.execute("SELECT COUNT(*) FROM page_memories").fetchone()[0]
    con.close()

    moved = 0
    if legacy_template_dir is not None and template_paths:
        legacy_template_dir.mkdir(parents=True, exist_ok=True)
        for tp in template_paths:
            src = Path(tp)
            if not src.is_file():
                # try relative under vnc_agent
                alt = Path("artifacts") / "memory" / "templates" / src.name
                src = alt if alt.is_file() else src
            if src.is_file():
                dest = legacy_template_dir / src.name
                shutil.move(str(src), str(dest))
                moved += 1

    return {
        "elements_deleted": n_el if delete_elements else 0,
        "pages_before": pages_before,
        "pages_after": pages_after,
        "templates_moved": moved,
        "identity_key_column": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db",
        default="data/vnc_agent.db",
        help="SQLite path relative to cwd or absolute",
    )
    ap.add_argument(
        "--legacy-templates",
        default="artifacts/memory/templates/legacy_invalid",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = Path(args.db)
    if args.dry_run:
        con = sqlite3.connect(db)
        n = con.execute("SELECT COUNT(*) FROM element_memories").fetchone()[0]
        p = con.execute("SELECT COUNT(*) FROM page_memories").fetchone()[0]
        print({"would_delete_elements": n, "pages": p})
        return 0
    result = migrate(
        db,
        template_dir=Path("artifacts/memory/templates"),
        legacy_template_dir=Path(args.legacy_templates),
        delete_elements=True,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
