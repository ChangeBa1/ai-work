# Contract: UI Index 消费方内部接口

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

本项目无对外 HTTP API，本契约定义 `vnc_agent/src/vnc_agent/ui_index/` 各模块之间、以及它们与
既有 `models/provider.py`、`domain/run.py`、`config.py`、`api/cli.py`、`planning/planner.py`、
`models/mimo_grounder.py` 的内部 Python 接口。对应 spec.md FR-001~019、Success Criteria、
research.md §9~12。

## 1. `ui_index/manifest.py`

```python
def read_manifest(bundle_dir: Path) -> tuple[BundleManifest | None, list[ValidationIssue]]:
    """只解析 manifest.yaml；不校验内容文件。bundle_dir 不存在/不可读时返回
    (None, [ValidationIssue(error_code=BUNDLE_DIR_NOT_FOUND, ...)])。manifest.yaml
    缺失时返回 (None, [ValidationIssue(error_code=MANIFEST_MISSING, ...)])。"""
```

**契约保证**：本函数是纯读取，MUST NOT 触发内容文件的任何 I/O；`schema_version` 的 MAJOR
校验在本函数内完成（不支持时仍返回已解析的 `BundleManifest`供错误报告展示身份信息，但
`issues` 非空）。

## 2. `ui_index/jsonl_reader.py`

```python
def iter_jsonl(
    path: Path,
    *,
    max_bytes: int,
    max_records: int,
) -> Iterator[tuple[int, dict[str, Any] | ValidationIssue]]:
    """逐行读取；每一项要么是 (line_no, parsed_dict)，要么是 (line_no, ValidationIssue)
    （JSONL_SYNTAX_ERROR）。累计字节数/行数超过上限时产出一条 RESOURCE_LIMIT_EXCEEDED
    ValidationIssue 后立即停止迭代（StopIteration），不读取超限之后的内容。"""
```

**契约保证**：纯生成器，MUST NOT 一次性把整个文件读入内存（逐行读取，Python 文件对象原生
迭代）；调用方（`validator.py`）负责区分 `dict` 与 `ValidationIssue` 两种产出类型。

## 3. `ui_index/validator.py`

```python
def validate_bundle(bundle_dir: Path, config: UiIndexConfig) -> ValidationReport:
    """FR-002 的完整实现：两遍遍历（第一遍解析+登记 ID+格式校验，第二遍引用完整性+
    parent 环检测+坐标空间+可信度），汇总全部问题，不因单个问题提前返回。"""
```

**校验顺序契约**（决定同一 bundle 多次运行产出的 `issues` 顺序稳定，便于测试断言）：

1. `bundle_dir` 存在性/可读性
2. manifest 解析 + schema 版本
3. `content_files` 必填文件存在性 + 路径穿越检查
4. 按 `screens.jsonl` → `elements.jsonl` → `transitions.jsonl` → `flows.jsonl` →
   `diagnostics.jsonl` 固定顺序，每个文件内按行号顺序：JSONL 语法 → 字段类型 → 重复 ID 登记
5. 全部 ID 登记完成后：跨记录引用完整性（含 parent 环检测、guards/anchors/neighbors 引用、
   坐标空间与坐标范围、可信度取值）
6. `content_files.*.sha256` 校验和比对（放在最后——即使内容有其它问题，校验和不一致也要
   独立报告，两者不互斥）

**契约保证**：任一步骤发现的问题不影响后续步骤继续执行（除非该步骤本身依赖前序步骤的产出，
如引用完整性依赖 ID 登记完成）；`ValidationReport.ok == (len(issues) == 0)`。

## 4. `ui_index/bundle.py`

```python
class UiIndexBundle:
    @classmethod
    def load(cls, bundle_dir: Path, config: UiIndexConfig) -> UiIndexBundle:
        """调用 validate_bundle()；report.ok is False 时抛出
        UiIndexValidationError(report)，MUST NOT 返回一个"部分可用"的实例。"""
```

**契约保证**：构造成功的 `UiIndexBundle` 实例的全部查询方法（`query_screen`/
`query_by_text`/`query_by_alias`/`query_by_role`/`query_transitions`）在其生命周期内是
只读、幂等、无副作用的纯函数（多次调用同参数返回相同结果，不修改内部状态）。

## 5. `ui_index/sanitizer.py`

```python
def to_visible_hint(element: Element, bundle: UiIndexBundle) -> VisibleElementHint:
    """allow-list 拷贝（research.md §10）。bundle 参数仅用于解析 anchors/neighbors
    引用的目标 element 的 visible_texts，不用于拷贝任何其它字段。"""
```

**契约保证**：函数体 MUST NOT 出现 `element.source_evidence`、`element.metadata`、
`element.screen_id`、`element.normalized_bounds` 的任何读取——这是一条静态可审查的代码
约束（code review 检查点），不是运行时过滤。

## 6. `ui_index/runtime_adapter.py`

```python
def build_hints(
    bundle: UiIndexBundle | None,
    current_screen: StructuredScreen,
    config: UiIndexConfig,
) -> tuple[list[VisibleElementHint], list[dict[str, Any]], IndexUsageAuditRecord]:
    """返回 (Planner 用的 hints, Grounder 用的 candidates, 本次审计记录)。
    bundle 为 None（未配置索引）时返回 ([], [], IndexUsageAuditRecord(outcome="not_configured", ...))。
    """
```

