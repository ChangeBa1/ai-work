# Quickstart: 验证外部 UI 分析索引消费与通用索引生产规则

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md) | **Contracts**: [contracts/](./contracts/)

本指南给出无需连接真实 VNC 环境即可验证本 feature 是否达成 spec.md Success Criteria（SC-001~
SC-011）的运行步骤。所有命令均在 `vnc_agent/` 目录下执行；命令引用的测试文件路径由
`/speckit-tasks` → `/speckit-implement` 阶段创建，本文件是验收契约，不是已存在代码的记录。

## 前置条件

```bash
cd vnc_agent
uv sync --extra dev   # 或已有虚拟环境 pip install -e ".[dev]"
```

无需 VNC 服务、无需模型 API Key——本 feature 的读取/校验/查询/运行时适配全部离线测试基于固定
构造的 bundle fixture 运行；唯一需要真实/桩化模型交互的场景（运行时提示注入到 Planner/
Grounder）复用既有 `StubGrounder`/桩 Planner Provider，不连接在线模型。

## 一、生产方交付示例（最小有效 bundle）

```bash
# from repo root:
uv run --directory vnc_agent vnc-agent ui-index validate ../.agents/skills/generate-ui-analysis-index/assets/bundle-template/minimal-valid-example
# or from vnc_agent/:
uv run vnc-agent ui-index validate ../.agents/skills/generate-ui-analysis-index/assets/bundle-template/minimal-valid-example
```

**预期**：退出码 `0`，`ValidationReport.ok == True`，`issues == []`。这份最小有效示例覆盖 `manifest.yaml` + 三个必填 `.jsonl` 文件、至少一个 `Screen`/`Element`/`Transition`，是 [contracts/ui-analysis-bundle-v1.md](./contracts/ui-analysis-bundle-v1.md) 的具体实例。

## 二、消费方——有效 bundle 加载与结构化查询（SC-001）

```bash
cd vnc_agent
uv run pytest tests/unit/ui_index/test_query.py tests/unit/ui_index/test_repository_load.py -v
```

**预期**：使用 `tests/fixtures/ui_index/valid_minimal/` 与跨场景 fixture，断言：

- `UiIndexBundle.load()` 成功返回，`manifest.bundle_id`/`schema_version` 可读。
- `query_screen` / `query_by_text` / `query_by_alias` / `query_by_role` / `query_transitions` 返回结构化结果；未命中返回空。
  元素/可执行动作/可见启用条件/可信度/证据来源。
- `query_by_text`/`query_by_alias`/`query_by_role`/`query_transitions` 各自返回与 bundle
  源数据一致的结果，且保留 `confidence`/`source_evidence` 字段（FR-005）。
- 未命中查询返回空列表/`None`，不抛异常、不返回近似匹配（FR-004）。

## 三、消费方——逐类无效 bundle 产生稳定可诊断错误（SC-002）

```bash
pytest tests/unit/ui_index/test_validator_error_matrix.py -v
```

