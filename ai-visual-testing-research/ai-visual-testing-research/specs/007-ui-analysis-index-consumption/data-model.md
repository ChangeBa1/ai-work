# Phase 1 Data Model: 外部 UI 分析索引消费与通用索引生产规则

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

本文件把 spec.md 的 Key Entities 落成 `vnc_agent/src/vnc_agent/ui_index/` 下的具体 Pydantic
模型，以及对既有模型（`models/provider.py`、`domain/run.py`、`config.py`）的增量修改。外部
wire-format 的规范性定义见 [contracts/ui-analysis-bundle-v1.md](./contracts/ui-analysis-bundle-v1.md)；
本文件是消费方内部表示，字段名与外部契约保持一致（消费方直接反序列化，不做字段改名映射）。

全部模型 MUST 通过业务无关性检查（Constitution Principle VI）：不含任何 POS/Barcode/预现计/
购物车等固定业务字段或分支，仅有通用 UI 结构概念。

## 1. `ui_index/schema.py` — Bundle 内容模型

### 1.1 `CoordinateSpace`

```python
BundleCoordinateSpace = Literal["design_pixels", "normalized_1000"]
```

对应 research.md §4；`design_pixels` 是本 feature 新增的字面量，刻意不同于既有
`models/coordinate_space.py::CoordinateSpace` 的 `"pixel"`，防止被误当作运行时截图像素坐标
直接使用。

### 1.2 `Confidence`（对应 research.md §5，FR-002/FR-025）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `level` | `Literal["confirmed", "statically_inferred", "visually_confirmed", "requires_runtime_verification"]` | 是 | FR-025 四类 |
| `score` | `float \| None`，`0.0 ≤ score ≤ 1.0` | 否 | 同一 `level` 内部排序，不改变 `level` 语义 |

### 1.3 `NormalizedBounds`（Element 专用，对应 FR-002 坐标校验、spec.md 用户输入"四、elements.jsonl"）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `coordinate_space` | `Literal["normalized_1000"]` | 是 | 固定取值——`normalized_bounds` 专用于送入 Grounder 候选管线，只接受千分比整数坐标（research.md §6）；`design_pixels` 不出现在这个字段，只出现在 `manifest.default_viewports`/描述性场景 |
| `x1`, `y1`, `x2`, `y2` | `int`，`0 ≤ 值 ≤ 1000` | 是 | 校验器 MUST 拒绝 `x1 >= x2` 或 `y1 >= y2`（spec.md 用户输入约束） |

### 1.4 `NeighborRef`（对应 research.md §7，解决 CHK019）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `direction` | `Literal["up", "down", "left", "right", "near"]` | 是 | 同一方向允许多条 |
| `element_id` | `str` | 是 | 引用同一 bundle 内的 element；悬空引用 = 校验失败 |

### 1.5 `Screen`（对应 spec.md 用户输入"三、screens.jsonl"）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `screen_id` | `str`，`^[A-Za-z0-9_.:-]{1,128}$` | 是 | 稳定 ID，bundle 内唯一 |
| `name` | `str` | 是 | 生产方给出的人类可读名称 |
| `screen_type` | `str`（开放 snake_case，见 research.md §8 同一开放词表原则） | 是 | 如 `page`/`modal`/`dialog`/`panel`，不做封闭校验 |
| `visible_titles` | `list[str]` | 是（可为空列表） | 画面级可见标题文字 |
| `aliases` | `list[str]` | 是（可为空列表） | OCR 别名/同义文字 |
| `parent_screen_id` | `str \| None` | 否 | 引用同一 bundle 内 screen；悬空引用 = 校验失败；MUST NOT 自引用或成环（与 Element.parent_element_id 同规则，§1.6） |
| `source_evidence` | `str \| None` | 否 | 仅用于离线溯源，MUST NOT 进入 `VisibleElementHint`（FR-015） |
| `confidence` | `Confidence` | 是 | §1.2 |
| `metadata` | `dict[str, Any] \| None` | 否 | 未知/自由扩展字段，透传不做语义解释 |

