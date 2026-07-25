# Feature Specification: 外部 UI 分析索引消费与通用索引生产规则

**Feature Branch**: `007-ui-analysis-index-consumption`

**Created**: 2026-07-25

**Status**: Draft

**Input**: 实现"外部 UI 分析索引消费与通用索引生产规则"。当前 vnc-agent 是通过 VNC 截图和键鼠事件执行
黑盒 GUI 自动化测试的通用框架。其他项目可能拥有 C#、Java、XAML、Web、Figma 或其他 UI 源码和设计资料，
并能够在各自项目中分析出画面、元素、相对位置、行为和页面跳转关系。本 feature 明确分离"索引生产方"
（外部项目）与"索引消费方"（当前 vnc-agent）：vnc-agent 只负责读取、校验、查询和使用外部项目已生成的
版本化 UI analysis bundle，为 testcase 编写与 Planner/Grounder 提供可见语义定位提示；vnc-agent 不得
扫描、解析或编译任何外部项目源码，不得引入语言相关的源码分析依赖，不得在运行时读取被测应用内部状态。
索引只能作为定位提示，不能替代基于当前 VNC 截图的目标定位与操作后独立验证。本 feature 还需产出一份
通用、语言与 UI 框架无关的 skill 文件（`.agents/skills/generate-ui-analysis-index/`），指导外部项目生成
符合同一 schema 的 bundle。

## Clarifications

### Session 2026-07-25

- Q: 当前项目是否提供任何源码分析能力（扫描/解析外部项目源码）？ → A: 不提供；当前项目只消费外部项目
  已生成的分析结果，不做任何源码分析。
- Q: 谁负责生成标准 UI analysis bundle？ → A: 由外部项目自行生成；当前项目不生成 bundle，只读取、
  校验、查询和使用。
- Q: 通用生产者 skill 是否需要附带针对某种语言/框架的实际分析器实现（如 Roslyn、MSBuild、XAML 解析
  器）？ → A: 不需要；该 skill 只规定分析目标、bundle 输出格式、可信度与证据来源的表达方式，以及交付
  前的校验流程，不实现任何具体语言的分析器，外部项目自行选择技术手段。
- Q: bundle 的具体文件与目录形式是什么？ → A: bundle 以目录形式交付，包含固定文件名：`manifest.yaml`、
  `screens.jsonl`、`elements.jsonl`、`transitions.jsonl` 为必需文件；`flows.jsonl`、
  `diagnostics.jsonl` 为可选文件。
- Q: schema 版本从哪个版本号开始，版本兼容策略是什么？ → A: schema 版本从 1.0 开始，遵循
  MAJOR.MINOR 语义化版本；不支持的主版本必须拒绝，受支持主版本内的次版本差异必须在保留未知字段
  （而非丢弃或报错）的前提下兼容读取。
- Q: 未配置索引时，既有 testcase 的行为是否允许变化？ → A: 不允许；未配置索引时系统行为必须与本
  feature 实现前完全一致。
- Q: 用户明确配置了索引但索引无效时应如何处理？ → A: 必须在测试执行前失败并返回可诊断错误，不得
  静默继续使用无效或部分有效的数据。
- Q: 索引查询/运行时匹配无命中时应如何处理？ → A: 回退到原有 Planner/Grounder 流程完成当前步骤，
  并记录审计信息，不得因未命中而中止或失败当前测试步骤。
- Q: 索引中记录的设计坐标或归一化坐标能否直接作为最终点击坐标？ → A: 不能；索引位置信息只能作为
  Grounder 的定位提示，最终点击坐标必须由 Grounder 基于当前实时 VNC 截图计算得出。
- Q: 发送给模型的索引上下文应限定为哪些内容？ → A: 只包含屏幕可见文字、角色、相对区域与邻接关系等
  可见语义与定位提示。
- Q: bundle 中记录的源码文件路径、类名、事件处理器等非可见实现细节，是否需要从 bundle 中彻底剔除？
  → A: 不需要剔除；这些信息可以作为离线溯源信息保留在 bundle 数据与本地审计记录中供人工排查，但默认
  不得作为发送给模型的上下文的一部分。
- Q: 通用索引格式（schema）本身能否包含 POS 或其他特定行业的固定字段？ → A: 不能；通用索引格式与
  当前项目核心实现必须业务无关，特定行业字段只允许出现在 testcase/fixture/profile 层。
- Q: 如何验证核心能力（读取/校验/查询/运行时提示/审计）确实业务无关？ → A: 至少使用两个互不相关的
  GUI fixture 验证核心能力。

### Session 2026-07-25（续，架构/PR 审查 checklist 反馈整改）

- Q: Element 的 `parent` 引用指向自身或形成循环引用时应如何处理？ → A: MUST 被判定为校验失败，
  纳入 FR-002 的引用完整性检查范围，不得静默接受或忽略循环部分。
- Q: Transition 的 guards/preconditions 引用了 bundle 中不存在的状态时应如何处理，"状态"本身在
  bundle 中是否有独立的全局声明文件？ → A: guards/preconditions 只允许引用 bundle 内已存在的
  element ID（表达该元素的可见/启用状态）或该 transition 记录自身内联声明的命名条件；不存在跨
  transition 共享的全局状态注册表。引用不存在的 element ID 或引用未在同一条记录内联声明的命名条件
  MUST 被判定为悬空引用校验失败。
