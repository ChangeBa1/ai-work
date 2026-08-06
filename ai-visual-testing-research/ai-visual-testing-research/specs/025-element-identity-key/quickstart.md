# Quickstart: 025-element-identity-key（离线验证）

**目标**: 不依赖真实 VNC，用既有 artifacts 截图/OCR 语义跑通  
**「写入身份 → 换一种措辞查询 → 命中（含强制模板校验）」**。

## Prerequisites

- 仓库根目录；已安装 `vnc_agent` 测试依赖（`cd vnc_agent && uv sync` 或项目惯用方式）。
- 本 feature 代码已实现（`/speckit-implement` 之后）；实现前可先跑既有 015 单测确认环境。
- 可选：本地存在  
  `vnc_agent/artifacts/memory/templates/f879a607-f68b-4e7a-8ff3-2d0f60164c36.png`  
  （历史 `小計` 模板；本 quickstart **默认使用合成帧**，不依赖该文件是否仍在）。

## 一条离线可复现命令

在仓库根目录执行：

```bash
cd vnc_agent && uv run pytest \
  tests/unit/test_memory_identity.py::test_write_identity_lookup_with_paraphrased_label_hits \
  -q
```

**期望**:

- 退出码 0；
- 该测试内部完成：`record_success`（短标签/可见 OCR `TOTAL` 或日文 fixture 标签）→  
  `lookup` 使用**不同措辞**的 `target_label` → 返回 `level=="high"` 且  
  `matched_bbox is not None`（模板路径强制走过 `match_element_template`）；
- 同文件中 `test_ambiguous_same_text_two_cells_no_hit` 等保持绿（多候选未命中）。

若实现阶段测试函数名微调，以 `tests/unit/test_memory_identity.py` 中标记  
`@pytest.mark.identity_paraphrase_hit` 的用例为准，命令改为：

```bash
cd vnc_agent && uv run pytest -m identity_paraphrase_hit -q
```

## 使用真实 artifacts 帧的扩展验证（可选）

当需要用 runs 目录真实截图时（仍无 VNC）：

1. 任选一帧含日文按钮的 safe 图，例如：  
   `vnc_agent/artifacts/runs/*/bundles/*/safe_evidence.png`  
   （路径随本地 artifacts 变化；用 `find vnc_agent/artifacts/runs -name 'safe_evidence.png' | head` 查找）。
2. 使用测试辅助或一次性脚本注入 OCR 列表（可从对应 `page_memories.payload.fingerprint.ocr_tokens`
   与已知 bbox 构造 `OCRItem`，样本见 research.md R5：`小計` @ ≈(867,627) on 1024×768）。
3. 对空库 `record_success(screen, "小計", region)` 再  
   `lookup(screen, "右下角的小計按钮")`，断言 high 命中。

推荐仍以 **pytest 固化** 上述步骤，避免手写脚本漂移；实现任务应把「真实 token 表」
放进 `tests/fixtures/memory/identity_ocr_samples.json`（来自 research 正反例）。

## 回归安全抽检

```bash
cd vnc_agent && uv run pytest \
  tests/unit/test_memory_store.py \
  tests/unit/test_memory_retrieval.py \
  tests/unit/test_memory_fingerprint.py \
  tests/e2e/test_scenario_19_page_element_memory.py \
  -q
```

关闭身份开关时（配置 `memory.identity_enabled: false`）行为回到 015 标签路径；  
`memory.enabled: false` 仍须与合入前一致（scenario 19 既有用例）。

## 存量库处理抽检（开发机）

```bash
# 仅检查行数；迁移实现后 element 应为 0 或仅新 identity 行
python3 - <<'PY'
import sqlite3
c=sqlite3.connect("vnc_agent/data/vnc_agent.db")
print("elements", c.execute("select count(*) from element_memories").fetchone()[0])
print("pages", c.execute("select count(*) from page_memories").fetchone()[0])
PY
```

迁移后期望：pages 仍为 5（或更多新页）；旧 8 行自然语言主键元素不再出现。

## 成功标准对照

| SC | 本 quickstart / 正式门禁 |
|----|--------------------------|
| SC-001 命中率 ≥30% | 演示：paraphrase hit >0。**正式**：`tasks.md` **T034** 对同一 `baseline/regression_suite_manifest.json` assert `hit_rate >= 0.30` |
| SC-002 误命中 ≤10% | 字段：US6 单测。**正式**：**T034** 三态（`hits≥20` 才判 `false_hit_rate≤0.10`；否则 `sc002_inconclusive`） |
| SC-003 p95 ≤50ms | 字段：lookup 耗时。**正式**：**T034** 三态（计时样本 `≥20` 才判 `p95_ms≤50`；否则 `sc003_inconclusive`；`SC003_MIN_SAMPLES=20`） |
| SC-004 开关 | `identity_enabled=false` / `enabled=false` 用例 |
| SC-005 无新模型 | 测试无 mock 新模型角色 |
| SC-006 跨场景 | contract 测试 + 日文 fixture 样本 |

**正式验收命令（实现 T001/T034 后）**：

```bash
cd vnc_agent && uv run python scripts/measure_element_memory_baseline.py \
  --manifest ../specs/025-element-identity-key/baseline/regression_suite_manifest.json \
  --out ../specs/025-element-identity-key/baseline/element_memory_hits_post_025.json
# 然后 assert 脚本（T034）对 post JSON 施加 SC-001/002/003（含三态）
uv run python scripts/assert_sc_metrics_025.py \
  --post ../specs/025-element-identity-key/baseline/element_memory_hits_post_025.json
# SC-002: hits<20 → sc002_inconclusive；SC-003: n_latency<20 → sc003_inconclusive
```

## 非目标

- 不在此启动真实 VNC 或调用在线 Planner/Grounder。
- 不验证 feature 026 画面版本索引。
