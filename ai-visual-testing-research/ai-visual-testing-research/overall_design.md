# VNC 黑盒 GUI 自动化测试 Agent

## 总体设计说明书

**文档状态：** 总体设计基线
**目标版本：** MVP v0.1
**目标平台：** Windows 10 被测环境
**控制方式：** VNC 纯黑盒
**Agent 类型：** 自研 GUI 自动化测试 Agent
**视觉模型：** MiMo-V2.5，作为主要 GUI Grounder 和视觉理解模型
**规划模型：** 可配置的强视觉/推理模型
**VNC 驱动：** vncdotool Python API

---

# 1. 设计目标

本系统是一款独立运行的 GUI 自动化测试 Agent。

系统通过 VNC 获取 Windows 10 屏幕像素，并通过 VNC 发送键盘和鼠标事件。系统不能读取 Windows UIA 控件树、进程信息、文件系统、注册表、浏览器 DOM 或应用内部接口。

系统必须具备：

1. 屏幕观察和结构化理解；
2. 测试任务规划；
3. GUI 元素定位；
4. 键盘和鼠标执行；
5. 页面稳定等待；
6. 独立结果验证；
7. 异常分类和恢复；
8. 测试轨迹记录和回放；
9. 页面、元素和失败经验记忆；
10. 受控的视觉自进化；
11. 低配置工作电脑可运行；
12. 模型、OCR、VNC 驱动和验证器可替换。

---

# 2. 核心设计原则

## 2.1 确定性运行时控制模型

系统运行流程由代码状态机控制。

模型只负责：

- 理解复杂截图；
- 生成语义计划；
- 定位动态目标；
- 分析未知异常；
- 执行低确定性的语义验证。

模型不负责：

- 自行决定无限重试；
- 自行判定测试最终通过；
- 直接控制底层 VNC 会话；
- 修改正式测试基线；
- 修改正式模型版本；
- 绕过危险操作策略。

## 2.2 Planner 与 Grounder 分离

```text
Planner
负责“下一步做什么”

Grounder
负责“目标具体在哪里”

Executor
负责“通过 VNC 如何执行”

Verifier
负责“操作是否真的成功”

```

Planner 不应直接输出裸坐标。

Grounder 不应自行决定测试流程。

Verifier 不应仅相信 Planner 或 Grounder 的自我判断。

## 2.3 键盘优先，视觉点击兜底

执行路径优先级：

```text
已验证回放动作
    ↓
快捷键
    ↓
Tab / Shift+Tab 焦点导航
    ↓
Win+R + PowerShell 配方
    ↓
OCR 文本定位
    ↓
模板或视觉锚点
    ↓
MiMo Grounding
    ↓
强模型异常分析

```

## 2.4 观察、执行、验证分离

标准闭环：

```text
Observe
  ↓
Understand
  ↓
Plan
  ↓
Ground
  ↓
Act
  ↓
Wait
  ↓
Observe Again
  ↓
Verify

```

不能使用：

```text
点击成功，因为模型认为自己点对了

```

必须使用：

```text
点击后重新截图，并通过独立证据判断是否达到预期状态

```

## 2.5 自进化不直接修改生产模型

实时允许更新：

- 页面记忆；
- 元素记忆；
- 失败记忆；
- 模板；
- 策略成功率；
- 置信度校准数据；
- 相似页面索引。

实时禁止：

- 自动训练生产模型；
- 自动替换生产模型；
- 自动修改正式断言；
- 自动覆盖正式回放脚本；
- 自动接受所有 UI 变化。

---

# 3. 总体架构

```text
┌───────────────────────────────────────────────────────────┐
│                    Test Management Layer                  │
│                                                           │
│  Test Case Loader  Run Controller  Report API  CLI        │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                     Agent Runtime                         │
│                                                           │
│  State Machine                                            │
│  Context Manager                                          │
│  Step Controller                                          │
│  Timeout / Retry / Cancellation                           │
└───────────────┬─────────────────────┬─────────────────────┘
                │                     │
       ┌────────▼────────┐   ┌────────▼────────┐
       │ Decision Layer  │   │ Experience Layer│
       │                 │   │                 │
       │ Planner         │   │ Page Memory     │
       │ Action Policy   │   │ Element Memory  │
       │ Recovery Engine │   │ Trajectory      │
       │ Risk Policy     │   │ Failure Memory  │
       └────────┬────────┘   └────────┬────────┘
                │                     │
                └──────────┬──────────┘
                           ▼
┌───────────────────────────────────────────────────────────┐
│                    Perception Layer                       │
│                                                           │
│ Screen Capture   Screen Diff   OCR   Template Matching    │
│ Page Recognition   Active Observation   MiMo Grounding    │
│ Confidence Fusion   Structured Screen Builder             │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                    Execution Layer                        │
│                                                           │
│ Action Router   Keyboard Executor   Mouse Executor        │
│ PowerShell Recipe Executor   Wait Engine   Verifier       │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                       VNC Driver                          │
│                                                           │
│ vncdotool Connection / Screenshot / Keyboard / Mouse      │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
                       Windows 10 VNC

```

---

# 4. 部署架构

MVP 使用模块化单体，不拆分微服务。

```text
控制端工作电脑
│
├─ vnc-test-agent 进程
│  ├─ Agent Runtime
│  ├─ Perception Pipeline
│  ├─ VNC Driver
│  ├─ Local Memory
│  ├─ SQLite
│  └─ HTML Report Server
│
├─ 本地文件目录
│  ├─ 截图
│  ├─ 模板
│  ├─ 日志
│  └─ 报告
│
└─ 外部 API
   ├─ MiMo-V2.5
   └─ 强 Planner 模型

```

MVP 仅运行：