- Q: 坐标字段所属的"坐标空间"应如何声明与校验？ → A: 每个携带坐标的字段 MUST 显式声明
  `coordinate_space`，取值为 `design_pixels`（生产方设计画布的原始像素坐标，非负整数）或
  `normalized_1000`（以 0–1000 闭区间整数表示的千分比归一化坐标，按画面宽/高换算，避免浮点精度
  问题）之一；未显式声明 `coordinate_space` 的坐标字段 MUST 被判定为校验失败。
- Q: FR-002 的"可信度字段落在合法取值范围内"与 FR-025 的四类可信度分类，是同一个字段还是两个独立
  字段？ → A: 是同一个复合字段：必需的 `level` 枚举（即 FR-025 定义的
  confirmed/statically_inferred/visually_confirmed/requires_runtime_verification 四类之一）加
  可选的 `score` 浮点数（0.0–1.0 闭区间，用于同一 `level` 内部排序，不改变 `level` 语义）。FR-002
  的"合法取值范围"校验同时约束 `level` 属于四类枚举、`score`（如提供）落在 [0,1]。
- Q: Edge Cases 中列出的开放问题（JSONL 语法错误、查询命中多个候选、索引目录不存在/不可读与 bundle
  内容无效的区分、索引命中但 Grounder 仍未能定位目标）是否都已有对应的 FR 给出处理结论？ → A: 否，
  此前遗漏；本轮补全：JSONL 逐行语法校验并入 FR-002；查询多候选返回全部候选列表（FR-004 新增）；
  目录不存在/不可读与 bundle 内容无效拆分为两个独立错误类别（FR-003 新增说明）；索引命中状态与
  Grounder 实际定位结果在审计记录中作为两个独立字段记录（FR-013 新增说明）。
- Q: "至少两个互不相关 GUI fixture 验证核心能力业务无关"这一要求，是否也对消费端能力（bundle 读取
  校验、查询、运行时提示与回退审计）单独构成可验收的 Success Criterion，而不只是对 producer skill
  的可移植性（SC-008）生效？ → A: 是；新增 SC-011，明确要求 User Story 1–3 定义的消费端能力也
  必须分别在至少两个互不相关的 GUI fixture 上验证，且至少一个 fixture 需覆盖至少一类 FR-002
  校验失败场景。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 读取并校验外部 UI 分析索引 (Priority: P1)

作为在 vnc-agent 中配置 UI 索引的测试工程师，我明确指定一个外部项目已生成的分析结果目录，系统读取该
目录中的版本化 UI analysis bundle，并在使用前完成 schema 版本、必填文件、字段类型、稳定 ID、重复 ID、
引用完整性、坐标范围、可信度取值、路径穿越与资源限制等方面的校验；bundle 有效时可被后续查询与运行时
使用，bundle 无效时在执行前返回包含字段路径的可诊断错误，不会静默使用损坏或不完整的数据。

**Why this priority**: 这是索引消费能力的地基——没有可靠的读取与校验，后续的查询、testcase 编写辅助
和运行时语义提示都无从谈起，且"无效索引静默生效"是最高风险的失败模式（可能导致测试基于错误的控件
知识做出判断）。

**Independent Test**: 准备若干符合 schema 的最小有效 bundle 与若干覆盖不同错误类别（缺失 manifest、
JSONL 语法错误、重复 ID、悬空引用、越界坐标、非法可信度、路径穿越等）的无效 bundle，逐一指向
vnc-agent 的索引加载入口，验证有效 bundle 被接受、每种无效 bundle 都产生包含具体字段路径的稳定错误、
且不产生任何测试执行副作用；覆盖该验证的最小有效 bundle 至少取自两个互不相关（技术栈或业务领域
不同）的 GUI fixture（SC-011）。

**Acceptance Scenarios**:

1. **Given** 一个目录路径指向符合当前 schema 主版本、字段完整、ID 唯一且引用完整的 bundle，**When**
   测试工程师配置该目录并触发索引加载，**Then** 系统成功加载并可返回该 bundle 的身份（producer、
   schema 版本、bundle 标识）供后续查询与审计使用。
2. **Given** 一个目录路径指向的 bundle 缺少必填的 manifest 文件，**When** 触发索引加载，**Then** 系统
   在执行前返回明确指出"缺失 manifest"及其期望路径的校验错误，并阻止该索引被使用。
3. **Given** 一个 bundle 中两条 element 记录使用了相同的稳定 element ID，**When** 触发索引加载，
   **Then** 系统返回指出重复 ID 及涉及的具体文件/行位置的校验错误。
4. **Given** 一个 transition 记录引用了不存在的 to-screen ID，**When** 触发索引加载，**Then** 系统
   返回指出该引用不完整（悬空引用）及其所在记录的校验错误。
5. **Given** 一个 element 的坐标字段声明 `coordinate_space` 为 `normalized_1000` 但取值超出
   [0, 1000] 闭区间（或声明 `design_pixels` 但取值为负数，或未声明 `coordinate_space`），
   **When** 触发索引加载，**Then** 系统返回指出坐标越界或坐标空间未声明及具体字段路径的校验错误。
6. **Given** 一个 bundle 文件路径包含试图跳出 bundle 根目录的相对路径片段，**When** 触发索引加载，
   **Then** 系统拒绝加载并返回路径穿越错误，不读取该路径指向的任何文件。
7. **Given** 未配置任何 UI 索引目录，**When** 运行任意既有 testcase，**Then** 系统行为与本 feature
   实现前完全一致，不产生索引相关的校验或加载动作。

---

### User Story 2 - 基于索引查询控件与流程知识辅助 testcase 编写 (Priority: P2)

