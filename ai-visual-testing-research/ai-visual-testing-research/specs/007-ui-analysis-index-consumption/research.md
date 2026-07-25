# Phase 0 Research: 外部 UI 分析索引消费与通用索引生产规则

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本文件记录 Phase 1 设计前必须锁定的技术决策。除非另有说明，"决策"直接对应 spec.md 中已确定的
FR/SC/Clarifications，本文件负责把它们落成具体的格式、算法与代码落点；不重新讨论 spec.md 已经
决定的范围问题。

## 0. 现状代码复用清单

设计前审查了 `vnc_agent/src/vnc_agent/` 现状代码，找到以下可以直接复用、避免重复造轮子的现成
扩展点：

| 现状代码 | 与本 feature 的关系 |
|---|---|
| `models/coordinate_space.py::CoordinateSpace = Literal["pixel", "normalized_1000"]`、`resolve_pixel_bbox()` | Grounder 侧已有的坐标空间 fail-safe 换算/拒绝机制；`normalized_1000` 语义与本 feature bundle 的 `normalized_1000` 完全一致（0–1000 千分比整数），可直接复用换算逻辑（§4） |
| `domain/grounding.py::GroundingCandidate`、`GroundingResult` | Grounder 候选与结果的既有模型；bundle 提示只能以"候选/证据"的身份进入这一既有管线，不能新开一条绕过它的路径（FR-009） |
| `domain/action.py::SemanticAction`、`TargetDescription` | `SemanticAction` 已经 MUST NOT 携带裸坐标（FR-013，见现状注释）；`TargetDescription.nearby_texts` 已经是"邻接文字"概念的先例，本 feature 的可见语义提示复用同一表达方式 |
| `models/provider.py::PlannerRequest`、`GroundingRequest` | Planner/Grounder 的既有请求模型，`GroundingRequest` 已有 `ocr_candidates`/`template_candidates: list[dict]` 字段——本 feature 的运行时提示按同一模式新增字段，不改变既有字段语义（§9） |
| `config.py::AgentConfig` 及其子配置（`PerceptionConfig`、`GroundingConfig`、`PlanningConfig` 等） | 既有"可选子配置、默认值即禁用/保守值"的模式；本 feature 的索引配置作为新的子配置加入，未配置时保持空/None（FR-001/011） |
| `domain/run.py::ActionIteration` | 每次动作迭代的既有记录容器（含 `grounding_result`、`recovery_attempts` 等可选字段）；审计记录作为新的可选字段加入同一容器，复用既有 `TestRun` → `StepRecord` → `ActionIteration` → HTML/JSON 报告的既有序列化链路，不新建存储表（FR-013、Constitution "制品与可观测性"） |
| `runtime/telemetry.py::log_event()`、`ModelCallAudit` | 既有结构化 JSON Lines 日志入口与审计类模型先例；索引使用审计复用同一日志机制，不新增日志格式 |
| `tests/unit/test_no_business_keywords_in_core.py` | 已存在的"核心代码无业务关键词"契约测试；本 feature 的业务无关性测试（SC-009）扩展这个既有测试文件的检查范围，而不是新建一个平行测试 |
| `api/cli.py`（Typer app） | 既有 CLI 入口；`ui-index validate`/`ui-index query` 作为新的子命令组加入，不新建独立可执行文件 |

## 1. Bundle 序列化格式

**Decision**: `manifest.yaml`（YAML）+ `screens.jsonl`/`elements.jsonl`/`transitions.jsonl`/
`flows.jsonl`/`diagnostics.jsonl`（JSON Lines，每行一条独立 JSON 对象）。

**Rationale**:
- manifest 是单一、结构化程度高、需要良好可读性和注释友好性的元信息文件，YAML 是本项目既有
  配置格式（`config.py` 已用 `PyYAML`），复用现有依赖，不新增解析库。