- 一个 Agent 进程；
- 一个 VNC 会话；
- 一个测试任务；
- 一个 SQLite 数据库；
- 一个本地产物目录。

不引入：

- MCP；
- LangGraph；
- Temporal；
- Kafka；
- Kubernetes；
- 分布式数据库；
- 本地大型视觉模型。

---

# 5. 技术栈


| 领域       | 技术                                 |
| -------- | ---------------------------------- |
| 开发语言     | Python 3.12+                       |
| 异步运行     | asyncio                            |
| 数据模型     | Pydantic v2                        |
| VNC      | vncdotool Python API               |
| 图像处理     | OpenCV                             |
| 数值处理     | NumPy                              |
| OCR      | 轻量 OCR Provider，可优先使用 ONNX Runtime |
| HTTP 客户端 | httpx                              |
| 配置       | YAML + Pydantic Settings           |
| 数据库      | SQLite                             |
| ORM      | SQLAlchemy 2.x 或 SQLModel          |
| 日志       | structlog                          |
| CLI      | Typer                              |
| API      | FastAPI，可在 MVP 后半阶段加入              |
| 测试       | pytest                             |
| 报告       | HTML + JSON                        |
| 模型结构化输出  | JSON Schema + Pydantic 校验          |


---

# 6. 工程目录设计

```text
vnc-test-agent/
├─ pyproject.toml
├─ README.md
├─ config/
│  ├─ agent.yaml
│  ├─ models.yaml
│  ├─ vnc-targets.yaml
│  └─ security-policy.yaml
│
├─ src/vnc_agent/
│  ├─ main.py
│  │
│  ├─ runtime/
│  │  ├─ agent_runtime.py
│  │  ├─ state_machine.py
│  │  ├─ run_context.py
│  │  ├─ step_controller.py
│  │  ├─ cancellation.py
│  │  └─ exceptions.py
│  │
│  ├─ domain/
│  │  ├─ testcase.py
│  │  ├─ observation.py
│  │  ├─ screen.py
│  │  ├─ action.py
│  │  ├─ grounding.py
│  │  ├─ verification.py
│  │  ├─ recovery.py
│  │  ├─ memory.py
│  │  └─ run.py
│  │
│  ├─ drivers/
│  │  ├─ base.py
│  │  ├─ vncdotool_driver.py
│  │  └─ key_mapping.py
│  │
│  ├─ perception/
│  │  ├─ pipeline.py
│  │  ├─ screenshot.py
│  │  ├─ screen_diff.py
│  │  ├─ stability.py
│  │  ├─ ocr/
│  │  ├─ template/
│  │  ├─ page_recognition.py
│  │  ├─ active_observer.py
│  │  ├─ structured_screen.py
│  │  └─ confidence_fusion.py
│  │
│  ├─ models/
│  │  ├─ provider.py
│  │  ├─ opencode_go.py
│  │  ├─ planner_client.py
│  │  ├─ mimo_grounder.py
│  │  ├─ visual_verifier.py
│  │  └─ response_parser.py
│  │
│  ├─ planning/
│  │  ├─ planner.py
│  │  ├─ action_policy.py
│  │  ├─ context_builder.py
│  │  ├─ plan_validator.py
│  │  └─ risk_policy.py
│  │
│  ├─ execution/
│  │  ├─ router.py
│  │  ├─ executor.py
│  │  ├─ mouse_executor.py
│  │  ├─ keyboard_executor.py
│  │  ├─ text_input.py
│  │  ├─ powershell_recipe.py
│  │  └─ safe_cleanup.py
│  │
│  ├─ verification/
│  │  ├─ engine.py
│  │  ├─ ocr_verifier.py
│  │  ├─ template_verifier.py
│  │  ├─ screen_change_verifier.py
│  │  ├─ page_verifier.py
│  │  ├─ visual_verifier.py
│  │  └─ composite_verifier.py
│  │
│  ├─ recovery/
│  │  ├─ classifier.py
│  │  ├─ engine.py
│  │  ├─ strategies.py
│  │  └─ desktop_reset.py
│  │
│  ├─ replay/
│  │  ├─ recorder.py
│  │  ├─ player.py
│  │  ├─ anchor_matcher.py
│  │  ├─ patch_builder.py
│  │  └─ patch_review.py
│  │
│  ├─ memory/
│  │  ├─ page_memory.py
│  │  ├─ element_memory.py
│  │  ├─ trajectory_memory.py
│  │  ├─ failure_memory.py
│  │  ├─ retrieval.py
│  │  ├─ fingerprint.py
│  │  └─ statistics.py
│  │
│  ├─ evolution/
│  │  ├─ experience_collector.py
│  │  ├─ outcome_labeler.py
│  │  ├─ hard_case_miner.py
│  │  ├─ dataset_exporter.py
│  │  └─ confidence_calibrator.py
│  │
│  ├─ storage/
│  │  ├─ database.py
│  │  ├─ repositories.py
│  │  ├─ artifact_store.py
│  │  └─ migrations/
│  │
│  ├─ reporting/
│  │  ├─ report_builder.py
│  │  ├─ html_report.py
│  │  └─ json_report.py
│  │
│  └─ api/
│     ├─ cli.py
│     └─ http.py
│
├─ skills/
│  ├─ windows-navigation/
│  ├─ windows-powershell/
│  ├─ windows-common-dialogs/
│  └─ applications/
│
├─ testcases/
├─ templates/
├─ data/
├─ artifacts/
└─ tests/

```

---

# 7. Agent Runtime 设计

## 7.1 Agent 状态

