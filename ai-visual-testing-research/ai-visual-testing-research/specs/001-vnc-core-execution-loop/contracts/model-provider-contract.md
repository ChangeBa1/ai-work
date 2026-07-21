# Contract: Planner / Grounder 模型提供方接口

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 FR-012~019、FR-046 与宪法 Core Principle II。本契约定义 `models/provider.py` 中
Planner 与 Grounder 两个 Protocol 的输入输出结构，使任何新增的模型供应商实现只需满足本
契约即可被替换接入，调用方（`planning/`）代码不需要改动。

## PlannerProvider

**方法**：`async def plan(request: PlannerRequest) -> PlannerResponse`

**PlannerRequest（请求）**：

```json
{
  "step_intent": "点击登录按钮",
  "expected": { "operator": "all", "conditions": [ { "type": "text_appears", "value": "欢迎" } ] },
  "structured_screen": { "...": "见 data-model.md §3" },
  "iteration_index": 1,
  "remaining_iteration_budget": 2,
  "previous_verification_result": {
    "status": "uncertain",
    "reason": "登录按钮被一个安全提示弹窗遮挡，无法确认点击是否命中",
    "evidence_refs": ["..."]
  },
  "recent_step_summaries": ["..."],
  "risk_policy": { "max_risk_level": "low" }
}
```

`iteration_index`/`remaining_iteration_budget`/`previous_verification_result` 三个字段
为 Clarification 2026-07-20 新增：当同一 `TestStep` 因验证未通过而进入下一轮
`ActionIteration`（见 data-model.md §9）时，Planner MUST 能看到上一轮为何未达成
`expected`，才能决定是重复原动作、切换候选，还是先插入一个前置微动作（如先关闭遮挡的
弹窗）。

**PlannerResponse（响应，MUST 通过 Pydantic 校验）**：

```json
{
  "task_completed_hint": false,
  "semantic_action": {
    "action_id": "act-001",
    "intent": "关闭遮挡的安全提示弹窗",
    "action_type": "press_key",
    "target": null,
    "keys": ["escape"],
    "risk_level": "low"
  },
  "needs_more_observation": false
}
```

**契约保证**：

- `semantic_action` 结构 MUST NOT 包含任何坐标字段（对应 data-model.md §4 的类型层面
  约束，落实 FR-013）。
- 响应 MUST 经过 JSON 解析 → Pydantic 校验 → 动作白名单校验 → 风险策略校验四层检查
  （对齐 overall_design.md 9.4）；连续两次无法产出合法结构时，调用方 MUST 将当前步骤
  标记为失败并进入恢复，而不是无限重试解析。
- `task_completed_hint`（Clarification 2026-07-20 由 `task_completed` 更名而来）MUST
  被调用方视为**仅供参考的提示**，用于决定是否值得再花一轮迭代——MUST NOT 作为该步骤
  通过与否的依据。步骤是否通过 MUST 只由本轮 `VERIFYING` 阶段针对 `TestStep.expected`
  独立算出的 `VerificationResult` 决定（宪法 Core Principle II/IV：Planner 不得自我
  判定测试通过）。即使 `task_completed_hint=true`，系统仍 MUST 执行本轮验证；即使
  `task_completed_hint=false`，只要本轮验证已经 `passed`，步骤也 MUST 立即判定通过，
  不强制消耗剩余迭代预算。
- 同一步骤内，Planner 允许在 `semantic_action` 中给出未在 `step_intent` 中声明的前置
  微动作（如关闭弹窗、滚动、聚焦），但每一轮返回的仍是单个语义动作，多轮迭代由调用方的
  状态机驱动，Planner 不得在一次响应中打包多个动作（保持"Planner 只回答下一步做什么"
  的单一职责）。

## PlannerProvider.describe_screen（视觉理解补充方法）

对应 FR-010（US2 观察管线的补充理解）与 FR-032/FR-031 的 `visual_question` 验证条件
（US7）。这两处都需要"让视觉模型看当前截图、给出一个明确回答"的能力，但输出形态不同——
前者要一段开放式页面描述，后者要一个可直接映射到通过/失败/不确定的判定——因此定义为
`PlannerProvider` 上的第三个方法，与 `plan` 共用同一 Planner 模型与鉴权配置，但请求/响应
结构独立于 `PlannerRequest`/`PlannerResponse`。

**方法**：`async def describe_screen(request: VisionUnderstandingRequest) -> VisionUnderstandingResponse`