作为编写 testcase 的用户，我希望针对一个已通过校验的 UI 索引，按画面、元素可见文字、OCR 别名、角色
（role）与页面跳转等维度查询结构化控件知识（相对位置、邻接元素、可执行动作、前置条件、点击后预期
画面变化等），以便在编写测试步骤时依据结构化事实而非猜测来描述目标与预期结果。

**Why this priority**: 在索引可靠加载（P1）之后，查询能力是把索引变成"生产力"的第一步，且相较运行时
集成（P3）风险更低、价值可独立验证。

**Independent Test**: 使用两个互不相关（技术栈或业务领域不同）的已知内容有效 bundle，分别按
screen ID、element 可见文字、别名、role 以及 transition 的 from/trigger/to 维度发起查询，验证
返回的结构化结果（相对区域、邻接元素、可执行动作、前置条件、预期变化、可信度、证据来源）与 bundle
源数据一致，且未命中查询返回明确的"未找到"结果而非报错或猜测值（SC-011）。

**Acceptance Scenarios**:

1. **Given** 一个已校验通过的 bundle 包含某 screen 及其若干 element，**When** 按该 screen ID 查询，
   **Then** 返回该画面下全部 element 的结构化知识（角色、可见文字/别名、相对区域、邻接元素、可执行
   动作、可见/启用条件、可信度、证据来源）。
2. **Given** 同一 bundle，**When** 按某个可见文字或 OCR 别名查询元素，**Then** 返回匹配该文字/别名的
   element 记录（可能跨多个 screen），并保留每条记录的可信度与证据来源。
3. **Given** 同一 bundle，**When** 按某个 role（如"按钮"类角色）查询，**Then** 返回该 role 下的全部
   element 及其所属 screen。
4. **Given** 同一 bundle包含一条 transition，**When** 按其 from screen 或 trigger element 查询页面
   跳转，**Then** 返回该 transition 的 trigger action、guards/preconditions、to screen、跳转类型
   （modal/replace/overlay/state-change）、预期新增和消失的可见元素、可信度与证据来源。
5. **Given** 查询条件在 bundle 中没有匹配项，**When** 发起查询，**Then** 系统返回明确的空结果，不
   返回猜测或近似匹配的数据、也不报错。

---

### User Story 3 - Planner/Grounder 运行时获取可见语义提示但不绕过截图定位与独立验证 (Priority: P3)

作为正在执行测试步骤的 Agent 运行时，当已配置并通过校验的 UI 索引中存在与当前画面相关的语义知识时，
Planner 与 Grounder 在做"下一步做什么"与"目标具体在哪里"的判断时，可以获得该画面相关元素的可见文字、
角色、相对区域、邻接文字等提示，用于缩小候选范围、提高定位准确率；但目标坐标仍必须由 Grounder 基于
当前实时 VNC 截图确定，索引中的设计坐标或归一化坐标不得直接成为最终点击坐标，操作后的通过判定仍必须
由 Verifier 基于重新采集的截图与独立证据得出，索引本身不构成动作成功或业务通过的证据。当索引中找不到
当前画面、或索引内容与当前截图明显不一致、或未配置索引时，系统必须回退到原有 Planner/Grounder 流程，
并记录相应的审计信息（包括是否命中、命中的 screen/element/transition ID、bundle 身份与 schema 版本）。
发送给模型的索引上下文只包含屏幕可见语义与定位提示，不默认包含源码文件路径、内部方法名等非可见实现
细节。

**Why this priority**: 这是索引能力对运行时准确率产生实际影响的场景，但同时是风险最高的部分（必须
严格维持"索引仅为提示、不得替代截图定位与独立验证"的边界），因此排在读取校验与离线查询验证过的能力
之后。

**Independent Test**: 使用一组既有回归 testcase（覆盖至少两个互不相关的 GUI fixture，SC-011），
分别在（a）不配置索引、（b）配置索引且当前画面命中、（c）配置索引但当前画面未命中、（d）配置索引
但索引内容与当前截图明显不一致 四种条件下重复运行，验证 (a) 与 (b)(c)(d) 相比在最终点击坐标来源
和 Verifier 判定依据上没有可观察的行为差异（均来自当前截图与独立验证），且 (b)(c)(d) 均产生对应
的审计记录，(c)(d) 均正确回退到原有流程而不是使用索引数据强行继续。

**Acceptance Scenarios**:

1. **Given** 已配置并通过校验的索引中存在与当前截图匹配的 screen 记录，**When** Planner/Grounder 处理
   当前测试步骤，**Then** 系统向 Planner/Grounder 提供该 screen 下相关元素的可见文字、角色、相对区域、
   邻接元素提示，且最终执行的点击坐标由 Grounder 基于当前截图重新计算得出，而非直接取自索引中的设计
   坐标或归一化坐标。
2. **Given** 一次动作执行完成，**When** Verifier 进行通过判定，**Then** 判定依据为操作后重新采集的
   截图与独立证据，索引数据不作为判定依据的一部分，即使索引中该 transition 声明了"预期新增/消失的
   可见元素"，也仅作为 Verifier 的参考线索而非直接判定条件。
3. **Given** 已配置索引，但索引中没有任何 screen 与当前截图匹配，**When** 处理当前测试步骤，**Then**
   系统回退到原有 Planner/Grounder 流程完成本步骤，并记录一条"索引未命中当前画面"的审计信息。
4. **Given** 已配置索引，且索引中存在名义上匹配的 screen，但其记录的可见元素与当前截图明显不一致
   （例如索引声称存在的关键元素在当前截图中完全不可见），**When** 处理当前测试步骤，**Then** 系统
   判定为索引与当前画面不一致，回退到原有流程并记录相应审计信息，不强行采用不一致的索引数据。
