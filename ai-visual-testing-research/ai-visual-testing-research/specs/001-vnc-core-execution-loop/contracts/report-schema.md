# Contract: 测试报告 Schema

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 FR-040~042（用户故事九）。JSON 报告是 HTML 报告的数据来源，两者 MUST 保持一致
（research.md §8）。

## JSON Schema（`report.json` 顶层结构）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TestRunReport",
  "type": "object",
  "required": ["run_id", "test_case_id", "status", "started_at", "ended_at", "steps"],
  "properties": {
    "run_id": { "type": "string" },
    "test_case_id": { "type": "string" },
    "status": { "type": "string", "enum": ["passed", "failed", "cancelled"] },
    "started_at": { "type": "string", "format": "date-time" },
    "ended_at": { "type": "string", "format": "date-time" },
    "steps": {
      "type": "array",
      "items": { "$ref": "#/$defs/StepReport" }
    }
  },
  "$defs": {
    "StepReport": {
      "type": "object",
      "required": ["step_id", "status", "iterations", "stage_durations_ms"],
      "properties": {
        "step_id": { "type": "string" },
        "status": { "type": "string", "enum": ["passed", "failed", "cancelled"] },
        "iterations": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/IterationReport" }
        },
        "model_names": { "type": "object" },
        "raw_model_response_refs": { "type": "array", "items": { "type": "string" } },
        "stage_durations_ms": { "type": "object" },
        "failure_reason": { "type": ["string", "null"] }
      }
    },
    "IterationReport": {
      "type": "object",
      "required": ["iteration_index", "verification_result"],
      "properties": {
        "iteration_index": { "type": "integer", "minimum": 0 },
        "before_frame_path": { "type": "string" },
        "after_frame_path": { "type": "string" },
        "semantic_action": { "type": "object" },
        "grounding_candidates": { "type": "array" },
        "selected_candidate": { "type": ["object", "null"] },
        "executable_action": { "type": "object" },
        "execution_result": { "type": "object" },
        "wait_result": { "type": "object" },
        "verification_result": {
          "type": "object",
          "required": ["status", "reason", "evidence_refs"],
          "properties": {
            "status": { "type": "string", "enum": ["passed", "failed", "uncertain"] },
            "reason": { "type": "string" },
            "evidence_refs": { "type": "array", "items": { "type": "string" } }
          }
        },
        "recovery_attempts": { "type": "array" }
      }
    }
  }
}
```

（`StepReport.iterations` 对应 data-model.md §9 的 `ActionIteration` 列表——Clarification
2026-07-20：一个测试步骤 MAY 包含多轮迭代，`status` 只取决于最后一轮 `verification_result`，
但报告 MUST 保留全部轮次，而不是只保留最后一轮，以便复核 Planner 每一轮做了什么。）

## 契约保证

- `status` 字段 MUST 与实际执行结果一致（即最后一轮 `iterations[-1].verification_result.
  status`，`uncertain` 在预算耗尽时归为 `failed`）；报告生成逻辑 MUST NOT 在任何步骤最终
  验证结果为 `failed`/`uncertain` 时仍将整体 `TestRun.status` 标记为 `passed`（对应
  SC-007）。
- 失败步骤的 `StepReport` MUST 包含 `failure_reason`，且其 `iterations` 中每一轮 MUST 包含
  `before_frame_path`/`after_frame_path`、`grounding_candidates`（如适用）、
  `verification_result.evidence_refs` 和 `recovery_attempts`，以支持无需重新运行即可定位
  问题、且能看清 Planner 在多轮迭代中分别尝试了什么（FR-042）。
- 报告渲染（HTML/JSON 均含）前 MUST 对配置中声明的敏感区域截图打码、对敏感字段脱敏
  （宪法"凭据与隐私"）；该遮罩只影响本报告的展示，MUST NOT 回写或影响已经发往外部模型
  API 的历史请求记录本身的语义（Clarification 2026-07-20，对应 FR-049——外发请求本就
  没有遮罩，报告侧的遮罩是展示层面的独立处理）。
- HTML 报告 MUST 由与 JSON 报告相同的 `TestRun`/`StepRecord` 数据源渲染，不得包含 JSON
  报告之外的额外事实性内容（避免两份报告口径不一致）。

## 向后兼容增量（feature 004，2026-07-23）

feature `004-frame-dedup-observability` 只在本 schema 之上做**纯增量**扩展；以上章节定义
的旧顶层键、`StepReport`/`IterationReport` 嵌套字段、类型、必填/可选关系、枚举、
null/缺省语义、数组顺序与 `status` 聚合规则全部保持不变，旧消费者忽略新增字段即可继续
正确解析。详见
[`specs/004-frame-dedup-observability/contracts/report-contract.md`](../../004-frame-dedup-observability/contracts/report-contract.md)
的完整定义；本节只记录对**本文件**的可见影响。

### `before_frame_path` / `after_frame_path` 语义澄清

这两个字段的契约语义从来只是"对应操作前/后的可读取证据路径"——本 schema **从未**承诺过
存在 `report_frames/` 目录、固定文件名、或"每条 iteration 一份独立副本"。feature 004 将
这两个字段从早期实现细节（复制到 `report_frames/` 的副本路径）改为直接解析并返回内容寻址
的安全物理路径（`safe_evidence` bundle 内已发布、经完整性校验的文件），这不构成字段语义
变更：

- 类型仍是字符串（或 `null`——语义不变：本次迭代未产生对应观察证据，或证据在完整性校验中
  不可用）。
- 前后关联不变：`before_frame_path` 始终对应操作前采集，`after_frame_path` 始终对应操作
  后采集。
- 可读取性不变：非 `null` 时该路径 MUST 指向一个真实存在、可被图片解码器解码的文件。
- 旧 `report_frames/` 文本路径值不再被保证；等价性验收改为比较解析后路径指向的
  **物理身份**（`artifact_sha256`）或对应逻辑帧的 `content_hash`，而非逐字节比较路径字符
  串本身。
- 证据缺失、越界、损坏、大小或哈希不匹配、不可解码、或遮罩身份不一致时，该字段值为
  `null`——这是"未产生证据"这一既有 null 语义的严格超集，不是新增的独立语义分支。

### 新增顶层字段（仅追加，不改变现有字段）

```json
{
  "frames": [],
  "stage_measurements": [],
  "performance_summary": {},
  "display_status": "通过",
  "localized_message": null
}
```

- `frames[]`：按 `capture_sequence` 排序的全部成功逻辑帧（观察/等待/重试/恢复/操作后验证
  五类来源），每项含 `frame_id`/`run_id`/`step_id`/`vnc_session_id`/`capture_sequence`/
  `captured_at`/`content_hash`/`scope`/`mask_identity`/`deduplicated`/
  `duplicate_of_frame_id`/`comparison_available`/`changed_since_last`/`safe_image_path`/
  `safe_artifact_sha256`/`artifact_bundle_id`/`analysis_source_refs`。永不包含私有
  （`private_model`）物理路径。
- `stage_measurements[]`：追加式阶段测量（`capture`/`pixel_hash`/`persistence`/`OCR`/
  `template`/`vision`/`planner`/`grounder`/`verification`/`report_build`，可选
  `report_output`），保留 `completed`/`failed`/`cancelled`/`unavailable` 状态与
  `duration_ms` 为 `null` 的未开始阶段语义（不得补零）。
- `performance_summary`：去重、物理写入、缓存命中、模型调用等运行级汇总及守恒校验结果，
  定义见 `telemetry-contract.md`。
- `display_status`/`localized_message`：可选的 zh-CN 展示字段；机器 `status`/
  `failure_reason` 字段始终保留且权威，前者只是展示层增量，MUST NOT 被当作机器判定依据。

### 稳定英文枚举与命名

以上现有字段与新增字段中的所有机器可读枚举值（`status`、`verification_result.status`、
`deduplicated`、`stage_measurements[].status`、`performance_summary.completeness` 等）
继续使用稳定英文标识符；HTML 报告的中文本地化（feature 004 User Story 4）只影响展示层，
不改变这些机器枚举、JSON 键名或 CSS class/data-marker 命名。

### 禁止事项

- 报告生成 MUST NOT 创建、复制、硬链接或软链接任何证据文件副本（含 `report_frames/` 或其
  他报告目录）——`before_frame_path`/`after_frame_path`/`frames[].safe_image_path` 全部
  指向唯一的、内容寻址的已发布安全证据物理文件。
- 报告输出 MUST NOT 包含任何 `private_model` 用途的物理路径；`private_persistence_allowed
  =false` 的帧在报告中的私有证据字段恒为不可用/`null`，不得静默回退到其他帧或路径。