**预期**：对 `tests/fixtures/ui_index/invalid/` 下按错误类别命名的子目录（每个子目录一种
错误）逐一加载，断言每种场景都在 [contracts/ui-analysis-bundle-v1.md §9](./contracts/ui-analysis-bundle-v1.md#9-错误码总表)
错误码表中命中预期的 `error_code`，且 `file`/`field_path`/`message` 非空（`line` 在适用
JSONL 场景下非空）。至少覆盖以下子目录：

`bundle_dir_not_found` / `schema_unsupported_major` / `manifest_missing` /
`content_file_missing` / `jsonl_syntax_error` / `duplicate_id` / `dangling_reference`
（含 element→screen、transition→element、parent 自引用/成环三种子变体）/
`dangling_guard_reference` / `missing_coordinate_space` / `coordinate_out_of_range`
（含越界值、`x1>=x2` 两种子变体）/ `invalid_confidence` / `invalid_diagnostic_confidence` /
`path_traversal` / `resource_limit_exceeded` / `checksum_mismatch`。

## 四、未配置索引——既有行为零变化（FR-011，SC-003 基线）

```bash
pytest tests/integration/test_execution.py -v   # 既有回归套件，本 feature 不修改其断言
pytest tests/unit/ui_index/test_no_index_passthrough.py -v
```

**预期**：`UiIndexConfig.bundle_dir is None` 时，`build_hints()` 返回
`([], [], IndexUsageAuditRecord(outcome="not_configured"))`；既有 `tests/integration/`
套件在不修改任何断言的前提下继续全部通过（"所有现有 testcase 在无索引模式下保持兼容"）。

## 五、运行时命中/未命中/不一致——审计与坐标溯源（SC-003/004/005/006）

```bash
pytest tests/integration/ui_index/test_runtime_adapter_outcomes.py -v
```

**预期**：使用两个互不相关的固定 `StructuredScreen` + bundle 组合（见七），分别验证：

- **命中**（`outcome="hit"`）：`PlannerRequest.ui_index_hints` 非空且只含
  `VisibleElementHint` 允许的六类字段；`GroundingRequest.ui_index_candidates` 非空；最终
  `GroundingResult.candidates[].bbox` 全部可追溯到 `resolve_pixel_bbox()` 换算结果，
  没有一条等于 bundle 原始 `normalized_bounds` 数值（SC-004）；`grounder_outcome` 独立于
  `outcome` 记录（CHK027）。
- **未命中**（`outcome="no_match"`）：`hints == []`，`no_match_reason ==
  "no_screen_matched"`，回退到既有 Planner/Grounder 流程且不中止步骤（FR-014）。
- **不一致**（`outcome="inconsistent"`）：构造一个标题匹配但关键 element 大量缺失的场景，
  断言 `no_match_reason == "screen_content_inconsistent"`，同样回退且不强行采用（FR-014）。
- 三种场景下 `record_index_usage()` 写入的 `IndexUsageAuditRecord` 均可在
  `ActionIteration.ui_index_audit` 与结构化日志（`event_name="ui_index_usage"`）中读到
  `bundle_id`/`schema_version`（SC-006）。
- Verifier 判定输入抽查：断言 `VerificationEngine.verify()` 的调用参数中不出现
  `Transition.expected_visible/expected_hidden/expected_state_changes` 的值（SC-005）。

## 六、模型上下文清理（SC-007）

```bash
pytest tests/unit/ui_index/test_sanitizer_allowlist.py -v
```

**预期**：构造一个 `source_evidence` 字段填入明显的源码路径字符串（如
`"src/components/CheckoutForm.tsx:42"`）的 `Element`，调用 `to_visible_hint()`，断言
返回对象的全部字段值中都不出现该字符串（结构性断言：直接反射 `VisibleElementHint` 的
字段集合与 §5 数据模型表逐一比对，而不是只做字符串包含检查，防止未来新增字段时漏检）。

## 七、Producer Skill 双 fixture 可移植性（SC-008，User Story 4）

```bash
python .agents/skills/generate-ui-analysis-index/scripts/../assets/bundle-template  # 占位：实现期确定生成脚本形式
python -m vnc_agent.ui_index.cli validate tests/fixtures/ui_index/fixture_web_form/
python -m vnc_agent.ui_index.cli validate tests/fixtures/ui_index/fixture_desktop_multiscreen/
```

**预期**：两个 fixture 分别代表"Web 表单流程"与"桌面/多画面导航流程"两个互不相关的业务
领域/技术栈，均按 `.agents/skills/generate-ui-analysis-index/` 的说明手工或半自动生成，
均通过 `ui-index validate` 校验；两者共同作为 §五 场景的输入之一，覆盖 SC-011 要求的
"至少一个 fixture 需覆盖至少一类 FR-002 校验失败场景"（可在其中一个 fixture 的变体版本
故意引入一处 §三 列出的错误类别）。

## 八、核心代码业务无关性（SC-009）

```bash
pytest tests/unit/test_no_business_keywords_in_core.py -v
```

**预期**：扩展既有测试的扫描范围至 `ui_index/` 全部新文件，断言不出现 POS/Barcode/预现计/
购物车等固定业务关键词作为字段名、常量或分支条件。

## 九、自动化测试总览与可审计输出（SC-010）

```bash
pytest tests/unit/ui_index/ tests/integration/ui_index/ -v --tb=short
```

**预期**：全部通过；测试运行产出的 pytest 报告 + 结构化 JSON Lines 日志
（`event_name="ui_index_usage"` 等）可用于事后审计，无需重新执行即可复核每条断言对应的
`error_code`/`outcome` 结论。

## 十、消费端能力跨场景验收（SC-011）

上述 §二、§三、§五 的每一组测试 MUST 分别以 §七 中两个互不相关 fixture 之一作为输入至少
运行一次（`pytest -k` 参数化或 fixture parametrize 均可，具体机制在 `tasks.md` 中细化），
不得只用单一 fixture 验证全部消费端能力。