### 1.6 `Element`（对应 spec.md 用户输入"四、elements.jsonl"）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `element_id` | `str`，同 `screen_id` 格式 | 是 | bundle 内唯一 |
| `screen_id` | `str` | 是 | 引用 `Screen`；悬空 = 校验失败 |
| `parent_element_id` | `str \| None` | 否 | 引用同一 bundle 内 element；MUST NOT 自引用（`parent_element_id == element_id`）或与其他 element 的 parent 链形成循环——校验算法：构建 parent 有向图，做环检测（DFS 染色法），任何环上的全部 element MUST 各自产出一条 `PARENT_CYCLE` 校验错误 |
| `name` | `str` | 是 | |
| `role` | `str`（开放 snake_case） | 是 | 如 `button`/`text_field`/`checkbox`/`list_item`，不做封闭校验（research.md §8 同一原则，UI role 天然开放） |
| `visible_texts` | `list[str]` | 是（可为空） | |
| `aliases` | `list[str]` | 是（可为空） | |
| `supported_actions` | `list[str]`，每项匹配 `^[a-z][a-z0-9_]*$` | 是（可为空） | 开放词表（research.md §8） |
| `state_conditions` | `dict[str, Any]` | 否，默认 `{}` | 声明式可见/启用条件；本 feature 不解释其内部结构语义，只做"存在即透传"处理，具体求值逻辑不在本 feature 范围（Assumptions） |
| `region` | `Literal["header","toolbar","sidebar_left","sidebar_right","body","footer","statusbar","modal","unknown"]` | 是，默认 `"unknown"` | research.md §6 |
| `normalized_bounds` | `NormalizedBounds \| None` | 否 | research.md §6/§9 |
| `anchors` | `list[str]`（element_id 列表） | 否，默认 `[]` | 引用同一 bundle 内 element；悬空 = 校验失败 |
| `neighbors` | `list[NeighborRef]` | 否，默认 `[]` | §1.4 |
| `expected_effects` | `list[str]` | 否，默认 `[]` | 点击后的预期效果描述（自由文本列表，仅供 Verifier 参考，FR-008，MUST NOT 被当作判定依据） |
| `source_evidence` | `str \| None` | 否 | 同 Screen，仅离线溯源 |
| `confidence` | `Confidence` | 是 | |
| `metadata` | `dict[str, Any] \| None` | 否 | |

### 1.7 `Transition`（对应 spec.md 用户输入"五、transitions.jsonl"）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `transition_id` | `str` | 是 | bundle 内唯一 |
| `from_screen_id` | `str` | 是 | 引用 Screen；悬空 = 校验失败 |
| `trigger_element_id` | `str` | 是 | 引用 Element；悬空 = 校验失败 |
| `trigger_action` | `str`（开放 snake_case） | 是 | research.md §8 |
| `guards` | `list[GuardRef]` | 否，默认 `[]` | `GuardRef = {element_id: str, condition: Literal["visible","enabled","hidden","disabled"]} \| {name: str}`（后者=同记录内联声明的命名条件，见 §1.8）；`element_id` 变体悬空 = 校验失败（research.md、spec.md Clarifications） |
| `to_screen_id` | `str` | 是 | 引用 Screen；悬空 = 校验失败 |
| `transition_type` | `Literal["modal", "replace", "overlay", "state_change"]` | 是 | spec.md 已固定的封闭枚举 |
| `expected_visible` | `list[str]` | 否，默认 `[]` | 预期新增可见元素（自由文本或 element_id，不强制） |
| `expected_hidden` | `list[str]` | 否，默认 `[]` | 预期消失可见元素 |
| `expected_state_changes` | `list[str]` | 否，默认 `[]` | 自由文本，仅供 Verifier 参考线索 |
| `source_evidence` | `str \| None` | 否 | |
| `confidence` | `Confidence` | 是 | |

### 1.8 `GuardRef`（对应 spec.md Clarifications 关于 guards/preconditions 的决议）

`guards` 列表中每一项 MUST 是以下两种形式之一（Pydantic 判别联合，按存在的字段区分）：

| 变体 | 字段 | 说明 |
|---|---|---|
| element 引用型 | `element_id: str`, `condition: Literal["visible","enabled","hidden","disabled"]` | `element_id` MUST 存在于同一 bundle；悬空视为 `DANGLING_GUARD_REFERENCE` |
| 内联命名条件型 | `name: str`, `description: str \| None` | 只在声明它的这一条 `Transition` 记录内部有意义，不进入任何跨记录共享的注册表；查询/校验 MUST NOT 尝试跨 transition 解析同名 `name` |

### 1.9 `Flow`（对应 spec.md 用户输入"六、flows.jsonl"，research.md 未单独提及处已延用 spec.md 决议）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `flow_id` | `str` | 是 | bundle 内唯一 |
| `name` | `str` | 是 | |
| `start_screen_id` | `str` | 是 | 引用 Screen；悬空 = 校验失败 |
| `steps` | `list[FlowStep]`，**有序列表**（解决 CHK010） | 是（至少 1 项） | 顺序即执行/预期顺序，不是无序集合或图 |
| `completion_screen_id` | `str` | 是 | 引用 Screen；悬空 = 校验失败 |
| `preconditions` | `list[GuardRef]` | 否，默认 `[]` | 复用 §1.8 判别联合 |
| `confidence` | `Confidence` | 是 | |

