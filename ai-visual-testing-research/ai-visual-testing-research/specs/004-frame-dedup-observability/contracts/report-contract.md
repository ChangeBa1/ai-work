# Contract: JSON Delta, Safe Evidence and zh-CN Presentation

**Feature**: [../spec.md](../spec.md) | **Base contract**: [Feature 001 report schema](../../001-vnc-core-execution-loop/contracts/report-schema.md)

## Backward compatibility rule

Feature 001/002/003 已有 JSON 顶层、steps、iterations 及其嵌套字段的英文键名、required/optional 关系、字段类型、machine enum、null/缺省语义、数组顺序、status 聚合规则与其他语义全部保持不变。消费者必须能够忽略 feature 004 新字段继续读取旧投影。旧 `before_frame_path`/`after_frame_path` 的契约语义仅是对应操作前/后可读取证据路径；基础 schema 未承诺 `report_frames` 目录、固定文件名或一条 iteration 一份副本，因此 feature 004 直接返回等价 safe physical path 不属于字段语义变更。

禁止：重命名旧键、本地化旧键或 enum、改变旧字段类型、把缺省改为 null 或把 null 改为缺省、改变数组顺序、删除旧字段、改变 status 聚合规则。两个旧路径字段允许从非契约性的报告副本字符串规范化为 safe physical path，但必须保持前后关联、可读取性和证据 physical identity/content hash 等价。

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

按 `capture_sequence` 排序，包含观察、等待、重试、恢复和操作后验证的所有成功逻辑帧。至少包含：

- `frame_id`, `run_id`, `step_id`, `vnc_session_id`
- `capture_sequence`, `captured_at`
- `content_hash`, `scope`, `mask_identity`
- `deduplicated`, `duplicate_of_frame_id`
- `comparison_available`, `changed_since_last`
- `safe_image_path`
- `safe_artifact_sha256`, `artifact_bundle_id`
- `analysis_source_refs`

不得输出 private model path。hash 优化失败允许 content_hash=null，并通过 optimization_errors/measurement 解释。

所有捕获调用方必须通过同一逻辑帧 recorder；兼容测试必须分别证明观察、稳定等待、重试、恢复和操作后验证帧进入该数组，不能只比较总数。失败采集尝试通过关联 measurement/counter/log 审计，不得伪造为 `frames[]` 元素。

### `stage_measurements[]`

遵循 [telemetry-contract.md](telemetry-contract.md)，保留 status 与 null duration 语义。

### `performance_summary`

遵循 [telemetry-contract.md](telemetry-contract.md) 的定义和守恒规则。

### Display fields

`display_status`/`localized_message` 是可选展示字段；machine `status`/`reason` 始终保留且权威。

## Safe evidence contract

- ReportBuilder 只接受 purpose=`safe_evidence` 的显式 PhysicalImageRef。
- resolved path 必须位于当前 run 的安全证据根，并来自有已提交逻辑引用的 published bundle；purpose、path、mask identity、byte_size、`artifact_sha256` 与 bundle manifest/逻辑帧必须匹配。
- resolver 必须读取实际文件 bytes，核对 byte size 与 SHA-256，并执行图片可解码性检查；`content_hash` 是遮罩前像素身份，禁止用于替代 safe 文件完整性校验。
- 多条逻辑证据引用同一 physical id 时，JSON/HTML 使用同一路径。
- 正常执行报告、离线重建、部分失败报告和兼容 CLI/旧入口必须装配同一 safe evidence resolver；任何路径都不得创建 `report_frames` 或其他报告证据副本，不得 copy/hardlink/symlink，也不得修改 ActionIteration/TestRun 中的既有路径或业务事实（仅允许追加规定的 `report_build` measurement）。
- private/越界/缺失/截断/损坏/byte-size mismatch/artifact-hash mismatch/不可解码/mask mismatch/orphan-bundle 证据标记为不可用并显示本地化警告，不得生成 HTML/JSON 可点击证据链接；原始审计引用可保留在受控机器字段，但 HTML 不得链接私有路径。
- 捕获策略禁止 private 持久化时，报告数据、原始审计引用和证据回退均不得包含 private_model 物理路径；model_image 为 null 不影响安全证据展示。
- HTML 使用相对安全链接；JSON 保持既有路径字段的“对应前/后安全证据”语义：`before_frame_path`/`after_frame_path` 由冻结 report view 解析为相应 safe physical path；新增 frame safe path 与其指向同一 physical identity。

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

静态 UI 标签、帮助、状态说明和错误说明必须来自资源包。可见英文/机器文本白名单仅限原始错误 code/detail、明确标识为机器值的 enum/data marker、模型/provider/产品标识及诊断必需的文件名/路径片段；白名单不得掩盖未翻译 UI。

展示 view-model 必须提供 machine value、display value 和稳定 css/data marker。Jinja 模板只取资源键与 display value，不包含 enum/error 翻译 if/映射。

## Error localization

- 已知 code：显示资源字典中文说明，同时显示原始 code/detail。
- 未知 code：显示通用中文说明，完整保留原始 code/detail，不猜测含义。
- JSON 原 `reason`/`failure_reason` 不修改；可新增 localized_message。
- 所有原始文本进入 HTML 前必须 autoescape。

## Encoding and rendering

- JSON/HTML/resource files 均为 UTF-8（BOM 策略必须一致且被读写器明确支持）。
- JSON `ensure_ascii=false`。
- HTML `<html lang="zh-CN">`、`<meta charset="utf-8">`。
- Jinja Environment 启用 HTML autoescape。
- 中文用例名、资源文本和原始错误详情落盘再读取后必须逐码点一致；U+FFFD、字符丢失和错误 HTML/JSON 转义分别判定失败。

## Shared report view

ReportBuilder 先组装基础 machine dict 与本地化草稿，结束并追加 `report_build` measurement 后仅执行该 measurement 的注入与不可变冻结；JSON renderer 直接消费唯一冻结 dict，HTML renderer 消费与其同源的冻结本地化 view-model。HTML 不得增加 JSON/事件源中不存在的事实。

## Compatibility tests

- 旧 JSON golden 对非路径旧字段做递归兼容投影，其存在/缺省、null、值、类型、enum、数组顺序和聚合结果必须相等；`before_frame_path`/`after_frame_path` 单独验证字段/类型/null、可读取性、safe purpose、前后关联及解析后的 physical id/content hash 等价，不要求旧 `report_frames` 文本值相等。
- 代表性 feature 001 旧消费者或旧 JSON Schema 在忽略未知新增字段后必须成功读取新报告，并得到与旧投影相同的业务结果。
- HTML 使用固定 run/time/path 完整快照和 DOM 可见文本扫描；除明确白名单外不得出现英文 UI，并单独检查资源覆盖、machine CSS/data marker、UTF-8 逐码点往返和 autoescape。
- 同一证据多次引用时路径相同；正常、离线、部分失败和兼容入口的报告目录均无新增 evidence PNG/link。