**契约保证**（FR-007/008/009/010/011/014 的落地点）：

- 本函数 MUST NOT 接触 `ExecutableAction`/VNC 驱动层——它只产出"提示候选"，不做任何执行
  决策；`GroundingRequest.ui_index_candidates` 与 `ocr_candidates`/`template_candidates`
  以相同方式参与 `models/mimo_grounder.py` 现有的候选融合逻辑，本函数不实现融合/排序，
  融合排序留在既有 Grounder 客户端代码中。
- `outcome == "hit"` 时才会产出非空 `hints`/`candidates`；`no_match`/`inconsistent`/
  `not_configured` 三种情况下 `hints == []` 且 `candidates == []`（回退到既有行为的类型层面
  保证——调用方不需要为不同 `outcome` 写不同分支就能获得"空提示"的安全默认值）。
- `IndexUsageAuditRecord` MUST 总是非 `None`（即使未配置索引也要产出 `not_configured`
  审计记录，供 SC-006 的"100% 覆盖率"断言）。

## 7. `ui_index/audit.py`

```python
def record_index_usage(iteration: ActionIteration, audit: IndexUsageAuditRecord) -> None:
    """iteration.ui_index_audit = audit；并通过 runtime/telemetry.py::log_event()
    写入结构化 JSON Lines 日志（event_name="ui_index_usage"）。"""
```

**契约保证**：写入 `ActionIteration` 与写入结构化日志是同一次调用的两个必然结果，不存在
"只写日志不写记录"或反之的中间状态（保证报告与日志两条审计路径不会出现不一致）。

## 8. CLI（`api/cli.py` 新增子命令组）

```text
vnc-agent ui-index validate <bundle_dir> [--json]
vnc-agent ui-index query --bundle-dir <dir> (--screen <id> | --text <t> | --alias <a> | --role <r> | --transition-from <id> | --transition-trigger <id> | --transition-to <id>) [--json]
```

**契约保证**：

- `validate` 退出码：`0` = `report.ok`，`1` = 存在 `issues`。`--json` 输出
  `ValidationReport` 的 JSON 序列化；默认输出人类可读的逐条问题列表（含 file/line/
  field_path/message）。
- `query` 要求先通过校验（内部调用 `UiIndexBundle.load()`）；校验失败时行为与 `validate`
  失败一致（非零退出码 + 报告问题），不尝试"忽略校验失败继续查询"。
- 两个命令均不修改 `bundle_dir` 下的任何文件（只读工具）。

## 9. 运行时集成时序（对应 spec.md User Story 3、FR-007~014）

```text
preflight（配置解析后、第一测试步骤前）：
  UiIndexConfig.bundle_dir is None
    → 不加载索引，运行时行为与本 feature 之前完全一致（FR-011）
  UiIndexConfig.bundle_dir is not None
    → UiIndexBundle.load(bundle_dir, config)
      → 失败：抛出 UiIndexValidationError，run 启动失败并展示 ValidationReport（FR-012）
      → 成功：bundle 实例贯穿整个 run 生命周期，只读，不重新加载

每个测试步骤的每次迭代（PlannerOrchestrator.plan() 之前）：
  hints, candidates, audit = build_hints(bundle, current_structured_screen, config)
  PlannerRequest.ui_index_hints = hints
  （Grounder 调用发生在 Planner 产出候选目标描述之后，属于既有既有 Grounder 调用路径）
  GroundingRequest.ui_index_candidates = candidates
  record_index_usage(current_iteration, audit)

Grounder（既有 MimoGrounderClient.ground() / StubGrounder）：
  候选融合时把 ui_index_candidates 与 ocr_candidates/template_candidates 一视同仁地
  纳入排序——本 feature 不改变既有融合算法本身，只新增一路候选来源（FR-009）。
  最终 GroundingResult.candidates 中的 bbox 仍然只可能来自"基于当前实时 VNC 截图计算"的
  结果——ui_index_candidates 的数值经过既有 resolve_pixel_bbox() 换算流程，与 OCR/模板
  候选走完全相同的坐标解析与越界检查代码路径，不存在单独的"索引候选直通"分支。

坐标出处的事后可追溯性（SC-004 的审计依据）：
  每次迭代已产出的 IndexUsageAuditRecord.hint_element_ids（本次实际组装进模型提示的
  element_id 列表）与该 ActionIteration.semantic_action.target/grounding_result 一并
  持久化在同一条 ActionIteration 记录中（既有 TestRun → StepRecord → ActionIteration
  序列化链路，Constitution"制品与可观测性"要求的完整运行轨迹）。事后复核 SC-004 时，
  只需比对同一条 ActionIteration 内的 hint_element_ids 与 grounding_result.candidates
  的来源标签（ocr/template/ui_index，融合逻辑保留候选来源以便调试，见 T047 实现细节），
  即可判定当次点击坐标是否被索引数据"直通"——不需要新增独立的坐标溯源字段，复用既有
  运行轨迹即可重建全链路证据。

Verifier（既有 VerificationEngine.verify()）：
  输入不变——仍然只接受操作后重新采集的截图与既有证据类型；本 feature 不向 Verifier 新增
  任何输入参数，`Transition.expected_visible/expected_hidden/expected_state_changes` 
  MUST NOT 出现在 Verifier 的判定输入中（FR-008/010/019）。
```