`FlowStep`：判别联合，恰好二选一（Pydantic 校验器强制"恰好一种非空"）：

| 变体 | 字段 | 说明 |
|---|---|---|
| transition 引用型 | `transition_id: str` | 引用同一 bundle 内 Transition；悬空 = 校验失败 |
| element/action 型 | `element_id: str`, `action: str`（开放 snake_case） | `element_id` 引用同一 bundle 内 Element；悬空 = 校验失败 |

### 1.10 `Diagnostic`（对应 spec.md 用户输入"七、diagnostics.jsonl"，解决 CHK009）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `diagnostic_id` | `str` | 是 | bundle 内唯一 |
| `category` | `Literal["unconfirmed_screen","unconfirmed_element","dynamic_element","uncertain_transition","unparsed_text","requires_runtime_calibration"]` | 是 | spec.md 用户输入七、列举的六类 |
| `target_ref` | `TargetRef \| None` | 否 | `TargetRef = {screen_id: str \| None, element_id: str \| None, transition_id: str \| None}`，非空字段 MUST 引用同一 bundle 内存在的记录，悬空 = 校验失败；`category` 无适用目标时（如 `unparsed_text`）可为 `None` |
| `reason` | `str` | 是 | 人类可读说明，为何无法确认 |
| `confidence` | `Confidence` | 是 | **MUST NOT** 出现 `level == "confirmed"`——诊断条目按定义是未确认项；校验器对 `Diagnostic.confidence.level == "confirmed"` 产出 `INVALID_DIAGNOSTIC_CONFIDENCE` 错误（落实 spec.md"禁止把这些内容伪装成高可信度索引项"） |
| `source_evidence` | `str \| None` | 否 | |

### 1.11 `BundleManifest`（对应 spec.md 用户输入"二、manifest.yaml"）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | `str`，匹配 `^\d+\.\d+$` | 是 | research.md §2；MAJOR 部分决定兼容性 |
| `bundle_id` | `str` | 是 | 本次生成的唯一标识（生产方生成，如 UUID） |
| `project_id` | `str` | 是 | 生产方项目标识，用于跨次生成关联 |
| `generated_at` | `datetime`（ISO 8601） | 是 | |
| `producer` | `{name: str, version: str}` | 是 | |
| `source_revision` | `str` | 是 | 生产方源资料的版本标识（如 commit hash），自由格式字符串 |
| `frameworks` | `list[str]` | 是（可为空列表） | 生产方使用的技术栈标签，仅描述性，消费方 MUST NOT 据此分支处理（FR-016/业务无关性同理适用于技术栈无关性） |
| `coordinate_spaces` | `list[BundleCoordinateSpace]` | 是（至少 1 项） | 声明本 bundle 实际使用到的坐标空间集合，消费方用于快速判断是否需要处理 `design_pixels`/`normalized_1000` 换算 |
| `default_viewports` | `list[Viewport]` | 否，默认 `[]` | `Viewport = {name: str, width: int, height: int}`，`design_pixels` 坐标的参照画布尺寸（描述性，不用于强制越界校验——`design_pixels` 值域本身只做非负校验，见 contracts） |
| `content_files` | `dict[str, ContentFileEntry]` | 是 | key 为相对文件名（`screens.jsonl` 等）；`ContentFileEntry = {required: bool, sha256: str \| None, record_count: int \| None}` |
| `metadata` | `dict[str, Any] \| None` | 否 | |

**未知字段处理**：`BundleManifest`（以及全部内容记录模型）使用
`model_config = ConfigDict(extra="allow")`；未知字段被保留在 Pydantic 的 `model_extra` 中，
不触发校验失败，也不参与任何既有字段的校验逻辑（research.md §2）。

## 2. `ui_index/errors.py` — 校验错误模型

### 2.1 `UiIndexErrorCode`