```python
class AgentState(str, Enum):
    CREATED = "created"
    CONNECTING = "connecting"
    PREPARING = "preparing"
    OBSERVING = "observing"
    UNDERSTANDING = "understanding"
    RETRIEVING_MEMORY = "retrieving_memory"
    PLANNING = "planning"
    RESOLVING_ACTION = "resolving_action"
    GROUNDING = "grounding"
    EXECUTING = "executing"
    WAITING = "waiting"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    RECORDING = "recording"
    STEP_COMPLETED = "step_completed"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"

```

## 7.2 核心状态流

```text
CREATED
   ↓
CONNECTING
   ├─ 失败 → FAILED
   ↓
PREPARING
   ├─ 失败 → RECOVERING
   ↓
OBSERVING
   ↓
UNDERSTANDING
   ↓
RETRIEVING_MEMORY
   ↓
PLANNING
   ├─ 需要更多观察 → OBSERVING
   ├─ 任务已完成 → VERIFYING
   ↓
RESOLVING_ACTION
   ├─ 快捷键/回放 → EXECUTING
   ├─ 需要视觉定位 → GROUNDING
   └─ 不安全 → FAILED 或等待人工
   ↓
GROUNDING
   ├─ 无候选 → RECOVERING
   ↓
EXECUTING
   ├─ 执行异常 → RECOVERING
   ↓
WAITING
   ├─ 超时 → RECOVERING
   ↓
VERIFYING
   ├─ 成功 → RECORDING
   ├─ 失败可恢复 → RECOVERING
   └─ 失败不可恢复 → FAILED
   ↓
RECORDING
   ↓
STEP_COMPLETED
   ├─ 有下一步 → OBSERVING
   └─ 无下一步 → PASSED

```

## 7.3 状态迁移要求

每次状态迁移必须记录：

- 运行 ID；
- 步骤 ID；
- 原状态；
- 新状态；
- 迁移原因；
- 时间；
- 当前重试次数；
- 当前错误类型；
- 关联截图；
- 关联动作。

---

# 8. 核心领域模型

## 8.1 测试用例

```python
class TestCase(BaseModel):
    id: str
    name: str
    description: str
    mode: Literal["explicit", "goal_driven", "replay"]
    target_id: str

    preconditions: list["TestStep"] = []
    steps: list["TestStep"] = []
    goal: str | None = None
    cleanup: list["TestStep"] = []

    timeout_seconds: int = 600
    risk_level: Literal["low", "medium", "high"] = "low"
    tags: list[str] = []

```

## 8.2 测试步骤

```python
class TestStep(BaseModel):
    id: str
    name: str
    intent: str

    action_hint: "SemanticAction | None" = None
    expected: "VerificationSpec"
    timeout_seconds: int = 60
    retry_policy: "RetryPolicy"

    allow_ai_replan: bool = True
    allow_self_heal: bool = True

```

## 8.3 屏幕帧

```python
class ScreenFrame(BaseModel):
    id: str
    run_id: str
    step_id: str | None

    timestamp: datetime
    width: int
    height: int

    image_path: str
    image_sha256: str
    perceptual_hash: str | None = None

    crop_origin: tuple[int, int] | None = None
    scale_factor: float = 1.0

```

## 8.4 OCR 元素

```python
class OCRItem(BaseModel):
    text: str
    bbox: tuple[int, int, int, int]
    confidence: float
    normalized_text: str

```

## 8.5 结构化屏幕状态

```python
class StructuredScreen(BaseModel):
    frame_id: str

    page_type: str | None
    page_confidence: float

    ocr_items: list[OCRItem]
    template_matches: list["TemplateMatch"]
    visual_elements: list["VisualElement"]

    modal_present: bool
    loading_present: bool
    screen_stable: bool

    changed_regions: list["Region"]
    dynamic_regions: list["Region"]

    summary: str

```

## 8.6 语义动作

```python
class SemanticAction(BaseModel):
    action_id: str
    intent: str

    action_type: Literal[
        "click",
        "double_click",
        "right_click",
        "type_text",
        "press_key",
        "hotkey",
        "scroll",
        "drag",
        "inspect",
        "wait",
        "finish"
    ]

    target: "TargetDescription | None"
    text_value_ref: str | None = None
    keys: list[str] = []

    expected_effects: list["ExpectedEffect"]
    preferred_methods: list[str] = []
    fallback_methods: list[str] = []

    risk_level: Literal["low", "medium", "high"]
    reasoning_summary: str

```

## 8.7 目标描述

```python
class TargetDescription(BaseModel):
    role: str | None = None
    text: str | None = None
    description: str

    expected_region: str | None = None
    nearby_texts: list[str] = []
    visual_features: list[str] = []

    must_be_enabled: bool = True

```

## 8.8 Grounding 结果

```python
class GroundingCandidate(BaseModel):
    bbox: tuple[int, int, int, int]
    confidence: float
    label: str | None
    reason: str
    sources: list[str]

class GroundingResult(BaseModel):
    found: bool
    candidates: list[GroundingCandidate]
    model_name: str
    model_version: str | None
    raw_response_path: str

```

## 8.9 可执行动作

```python
class ExecutableAction(BaseModel):
    method: Literal[
        "replay",
        "keyboard",
        "mouse",
        "powershell_recipe"
    ]

    operation: str
    coordinates: tuple[int, int] | None = None
    bbox: tuple[int, int, int, int] | None = None
    keys: list[str] = []
    text: str | None = None

    preconditions: list[str] = []
    safety_checks: list[str] = []

```

## 8.10 验证结果

```python
class VerificationResult(BaseModel):
    status: Literal["passed", "failed", "uncertain"]
    confidence: float
    reason: str

    matched_conditions: list[str]
    failed_conditions: list[str]
    evidence_paths: list[str]

    suggested_failure_type: str | None = None

```

---

# 9. 模块设计

# 9.1 VNC Driver