5. **Given** 未配置任何索引，**When** 执行既有 testcase，**Then** Planner/Grounder/Verifier 的行为与
   本 feature 实现前完全一致。
6. **Given** 已配置索引且发生一次命中，**When** 检查本次运行产生的审计/运行轨迹，**Then** 可以查到
   该次命中所引用的 bundle 身份、schema 版本、命中的 screen ID、element ID（如适用）与 transition ID
   （如适用）。
7. **Given** 已配置索引，**When** 检查发送给模型的索引相关上下文内容，**Then** 其中只包含屏幕可见
   语义与定位提示（文字、角色、相对区域、邻接关系等），不包含源码文件路径、内部方法名或其他非可见
   实现细节。

---

### User Story 4 - 使用通用生产者 skill 生成可被校验的索引 bundle (Priority: P4)

作为拥有 C#/Java/XAML/Web/Figma 等 UI 源码或设计资料的外部项目维护者，我需要一份与具体语言和 UI 框架
无关的通用说明，指导我从自己项目的资料中识别画面、元素、文字、角色、相对位置、邻接关系、动作、状态、
页面跳转与业务流程，并按规定的文件、字段、引用关系、稳定 ID、schema 版本、producer 信息、source
revision、可信度与证据来源生成 UI analysis bundle；该说明区分已确认、静态推断、视觉确认与需要真实
运行验证的数据，禁止把无法确认的信息伪装成确定事实，并提供空白模板与最小有效示例，同时要求我在交付前
使用 vnc-agent 提供的 validator 验证 bundle。该说明本身不附带任何针对特定语言的源码分析器实现。

**Why this priority**: 该 skill 是让"索引生产方"生态成立的必要条件，但其价值依赖于前三个用户故事定义
的消费端契约（schema、校验规则、查询维度、运行时使用边界）已经明确，因此放在最后交付。

**Independent Test**: 挑选两个互不相关、技术栈不同的最小 GUI fixture（例如一个基于 Web 表单流程、一个
基于桌面/XAML 风格的多画面流程，两者业务领域不同），分别按照该 skill 的说明手工或半自动生成 bundle，
用 vnc-agent 的 validator 验证两者均能通过校验，且 skill 文件本身不包含任何特定语言的解析代码或工具
依赖。

**Acceptance Scenarios**:

1. **Given** `.agents/skills/generate-ui-analysis-index/` 目录下的 skill 说明，**When** 检查其内容，
   **Then** 其中的指导语言与描述方式不依赖任何特定编程语言或 UI 框架的术语/API。
2. **Given** 该 skill 规定的 bundle 文件与字段清单，**When** 对照本 feature 定义的 Manifest / Screen /
   Element / Transition / Flow / Diagnostic 等标准结果概念逐项核对，**Then** 每个必需文件、字段、
   类型与引用关系均有明确规定，且与 vnc-agent 校验器的规则一致。
3. **Given** 该 skill 提供的空白模板与最小有效示例，**When** 直接用 vnc-agent 的 validator 校验该
   最小有效示例，**Then** 校验通过。
4. **Given** 两个技术栈不同、业务领域不相关的 GUI fixture，**When** 分别依据该 skill 生成各自的
   bundle 并用 validator 校验，**Then** 两个 bundle 均通过校验，且生成过程未依赖任何本 feature 之外
   提供的语言专用源码分析器。
5. **Given** skill 中关于"数据置信来源"的说明，**When** 检查其定义，**Then** 明确区分"已确认
   （confirmed）"、"静态推断（statically inferred）"、"视觉确认（visually confirmed）"、"需要真实
   运行验证（requires runtime verification）"四类，并说明每类数据在证据来源字段中应如何表达。

### Edge Cases

- bundle 目录存在但为空、或缺少全部数据文件时：产生"缺失必填数据文件"类校验错误，列出缺失的具体
  文件名（FR-002、FR-003）。
- 数据文件是合法 JSON 但不是合法 JSONL（例如整份文件是一个 JSON 数组而非逐行记录）时：产生
  "JSONL 语法错误"类校验错误，指出首个不合法行的行号（FR-002）。
- bundle 的 schema 主版本高于/低于当前 vnc-agent 支持的范围时：不得静默按不受支持的版本解析；
  MUST 明确拒绝并说明支持的版本范围。schema 版本从 1.0 起遵循 MAJOR.MINOR 语义化版本；受支持主
  版本内出现的次版本差异与未知字段必须被保留并兼容读取，不得丢弃或报错（FR-002）。
- 同一 bundle 在生成过程中被部分覆盖或截断（例如校验和与实际内容不一致）时：若 manifest 提供了
  校验和，MUST 通过校验和比对检测并拒绝加载（FR-002）。
- 一个 element 的 parent 引用指向自身或形成循环引用时：MUST 被判定为校验失败，纳入跨文件/跨记录
  引用完整性检查范围（FR-002）。
- 一个 transition 的 guards/preconditions 引用了 bundle 中不存在的 element，或引用了未在同一条
  transition 记录内联声明的命名条件时：MUST 被判定为悬空引用校验失败；guards/preconditions 不存在
  跨记录共享的全局状态注册表（FR-002）。
- bundle 体积或记录数量超出预设资源限制（例如超大 JSONL 文件、超多记录数）时：MUST 在不完整加载
  全部内容到内存的前提下尽早检测并报告"超出资源限制"错误（具体阈值维度见 FR-002 与 Assumptions，
  数值属实现期配置）。