**VisionUnderstandingRequest（请求）**：

```json
{
  "mode": "describe",
  "image_ref": "artifacts/runs/.../frames/step-003-before.png",
  "structured_screen_hint": { "ocr_items": [], "template_matches": [], "changed_regions": [] },
  "question": null
}
```

```json
{
  "mode": "answer_question",
  "image_ref": "artifacts/runs/.../frames/step-004-after.png",
  "structured_screen_hint": { "...": "同上，可选" },
  "question": "屏幕上是否出现\"欢迎\"文字？"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `Literal["describe","answer_question"]` | `describe` 对应 FR-010；`answer_question` 对应 FR-032 的 `visual_question` |
| `image_ref` | str | 待理解/待回答问题所依据的原始截图，MUST NOT 遮罩（与 `PlannerRequest`/`GroundingRequest` 相同，遮罩仅作用于本地持久化与报告，见下方"图像不遮罩"契约保证） |
| `structured_screen_hint` | object \| null | 可选，已知的 OCR/模板/变化检测结果，帮助模型聚焦，不替代模型自身判断 |
| `question` | str \| null | `mode="answer_question"` 时 MUST 提供，取值为 `VerificationCondition.value`；`mode="describe"` 时 MUST 为 `null` |

**VisionUnderstandingResponse（响应，MUST 通过 Pydantic 校验）**：

```json
{
  "mode": "describe",
  "description": "当前为登录页面，账号/密码输入框均为空，焦点在账号输入框",
  "answer": null,
  "confidence": 0.88,
  "reason": "",
  "model_name": "planner-v1"
}
```

```json
{
  "mode": "answer_question",
  "description": null,
  "answer": "passed",
  "confidence": 0.93,
  "reason": "页面右上角出现\"欢迎，张三\"字样",
  "model_name": "planner-v1"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `Literal["describe","answer_question"]` | 回显请求的 `mode` |
| `description` | str \| null | `mode="describe"` 时 MUST 填充，对应 data-model.md §3 `VisionUnderstanding.description`；`mode="answer_question"` 时 MUST 为 `null` |
| `answer` | `Literal["passed","failed","uncertain"] \| null` | `mode="answer_question"` 时 MUST 填充，直接对应 `VerificationResult` 三态之一（FR-033）；`mode="describe"` 时 MUST 为 `null` |
| `confidence` | float(0~1) | 模型对本次描述/回答的置信度 |
| `reason` | str | `answer_question` 时 MUST 说明判断依据（用于证据留存，FR-040）；`describe` 时可为空 |
| `model_name` | str | 对应 data-model.md §3 `VisionUnderstanding.model_name` |

**Wire 协议订正（2026-07-22，与 GrounderProvider 的同类问题一并发现）**：
`models/planner_client.py` 的 `HttpPlannerClient.describe_screen()` 早期实现把整个
`VisionUnderstandingRequest`（含 `image_ref` 这个本地文件路径字符串）直接 `json.dumps()`
成一段文本塞进 `messages[].content`，**从未真正读取图片字节并发送给模型**——对一个视觉
理解/视觉问答接口而言，这等于模型永远看不到截图，只看到一个它无法访问的文件路径字符串。
MUST 修复为：与 `plan()` 一样命中 `POST {base_url}/chat/completions`（OpenAI 兼容格式，
`describe_screen` 与 `plan` 共用同一 Planner 供应商配置，无需另外文档化 base_url/端点），
但 `messages[].content` MUST 使用多模态数组形式，将 `request.image_ref` 指向的本地文件
读取字节、base64 编码后作为
`{"type": "image_url", "image_url": {"url": "data:image/png;base64,<...>"}}` 内容块内联；
文本部分携带 `mode`（`describe` 或 `answer_question`）、`question`（若有）、
`structured_screen_hint`。响应仍按 `choices[0].message.content` 取文本、解析为
`VisionUnderstandingResponse`（`response_format: {"type": "json_object"}` 已经在约束
输出为 JSON，不需要像 Grounder 那样额外处理 markdown 代码块包裹，但仍 SHOULD 做防御性
剥离）。

**契约保证**：

- `mode="describe"` 的响应 MUST NOT 直接给出 `passed`/`failed`/`uncertain` 判定——它只是
  补充理解，写入 `StructuredScreen.vision_understanding`，不作为验证依据（FR-010 与 FR-032
  的调用时机、下游用途相互独立，不得混用同一次响应）。
- `mode="answer_question"` 时，模型无法给出明确回答（如问题指向的内容既不能确认存在也不能
  确认不存在）MUST 返回 `answer="uncertain"`，MUST NOT 强行猜测为 `passed`/`failed`
  （对齐 FR-033 的"不确定不得被折叠"要求）。
- **`mode="describe"` 的不确定路径（需求质量门禁 2026-07-21 补充，此前仅定义了
  `answer_question` 模式的不确定路径）**：模型对当前页面缺乏把握时 MUST 仍返回一个非空
  `description`（可以是"无法确定页面具体内容"等如实陈述），MUST NOT 返回空字符串或省略
  该字段，并配以相应偏低的 `confidence`；`describe` 模式不存在 `passed`/`failed`/
  `uncertain` 三态判定，只有"描述内容 + 置信度"，调用方（`perception/pipeline.py`）在
  `confidence` 低于配置阈值时 MAY 将其视为"补充理解也未能提供有效信息"，但仍 MUST 保留
  该记录用于证据留存（FR-040）。
- **`describe_screen` 为 `PlannerProvider` 的必需方法（需求质量门禁 2026-07-21 补充）**：
  与 `plan` 同为 Protocol 的必需方法，任何新增的 Planner 供应商实现 MUST 实现
  `describe_screen`。若某个模型供应商本身不具备可靠的视觉理解能力（如纯文本推理模型），
  其 `describe_screen` 实现 MUST 通过返回低置信度 `description`（`mode="describe"`）或
  `answer="uncertain"`（`mode="answer_question"`）等方式明确表达"不支持/没有把握"，
  MUST NOT 抛出未处理异常导致调用方崩溃，也 MUST NOT 拒绝装配（装配校验见
  research.md 新增决策项）；调用方在收到这类"不支持"响应时，处理方式与遇到
  `uncertain`/低置信度结果一致，不需要专门的"不支持"分支。此规则同时回答了"某供应商声明
  支持 `plan` 但不支持 `describe_screen`"的场景：这种情况 MUST NOT 发生于装配阶段（因为
  `describe_screen` 是必需方法），只可能表现为该方法在语义上总是返回低置信度/uncertain。
- **超时（需求质量门禁 2026-07-21 补充）**：`describe_screen` 的调用超时 MUST 复用
  `models.planner.timeout_seconds`（即与 `plan` 相同的默认 60s，见 plan.md Performance
  Goals），除非显式配置了独立的 `models.planner.describe_screen_timeout_seconds`（见
  data-model.md §11）；不引入未声明的第二套隐式默认值。
- 图像不遮罩：`image_ref` 指向的截图 MUST 为原始未遮罩画面，规则与 `PlannerRequest`/
  `GroundingRequest` 一致（FR-049）。
- `raw_response_ref`（存档路径）由调用方（`perception/pipeline.py` 或
  `verification/visual_verifier.py`）在持久化时记录，不属于本响应体字段本身。

## GrounderProvider（默认实现：OpenCode Go API 上的 MiMo-V2.5）

**方法**：`async def ground(request: GroundingRequest) -> GroundingResult`

**GroundingRequest（请求，对应 FR-015）**：

```json
{
  "image_ref": "artifacts/runs/.../frames/step-003-before.png",
  "crop_offset": [0, 0],
  "target": {
    "role": "button",
    "text": "保存",
    "description": "编辑窗口右下角的主按钮",
    "nearby_texts": ["取消"]
  },
  "ocr_candidates": [],
  "template_candidates": []
}
```

**GroundingResult（响应，对应 FR-016~018，MUST 通过 Pydantic 校验）**：

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
  ],
  "model_name": "mimo-v2.5"
}
```

**契约保证**：

- `candidates` 长度 MUST ≤ 3（FR-016）；`found=false` 时 `candidates` MUST 为空数组。
- `bbox` MUST 是还原到原始 VNC 屏幕分辨率后的像素坐标；若 `image_ref` 对应裁剪图，
  实现 MUST 在返回前应用 `crop_offset` 完成还原（FR-017），调用方不再二次换算。
- 无法可靠判断时 MUST 返回 `found=false`，MUST NOT 编造坐标（FR-018）。
- 调用方在执行前 MUST 校验每个候选 `bbox` 落在当前 `StructuredScreen.resolution` 范围内
  （FR-019），越界候选被丢弃且不计入"已找到"。
- **置信度分级路由（Clarification 2026-07-20，由调用方而非 Grounder 本身实现）**：
  Grounder 只需如实返回 `found` 与每个候选的 `confidence`；由 `planning/action_policy.py`
  依据配置阈值把结果分类为 `target_not_found`（`found=false`）、
  `grounding_low_confidence/overall_low_confidence`（Top-1 置信度低于阈值）或
  `grounding_low_confidence/top1_top2_close`（Top-1、Top-2 置信度差值小于阈值），三者
  对应的 `FailureType`/`sub_reason` 定义见 data-model.md §8。Grounder 实现 MUST NOT 自行
  吞掉某个候选或提前做二选一——即使两个候选置信度接近，也 MUST 原样都放进 `candidates`，
  由调用方决定如何处理。
- **图像不遮罩（Clarification 2026-07-20，对应 FR-049）**：`image_ref` 指向的截图 MUST
  为原始未遮罩画面；本地敏感区域遮罩只应用于持久化制品与报告渲染，MUST NOT 在构造
  `GroundingRequest`/`PlannerRequest`/`VisionUnderstandingRequest` 时对截图做遮罩处理。

## GrounderProvider 默认实现：MiMo-V2.5 / OpenCode Go 真实 Wire 协议（订正 2026-07-22）

**问题**：本文档前面给出的 `GroundingRequest`/`GroundingResult` JSON 示例，是
`models/provider.py` 中 `GrounderProvider.ground()` 这个 **Python 内部 Protocol** 的
输入/输出形状，供 `planning/action_policy.py`、`runtime/agent_runtime.py` 等调用方使用，
MUST 保持不变——这不是问题。问题出在 `models/mimo_grounder.py` 的默认实现
`MimoGrounderClient`：它把这份内部形状原样 `POST` 给了一个自行发明的路径
`{base_url}/v1/ground`，从未对照过 OpenCode Go 的真实 HTTP 接口。核实官方文档
（https://opencode.ai/docs/zh-cn/go）后确认，真实协议与此完全不同，MUST 订正。

**真实外部协议（`MimoGrounderClient` MUST 在内部完成"内部契约 → 真实 wire 协议"的转换，
调用方 `GrounderProvider.ground()` 的签名不受影响）**：

| 项目 | 值 |
|---|---|
| Base URL | `https://opencode.ai/zen/go/v1`（云端托管服务，不是本地地址；`config/models.yaml` 中 `grounder.base_url` 的默认值 MUST 更新为此值，此前占位的 `http://127.0.0.1:4096` 不可用） |
| 端点 | `POST /chat/completions`（OpenAI 兼容格式；MiMo 与 Grok/GLM/Kimi/DeepSeek 共用此端点，与走 `/v1/messages` 的 MiniMax/Qwen 不同） |
| 鉴权 | `Authorization: Bearer <api_key>`（`api_key_env` 解析出的密钥），`Content-Type: application/json` |
| 模型标识 | ✅ **已用真实端点实测复核（2026-07-22）**：MUST 使用裸模型名，MUST NOT 加
  `"opencode-go/"` 前缀。`GET {base_url}/models` 返回的 ID 全部是裸名（如
  `"mimo-v2.5"`、`"kimi-k3"`、`"glm-5.2"`）；实测 `POST /chat/completions` 传
  `"model": "mimo-v2.5"` 返回 200 正常完成，传 `"model": "opencode-go/mimo-v2.5"`
  返回 401 且错误信息明确为 `{"type":"ModelError","message":"Model
  opencode-go/mimo-v2.5 is not supported"}`。`"opencode-go/<model-id>"` 前缀形式
  是 OpenCode 自己 TUI/内部 provider 配置里引用上游模型的写法，不是直接调用这个 REST
  API 时 `model` 字段该填的值——这一点此前曾被误判为已确认，特此订正。 |