职责：

- 建立和关闭 VNC 连接；
- 保持长连接；
- 获取截图；
- 获取区域截图；
- 鼠标移动；
- 鼠标点击；
- 鼠标拖拽；
- 键盘输入；
- 组合键；
- 释放修饰键；
- 检查连接状态；
- 有限次数重连。

内部接口：

```python
class VNCDriver(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def capture(self) -> bytes: ...

    async def move(self, x: int, y: int) -> None: ...
    async def click(self, x: int, y: int, button: int = 1) -> None: ...
    async def double_click(self, x: int, y: int) -> None: ...
    async def drag(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> None: ...

    async def press(self, key: str) -> None: ...
    async def hotkey(self, keys: list[str]) -> None: ...
    async def type_text(self, text: str) -> None: ...

    async def release_modifiers(self) -> None: ...
    async def health_check(self) -> bool: ...

```

实现要求：

- vncdotool 的阻塞调用使用专用线程封装；
- Agent 主事件循环不得被 VNC 阻塞；
- 所有动作增加超时；
- 动作前后可选保存截图；
- 连接重建后必须重新观察，不得直接继续动作。

---

# 9.2 Perception Pipeline

感知流水线分为快速路径和深度路径。

## 快速路径

每次观察执行：

1. 获取截图；
2. 计算图像哈希；
3. 与上一帧比较；
4. OCR；
5. 模板匹配；
6. 查询页面记忆；
7. 生成基础 StructuredScreen。

## 深度路径

在以下情况触发：

- 页面无法识别；
- 测试步骤需要复杂视觉理解；
- Grounding 目标动态；
- OCR 和模板相互冲突；
- 出现未知弹窗；
- 验证结果不确定。

深度路径执行：

1. MiMo 页面理解；
2. 局部裁剪；
3. 局部放大；
4. 候选框标注；
5. 多源置信度融合。

接口：

```python
class PerceptionPipeline:
    async def observe(
        self,
        context: RunContext,
        mode: Literal["fast", "deep"] = "fast",
        roi: Region | None = None,
    ) -> StructuredScreen:
        ...

```

---

# 9.3 Active Observer

Active Observer 负责决定“下一张图怎么看”。

支持的观察动作：

- 全屏低分辨率；
- 原始分辨率全屏；
- 指定 ROI；
- ROI 放大；
- 连续多帧；
- 带候选框标注图；
- 局部 OCR；
- 局部模板匹配。

示例：

```json
{
  "type": "inspect",
  "region": [1100, 600, 1920, 1080],
  "operations": [
    "crop",
    "zoom_3x",
    "ocr",
    "grounding"
  ]
}

```

---

# 9.4 Planner

Planner 输入：

- 测试目标；
- 当前步骤；
- 当前 StructuredScreen；
- 降采样截图；
- 最近若干步骤摘要；
- 历史失败摘要；
- 可用技能；
- 可用动作；
- 安全策略；
- 相似页面经验。

Planner 输出：

- 当前任务是否完成；
- 下一步语义动作；
- 预期效果；
- 是否需要额外观察；
- 备用路径；
- 风险等级。

Planner 的输出必须经过：

1. JSON 解析；
2. Pydantic 校验；
3. 动作白名单校验；
4. 风险策略校验；
5. 引用数据校验；
6. 最大长度校验。

连续两次无法输出有效结构时，当前步骤失败并进入恢复。

---

# 9.5 Action Policy

Action Policy 将语义动作转换为一个或多个候选执行方案。

示例：

```text
语义动作：保存当前文档

候选方案：
1. Ctrl+S
2. Alt+F 后按 S
3. OCR 找“保存”
4. 模板找保存图标
5. MiMo Grounding

```

选择因素：

- 历史成功率；
- 当前页面；
- 页面是否匹配历史记忆；
- 是否有快捷键；
- 是否有模板；
- OCR 是否找到唯一目标；
- MiMo 调用成本；
- 操作风险；
- 目标是否可能重复。

接口：

```python
class ActionPolicy:
    async def resolve(
        self,
        action: SemanticAction,
        screen: StructuredScreen,
        memory: "RetrievedExperience",
    ) -> list[ExecutableAction]:
        ...

```

---

# 9.6 Grounder

Grounder 主要使用 MiMo-V2.5。

输入：

```json
{
  "task": "定位目标控件",
  "target": {
    "role": "button",
    "text": "保存",
    "description": "编辑窗口右下角的主按钮",
    "nearby_texts": ["取消"]
  },
  "screen": {
    "width": 1920,
    "height": 1080
  },
  "ocr_candidates": [],
  "template_candidates": [],
  "history_candidates": []
}

```

输出：

```json
{
  "found": true,
  "candidates": [
    {
      "bbox": [1510, 915, 1635, 970],
      "confidence": 0.92,
      "label": "保存",
      "reason": "右下角主要按钮，与取消按钮相邻"
    }
  ]
}

```

Grounder 设计要求：

- 默认输出 Top-3；
- 坐标统一为原图像素坐标；
- 若输入为裁剪图，必须记录裁剪偏移；
- 系统统一完成坐标还原；
- 不允许只输出自然语言；
- 无法判断时必须返回 `found=false`；
- 执行前进行边界校验；
- 点击点默认使用 bbox 内部安全点，而不是机械中心点。

安全点击点计算：

```text
优先点击 bbox 中心附近
避开边缘 15%
避开 OCR 文字外溢区域
避开与其他候选重叠区域

```

---

# 9.7 Execution Router

根据 `ExecutableAction.method` 选择：

- Replay Executor；
- Keyboard Executor；
- Mouse Executor；
- PowerShell Recipe Executor。

执行结果包括：

