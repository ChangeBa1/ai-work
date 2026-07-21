# Phase 0 Research: VNC 黑盒 GUI 自动化测试核心执行闭环

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本阶段的目标是在进入 Phase 1 设计前，把 Technical Context 中隐含的技术决策显式化并给出
理由，确保没有遗留的 `NEEDS CLARIFICATION`。spec.md 与 overall_design.md 已经把大部分
技术选型作为"固定约束"给出（vncdotool、MiMo-V2.5 via OpenCode Go API、Planner 可替换、
自研 Agent Runtime、无独立显卡、无本地大型视觉模型），因此本文档聚焦于这些固定约束之下
仍需要决定的具体实现方式。

## 1. vncdotool 的阻塞调用与 asyncio 主循环的桥接

- **Decision**: vncdotool 基于 Twisted，其 API 在当前线程中是阻塞的；Agent Runtime 使用
  `asyncio` 作为主事件循环。VNCDriver 内部为每个 VNC 会话维护一个专用的后台线程运行
  Twisted reactor（或使用 `asyncio.to_thread` 包装每次阻塞调用），驱动层通过
  `asyncio.Queue` 或 `run_in_executor` 将截图/键鼠请求跨线程转发，返回结果时通过
  `asyncio.Future` 回传给主循环。
- **Rationale**: 保证 Agent 主事件循环不被 VNC 阻塞（对齐 overall_design.md 9.1 的实现
  要求），同时不需要将整个状态机改写为同步代码。
- **Alternatives considered**:
  - 直接同步驱动整个 Agent Runtime（放弃 asyncio）——会让并发的等待/超时/取消逻辑变得
    笨重，且与后续可能的多会话扩展方向相悖，故拒绝。
  - 用其他纯 Python VNC 客户端库替换 vncdotool——违反 spec 的固定约束（FR 明确要求
    vncdotool），故拒绝。

## 2. 轻量 OCR 引擎选型

- **Decision**: 使用基于 ONNX Runtime 推理的轻量检测+识别流水线（如 RapidOCR 一类的
  ONNX 发行版），CPU 推理，按需加载模型，不常驻大模型进程。
- **Rationale**: 满足"控制端不能运行本地大型视觉语言模型""本地只允许使用轻量图像处理、
  OCR、模板匹配"的固定约束；ONNX Runtime 相比引入完整深度学习框架（PyTorch/TensorFlow）
  更轻量，符合弱配置办公电脑的资源约束（宪法 21.1/21.2）。
- **Alternatives considered**:
  - Tesseract——对中英文混排、非规整 UI 文本的识别效果通常弱于现代检测+识别两阶段模型，
    拒绝作为默认项，但可作为未来可插拔的备选 OCR Provider。
  - 云端 OCR API——引入额外的外部依赖和网络往返延迟，且与"本地只允许轻量图像处理/OCR"
    的约束冲突，拒绝。

## 3. Agent Runtime 状态机实现方式

- **Decision**: 手写的显式异步状态机（`AgentState` 枚举 + 转移表 + `StepController`），
  不引入第三方状态机库或工作流引擎。
- **Rationale**: 直接对齐宪法 ADR-001（自研状态机，不引入 LangGraph）与 Core Principle
  I（确定性运行时控制模型）；状态少且转移规则明确（详见 data-model.md 的状态转移表），
  手写实现更易审计、调试成本更低、依赖更少。
- **Alternatives considered**:
  - `transitions` / `python-statemachine` 等状态机库——增加依赖且转移逻辑本身并不复杂，
    收益有限，拒绝。
  - LangGraph 或其他 Agent 编排框架——违反宪法"架构约束"中 MVP 阶段的明确排除项，拒绝。

## 4. Planner / Grounder 的可替换性实现

