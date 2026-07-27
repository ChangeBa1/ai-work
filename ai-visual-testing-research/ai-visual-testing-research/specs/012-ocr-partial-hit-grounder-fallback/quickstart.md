# Quickstart: OCR 可疑命中转 Grounding 兜底

```bash
cd vnc_agent
uv sync --extra dev
```

## 场景 1：可疑命中转 grounding（US1/US2，新行为）

```bash
uv run pytest tests/unit/test_action_policy_ocr_suspicion.py -v
```

预期：非精确包含命中 / 精确低置信命中 / 单字符命中 → `needs_grounding=True`、
`PolicyResult.ocr_suspicion.reasons` 含对应原因码
（`partial_text_overlap` / `low_confidence` / `short_text`）；
真子串 miss（「ジ袋」⊂「レジ袋」）→ 照旧落 grounding 且补 `truncated_ocr_read` 观测数据。

## 场景 2：零回归门禁（US3）

```bash
uv run pytest tests/unit/test_action_policy_priority.py \
             tests/fixtures/test_action_policy_sanity_check.py -v
```

预期：精确高置信命中直点行为逐字段一致；grounding 防线（距离一致性）用例零修改仍绿。

## 全量

```bash
uv run pytest tests/unit tests/fixtures -q   # 基线（改动前）：762 passed
uv run pytest tests/e2e -q                   # 基线（改动前）：40 passed
```

## 配置

`config/agent.yaml`:

```yaml
planning:
  ocr_direct_click_min_confidence: 0.85   # [0,1]；唯一 OCR 命中直点所需最低置信度，调高更保守
```

注意：运行时装配层（runtime/）在本 feature 冻结，yaml 自定义值到 `ActionPolicy` 构造点的
接线为后续一行级任务（plan.md Complexity Tracking）；默认部署（0.85）行为双端一致。