```python
class ExecutionResult(BaseModel):
    success: bool
    started_at: datetime
    ended_at: datetime
    duration_ms: int

    executed_operation: str
    coordinates: tuple[int, int] | None
    error_code: str | None
    error_message: str | None

```

执行成功只表示 VNC 动作已发送，不表示业务操作成功。

业务成功必须由 Verifier 判断。

---

# 9.8 Wait Engine

Wait Engine 不使用固定 sleep 作为唯一判断条件。

支持：

- 最短等待；
- 最大等待；
- 多帧稳定；
- ROI 稳定；
- OCR 文本出现；
- 模板出现；
- 错误弹窗出现；
- 页面类型改变；
- VNC 断开。

建议默认参数：

```yaml
wait:
  min_delay_ms: 300
  capture_interval_ms: 500
  stable_frame_count: 3
  pixel_diff_threshold: 0.015
  default_timeout_seconds: 20

```

屏幕稳定判定：

```text
连续获取 3 帧
   ↓
屏蔽动态区域
   ↓
比较指定 ROI
   ↓
连续两次差异低于阈值
   ↓
判定稳定

```

---

# 9.9 Verification Engine

Verifier 使用责任链模式。

优先级：

```text
确定性规则
    ↓
OCR
    ↓
模板
    ↓
页面状态
    ↓
画面变化
    ↓
VLM 语义验证

```

验证规范示例：

```yaml
expected:
  all:
    - type: text_appears
      text: "保存成功"
      region: [1200, 700, 1900, 1080]

    - type: template_disappears
      template: "unsaved_marker.png"

```

复合断言结构：

```python
class VerificationSpec(BaseModel):
    operator: Literal["all", "any", "not"]
    conditions: list["VerificationCondition"]
    timeout_seconds: int = 15
    continuous_frames: int = 1

```

Verifier 返回：

- `passed`；
- `failed`；
- `uncertain`。

`uncertain` 不得直接作为通过。

系统可以：

- 调用更强验证器；
- 获取局部高清截图；
- 进入恢复；
- 要求人工确认。

---

# 9.10 Recovery Engine

错误类型：

```python
class FailureType(str, Enum):
    VNC_CONNECT_FAILED = "vnc_connect_failed"
    VNC_DISCONNECTED = "vnc_disconnected"
    BLACK_SCREEN = "black_screen"
    SCREEN_FROZEN = "screen_frozen"

    PAGE_UNKNOWN = "page_unknown"
    TARGET_NOT_FOUND = "target_not_found"
    GROUNDING_LOW_CONFIDENCE = "grounding_low_confidence"

    ACTION_SEND_FAILED = "action_send_failed"
    ACTION_NO_EFFECT = "action_no_effect"
    WRONG_TARGET = "wrong_target"

    INPUT_METHOD_ERROR = "input_method_error"
    FOCUS_ERROR = "focus_error"

    UNEXPECTED_DIALOG = "unexpected_dialog"
    PAGE_NOT_STABLE = "page_not_stable"
    ASSERTION_FAILED = "assertion_failed"

    UAC_OR_SECURE_DESKTOP = "uac_or_secure_desktop"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

```

恢复策略表：


| 错误             | 首选恢复                      |
| -------------- | ------------------------- |
| VNC 中断         | 有限重连，重新观察                 |
| 页面未稳定          | 延长等待，缩小 ROI               |
| 目标不存在          | 重新观察，局部放大                 |
| Grounding 置信度低 | OCR/模板融合，强模型裁决            |
| 点击无效果          | 第二候选、键盘路径、重新定位            |
| 输入法错误          | Esc、释放修饰键、切换英文输入          |
| 焦点错误           | 点击目标框内部、Tab 导航            |
| 未知弹窗           | 强模型分类，执行安全动作              |
| 页面错误           | Esc、Alt+Left、Alt+F4、Win+D |
| UAC 安全桌面       | 立即停止并报告环境限制               |


每个恢复策略必须配置：

- 最大次数；
- 冷却时间；
- 是否消耗全局重试额度；
- 是否允许改变动作路径；
- 是否需要强模型；
- 是否需要人工确认。

---

# 10. 运行模式设计

# 10.1 探索模式

适用于新用例。

流程：

```text
观察
→ 检索经验
→ Planner 规划
→ Action Policy
→ Grounding
→ 执行
→ 验证
→ 记录经验
→ 生成可回放步骤

```

特点：

- Planner 调用较多；
- MiMo Grounding 调用较多；
- 保存完整截图和模型响应；
- 自动产生候选回放轨迹。

# 10.2 回放模式

适用于正式回归。

流程：

```text
识别页面
→ 加载历史回放步骤
→ 匹配模板或 OCR 锚点
→ 执行动作
→ 验证

```

只有失败时：

```text
回放失败
→ MiMo 重新定位
→ 验证
→ 生成候选补丁

```

# 10.3 调试模式

调试模式额外输出：

- OCR 边框图；
- 模板匹配图；
- Grounding Top-K 图；
- 实际点击位置；
- 页面变化热区；
- 状态机当前状态；
- 模型请求和响应；
- 验证证据。

---

# 11. Record-Replay 设计

回放步骤结构：

```python
class ReplayStep(BaseModel):
    step_id: str
    page_fingerprint: "PageFingerprint"

    semantic_action: SemanticAction
    preferred_method: str

    target_template_path: str | None
    anchor_texts: list[str]
    relative_position: tuple[float, float] | None
    normalized_bbox: tuple[float, float, float, float] | None

    expected: VerificationSpec
    success_count: int
    failure_count: int
    version: int

```

回放目标定位顺序：

```text
页面指纹匹配
    ↓
目标模板匹配
    ↓
OCR 锚点匹配
    ↓
历史相对位置
    ↓
MiMo 重新 Grounding

```