- 索引查询命中多个候选（例如同一可见文字在同一画面出现多次）时：MUST 返回全部候选的确定性排序
  列表（如按稳定 ID 排序），不得静默选择其中之一或丢弃候选（FR-004）。
- 当前截图与索引中记录的画面在部分区域相似但整体不足以判定为同一 screen 时："明显不一致"的具体
  阈值与判定算法属于实现期决定（见 Assumptions），但行为契约在规范层面已固定：判定为不一致时
  MUST 回退到原有流程并记录审计信息，不得强行采用不一致的索引数据（FR-014）。
- 已配置的索引目录路径本身不存在或不可读时：MUST 产生与"目录存在但 bundle 内容无效"不同的独立
  错误类别（如"索引目录不可访问"），两者均遵循 FR-012 的"执行前失败"处理，但错误类别可区分
  （FR-003）。
- 运行时索引命中后，若该次 Grounder 最终仍未能在当前截图上定位到目标：审计记录 MUST 将"索引命中
  状态"与"本次 Grounder 实际定位结果"记录为两个独立字段，命中不隐含定位成功（FR-013）。

## Requirements *(mandatory)*

### Functional Requirements — 索引消费（当前 vnc-agent 项目）

- **FR-001**: 系统 MUST 支持用户在配置中明确指定一个本地目录路径作为 UI analysis bundle 的来源，
  未指定时不得尝试自动发现或猜测索引位置。
- **FR-002**: 系统 MUST 在使用 bundle 前完成以下校验，并在任一项失败时视整个 bundle 为无效：
  schema 主版本受支持性（schema 版本从 1.0 起遵循 MAJOR.MINOR 语义化版本；不支持的主版本必须拒绝，
  受支持主版本内的次版本差异与未知字段必须被保留并兼容读取，不得丢弃或报错）、manifest 存在性、
  全部必填数据文件存在性（`manifest.yaml`、`screens.jsonl`、`elements.jsonl`、`transitions.jsonl`；
  `flows.jsonl`、`diagnostics.jsonl` 为可选文件，缺失不视为校验失败）、各 `.jsonl` 文件的逐行
  JSONL 语法合法性（每行 MUST 为独立合法 JSON 对象；整份文件为单一 JSON 数组或存在不合法行均视为
  JSONL 语法错误）、各文件字段类型正确性、稳定 ID 格式合法性、bundle 内 ID 唯一性（无重复）、跨
  文件与跨记录引用完整性（element→screen 不得悬空；element 的 `parent` 引用不得指向自身或形成
  循环引用；transition→screen/element 不得悬空；transition 的 guards/preconditions 只允许引用
  bundle 内存在的 element ID 或该 transition 记录自身内联声明的命名条件，引用不存在的 element ID
  或未内联声明的命名条件均视为悬空引用）、每个携带坐标的字段均显式声明 `coordinate_space`
  （取值为 `design_pixels` 或 `normalized_1000` 之一，未声明视为校验失败）且坐标值落在该
  `coordinate_space` 的合法范围内（`design_pixels` 为非负整数；`normalized_1000` 为 0–1000
  闭区间整数）、可信度字段落在合法取值范围内（可信度为复合字段：必需的 `level` 枚举属于 FR-025
  定义的四类之一，可选的 `score` 落在 [0.0, 1.0] 闭区间）、文件路径不发生目录穿越、bundle 总体
  规模不超过预设资源限制、bundle 校验和（如提供）与实际内容一致。
- **FR-003**: 系统 MUST 为每一类校验失败生成包含"错误类别"与"具体字段路径/文件位置"的稳定错误
  描述，使用户能够定位问题所在记录与字段，而不是只报告"bundle 无效"。配置的索引目录本身不存在或
  不可读时，MUST 产生与"目录存在但 bundle 内容未通过 FR-002 校验"不同的独立错误类别（例如"索引
  目录不可访问"），两者虽均遵循 FR-012 的"执行前失败"处理，但错误类别 MUST 可区分。
- **FR-004**: 系统 MUST 提供按以下维度查询已校验通过的索引的能力：screen（含其全部 element）、
  element 可见文字、OCR 别名、element role、相对位置/相对区域、邻接元素、element 支持的可执行
  动作、element 的可见/启用状态条件、transition（按 from screen、trigger element、trigger
  action、to screen）、transition 的 guards/preconditions、transition 预期新增/消失的可见元素。
  查询命中多个候选时，系统 MUST 返回全部候选的确定性排序列表（如按稳定 ID 排序），不得静默选择
  其中之一或丢弃候选。
- **FR-005**: 查询结果 MUST 保留原始记录的可信度（confidence）与证据来源（evidence source）字段，
  不得在查询过程中丢失或篡改这些字段。
- **FR-006**: 系统 MUST 允许 testcase 编写过程使用上述查询能力获取结构化控件知识（而非要求用户
  直接阅读 bundle 原始文件）。
- **FR-007**: 系统 MUST 能够针对"当前画面"（由当前 VNC 截图确定）从已校验索引中检索相关的可见
  语义提示（元素可见文字、角色、相对区域、邻接文字），并将其作为可选输入提供给 Planner 与
  Grounder 的决策过程。
- **FR-008**: 索引提供的任何数据 MUST NOT 被系统视为动作执行成功或业务判定通过的证据；索引中记录
  的"点击后预期效果"仅可作为 Verifier 的参考线索，不得替代操作后重新采集的截图与独立证据。