- 内容文件（screens/elements/transitions/flows/diagnostics）是同构记录的重复列表，JSONL 天然
  支持逐行流式读取、逐行定位错误（行号）、增量追加，且任何语言/工具链都能生成（不要求生产方
  引入特定 JSON 库之外的依赖），满足 FR-002 的"JSONL 语法错误"校验类别与 FR-003 的"行号"要求。
- 不选单一大 JSON 文件：大 JSON 文件必须整体解析后才能发现语法错误或校验单条记录，不满足
  "MUST 在不完整加载全部内容到内存的前提下尽早检测"（Edge Cases，资源限制），且错误定位只能到
  文件而非行。
- 不选 SQLite/二进制格式：生产方技术栈差异巨大（C#/Java/XAML/Web/Figma），要求生产方生成二进制
  格式会显著提高生产门槛，且破坏"通用、语言无关"的 skill 目标（FR-020）；纯文本格式任何工具链都
  能不依赖专用库生成。

**Alternatives considered**: 单一 JSON 文件（拒绝，见上）；SQLite（拒绝，见上）；Protocol
Buffers/其他二进制 schema（拒绝：要求生产方安装代码生成工具，且失去人工可读性，不利于
"人工排查"离线溯源场景）。

## 2. Schema 版本策略

**Decision**: `schema_version` 字段值为字符串 `"MAJOR.MINOR"`（如 `"1.0"`），起始版本 `1.0`。
消费方按 MAJOR 做二元判断（受支持集合是一个显式白名单，本 feature 初始只含 `1`）；同一受支持
MAJOR 内的任意 MINOR，消费方 MUST 使用"宽容读取"（读取已知字段、未知字段原样保留在
`metadata`/`extra` 透传字段中，不因未知字段报错）。

**Rationale**: 直接落实 spec.md FR-002/Clarifications 已确定的规则；用 Pydantic v2 的
`model_config = ConfigDict(extra="allow")`（或等价的"已知字段严格校验 + 未知字段透传"策略）即可
零额外代码实现"未知字段保留"，不需要手写通用 JSON diff/patch 逻辑。

**Alternatives considered**：语义化版本号 `MAJOR.MINOR.PATCH`（拒绝：bundle 是"生成物"而非
"发布的软件包"，PATCH 级别的区分对消费方读取行为没有意义，徒增生产方负担）。

## 3. JSONL 流式读取与失败策略

**Decision**: `ui_index/jsonl_reader.py` 提供一个生成器 `iter_jsonl(path) -> Iterator[tuple[int, dict]]`，
按行读取、每行独立 `json.loads`，行号从 1 开始；解析失败立即产出一个携带该行号的
`ValidationIssue`（不中断整个文件的读取——继续读取后续行以便一次性收集尽量多的问题）。校验
（`ui_index/validator.py`）在一次流式遍历中做完"语法 + 字段类型 + 唯一 ID + 引用登记"，第二遍
（引用只有在全部 ID 登记后才能确认悬空与否）做"引用完整性 + 坐标空间 + 可信度 + parent 循环"
检查。全部问题汇总进单个 `ValidationReport`，而不是遇到第一个错误就中止（FR-003 要求"稳定错误
描述"，一次性给出全部问题比反复提交-发现单个错误的体验更符合生产方交付前自检的场景）。

**失败策略**：`ValidationReport.ok` 为 `False` 时，bundle 整体 MUST NOT 进入可查询/可用于运行时
状态（FR-012）；`UiIndexBundle.load()` 在这种情况下抛出 `UiIndexValidationError(report)`，调用方
（preflight 阶段）捕获后作为执行前失败处理，不吞掉细节。

**资源限制默认值**（Assumptions 明确阈值属实现期配置，此处给出本 feature 的默认值，可通过
`UiIndexConfig` 覆盖）：单个内容文件 MUST NOT 超过 50 MB 或 200,000 行，取先达到者；bundle 目录
总大小 MUST NOT 超过 200 MB。读取时按字节/行数累计计数，超限立即停止读取并产出
`RESOURCE_LIMIT_EXCEEDED`，不要求先加载完整文件再计数。

