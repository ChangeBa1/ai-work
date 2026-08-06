"""Feature 025 migration: purge legacy element_memories, keep pages."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_element_identity_025.py"
_spec = importlib.util.spec_from_file_location("migrate_element_identity_025", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
migrate = _mod.migrate


def test_migrate_deletes_elements_keeps_pages(tmp_path: Path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE page_memories (
            page_id VARCHAR(64) PRIMARY KEY,
            resolution_w INT, resolution_h INT,
            hit_count INT, last_seen_at DATETIME, payload JSON
        );
        CREATE TABLE element_memories (
            element_id VARCHAR(64) PRIMARY KEY,
            page_id VARCHAR(64),
            target_label VARCHAR(512),
            success_count INT, failure_count INT,
            last_success_at DATETIME, payload JSON
        );
        """
    )
    con.execute(
        "INSERT INTO page_memories VALUES (?,?,?,?,?,?)",
        ("p1", 1024, 768, 1, None, "{}"),
    )
    con.execute(
        "INSERT INTO element_memories VALUES (?,?,?,?,?,?,?)",
        (
            "e1",
            "p1",
            "小計",
            1,
            0,
            None,
            json.dumps({"element_id": "e1", "target_label": "小計", "template_path": None}),
        ),
    )
    con.commit()
    con.close()

    result = migrate(
        db,
        template_dir=None,
        legacy_template_dir=tmp_path / "legacy",
        delete_elements=True,
    )
    assert result["elements_deleted"] == 1
    assert result["pages_before"] == 1
    assert result["pages_after"] == 1

    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM element_memories").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM page_memories").fetchone()[0] == 1
    cols = {r[1] for r in con.execute("PRAGMA table_info(element_memories)")}
    assert "identity_key" in cols
    con.close()


@pytest.mark.asyncio
async def test_legacy_identity_key_not_hit(tmp_path: Path):
    from datetime import UTC, datetime

    import cv2
    import numpy as np

    from vnc_agent.config import MemoryConfig
    from vnc_agent.domain.memory import ElementMemory
    from vnc_agent.domain.observation import OCRItem, Region, StructuredScreen
    from vnc_agent.memory.service import PageElementMemory
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory
    from vnc_agent.storage.repositories import MemoryRepository

    engine = make_engine(str(tmp_path / "mem.db"))
    await init_db(engine)
    repo = MemoryRepository(make_session_factory(engine))
    # insert legacy-like element via save with empty identity_key
    from vnc_agent.domain.memory import PageFingerprint, PageMemory

    page = PageMemory(
        page_id="p-legacy",
        fingerprint=PageFingerprint(
            phash="0" * 16, ocr_tokens=["total"], layout_cells=["0,0"], resolution=(300, 200)
        ),
        resolution=(300, 200),
        hit_count=1,
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    await repo.save_page(page)
    el = ElementMemory(
        element_id="legacy-1",
        page_id="p-legacy",
        target_label="total",
        identity_key="",  # legacy
        bbox=(150, 85, 170, 95),
        success_count=1,
        created_at=datetime.now(UTC),
    )
    await repo.save_element(el)

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    xx, yy = np.meshgrid(np.arange(20), np.arange(10))
    pat = ((xx * 23 + yy * 57) % 256).astype(np.uint8)
    frame[85:95, 150:170] = np.stack([pat, 255 - pat, pat // 2], axis=-1)
    path = tmp_path / "f.png"
    cv2.imwrite(str(path), frame)
    screen = StructuredScreen(
        frame_id="f",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
        ocr_items=[OCRItem(text="TOTAL", bbox=(150, 85, 170, 95), confidence=0.9)],
        image_path=str(path),
    )
    svc = PageElementMemory(
        repo=repo,
        template_dir=tmp_path / "t",
        config=MemoryConfig(identity_enabled=True),
    )
    hit = await svc.lookup(screen, "TOTAL")
    assert hit is None  # empty identity_key filtered