- **FR-009**: 运行时最终执行的目标定位坐标 MUST 始终由 Grounder 基于当前实时 VNC 截图计算得出；
  索引中记录的设计坐标或归一化坐标 MUST NOT 被直接作为最终点击坐标使用，也 MUST NOT 绕过 Grounder
  的目标定位过程。
- **FR-010**: Verifier 的通过判定 MUST 始终基于操作后重新采集的截图与独立证据；索引数据 MUST NOT
  单独或联合构成判定通过的依据。
- **FR-011**: 若测试执行未配置任何 UI 索引目录，系统的行为（Planner/Grounder/Verifier 决策路径、
  最终产出）MUST 与本 feature 实现前完全一致。
- **FR-012**: 若用户明确配置了 UI 索引目录但该目录指向的 bundle 未通过 FR-002 中的任一校验项，
  系统 MUST 在开始使用该索引前返回诊断错误并阻止后续基于该索引的查询与运行时提示注入；系统
  MUST NOT 静默忽略校验失败并继续使用部分有效或全部无效的数据。
- **FR-013**: 系统 MUST 记录每次索引使用的可审计信息，至少包括：bundle 身份（producer、bundle
  标识）、schema 版本、本次运行中命中的 screen ID 列表、element ID 列表、transition ID 列表
  （命中为空时也需记录"未命中"及原因，如"索引中找不到当前画面"或"索引与当前截图明显不一致"）。
  "索引命中状态"与"本次 Grounder 实际定位结果"MUST 记录为两个独立字段：即使索引命中了当前画面，
  审计记录也 MUST NOT 因此推断或隐含本次 Grounder 定位一定成功；命中与定位结果的成败组合 MUST
  均可独立从审计记录中读出。
- **FR-014**: 当索引中没有与当前画面匹配的 screen 记录、或匹配的 screen 记录与当前截图的可见
  元素明显不一致时，系统 MUST 回退到未使用索引时的原有 Planner/Grounder 流程完成当前步骤，并
  记录对应的审计信息，MUST NOT 因为回退而中止或失败当前测试步骤。
- **FR-015**: 系统发送给模型（Planner/Grounder 等）的索引相关上下文 MUST 只包含屏幕可见语义与
  定位提示（如可见文字、别名、角色、相对区域、邻接元素文字），MUST NOT 默认包含 bundle 中记录的
  源码文件路径、内部方法名或其他非可见实现细节字段。这些非可见实现细节字段 MAY 保留在 bundle
  数据与本地审计记录中作为离线溯源信息供人工排查使用，但 MUST NOT 成为默认发送给模型的上下文的
  一部分。
- **FR-016**: 索引消费相关的核心实现（读取、校验、查询、运行时提示注入、审计）MUST 是业务无关的
  通用能力，MUST NOT 包含任何特定被测应用、行业或页面场景专用的固定字段、关键词或分支逻辑（例如
  POS、Barcode、预/现计、购物车等仅可出现在测试用例/fixture/profile 中，不得出现在核心模型或
  核心处理逻辑中）。
- **FR-017**: 系统 MUST NOT 扫描或解析任何外部项目的源码文件（包括但不限于 C#、Java、
  JavaScript/TypeScript、XAML、HTML/Web、Figma 设计文件），MUST NOT 打开或编译 `.sln`、
  `.csproj` 等项目文件，MUST NOT 引入 Roslyn、MSBuildWorkspace、JavaParser、TypeScript
  Compiler 等语言相关源码分析依赖，MUST NOT 推断外部项目的 UI 事件处理器或自动生成其源码调用图。
- **FR-018**: 系统在运行时 MUST NOT 读取被测应用的源码、UI Automation 树、DOM、进程信息、文件
  系统或其他内部接口；索引消费能力的全部输入 MUST 限定为用户明确指定目录中的已生成 bundle 文件
  与运行时的 VNC 截图。
- **FR-019**: 系统 MUST NOT 因为索引记录声称某个动作会成功或某个跳转会发生，而跳过或简化操作后
  的截图重新采集与独立验证步骤。

### Functional Requirements — 通用索引生产者 skill

- **FR-020**: 系统 MUST 在 `.agents/skills/generate-ui-analysis-index/` 提供一份面向外部项目的
  通用 skill 说明文件，其指导语言与示例表达 MUST NOT 依赖任何特定编程语言、UI 框架或工具链的
  专有 API 或术语。
- **FR-021**: 该 skill MUST 指导外部项目从其自有资料中识别以下概念并落实到 bundle 中：画面
  （screen）、元素（element）、可见文字、角色（role）、相对位置、邻接关系、可执行动作、元素状态、
  页面跳转（transition）以及业务流程（flow）。
- **FR-022**: 该 skill MUST 规定 bundle 必须包含的文件清单，并对每个文件规定其记录对应的标准
  结果概念（Manifest、Screen、Element、Transition、Flow、Diagnostic/Unresolved Item 之一）。
  该清单 MUST 与消费端一致：`manifest.yaml`、`screens.jsonl`、`elements.jsonl`、
  `transitions.jsonl` 为必需文件，`flows.jsonl`、`diagnostics.jsonl` 为可选文件。
- **FR-023**: 该 skill MUST 为每个文件规定字段名称、数据类型与跨文件引用关系，且这些规定 MUST
  与本 feature 消费端（FR-002、FR-004）的校验与查询能力保持一致，不得产生消费端无法解析或校验
  的字段约定。
- **FR-024**: 该 skill MUST 规定稳定 ID 的表达方式（在 bundle 范围内唯一且跨重新生成保持稳定）、
  schema 版本号的表达方式、producer 信息（如生产该 bundle 的工具/项目标识）、source revision
  （生成时对应的源资料版本标识）、可信度（confidence）取值范围与含义、以及证据来源（evidence
  source）字段的表达方式。