```python
class UiIndexErrorCode(StrEnum):
    BUNDLE_DIR_NOT_FOUND = "bundle_dir_not_found"          # FR-003：目录不存在/不可读
    SCHEMA_UNSUPPORTED_MAJOR = "schema_unsupported_major"
    MANIFEST_MISSING = "manifest_missing"
    CONTENT_FILE_MISSING = "content_file_missing"
    JSONL_SYNTAX_ERROR = "jsonl_syntax_error"
    FIELD_TYPE_ERROR = "field_type_error"
    DUPLICATE_ID = "duplicate_id"
    DANGLING_REFERENCE = "dangling_reference"
    PARENT_CYCLE = "parent_cycle"
    DANGLING_GUARD_REFERENCE = "dangling_guard_reference"
    MISSING_COORDINATE_SPACE = "missing_coordinate_space"
    COORDINATE_OUT_OF_RANGE = "coordinate_out_of_range"
    INVALID_CONFIDENCE = "invalid_confidence"
    INVALID_DIAGNOSTIC_CONFIDENCE = "invalid_diagnostic_confidence"
    PATH_TRAVERSAL = "path_traversal"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    CHECKSUM_MISMATCH = "checksum_mismatch"
```

字符串值即 FR-003 要求的"稳定 error_code"，MUST NOT 在后续修订中改名（只能新增）。

### 2.2 `ValidationIssue`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `error_code` | `UiIndexErrorCode` | 是 | |
| `file` | `str \| None` | 否 | 相对 bundle 根目录的文件名；`BUNDLE_DIR_NOT_FOUND` 时为 `None` |
| `line` | `int \| None` | 否 | JSONL 行号（从 1 开始）；manifest.yaml 相关错误、`BUNDLE_DIR_NOT_FOUND` 时为 `None` |
| `field_path` | `str \| None` | 否 | 如 `"elements[42].normalized_bounds.x1"` |
| `message` | `str` | 是 | 人类可读原因 |

### 2.3 `ValidationReport`

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | `bool` | `len(issues) == 0` |
| `bundle_dir` | `str` | |
| `issues` | `list[ValidationIssue]` | 空列表 = 通过 |
| `manifest` | `BundleManifest \| None` | 仅当 manifest 本身成功解析时非空（即便后续内容文件校验失败，manifest 身份信息仍可用于错误报告与审计） |

## 3. `ui_index/bundle.py` — 加载后的可查询对象

### 3.1 `UiIndexBundle`

内部持有（校验通过后才会构造）：`manifest: BundleManifest`、按 ID 建立的索引字典
（`screens: dict[str, Screen]`、`elements: dict[str, Element]`、
`transitions: dict[str, Transition]`、`flows: dict[str, Flow]`、
`diagnostics: dict[str, Diagnostic]`）、辅助倒排索引（文字/别名 → element_id 列表、
role → element_id 列表、screen_id → element_id 列表、from_screen_id/trigger_element_id/
to_screen_id → transition_id 列表)。

```python
class UiIndexBundle:
    @classmethod
    def load(cls, bundle_dir: str) -> "UiIndexBundle":
        """校验并加载；FR-002 任一项失败时抛出 UiIndexValidationError(report)。"""

    def query_screen(self, screen_id: str) -> ScreenQueryResult | None: ...
    def query_by_text(self, text: str) -> list[ElementQueryResult]: ...
    def query_by_alias(self, alias: str) -> list[ElementQueryResult]: ...
    def query_by_role(self, role: str) -> list[ElementQueryResult]: ...
    def query_transitions(
        self,
        *,
        from_screen_id: str | None = None,
        trigger_element_id: str | None = None,
        to_screen_id: str | None = None,
    ) -> list[Transition]: ...
```

查询命中多个候选时返回值 MUST 按 `element_id`/`transition_id` 字典序排序（确定性排序，
research.md、FR-004）；未命中返回空列表/`None`，不抛异常、不猜测近似匹配（FR-004）。

### 3.2 `UiIndexValidationError`

标准异常，携带 `report: ValidationReport`；preflight 阶段捕获后转成执行前失败（FR-012），
不允许静默降级为"部分可用"。

## 4. 运行时集成模型（`ui_index/runtime_adapter.py`）

### 4.1 `VisibleElementHint`（发送给模型的唯一形态，对应 FR-015、research.md §10）

| 字段 | 类型 | 说明 |
|---|---|---|
| `element_id` | `str` | 用于审计关联（§5），MUST NOT 单独构成"内部实现细节"——element_id 是 bundle 内的抽象标识，不是源码符号 |
| `visible_texts` | `list[str]` | |
| `aliases` | `list[str]` | |
| `role` | `str` | |
| `region` | `str` | |
| `anchor_texts` | `list[str]` | 由 `anchors` 引用的 element 的 `visible_texts` 摘要（只取文字，不透出对方 element_id 之外的字段） |
| `neighbor_texts` | `dict[Literal["up","down","left","right","near"], list[str]]` | 由 `neighbors` 引用的 element 的 `visible_texts` 摘要 |