**Alternatives considered**：遇到第一个错误立即中止（拒绝：不符合"生产方一次性看到全部问题"
的交付体验，且与其它同类 validate 工具惯例不符）；先整体读入内存再统一校验（拒绝：违反资源限制
要求与"弱配置电脑"约束）。

## 4. 坐标空间 (`coordinate_space`) 与既有 Grounder 坐标协议的关系

**Decision**: bundle 侧 `coordinate_space` 取值为 `"design_pixels"` 或 `"normalized_1000"`
——**故意不复用**既有 `models/coordinate_space.py::CoordinateSpace` 的字面量 `"pixel"`，改用
`"design_pixels"`。`normalized_1000` 语义与既有 Grounder 协议完全相同（0–1000 千分比整数，按
画面宽高换算），可直接复用 `resolve_pixel_bbox()` 的换算分支；`design_pixels` 特指"生产方设计
画布的原始像素坐标"，是一个新概念，与运行时 VNC 截图的物理像素坐标（既有协议里的 `"pixel"`）
不是同一件事——生产方声明的设计画布分辨率可能与被测应用实际运行分辨率不同。

**Rationale**: 如果直接复用字面量 `"pixel"`，容易被后续维护者误读为"这些坐标可以像 Grounder 的
`"pixel"` 候选一样直接当作运行时像素坐标使用"，从而破坏 FR-009（索引坐标 MUST NOT 绕过
Grounder）。用不同的字面量强制在类型层面区分"生产方设计时坐标"与"运行时截图坐标"，任何试图把
`design_pixels` 数值直接传给 `models/coordinate_space.py::resolve_pixel_bbox()` 的代码在 review
时都会因为字面量不匹配而立刻显眼。

`normalized_bounds`（Element 的可选精确定位先验）内部使用的 `coordinate_space` 只允许
`"normalized_1000"`（见 §6 data-model 决策），`design_pixels` 只用于 `manifest.default_viewports`
与可选的粗粒度 `region` 描述，不进入 Grounder 候选管线。

**Alternatives considered**：直接复用 `"pixel"` 字面量（拒绝，见上，混淆风险）；为 bundle 单独定义
一套完全独立的坐标空间类型系统、不做归一化（拒绝：normalized_1000 复用既有换算代码的收益足够大，
没有理由重新发明）。

## 5. 可信度 (`confidence`) 复合结构

**Decision**: `Confidence` 模型 = `{level: Literal["confirmed", "statically_inferred",
"visually_confirmed", "requires_runtime_verification"], score: float | None (0.0–1.0)}`。
`level` 必填，`score` 可选。

**Rationale**: 直接落实 spec.md Clarifications 的结论；用 Pydantic 建一个独立的可复用
`Confidence` 子模型（而不是把 `level`/`score` 摊平进每个实体），使 Element/Transition/
Diagnostic 共享同一验证逻辑与同一 JSON Schema 片段，避免三处重复实现"合法取值范围"校验。

## 6. `region` 与 `normalized_bounds` 的关系（解决 spec.md 遗留的 CHK018 歧义）

**Decision**: 两者是独立的、语义不同的可选字段，不是同一信息的两种表达：

- `region`：粗粒度、定性的区域标签，`Literal["header", "toolbar", "sidebar_left",
  "sidebar_right", "body", "footer", "statusbar", "modal", "unknown"]`，供可见语义提示直接
  使用（人类/模型可读），生产方即使没有做像素级分析也能填写。
- `normalized_bounds`：精确的、可选的定位先验矩形 `{coordinate_space: "normalized_1000",
  x1, y1, x2, y2}`，只在生产方确实做了像素级/布局级分析时提供，专门喂给 Grounder 候选管线
  （§9），不直接进入发送给模型的可见语义文本。