| 图片输入 | ⚠️ **NEEDS VERIFICATION**：官方文档未明确说明多模态图片传参格式。按 OpenAI 兼容 API 的通行做法，MUST 先尝试标准形式：`messages[].content` 为数组，其中一项为 `{"type": "image_url", "image_url": {"url": "data:image/png;base64,<...>"}}`；图片 MUST 从 `request.image_ref` 指向的本地文件读取字节并 base64 编码后内联传入（OpenCode 的服务器读不到调用方本机文件系统，`image_ref` 这个本地路径 MUST NOT 被当作可远程访问的 URL 直接传递） |
| 响应形态 | 标准 OpenAI `chat.completion` 对象，实际的定位结果（`found`/`candidates`/...）出现在 `choices[0].message.content` 这段**文本**里，不是一个专用的结构化字段——因此需要靠 prompt 让模型把结果严格按约定 JSON 格式输出，再由客户端从文本中解析 JSON |

**请求体构造（`MimoGrounderClient.ground()` 内部职责）**：

```json
{
  "model": "mimo-v2.5",
  "messages": [
    {
      "role": "system",
      "content": "你是一个 GUI 元素定位助手。根据截图和目标描述，只输出一个 JSON 对象（不要 markdown 代码块、不要任何多余文字），格式为：{\"found\": bool, \"candidates\": [{\"bbox\": [x1,y1,x2,y2], \"confidence\": 0~1 之间的数, \"label\": string 或 null, \"reason\": string}]}。bbox 为图片内的像素坐标；candidates 最多 3 个，按置信度降序；无法可靠判断时返回 {\"found\": false, \"candidates\": []}，不得编造坐标。"
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "目标：role=button, text=保存, description=编辑窗口右下角的主按钮, nearby_texts=[取消]。已知 OCR/模板候选（供参考，不代表最终答案）：<ocr_candidates 与 template_candidates 的精简摘要>"
        },
        {
          "type": "image_url",
          "image_url": { "url": "data:image/png;base64,<base64 编码后的截图字节>" }
        }
      ]
    }
  ]
}
```

