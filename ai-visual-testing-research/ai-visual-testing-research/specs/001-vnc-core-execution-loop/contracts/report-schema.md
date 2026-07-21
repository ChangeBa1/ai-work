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