两者都存在时，消费方 MUST NOT 尝试用其中一个反推另一个，也不做一致性强校验（生产方可能在不同
分析阶段独立得出两者）——`region` 只用于文本提示，`normalized_bounds` 只用于坐标候选，职责不
重叠。

**Alternatives considered**：把 `region` 定义为 `normalized_bounds` 的粗化版本、强制二者一致
（拒绝：会要求生产方即使只填了粗粒度标签也要保证与像素矩形不矛盾，提高生产门槛，且 spec.md 从未
要求两者语义相同）。

## 7. 邻接关系 (`anchors`/`neighbors`) 表达方式（解决 CHK019）

**Decision**: `anchors: list[str]`（element_id 列表，作为该元素最稳定、最适合用于 OCR
相对定位的参照元素——生产方主观标注的一个子集）；`neighbors: list[NeighborRef]`，
`NeighborRef = {direction: Literal["up", "down", "left", "right", "near"], element_id: str}`，
允许同一方向出现多条记录（不强制唯一）。

**Rationale**: 固定方向枚举 + 允许重复，既满足 FR-004/FR-007 "上下左右"查询维度的确定性，又不
强迫生产方在"只有一个邻居"的简单场景和"同一方向有多个邻居"的复杂场景之间做取舍。`anchors` 与
`neighbors` 是两个独立概念：前者回答"用什么定位我"，后者回答"我旁边有什么"——都在 FR-004 的
"邻接元素"查询范围内，查询服务合并暴露。

## 8. `supported_actions` 与 `transition_type` 的开放/封闭词表（解决 CHK012）

**Decision**: `transition_type` 是封闭枚举 `Literal["modal", "replace", "overlay",
"state_change"]`（spec.md 已固定）。`supported_actions` 是开放词表：字段类型为
`list[str]`，每个元素 MUST 匹配 `^[a-z][a-z0-9_]*$`（小写 snake_case），消费方只做格式校验，
不做词表成员校验；`trigger_action`（Transition）同样是开放 snake_case 字符串，不要求与
`supported_actions` 中的值相同（trigger_action 描述"实际触发该跳转的动作"，可能是
`supported_actions` 中某一项，也可能是隐式动作如 `auto_navigate`）。产出方 skill 的
`references/confidence-rules.md`/`bundle-contract.md` 给出推荐词表（`click`、`double_click`、
`type_text`、`select`、`toggle`、`hover`、`drag`、`scroll`、`expand`、`collapse`、`submit`、
`focus` 等）供参考，但消费方 MUST NOT 硬编码这份词表作为校验白名单——不同 UI 框架的可执行动作
集合天然是开放的，把它做成封闭枚举会让 skill 无法覆盖未预见的 UI 范式，且封闭词表本身就是一种
隐性的"业务/框架耦合"，与 Principle VI 的通用性要求冲突。

## 9. Planner/Grounder 运行时集成点

**Decision**:
- `models/provider.py::PlannerRequest` 新增 `ui_index_hints: list[VisibleElementHint] =
  Field(default_factory=list)`（可选、默认空列表，未配置索引或未命中时天然为空，Planner 现有
  处理逻辑不需要为"空列表"专门分支）。
- `models/provider.py::GroundingRequest` 新增 `ui_index_candidates: list[dict[str, Any]] =
  Field(default_factory=list)`，与既有 `ocr_candidates`/`template_candidates` 同构（同一"候选
  证据来源"角色），只包含 `normalized_bounds` 换算得到的候选区域 + 标签 + 置信度，不包含裸
  `SemanticAction` 坐标（FR-009）。Grounder 现有的候选融合/排序逻辑天然把这份候选和 OCR/模板
  候选一视同仁地参与竞争，不新开"索引优先"特权通道。
- `domain/run.py::ActionIteration` 新增 `ui_index_audit: IndexUsageAuditRecord | None = None`。