**结构性保证**：`VisibleElementHint` 的字段集合是这张表的全部——模型定义中不存在
`source_evidence`/`metadata`/`screen_id`/`normalized_bounds` 等字段，`to_visible_hint()`
（research.md §10）不接受"透传未知字段"的调用路径。这是 FR-015/CHK031 要求的结构性保证。

### 4.2 `IndexUsageAuditRecord`（对应 FR-013，`domain/run.py::ActionIteration.ui_index_audit`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `bundle_id` | `str` | 来自 `BundleManifest.bundle_id` |
| `schema_version` | `str` | |
| `outcome` | `Literal["hit", "no_match", "inconsistent", "not_configured"]` | `not_configured` 仅用于显式记录"本次运行未配置索引"这一审计基线状态（不代表异常） |
| `matched_screen_id` | `str \| None` | `outcome == "hit"` 时非空 |
| `hint_element_ids` | `list[str]` | 本次实际组装进 `VisibleElementHint` 列表的 element_id（用于 SC-006/CHK027 的坐标溯源审计） |
| `candidate_transition_ids` | `list[str]` | 命中 screen 下相关的 transition_id（供 Planner 参考，不代表已发生跳转） |
| `no_match_reason` | `Literal["no_screen_matched", "screen_content_inconsistent"] \| None` | `outcome` 为 `no_match`/`inconsistent` 时非空 |
| `grounder_outcome` | `Literal["not_attempted", "succeeded", "failed"]` | 与 `outcome` 独立字段（CHK027/FR-013 新增说明）：即使 `outcome == "hit"`，`grounder_outcome` 仍如实反映本次 Grounder 是否成功定位，命中不隐含定位成功 |

## 5. 既有模型的增量修改

| 文件 | 修改 | 对应 |
|---|---|---|
| `models/provider.py` | `PlannerRequest` 新增 `ui_index_hints: list[VisibleElementHint] = Field(default_factory=list)` | FR-007 |
| `models/provider.py` | `GroundingRequest` 新增 `ui_index_candidates: list[dict[str, Any]] = Field(default_factory=list)`（每项 `{bbox, coordinate_space: "normalized_1000", confidence, label, reason}`，与既有 `ocr_candidates` 同构） | FR-007/FR-009 |
| `domain/run.py` | `ActionIteration` 新增 `ui_index_audit: IndexUsageAuditRecord \| None = None` | FR-013 |
| `config.py` | `AgentConfig` 新增 `ui_index: UiIndexConfig = Field(default_factory=UiIndexConfig)`；`UiIndexConfig = {bundle_dir: str \| None = None, screen_match_min_score: float = 0.6, screen_inconsistency_max_missing_ratio: float = 0.7, max_content_file_bytes: int = 50_000_000, max_content_file_records: int = 200_000, max_bundle_total_bytes: int = 200_000_000}` | FR-001/011，research.md §3/§9 |

## 6. 实体关系图（文字版）

```
BundleManifest 1---* ContentFileEntry（每个内容文件一条，含 sha256/record_count）

Screen 1---* Element（Element.screen_id → Screen.screen_id）
Screen 0..1 --- Screen（parent_screen_id，禁自引用/成环）
Element 0..1 --- Element（parent_element_id，禁自引用/成环）
Element *---* Element（anchors, neighbors，均为悬空即失败的引用）

Transition *---1 Screen（from_screen_id, to_screen_id）
Transition *---1 Element（trigger_element_id）
Transition *---* (Element | 内联命名条件)（guards，判别联合）

Flow *---1 Screen（start_screen_id, completion_screen_id）
Flow 1---* FlowStep（有序，FlowStep 判别联合引用 Transition 或 Element）
Flow *---* (Element | 内联命名条件)（preconditions，同 guards 判别联合）

Diagnostic 0..1---1 (Screen | Element | Transition)（target_ref，可选目标引用）

UiIndexBundle（消费方运行时对象）1---1 BundleManifest
UiIndexBundle 1---* Screen/Element/Transition/Flow/Diagnostic（全部通过 FR-002 校验后的记录）

ActionIteration（既有） 0..1---1 IndexUsageAuditRecord
PlannerRequest（既有） 0..*---1 VisibleElementHint（ui_index_hints）
GroundingRequest（既有） 0..*---1 dict（ui_index_candidates，源自 Element.normalized_bounds）
```