自愈补丁结构：

```python
class ReplayPatch(BaseModel):
    patch_id: str
    replay_step_id: str

    old_version: int
    proposed_version: int

    old_target: dict
    new_target: dict

    reason: str
    before_image: str
    after_image: str
    verification_evidence: list[str]

    status: Literal[
        "pending",
        "approved",
        "rejected"
    ]

```

---

# 12. 自进化设计

# 12.1 在线进化

在线进化不训练模型权重。

实时更新：

## 页面记忆

记录：

- 页面类型；
- 页面 OCR 特征；
- 图像哈希；
- 稳定模板；
- 常见动态区域；
- 常见元素；
- 分辨率；
- 应用上下文。

## 元素记忆

记录：

- 元素语义；
- 文本；
- 模板；
- 历史 Bounding Box；
- 周边文字；
- 所属页面；
- 成功率；
- 最后出现时间。

## 失败记忆

记录：

- 错误类型；
- 错误截图；
- 错误动作；
- 失败候选；
- 成功恢复方式；
- 是否需要人工处理。

## 策略统计

记录：

```text
策略：OCR 文本定位
页面：登录页
目标：登录按钮
尝试：120
成功：114
平均耗时：80ms

```

Action Policy 使用这些数据进行动态路由。

# 12.2 经验采集

每个 Agent Step 生成 `VisualExperience`：

```python
class VisualExperience(BaseModel):
    run_id: str
    step_id: str

    before_frame_id: str
    after_frame_id: str

    page_before: str | None
    page_after: str | None

    semantic_action: dict
    grounding_candidates: list[dict]
    selected_candidate: dict | None

    execution_result: dict
    verification_result: dict

    outcome: Literal[
        "success",
        "failure",
        "uncertain"
    ]

    failure_type: str | None
    human_correction: dict | None

    planner_model: str
    grounder_model: str
    prompt_versions: dict

```

# 12.3 困难样本挖掘

满足任一条件时进入困难样本库：

- Grounder 置信度低；
- Top-1 失败但 Top-2 成功；
- Planner 与 Grounder 冲突；
- OCR 与 MiMo 冲突；
- 连续重试；
- 人工纠正；
- 未知页面；
- 未知弹窗；
- 自愈成功；
- 高置信度预测失败。

# 12.4 离线训练接口

MVP 不负责训练，但应支持导出：

```text
截图
+ 目标语义描述
+ 正确 Bounding Box
+ 错误候选
+ 页面类型
+ 验证结果

```

未来可训练：

- 页面分类器；
- 常用元素检测器；
- Grounding Reranker；
- 应用专用小模型。

---

# 13. 页面相似度和经验检索

页面指纹由以下特征构成：

```text
感知哈希
+ OCR 关键词集合
+ OCR 文本位置分布
+ 稳定模板集合
+ 页面布局特征
+ 分辨率
+ 应用上下文

```

MVP 不强制使用大型图像 Embedding 模型。

页面相似度示例：

```text
总分 =
  0.30 × pHash 相似度
+ 0.30 × OCR 文本相似度
+ 0.20 × OCR 布局相似度
+ 0.20 × 模板匹配相似度

```

阈值建议：

```yaml
memory:
  page_match_high: 0.88
  page_match_medium: 0.72
  page_match_low: 0.55

```

- 高匹配：可直接使用历史页面经验；
- 中匹配：使用经验，但必须重新验证；
- 低匹配：只作为 Planner 参考；
- 无匹配：按新页面处理。

---

# 14. PowerShell 黑盒配方设计

PowerShell 只能通过 VNC 键盘打开并输入。

配方示例：

```yaml
id: check_file_exists
name: 检查文件是否存在
risk_level: read_only

parameters:
  path:
    type: string
    required: true
    max_length: 260

command_template: >
  $ok = Test-Path -LiteralPath '{{ path }}';
  if ($ok) {
    Write-Output '__RESULT__:OK'
  } else {
    Write-Output '__RESULT__:FAIL'
  }

success:
  ocr_contains: "__RESULT__:OK"

failure:
  ocr_contains: "__RESULT__:FAIL"

timeout_seconds: 15
allow_unattended: true

```

执行流程：

```text
释放修饰键
→ Win+R
→ 输入 powershell -NoLogo -NoProfile
→ Enter
→ 等待 PowerShell 出现
→ 输入配方命令
→ Enter
→ 等待结果标记
→ OCR 验证

```

命令安全措施：

- 参数长度限制；
- 参数类型验证；
- 特殊字符转义；
- 禁止模型直接提供完整命令；
- 禁止未注册配方；
- 高风险配方默认需要确认；
- 报告中隐藏敏感参数。

---

# 15. 测试用例格式

示例：

```yaml
id: app-login-001
name: 正确账号登录
mode: explicit
target_id: win10-test-01

timeout_seconds: 180
risk_level: low

steps:
  - id: open-app
    name: 打开应用
    intent: 打开 ExampleApp

    action_hint:
      action_type: hotkey
      keys: ["WIN", "R"]

    expected:
      operator: all
      conditions:
        - type: text_appears
          text: "运行"

  - id: input-username
    name: 输入用户名
    intent: 在用户名输入框输入测试账号

    expected:
      operator: any
      conditions:
        - type: text_appears
          text: "test_user"
        - type: screen_region_changed
          region: [500, 300, 1200, 650]

  - id: submit-login
    name: 提交登录
    intent: 点击登录按钮

    expected:
      operator: all
      timeout_seconds: 30
      conditions:
        - type: text_appears
          text: "欢迎"
        - type: text_disappears
          text: "密码"

cleanup:
  - id: close-app
    name: 关闭应用
    intent: 关闭当前应用窗口

```