**Rationale**: 三处都是在既有请求/记录模型上新增一个默认安全（空/None）的可选字段，未配置索引
时的既有单元测试/集成测试不需要任何改动即可继续通过（FR-011 的"行为完全一致"在类型系统层面
就是"新增字段默认值不影响任何既有断言"）。

**画面匹配算法**（"索引命中当前画面"的判定，落实 FR-014 与 Assumptions 中"具体阈值属于实现期
决定"）：
1. 取当前 `StructuredScreen.ocr_items` 识别出的全部文字，与索引中每个 `Screen` 的
   `visible_titles ∪ aliases` 以及该 screen 下 `Element.visible_texts ∪ aliases` 做归一化
   文本匹配（复用现状 OCR 文本归一化容差逻辑，不新造字符串匹配算法）。
2. 每个候选 screen 计算 `match_score = 匹配到的 (标题∪别名∪元素文字) 数量 / 该 screen 声明的
   (标题∪别名∪元素文字) 总数`。取 `match_score` 最高的 screen 作为候选命中；
   `match_score < screen_match_min_score`（默认 `0.6`，`UiIndexConfig` 可调）时判定为
   **未命中**（FR-014 第一分支："索引中找不到当前画面"）。
3. 候选命中后，进一步计算该 screen 下 `confidence.level in {"confirmed",
   "visually_confirmed"}` 的 element 中，`visible_texts`/`aliases` 未在当前 OCR 结果中找到的
   比例 `missing_ratio`。`missing_ratio > screen_inconsistency_max_missing_ratio`（默认
   `0.7`，可调）时判定为**不一致**（FR-014 第二分支："索引与当前截图明显不一致"），回退且
   审计记录该原因；否则判定为**命中**，进入 §6/§7 决策产出的 hint 组装。

**Alternatives considered**：用视觉/感知哈希做画面相似度匹配（拒绝：需要额外模型/依赖，且
"弱配置电脑"约束下不适合引入新的图像相似度计算；文本匹配复用现有 OCR 管线零新增依赖）；固定
"至少 N 个标题匹配"的绝对计数阈值（拒绝：不同 screen 声明的文字数量差异很大，比例阈值更公平）。

## 10. 可见语义提示 (`VisibleElementHint`) 白名单清理

**Decision**: `ui_index/sanitizer.py::to_visible_hint(element: Element) -> VisibleElementHint`
是一个**显式字段拷贝函数**（allow-list，不是 blacklist/脱敏函数）：只读取
`visible_texts`、`aliases`、`role`、`region`、`anchors`（转换为对应 anchor 元素的
`visible_texts` 摘要，不透出 anchor 的 element_id 之外的内部字段）、`neighbors`（同理，只转换
方向 + 对方 `visible_texts` 摘要）六类信息，构造一个全新的 `VisibleElementHint` 对象。函数体
中不存在任何"复制整个 Element 再删除敏感字段"的路径——`source_evidence`、`metadata`、
`element_id`/`screen_id` 等字段从代码结构上就不可能进入 `VisibleElementHint`（FR-015/CHK031
要求的"结构性保证"而非"人工审查保证"，见 data-model.md §5）。

**Rationale**: allow-list 天然对"未来 bundle schema 新增一个恰好包含内部实现细节的字段"免疫
——新字段不会被自动透出，需要显式修改 `to_visible_hint()` 才会出现在模型上下文中，任何这类
修改都会在 PR diff 中显眼。反之 blacklist（"复制所有字段再删掉几个"）在 schema 演进时容易
悄悄泄漏新字段。

## 11. CLI 与配置入口

**Decision**: 在既有 `api/cli.py`（Typer app）新增子命令组 `ui-index`：
- `vnc-agent ui-index validate <bundle_dir>`：执行 §3 的完整校验，退出码非零表示失败，输出
  `ValidationReport` 的人类可读摘要（默认）或 `--json` 结构化输出。