- **FR-025**: 该 skill MUST 明确区分至少四类数据来源可信度：已确认（confirmed）、静态推断
  （statically inferred）、视觉确认（visually confirmed）、需要真实运行验证（requires runtime
  verification），并说明每类数据在 bundle 中应如何标注。这四类是 Key Entities「可信度
  (confidence)」复合字段中 `level` 枚举的取值集合；该 skill MUST 说明可信度字段的复合结构
  （必需的 `level` 枚举 + 可选的 `score` 浮点数），不得让外部项目将两者理解为无关的两个字段。
- **FR-026**: 该 skill MUST 明确禁止外部项目将无法确认的信息标注为已确认事实（例如禁止把静态
  推断的页面跳转标注为 confirmed）。
- **FR-027**: 该 skill MUST 提供一个空白 bundle 模板（可直接复制填写的文件骨架）与一个最小有效
  示例（可直接通过 vnc-agent validator 校验的完整 bundle）。
- **FR-028**: 该 skill MUST 明确告知外部项目，在交付 bundle 前必须使用当前 vnc-agent 提供的
  validator 完成校验，并说明校验不通过时不应交付。
- **FR-029**: 该 skill 本身 MUST NOT 附带针对某一具体语言或框架的实际源码分析器实现；外部项目
  自行选择技术手段（Roslyn、通用 AST 解析、XAML 解析器、人工标注等）生成符合该 skill 规定格式的
  bundle。

### Key Entities *(include if feature involves data)*

- **Bundle 文件布局**: 一个 bundle 以目录形式交付，包含固定命名的文件：`manifest.yaml`（必需，对应
  Bundle Manifest）、`screens.jsonl`（必需，每行一条 Screen 记录）、`elements.jsonl`（必需，每行
  一条 Element 记录）、`transitions.jsonl`（必需，每行一条 Transition 记录）、`flows.jsonl`（可选，
  每行一条 Flow 记录）、`diagnostics.jsonl`（可选，每行一条 Diagnostic/Unresolved Item 记录）。
  "必填数据文件"的校验（FR-002、FR-003）与"缺失必填数据文件"类 Edge Case 均以此清单为准；schema
  版本从 1.0 起遵循 MAJOR.MINOR 语义化版本。
- **Bundle Manifest**: 标识一个 UI analysis bundle 的身份与元信息，包括 schema 版本、producer
  信息、source revision、bundle 生成时间、bundle 内文件清单及其校验和（如提供）。是校验流程的
  入口点。
- **Screen**: 代表被分析 UI 中的一个"画面"（页面/窗口/模态/视图等的抽象），拥有稳定 screen ID、
  可选的画面级可见语义摘要，是 element 与 transition 的归属/引用锚点。
- **Element**: 代表画面中的一个可交互或可见控件，拥有稳定 element ID、所属 screen ID、可选 parent
  element（MUST NOT 指向自身或形成循环引用）、UI role、可见文字及别名列表、支持的动作列表、可见/
  启用状态条件、可选的设计布局或归一化布局（携带坐标的字段 MUST 显式声明所属「坐标空间」）、相对
  区域、上下左右或附近元素引用、点击后的预期效果描述、可信度（「可信度」复合字段）、证据来源。
- **坐标空间 (coordinate_space)**: 每个携带坐标的字段（设计布局、归一化布局、相对区域等）MUST
  显式声明其所属坐标空间，取值为以下二者之一：`design_pixels`（生产方设计画布的原始像素坐标，
  非负整数）或 `normalized_1000`（以 0–1000 闭区间整数表示的千分比归一化坐标，按画面宽/高换算，
  避免浮点精度问题）。未显式声明 `coordinate_space` 的坐标字段视为校验失败（FR-002）。
- **可信度 (confidence)**: Element、Transition、Diagnostic/Unresolved Item 记录中的可信度字段
  MUST 表示为复合结构：必需的 `level` 枚举（`confirmed` | `statically_inferred` |
  `visually_confirmed` | `requires_runtime_verification`，即 FR-025 定义的四类）与可选的
  `score` 浮点数（0.0–1.0 闭区间，用于同一 `level` 内部细分排序，不改变 `level` 语义）。FR-002
  中"可信度字段落在合法取值范围内"具体指 `level` 属于上述四类枚举之一，且 `score`（如提供）落在
  [0.0, 1.0] 闭区间。
- **Transition**: 代表一次页面跳转，拥有 from screen、trigger element、trigger action、
  guards/preconditions（只允许引用 bundle 内存在的 element ID 或该 transition 记录自身内联
  声明的命名条件，不存在跨记录共享的全局状态注册表）、to screen、跳转类型
  （modal/replace/overlay/state-change）、预期新增和消失的可见元素列表、可信度（「可信度」复合
  字段）、证据来源。
- **Flow**: 代表由若干 transition 组成的业务流程片段（画面/跳转的有序或有向组合），用于表达比
  单个 transition 更高层的用户旅程语境，本身不引入具体业务字段，只引用 screen/transition 的
  稳定 ID。
- **Diagnostic / Unresolved Item**: 代表生产方在分析过程中无法确认或需要额外验证的条目，拥有
  目标引用（指向相关的 screen/element/transition ID）、原因说明、可信度（同一「可信度」复合
  字段结构）、证据来源（例如某个跳转条件推断置信度低、某个元素的邻接关系无法从静态资料确定），
  供消费方与人工审阅参考，不参与运行时的默认信任链路。