- **Decision**: 定义 `ModelProvider` 系列 Protocol（`PlannerProvider`、`GrounderProvider`），
  运行时通过配置文件（`models.yaml`）中的 `provider` 字段选择具体实现类并在启动时注入；
  所有跨模型的请求/响应统一走 Pydantic 模型 + JSON Schema 校验（对齐 overall_design.md
  9.4/9.6 的输入输出结构）。Grounder 默认实现固定通过 OpenCode Go API 调用 MiMo-V2.5；
  Planner 默认实现为可配置的强视觉/推理模型，但通过同一 Protocol 与 httpx 异步客户端
  访问，不与具体供应商 SDK 耦合。
- **Rationale**: 直接满足 FR-046（Planner 必须可替换，不得与特定模型供应商耦合）与宪法
  Core Principle II；用 Protocol + 配置注入而非硬编码 if/else，保证新增供应商时无需修改
  调用方代码。
- **Alternatives considered**:
  - 直接依赖某个模型供应商官方 SDK 的具体类型——会把供应商耦合进调用方签名，拒绝。
  - 引入通用 LLM 网关框架（如 LiteLLM）统一多模型调用——增加不必要的依赖面，且本功能
    的调用面很小（两个角色、两个方法），手写 Protocol 更符合"简单优先"和弱配置环境的
    约束，拒绝在本切片引入。

## 5. 屏幕稳定性判定算法

- **Decision**: 连续采集 ≥3 帧，先对已配置的动态区域（任务栏时钟、鼠标指针邻域、加载
  动画区域）打掩码，再计算相邻帧在目标 ROI 内的像素差异比例，连续两次差异低于阈值即判定
  稳定；同时支持"预期文字/模板提前出现"和"VNC 断开/错误画面"两类提前终止条件。
- **Rationale**: 直接对应 spec 用户故事六的验收场景与 overall_design.md 9.8 给出的默认
  参数（`min_delay_ms`、`capture_interval_ms`、`stable_frame_count=3`、
  `pixel_diff_threshold`），复用已经过设计评审的既有方案，避免另起炉灶。
- **Alternatives considered**:
  - 仅用固定 `sleep`——被 spec 明确禁止（用户故事六背景陈述）。
  - 基于感知哈希（pHash）代替像素差异——对局部小变化（如加载动画之外区域的细微渲染差异）
    不够敏感，作为页面记忆阶段的相似度特征更合适，本闭环阶段仍以像素级 ROI 差异为主。

## 6. 存储层 ORM 选型

- **Decision**: SQLAlchemy 2.x（Core + ORM，`asyncio` 驱动 `aiosqlite`）承载
  `storage/database.py` 与 `storage/repositories.py`。
- **Rationale**: overall_design.md 技术栈允许 SQLAlchemy 2.x 或 SQLModel 二选一；
  SQLAlchemy 2.x 原生支持 `asyncio` 引擎，且团队后续如需要迁移到 PostgreSQL（overall
  design 的远期扩展方向）时改动面更小。
- **Alternatives considered**:
  - SQLModel——本质是 SQLAlchemy + Pydantic 的组合封装，对已经以 Pydantic v2 为核心数据
    模型的本项目收益不明显，且版本更新频率和生态成熟度略逊于直接使用 SQLAlchemy 2.x，
    故本切片选择更成熟的直接方案。

## 7. 凭据与敏感信息处理

- **Decision**: VNC 密码与模型 API Key 一律通过环境变量读取（`pydantic-settings` 的
  `BaseSettings` 自动绑定），`vnc-targets.yaml`/`models.yaml` 中仅保留环境变量引用名而非
  明文值；`structlog` 配置处理器（processor）在写日志前按字段名黑名单过滤敏感字段。
- **Rationale**: 直接落实 FR-047 与宪法"凭据与隐私"条款；环境变量是无需额外依赖即可
  在弱配置办公电脑和 CI 环境中一致工作的最简方案。
- **Alternatives considered**:
  - 操作系统凭据存储（Windows Credential Manager / `keyring` 库）——作为可选增强手段
    保留在 research 备忘中，非本切片默认路径，避免为最小闭环引入额外的平台相关依赖。