敏感数据通过引用传入：

```yaml
text_value_ref: secrets.login.username

```

不得直接写入测试用例正文。

---

# 16. 数据库设计

MVP 使用 SQLite。

主要表：

```text
vnc_targets
test_cases
test_runs
test_steps
state_transitions
screen_frames
observations
semantic_actions
grounding_results
execution_results
verification_results
recovery_attempts
page_memories
element_memories
trajectory_memories
failure_memories
visual_experiences
replay_scripts
replay_steps
replay_patches
human_corrections
strategy_statistics
model_versions
prompt_versions

```

关键关系：

```text
test_run
  ├─ test_step
  │   ├─ screen_frame
  │   ├─ observation
  │   ├─ semantic_action
  │   ├─ grounding_result
  │   ├─ execution_result
  │   ├─ verification_result
  │   └─ recovery_attempt
  │
  └─ visual_experience

```

---

# 17. 文件存储设计

```text
artifacts/
└─ runs/
   └─ 2026-07-20/
      └─ <run-id>/
         ├─ run.json
         ├─ report.html
         ├─ report.json
         ├─ logs/
         │  └─ events.jsonl
         ├─ frames/
         │  ├─ step-001-before.png
         │  └─ step-001-after.png
         ├─ annotated/
         │  ├─ step-001-ocr.png
         │  └─ step-001-grounding.png
         ├─ model/
         │  ├─ planner-request.json
         │  ├─ planner-response.json
         │  ├─ grounder-request.json
         │  └─ grounder-response.json
         └─ templates/
            └─ generated-target.png

```

截图保存策略可配置：

```yaml
artifacts:
  screenshot_policy: step
  save_model_payloads: true
  save_success_annotations: false
  retention_days: 30

```

---

# 18. 配置设计

主配置：

```yaml
runtime:
  max_step_count: 100
  max_recovery_attempts_per_step: 3
  max_total_recovery_attempts: 10
  save_checkpoint_after_each_step: true

vnc:
  driver: vncdotool
  connect_timeout_seconds: 15
  action_timeout_seconds: 10
  reconnect_attempts: 2

perception:
  ocr_enabled: true
  template_enabled: true
  mimo_enabled: true
  full_screen_ocr_every_step: true
  local_memory_limit_mb: 1200

models:
  planner:
    provider: configurable
    model: strong-vision-model
    timeout_seconds: 60

  grounder:
    provider: opencode-go
    model: mimo-v2.5
    timeout_seconds: 30
    top_k: 3

verification:
  prefer_deterministic: true
  visual_fallback_enabled: true

replay:
  enabled: true
  auto_generate: true
  patch_auto_apply: false

evolution:
  collect_experience: true
  update_memory_online: true
  train_model_online: false

```

---

# 19. 安全设计

## 19.1 凭据

- VNC 密码不写入 YAML 明文；
- 模型 API Key 通过环境变量或操作系统凭据存储；
- 测试数据中的密码使用引用；
- 日志自动过滤敏感字段。

## 19.2 截图

- 支持定义敏感区域；
- 报告中可对敏感区域打码；
- 密码输入步骤默认不保存输入后的局部截图；
- 截图按保留策略自动清理。

## 19.3 动作安全

危险动作分级：

```text
low
普通点击、输入、页面导航

medium
关闭应用、删除测试数据、修改测试配置

high
重启、关机、系统配置、网络配置、批量删除

```

高风险动作必须：

- 来自白名单测试步骤；
- 通过风险策略检查；
- 使用注册配方；
- 无人值守运行时显式允许。

---

# 20. 日志和可观测性

日志采用 JSON Lines。

每条日志至少包含：

```json
{
  "timestamp": "2026-07-20T21:30:00+09:00",
  "level": "INFO",
  "run_id": "run-123",
  "step_id": "login-submit",
  "state": "grounding",
  "event": "grounding_completed",
  "duration_ms": 1820,
  "candidate_count": 3
}

```

核心指标：

- VNC 连接时间；
- 单步耗时；
- OCR 耗时；
- Planner 耗时；
- Grounder 耗时；
- 模型调用次数；
- Grounding Top-1 成功率；
- Grounding Top-3 成功率；
- 重试次数；
- 恢复成功率；
- 页面记忆命中率；
- 回放命中率；
- 单用例模型成本。

---

# 21. 弱配置电脑优化

## 21.1 内存控制

- 同时只处理一个 VNC 会话；
- 截图处理完成后及时释放 NumPy 数组；
- 只保留最近 3～5 帧在内存；
- 原始截图立即写盘；
- OCR 模型按需加载；
- 不同时加载多个本地模型；
- 不在内存中缓存完整历史截图。

## 21.2 CPU 控制

- 页面稳定时不持续高频截图；
- 默认截图间隔 500ms；
- OCR 优先运行 ROI；
- 模板匹配优先限制 ROI；
- 不进行实时视频分析；
- 不使用本地大型视觉模型。

## 21.3 模型调用控制

- 页面未变化时不重复调用 Planner；
- 历史经验命中时不立即调用 MiMo；
- OCR 能唯一定位时不调用 Grounder；
- 回放成功时不调用 Planner；
- 语义验证只作为最后手段。

---

# 22. 容错设计

## 22.1 进程退出恢复

每完成一个测试步骤后保存检查点：

```json
{
  "run_id": "run-123",
  "last_completed_step": "step-004",
  "current_page": "report-list",
  "replay_version": 3
}

```

MVP 恢复粒度：

- 从当前测试步骤重新开始；
- 不从鼠标按下等动作中间恢复。

## 22.2 VNC 断线

流程：