- **Validation Report**: 消费方对一次 bundle 加载产生的结构化校验结果，包含通过/失败状态、每条
  错误的类别与字段路径，是 FR-003、FR-012 的直接产出。
- **Index Usage Audit Record**: 消费方在运行时每次尝试使用索引后产生的审计条目，包含 bundle 身份、
  schema 版本、是否命中、命中/未命中的 screen/element/transition ID 或未命中原因，是 FR-013 的
  直接产出。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 给定任意一个符合本 feature 定义 schema 的最小有效 bundle，用户可以在不阅读 bundle
  原始文件内容的前提下，通过查询能力获得该 bundle 中全部画面、元素与页面跳转的结构化知识。
- **SC-002**: 针对本 feature "五、错误处理"小节列举的每一类无效 bundle 场景（不支持的 schema 主
  版本、缺失 manifest、缺失必填数据文件、JSONL 语法错误、重复 ID、悬空引用、无效归一化坐标、
  非法可信度、路径穿越、超出资源限制、部分写入/校验和不一致），加载该场景对应的样例 bundle 均
  产生包含具体字段路径或文件位置的稳定错误，且不产生任何测试执行副作用。
- **SC-003**: 使用同一批既有回归 testcase，分别在"未配置索引"与"配置了索引但当前画面不在索引
  覆盖范围内"两种条件下运行，两者的最终执行结果（点击坐标来源、Verifier 判定依据、测试通过/
  失败结论）在人工复核下不可区分，仅审计记录中的索引命中信息不同。
- **SC-004**: 在索引命中当前画面的运行中，人工抽查运行轨迹可以确认：全部最终点击坐标均可追溯到
  基于当前截图的 Grounder 计算结果，没有一次点击坐标直接等于索引中记录的设计坐标或归一化坐标。
- **SC-005**: 在索引命中当前画面的运行中，人工抽查运行轨迹可以确认：全部通过判定均可追溯到操作
  后重新采集的截图与独立证据，没有一次通过判定仅依据索引中记录的"预期效果"字段。
- **SC-006**: 每一次索引被实际用于运行时决策（无论命中与否），事后均可从审计输出中查到对应的
  bundle 身份、schema 版本与命中/未命中详情，覆盖率达到 100%。
- **SC-007**: 抽查发送给模型的索引相关上下文内容，其中不出现 bundle 源数据中标注为"源码路径/
  内部方法名/非可见实现细节"类别的字段值。
- **SC-008**: 两名分别只熟悉不同技术栈（例如一名只熟悉 Web 前端资料、一名只熟悉桌面/XAML 资料）
  的使用者，仅依据 `.agents/skills/generate-ui-analysis-index/` 的说明，各自独立生成一个 bundle，
  两者均可通过 vnc-agent 的 validator 校验，且两份 bundle 覆盖的业务领域互不相关。
- **SC-009**: 审查索引消费相关的核心实现代码，不出现任何固定业务关键词（如 POS、Barcode、
  预/现计、购物车）作为字段名、常量或分支条件；相关业务示例仅出现在 testcase/fixture 层。
- **SC-010**: 本 feature 新增的读取、校验、查询、运行时回退与审计行为均有自动化测试覆盖，测试
  产出的报告/日志可用于事后审计，无需人工重新执行即可复核结论。
- **SC-011**: User Story 1–3 定义的消费端能力（bundle 读取与校验、查询、运行时提示与回退审计）
  分别使用至少两个互不相关（技术栈或业务领域不同）的 GUI fixture 完整验证一遍，而不仅依赖
  producer skill 可移植性验证（SC-008）间接覆盖；其中至少一个 fixture 的验证过程需覆盖至少一类
  FR-002 校验失败场景，确保错误处理路径同样经过跨场景验证，而非只验证正常流程。

## Assumptions

- 索引消费方（vnc-agent）与索引生产方（外部项目）之间的唯一契约是文件系统上的一个版本化 bundle
  目录；本 feature 不假设两者之间存在实时 API、RPC 或共享进程通信。
- "用户明确指定的分析结果目录"通过 vnc-agent 现有的配置/testcase 声明机制传入（具体配置载体的
  技术形式属于实现细节，不在本规范中约束），未配置时视为"未启用索引能力"。
- schema 版本策略（起始版本、主/次版本兼容规则）已在 FR-002 与 Key Entities「Bundle 文件布局」中
  明确规定，此处不再重复；缺失的可选字段按未提供处理，不视为校验失败。
- "资源限制"（bundle 总体积、单文件记录数上限等）的具体阈值属于实现期确定的默认配置，具备可调整
  空间；规范层面只要求存在此类限制并在超限时产生稳定错误，不固定具体数值。
- "索引与当前截图明显不一致"的判定依据关键可见元素的存在性与可辨识文字的匹配程度，允许一定的
  视觉噪声容差；具体阈值与算法属于实现细节，规范层面只约束其行为契约（不一致时必须回退并审计，
  不得强行采用）。
- 通用生产者 skill 面向的是"具备一定 UI 分析能力（人工或半自动）的外部项目维护者"，不假设其熟悉
  vnc-agent 内部实现，也不假设其具备特定语言的静态分析工具链；skill 只规定产出契约，不规定生产
  过程使用的具体工具。
- 至少两个互不相关 GUI fixture 的跨场景验证（用于 FR/SC 中的"业务无关"证明）可以是精简的示例
  级 fixture，不要求覆盖外部真实生产项目的完整功能面，只需在结构上代表不同技术栈/不同业务领域。