## 8. HTML 报告生成方式

- **Decision**: 使用 Jinja2 模板渲染单文件 HTML 报告（内嵌截图缩略图链接、步骤时间线、
  失败证据折叠区）；JSON 报告直接由 Pydantic 模型 `model_dump_json()` 产出，保证与 HTML
  报告引用同一份数据来源，不重复维护两套报告逻辑。
- **Rationale**: Jinja2 是 Python 生态中最轻量成熟的模板方案，不需要浏览器端框架或构建
  步骤，适合弱配置办公电脑上直接查看的静态报告场景。
- **Alternatives considered**:
  - 纯字符串拼接——难以维护复杂的步骤/证据嵌套结构，拒绝。
  - 引入前端框架（React/Vue）生成动态报告——超出本切片"模块化单体、依赖最小化"的约束，
    且报告是一次性生成的静态产物，不需要客户端交互框架。

## 9. VNC 集成测试与端到端测试的目标环境

- **Decision**: 集成测试与端到端测试针对一个本地可控的测试用 VNC 服务器（例如运行在
  CI/开发机本地的 TigerVNC/x11vnc 或一个专门准备的 Windows 10 VNC 测试环境），通过
  `config/vnc-targets.yaml` 中的测试专用条目连接；不依赖生产被测机器。
- **Rationale**: 保证测试可重复执行、不影响真实业务环境，同时仍然覆盖"真实 VNC 协议
  往返"这一集成测试门禁要求（而非仅靠 mock）。
- **Alternatives considered**:
  - 完全 mock VNCDriver 而不做真实协议集成测试——无法验证 vncdotool 集成本身的正确性
    （截图格式、按键映射、断线重连等），不满足宪法"测试覆盖门禁"中对 VNC 集成测试的
    要求，拒绝作为唯一测试手段（但仍保留作为离线单元测试的补充）。

## 10. 步骤内多轮迭代的预算实现（2026-07-20 澄清会话新增）

- **Decision**: `StepController` 为每个 `TestStep` 维护一个单一的剩余预算计数器
  （初始值 = `TestStep.max_retries`），`ActionIteration` 每开启一轮消耗一点；验证失败重试、
  Planner 插入的前置微动作、VNC 断线重连触发的整步重新执行，三者共用同一计数器，不分别
  开辟独立上限。
- **Rationale**: spec.md 的三处澄清（步骤内微动作迭代、VNC 重连后重做步骤）都明确"计入该
  步骤的 `max_retries`"，共享计数器是唯一与三处澄清同时一致的实现方式；分立计数器会让
  "最坏情况下一个步骤能跑多少轮"变得不可预测，违反宪法"恢复与重试门禁"要求的显式上限。
- **Alternatives considered**：为微动作迭代单独设置 `max_iterations` 计数器——会与
  `max_retries` 产生两套预算语义，测试用例作者需要同时理解两个数字才能预估最坏运行时长，
  拒绝。

## 11. Grounding 置信度阈值与 Top-1/Top-2 差值阈值的默认来源（2026-07-20 澄清会话新增）

- **Decision**: 两个阈值（`grounding.confidence_threshold` 判定"整体偏低"、
  `grounding.top1_top2_margin_threshold` 判定"难以取舍"）作为独立的可配置项，初始默认值
  在实现阶段结合 MiMo-V2.5 在参考测试场景上的实测分布给出，不在规格/研究阶段固化具体数字。
- **Rationale**: spec.md 的 Assumptions 已明确"置信度阈值等具体数值型参数……具体数值由
  实现阶段依据实测调优"；两个阈值分开配置，是因为它们对应不同的失败子原因
  （`overall_low_confidence` vs `top1_top2_close`，见 data-model.md §8），合并成一个阈值
  会丢失"到底是模型整体没把握，还是两个候选真的很像"这一区分度，而这个区分度正是本次
  澄清要求保留的。
