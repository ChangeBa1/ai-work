# Contract: JSON Delta, Safe Evidence and zh-CN Presentation

**Feature**: [../spec.md](../spec.md) | **Base contract**: [Feature 001 report schema](../../001-vnc-core-execution-loop/contracts/report-schema.md)

## Backward compatibility rule

Feature 001/002/003 已有 JSON 顶层键、steps/iterations 字段、英文键名、字段类型、machine enum 与语义全部保持不变。消费者必须能够忽略 feature 004 新字段继续读取旧投影。

禁止：重命名旧键、本地化旧键或 enum、改变旧字段类型、删除旧字段、改变 status 聚合规则。

## Additive JSON fields

```json
{
  "frames": [],
  "stage_measurements": [],
  "performance_summary": {},
  "display_status": "通过",
  "localized_message": null
}
```

### `frames[]`

按 `capture_sequence` 排序，包含观察、等待、重试和验证的所有成功逻辑帧。至少包含：

- `frame_id`, `run_id`, `step_id`, `vnc_session_id`
- `capture_sequence`, `captured_at`
- `content_hash`, `scope`, `mask_identity`
- `deduplicated`, `duplicate_of_frame_id`
- `comparison_available`, `changed_since_last`
- `safe_image_path`
- `analysis_source_refs`

不得输出 private model path。hash 优化失败允许 content_hash=null，并通过 optimization_errors/measurement 解释。

所有捕获调用方必须通过同一逻辑帧 recorder；兼容测试必须分别证明观察、稳定等待、重试和操作后验证帧进入该数组，不能只比较总数。

### `stage_measurements[]`

遵循 [telemetry-contract.md](telemetry-contract.md)，保留 status 与 null duration 语义。

### `performance_summary`

遵循 [telemetry-contract.md](telemetry-contract.md) 的定义和守恒规则。

### Display fields

`display_status`/`localized_message` 是可选展示字段；machine `status`/`reason` 始终保留且权威。

## Safe evidence contract

- ReportBuilder 只接受 purpose=`safe_evidence` 的显式 PhysicalImageRef。
- resolved path 必须位于当前 run 的安全证据根，文件存在且 mask identity 与逻辑帧匹配。
- 多条逻辑证据引用同一 physical id 时，JSON/HTML 使用同一路径。
- 正常构建不得创建 `report_frames` 或修改 ActionIteration/TestRun 中的路径。
- private/越界/缺失/损坏/mask mismatch 证据标记为不可用并显示本地化警告；原始审计引用可保留在受控机器字段，但 HTML 不得链接私有路径。
- 捕获策略禁止 private 持久化时，报告数据、原始审计引用和证据回退均不得包含 private_model 物理路径；model_image 为 null 不影响安全证据展示。
- HTML 使用相对安全链接；JSON 保持既有路径字段语义，并新增 safe frame path。

## Locale configuration

```yaml
reporting:
  locale: zh-CN
```

- 默认且本 feature 唯一必需资源包为 `zh-CN`。
- 未登记 locale 在配置加载阶段失败，不静默 fallback。
- 未来语言通过完整资源包注册，不改变 machine enum 或 CSS class。
- execute 与离线 report 两条 CLI 装配路径都必须显式传递 locale。

## Resource registry contract

资源包至少覆盖：

- 报告标题、用例、状态、开始/结束时间；
- 步骤、迭代、验证结果、动作效果；
- 失败原因、恢复、证据、前置条件、动作审计；
- 性能摘要、阶段、缓存、模型调用、图片计数；
- 空值、不可用、证据异常、未知错误；
- 所有报告可见 status/action-effect/verification label；
- 已知稳定错误码。

展示 view-model 必须提供 machine value、display value 和稳定 css/data marker。Jinja 模板只取资源键与 display value，不包含 enum/error 翻译 if/映射。

## Error localization

- 已知 code：显示资源字典中文说明，同时显示原始 code/detail。
- 未知 code：显示通用中文说明，完整保留原始 code/detail，不猜测含义。
- JSON 原 `reason`/`failure_reason` 不修改；可新增 localized_message。
- 所有原始文本进入 HTML 前必须 autoescape。

## Encoding and rendering

- JSON/HTML/resource files 均为 UTF-8。
- JSON `ensure_ascii=false`。
- HTML `<html lang="zh-CN">`、`<meta charset="utf-8">`。
- Jinja Environment 启用 HTML autoescape。
- 中文用例名和错误详情不得包含 U+FFFD 或乱码。

## Shared report view

ReportBuilder 先组装基础 machine dict 与本地化草稿，结束并追加 `report_build` measurement 后仅执行该 measurement 的注入与不可变冻结；JSON renderer 直接消费唯一冻结 dict，HTML renderer 消费与其同源的冻结本地化 view-model。HTML 不得增加 JSON/事件源中不存在的事实。

## Compatibility tests

- 旧 JSON golden 做递归兼容投影，所有旧字段值/类型/enum 必须相等。
- HTML 使用固定 run/time/path 完整快照，并单独检查资源覆盖、machine CSS/data marker、UTF-8 和 autoescape。
- 同一证据多次引用时路径相同，报告目录无新增 evidence PNG。
