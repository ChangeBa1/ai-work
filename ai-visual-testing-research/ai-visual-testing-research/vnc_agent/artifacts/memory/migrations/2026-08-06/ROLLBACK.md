# Rollback element identity migration (025)

## Restore pre-migration DB

```bash
cp artifacts/memory/migrations/2026-08-06/vnc_agent.db.bak data/vnc_agent.db
```

Or re-import `element_memories_legacy_015.jsonl` into a clean `element_memories` table.

## Code path without structured identity

Set in config:

```yaml
memory:
  identity_enabled: false
```

Runtime uses 015 `target_label` exact match path.

## Templates

Moved templates may be under `artifacts/memory/templates/legacy_invalid/`.