- **Alternatives considered**：只用一个阈值、Top-2 存在且置信度 > 阈值即视为"不确定"——
  实现更简单，但会把"模型压根没找到"和"模型找到但纠结选哪个"混为一谈，不满足澄清要求的
  子原因区分，拒绝。

## 12. 敏感区域遮罩的实现落点（2026-07-20 澄清会话新增）

- **Decision**: 遮罩逻辑只实现在两处出口：`storage/artifact_store.py`（截图落盘前）与
  `reporting/*`（报告渲染前）；`models/planner_client.py`、`models/mimo_grounder.py` 构造
  外发请求体时直接引用未经处理的原始 `ScreenFrame`，不经过遮罩函数。
- **Rationale**: 直接落实 FR-049——遮罩与"是否发往外部"是两个独立维度，把遮罩实现收敛在
  "落盘"与"渲染"这两个天然的序列化边界上，比在每个模型调用点判断"这次要不要遮罩"更不容易
  出错、也更容易通过代码评审核对（"凡是发往 `models/` 的截图路径都不经过遮罩函数"这一条
  规则本身就是可静态检查的）。
- **Alternatives considered**：在 `ScreenFrame` 上加一个 `masked_variant_path` 字段，所有
  消费方自行选择用原图还是遮罩图——增加了每个调用点"选对字段"的心智负担和出错空间，且与
  "遮罩只影响落盘与报告"这一简单规则相比收益不明显，拒绝。

## 13. Provider 实现的启动期校验（需求质量门禁 2026-07-21 新增）

- **Decision**: `models/provider.py` 中 `PlannerProvider`/`GrounderProvider` 定义为
  `typing.Protocol`（`@runtime_checkable`）；Runtime 在按 `models.yaml` 的 `provider`
  字段装配具体实现类之后、进入 `PREPARING` 之前，MUST 执行一次结构化校验（`isinstance`
  对照 `@runtime_checkable` Protocol，或等价的显式方法存在性检查），确认该实现类具备
  Protocol 要求的全部方法（`PlannerProvider` 需同时具备 `plan` 与 `describe_screen`，见
  contracts/model-provider-contract.md）。校验失败 MUST 在启动阶段直接报错退出，MUST NOT
  等到运行期间实际调用缺失方法时才失败。
- **Rationale**: `typing.Protocol` 的静态类型检查只在开发期（mypy/pyright）生效，
  运行时装配一个来自配置文件字符串（`provider` 字段）动态加载的类时，静态检查不覆盖这条
  路径；显式的启动期 `isinstance` 校验是标准做法，成本低（一次性检查），能把"新供应商漏
  实现某个方法"这类错误从运行期间某个测试步骤执行到一半时才暴露，提前到进程启动的确定性
  报错，对齐宪法 Core Principle I"确定性运行时控制"的精神（失败模式应可预测、可提前发现）。
- **Alternatives considered**：不做启动期校验，依赖运行时首次调用缺失方法时的
  `AttributeError` 自然暴露——会让"Planner 供应商配置错误"这类问题伪装成"运行期间某个
  测试步骤莫名失败"，增加排障成本，且与 FR-046"新增供应商不需要修改调用方代码"的可替换性
  承诺相悖（调用方代码本不应该需要处理"方法不存在"这种本应在装配期就能发现的错误），拒绝。

## 结论

以上 13 项决策覆盖了 Technical Context 中所有需要具体化的技术点，并吸收了 2026-07-20
澄清会话对 5 个高影响问题的结论、以及 2026-07-21 需求质量门禁（`/speckit-checklist`
core-loop.md）复核过程中新增的 Provider 启动期校验决策；spec.md 给出的固定约束
（vncdotool、MiMo-V2.5 via OpenCode Go API、Planner 可替换、自研 Runtime、无独立显卡、
无本地大型视觉模型、单 VNC 会话）均已在决策中被尊重，没有遗留 `NEEDS CLARIFICATION`。
可以进入 Phase 1 设计。