```text
检测断线
→ 停止发送动作
→ 保存当前状态
→ 有限重连
→ 重新截图
→ 识别当前页面
→ 判断能否继续当前步骤

```

## 22.3 模型 API 失败

处理：

- 有限重试；
- 指数退避；
- 超时；
- 保存请求摘要；
- 切换备用模型；
- 无备用模型时失败并报告。

---

# 23. 测试策略

## 23.1 单元测试

覆盖：

- 坐标转换；
- Bounding Box 边界；
- OCR 文本标准化；
- 页面相似度；
- 状态迁移；
- 风险策略；
- 重试策略；
- 复合断言；
- PowerShell 参数转义。

## 23.2 离线截图测试

使用固定截图测试：

- OCR；
- 模板匹配；
- 页面识别；
- Grounding 响应解析；
- Planner 响应解析；
- Verification；
- Recovery 分类。

不需要连接真实 VNC。

## 23.3 VNC 集成测试

覆盖：

- 建立连接；
- 截图；
- 键盘输入；
- 鼠标点击；
- 组合键；
- 断线重连；
- 分辨率读取。

## 23.4 端到端测试

最少覆盖：

- 打开运行窗口；
- 输入文本；
- 打开 PowerShell；
- 执行只读命令；
- 点击应用按钮；
- 验证页面变化；
- 模拟点击失败；
- 模拟未知弹窗；
- 回放；
- 自愈补丁生成。

---

# 24. MVP 实施阶段

## 阶段 1：VNC 基础驱动

交付：

- VNC 长连接；
- 截图；
- 键鼠操作；
- 快捷键；
- 修饰键释放；
- 基础日志。

## 阶段 2：屏幕感知

交付：

- ScreenFrame；
- 截图差异；
- 多帧稳定；
- OCR；
- 模板匹配；
- StructuredScreen。

## 阶段 3：模型接入

交付：

- ModelProvider 接口；
- Planner；
- MiMo Grounder；
- 结构化输出；
- Top-K 候选；
- 坐标转换。

## 阶段 4：Agent 状态机

交付：

- 状态机；
- Action Policy；
- Executor；
- Wait Engine；
- Verification Engine；
- Retry；
- Recovery。

## 阶段 5：测试用例和报告

交付：

- YAML 用例；
- CLI；
- HTML 报告；
- JSON 报告；
- 失败截图和证据。

## 阶段 6：Replay 和经验记忆

交付：

- 轨迹记录；
- 页面指纹；
- 页面记忆；
- 元素记忆；
- 回放脚本；
- 自愈补丁。

## 阶段 7：自进化闭环

交付：

- 策略成功率；
- 困难样本库；
- 人工纠正；
- 置信度校准；
- 训练数据导出。

---

# 25. 关键技术决策

## ADR-001 自研状态机

决定：

MVP 使用自研显式状态机，不引入 LangGraph。

原因：

- 流程可控；
- 容易调试；
- 依赖少；
- 更符合测试运行时；
- 后续仍可迁移。

## ADR-002 不以 MCP 作为内部架构

决定：

模块通过 Python Protocol 和内部注册表解耦。

原因：

- 高频截图和键鼠调用不适合增加远程协议开销；
- MCP 工具上下文对运行时无必要；
- 后续可单独实现 MCP Adapter。

## ADR-003 MiMo 是 Grounder，不是 Agent

决定：

MiMo-V2.5 负责视觉理解和 Grounding，不控制整体工作流。

## ADR-004 验证独立

决定：

Verifier 必须根据操作后截图重新计算，不能依赖执行模型的自我判断。

## ADR-005 自愈需要审核

决定：

自愈只生成候选补丁，不自动修改正式测试基线。

## ADR-006 模块化单体

决定：

MVP 为单进程模块化单体。

原因：

- 当前仅单 VNC 会话；
- 工作电脑配置较弱；
- 便于快速调试；
- 降低部署和维护成本。

---

# 26. MVP 完成标准

满足以下条件，MVP 可视为完成：

1. 能稳定连接一台 Windows 10 VNC；
2. 能截图并执行键鼠操作；
3. 能通过 OCR、模板和 MiMo 理解目标；
4. Planner 与 Grounder 已分离；
5. MiMo 能返回 Top-K Bounding Box；
6. 能执行键盘优先的动作策略；
7. 能通过多帧检测等待页面稳定；
8. 每个正式步骤均能验证；
9. 能分类并处理常见失败；
10. 能保存完整运行轨迹；
11. 能生成 HTML 和 JSON 报告；
12. 能将成功探索转为回放；
13. 回放失败后能生成自愈候选补丁；
14. 能积累页面、元素和失败经验；
15. 单会话运行不要求独立显卡；
16. 不运行本地大型视觉模型；
17. 不存在无限重试；
18. 不会自动修改正式测试断言。

---

# 27. 总体设计结论

系统最终采用：

```text
模块化单体 Python Agent Runtime
│
├─ 自研显式状态机
├─ 强视觉 Planner
├─ MiMo-V2.5 Grounder
├─ OCR + 模板 + Screen Diff
├─ 页面和元素经验记忆
├─ 键盘优先 Action Policy
├─ vncdotool VNC Executor
├─ 独立 Verification Engine
├─ 结构化 Recovery Engine
├─ Record-Replay
├─ 待审核自愈补丁
└─ 受控自进化数据闭环

```

该设计能够在纯 VNC 黑盒、低配置控制电脑的约束下落地，同时为后续扩展以下能力保留接口：

- 多 VNC Worker；
- Web 管理界面；
- CI 接入；
- 本地专用轻量模型；
- 云端训练流水线；
- 模型 Shadow 测试；
- PostgreSQL 和对象存储；
- 分布式任务调度；
- MCP 或其他外部工具协议适配。