- `vnc-agent ui-index query --screen <id> | --text <t> | --alias <a> | --role <r> |
  --transition-from <id>`：对一个已校验 bundle 发起 §4 FR-004 定义的查询，输出结构化结果。

配置入口：`config.py::AgentConfig` 新增 `ui_index: UiIndexConfig = Field(default_factory=UiIndexConfig)`
子配置，`UiIndexConfig.bundle_dir: str | None = None`（`None` = 未启用索引，FR-001/011 的默认
安全值）。测试运行时若 `bundle_dir` 非空但加载/校验失败，preflight 阶段（既有 run 启动流程中
配置解析之后、第一步执行之前）MUST 抛出错误并阻止执行（FR-012）。

**Rationale**: 复用既有 Typer app 而非新建独立可执行文件，符合 Constitution"单进程模块化单体
架构"约束；子命令组模式与其它现有 `vnc-agent <noun> <verb>` 风格一致（需在实现期核对现状
`cli.py` 的既有子命令组命名习惯）。

## 12. 通用生产者 skill 的结构与校验工具

**Decision**: skill 位于 `.agents/skills/generate-ui-analysis-index/`，遵循用户在本次
`/speckit-plan` 输入中给出的目录结构（`SKILL.md` + `agents/openai.yaml` + `references/*.md` +
`assets/bundle-template/`）。`references/bundle-contract.md` 的内容 MUST 与
`specs/007-ui-analysis-index-consumption/contracts/ui-analysis-bundle-v1.md`
（本 feature 的权威契约）保持一致——`tasks.md` 中安排一个显式的一致性检查任务（例如脚本比对两份
文档中的字段清单），防止后续维护时只改一处导致漂移。`assets/bundle-template/` 存放"空白模板"
（可直接复制的文件骨架，字段占位但类型/结构合法）与"最小有效示例"（真实可通过 validator 的最小
bundle）两套内容。

skill 校验使用用户机器上已安装的 `skill-creator` skill 自带脚本
`scripts/quick_validate.py <skill_directory>`（当前环境路径：
`~/.claude/skills/skill-creator/scripts/quick_validate.py`，是用户级工具而非本仓库文件，实现期
通过 `Skill(skill-creator)` 或直接调用该脚本路径执行）。该脚本只校验 `SKILL.md` 的 YAML
frontmatter（`name`/`description` 等字段的格式与长度），不校验目录结构本身或 bundle 内容——
bundle 内容的正确性仍然由 `assets/bundle-template/` 中的最小有效示例通过本 feature 的
`ui-index validate` CLI 命令来证明（User Story 4 Acceptance Scenario 3）。

**Rationale**: 直接采纳用户给出的目录结构与工具链，不引入额外的 skill 打包/校验框架。

## 13. 拒绝的整体性替代方案

- **把索引数据直接嵌入 testcase YAML**：拒绝。索引是"外部项目生成、体量可能远大于单个
  testcase"的独立制品，嵌入 YAML 会导致 testcase 文件膨胀且失去独立版本化/独立校验的能力，
  也违反"索引是可选依赖"的解耦要求（FR-001 明确是"目录路径"而非内联数据）。
- **消费方在运行时对 bundle 做二次分析/推断补全缺失字段**：拒绝。消费方的职责边界是"读取、
  校验、查询、使用"，任何"补全/推断"都越界到生产方职责，且违反 FR-017/018 的黑盒边界。
- **用一个通用 JSON Schema 文件描述 bundle 格式、消费方用通用 JSON Schema 校验器做全部校验**：
  部分采纳——字段类型/必填性校验确实可以用 JSON Schema 表达并复用现成校验库，但引用完整性
  （跨记录、跨文件）、parent 循环检测、坐标空间语义校验、resource limit 流式检测这几类校验
  是 JSON Schema 表达能力之外的，仍需专用校验代码；因此不追求"纯 JSON Schema 方案"，data-model.md
  §5 的 Pydantic 模型只覆盖字段级校验，§ referential integrity 校验是独立的手写遍历。