**响应解析（`models/response_parser.py` 的 `parse_grounding_response` MUST 调整为先从
`choices[0].message.content` 取出文本，再对该文本做 JSON 解析，而不是假设整个 HTTP 响应体
本身就是 `GroundingResult` 形状）**：

1. 取 `resp.json()["choices"][0]["message"]["content"]` 得到模型输出的原始文本。
2. 若文本被包裹在 ```json ... ``` 代码块中，MUST 先剥离代码块标记再解析（模型有时会不遵从
   "不要 markdown" 的指令）。
3. `json.loads()` 解析为 `{"found": ..., "candidates": [...]}`，映射为内部
   `GroundingResult`（`bbox`/`confidence`/`label`/`reason` 逐字段对应，`model_name` 由调用方
   从 `self.cfg.model` 填入，不依赖模型自报）。
4. 解析失败（非法 JSON、字段缺失）MUST 归类为 `verification`-无关的模型响应异常，按
   FR-036 的 `timeout`/通用异常路径处理并触发恢复，MUST NOT 让异常直接向上抛出终止整个
   `TestRun`。
5. 坐标还原（`crop_offset`）、候选数量截断至 3、越界过滤（FR-019）等既有逻辑不变，仍在
   `MimoGrounderClient.ground()` 完成 JSON 解析之后执行。

**为什么不改内部 `GroundingRequest`/`GroundingResult` 契约本身**：这两个类型是
`planning/`、`runtime/` 等调用方与 `GrounderProvider` Protocol 之间的接口，已经被多处代码和
测试依赖（`action_policy.py` 的候选边界校验、`tests/fixtures/test_mimo_grounder.py` 等）；
真正缺失的是 `MimoGrounderClient` 这一个具体实现类内部"如何把内部请求翻译成真实 HTTP
调用"的逻辑，属于该类的实现细节，不影响 Protocol 签名，因此保持"可替换性契约"（下节）中
"新增供应商只需新增实现类，不要求修改调用方代码"这一原则不变。

## 可替换性契约

- 两个 Protocol（`PlannerProvider` 含 `plan`/`describe_screen` 两个方法、
  `GrounderProvider` 含 `ground` 方法）的具体实现类通过 `models.yaml` 中的 `provider`
  字段在启动时装配（见 research.md §4）；新增供应商 MUST 只需新增一个实现类并注册，
  MUST NOT 要求修改 `planning/`、`perception/`、`verification/` 或 `execution/` 中的
  调用代码。
- Grounder 的默认实现固定为"通过 OpenCode Go API 调用 MiMo-V2.5"（spec 固定约束），
  但 Protocol 本身不假设具体供应商，允许未来替换。
- `describe_screen` 与 `plan` 共用同一个 `PlannerProvider` 实现类与同一份
  `models.planner.*` 配置（provider/超时/API Key），替换 Planner 供应商时两个方法
  MUST 一并切换，不允许 `plan` 与 `describe_screen` 分别指向不同供应商。
