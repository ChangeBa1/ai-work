# Contract: `ui-analysis-bundle-v1`（外部 UI Analysis Bundle 交换格式）

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

本契约是**索引生产方**（外部项目）与**索引消费方**（vnc-agent）之间唯一的交换格式定义。生产方
按本契约生成文件，消费方按本契约校验/读取；双方不需要共享任何代码、进程或运行时。本契约与
`.agents/skills/generate-ui-analysis-index/references/bundle-contract.md`（供生产方阅读的
skill 版本）内容 MUST 保持一致——后者是面向生产方的说明文档，本文件是权威版本，`tasks.md`
安排一致性检查任务。

对应 spec.md FR-001~029、FR-020~029、Key Entities、Clarifications 全部条款。

## 0. Schema 版本

当前版本：`1.0`（`schema_version` 字段值为字符串 `"1.0"`）。版本号遵循
`"{MAJOR}.{MINOR}"`：

- 消费方 MUST 拒绝 `MAJOR` 不在受支持集合内的 bundle（当前受支持集合 = `{1}`），错误码
  `schema_unsupported_major`。
- 同一受支持 `MAJOR` 内，消费方 MUST 兼容读取任意 `MINOR`：已知字段正常校验，**未知字段
  MUST 被保留**（不丢弃、不报错、不参与任何校验逻辑）。生产方新增可选字段不需要等待消费方
  升级即可安全交付。

## 1. 目录结构

```text
<bundle_dir>/
├── manifest.yaml         # 必需
├── screens.jsonl         # 必需
├── elements.jsonl        # 必需
├── transitions.jsonl     # 必需
├── flows.jsonl           # 可选
└── diagnostics.jsonl     # 可选
```

- 文件名 MUST 与上表完全一致（大小写敏感），不允许改名或额外的顶层文件影响校验（额外文件被
  忽略，不报错，除非其路径违反 §1.1 的路径穿越规则）。
- `.jsonl` 文件 MUST 是 UTF-8 编码、每行一个独立 JSON 对象（"JSON Lines"）；整份文件是单一
  JSON 数组、或任意一行不是合法 JSON 对象，均视为 `jsonl_syntax_error`，消费方报告首个不合法
  行的行号后继续扫描其余行以汇总全部问题。
- `manifest.yaml` MUST 是合法 YAML，顶层为一个映射（mapping）。

### 1.1 路径穿越

`manifest.content_files` 的 key 与实际磁盘上的文件名 MUST 是不含路径分隔符、不含 `..`、不是
绝对路径的纯文件名；消费方在解析 `content_files` 后、实际打开文件前 MUST 校验每个 key 解析后
的绝对路径仍位于 `<bundle_dir>` 内部，违反时报告 `path_traversal`，不打开该路径指向的任何
文件。

## 2. `manifest.yaml`

```yaml
schema_version: "1.0"
bundle_id: "b7e4f6a2-..."
project_id: "acme-checkout-webapp"
generated_at: "2026-07-25T09:00:00Z"
producer:
  name: "acme-ui-analyzer"
  version: "0.3.1"
source_revision: "git:4f9c1a2"
frameworks: ["react", "typescript"]
coordinate_spaces: ["normalized_1000"]
default_viewports:
  - name: "desktop"
    width: 1920
    height: 1080
content_files:
  manifest.yaml: {required: true, sha256: null, record_count: null}
  screens.jsonl: {required: true, sha256: "3b1e...", record_count: 12}
  elements.jsonl: {required: true, sha256: "9fa0...", record_count: 87}
  transitions.jsonl: {required: true, sha256: "1cd4...", record_count: 20}
  flows.jsonl: {required: false, sha256: "7e21...", record_count: 3}
  diagnostics.jsonl: {required: false, sha256: null, record_count: null}
metadata: {}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `schema_version` | string | 是 | 匹配 `^\d+\.\d+$`；MAJOR 不受支持 → `schema_unsupported_major` |
| `bundle_id` | string | 是 | 非空 |
| `project_id` | string | 是 | 非空 |
| `generated_at` | string（ISO 8601） | 是 | 可解析为日期时间 |
| `producer.name` | string | 是 | 非空 |
| `producer.version` | string | 是 | 非空 |
| `source_revision` | string | 是 | 非空 |
| `frameworks` | list[string] | 是（可为空数组） | 仅描述性，消费方不据此分支 |
| `coordinate_spaces` | list[string] | 是（至少 1 项） | 每项 MUST ∈ `{"design_pixels", "normalized_1000"}` |
| `default_viewports` | list[object] | 否 | 每项 `{name, width>0, height>0}` |
| `content_files` | map[string → object] | 是 | 见下 |
| `content_files.<name>.required` | boolean | 是 | `screens.jsonl`/`elements.jsonl`/`transitions.jsonl`/`manifest.yaml` 对应条目 MUST 为 `true`；`flows.jsonl`/`diagnostics.jsonl` MUST 为 `false` 或缺省 |
| `content_files.<name>.sha256` | string \| null | 否 | 提供时，消费方 MUST 用实际文件内容重新计算 sha256 比对；不一致 → `checksum_mismatch`。省略/`null` 时跳过该文件的校验和检测（但仍执行其余全部校验，checksum 不是唯一的完整性检测手段——语法/引用/唯一性校验独立生效） |
| `content_files.<name>.record_count` | int \| null | 否 | 提供时仅作为诊断信息展示，不强制与实际行数一致（避免生产方增量写入场景产生误报） |
| `metadata` | map \| null | 否 | 自由扩展，透传 |

- 缺失 `manifest.yaml` 本身 → `manifest_missing`（无 `content_files` 条目可参考，file/line 均为
  `null`）。
- `content_files` 中标记 `required: true` 的文件在磁盘上不存在 → `content_file_missing`。
- 目录本身不存在或不可读（与"目录存在但内容无效"是两个独立错误类别）→
  `bundle_dir_not_found`。

## 3. `screens.jsonl`

```json
{"screen_id": "screen.checkout", "name": "Checkout", "screen_type": "page", "visible_titles": ["结账", "Checkout"], "aliases": ["支付页"], "parent_screen_id": null, "confidence": {"level": "confirmed", "score": 0.95}}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `screen_id` | string，`^[A-Za-z0-9_.:-]{1,128}$` | 是 | bundle 内唯一，重复 → `duplicate_id` |
| `name` | string | 是 | |
| `screen_type` | string，`^[a-z][a-z0-9_]*$` | 是 | 开放词表，仅格式校验 |
| `visible_titles` | list[string] | 是（可空） | |
| `aliases` | list[string] | 是（可空） | |
| `parent_screen_id` | string \| null | 否 | 非空时 MUST 引用已存在 `screen_id`（悬空 → `dangling_reference`），MUST NOT 等于自身 `screen_id`、MUST NOT 与其他 screen 形成 parent 环（→ `dangling_reference` 复用同一错误码，`field_path` 指出成环路径） |
| `source_evidence` | string \| null | 否 | 仅离线溯源，消费方 MUST NOT 默认发送给模型 |
| `confidence` | Confidence 对象 | 是 | 见 §6 |
| `metadata` | map \| null | 否 | |

## 4. `elements.jsonl`

```json
{"element_id": "el.checkout.submit_btn", "screen_id": "screen.checkout", "parent_element_id": null, "name": "Submit", "role": "button", "visible_texts": ["提交", "Submit"], "aliases": [], "supported_actions": ["click"], "state_conditions": {"enabled_when": "cart_non_empty"}, "region": "footer", "normalized_bounds": {"coordinate_space": "normalized_1000", "x1": 620, "y1": 900, "x2": 780, "y2": 960}, "anchors": [], "neighbors": [{"direction": "left", "element_id": "el.checkout.cancel_btn"}], "expected_effects": ["导航到订单确认页"], "confidence": {"level": "visually_confirmed", "score": 0.8}}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `element_id` | string，同 screen_id 格式 | 是 | bundle 内唯一 |
| `screen_id` | string | 是 | 引用已存在 screen，悬空 → `dangling_reference` |
| `parent_element_id` | string \| null | 否 | 悬空/自引用/成环 → `dangling_reference` / `parent_cycle` |
| `name` | string | 是 | |
| `role` | string，`^[a-z][a-z0-9_]*$` | 是 | 开放词表 |
| `visible_texts` | list[string] | 是（可空） | |
| `aliases` | list[string] | 是（可空） | |
| `supported_actions` | list[string]，每项 `^[a-z][a-z0-9_]*$` | 是（可空） | 开放词表 |
| `state_conditions` | object | 否，默认 `{}` | 透传，消费方不解释内部结构 |
| `region` | string枚举 | 是，默认 `"unknown"` | `header\|toolbar\|sidebar_left\|sidebar_right\|body\|footer\|statusbar\|modal\|unknown` |
| `normalized_bounds` | object \| null | 否 | 存在时：`coordinate_space` MUST 为 `"normalized_1000"`（缺失该字段 → `missing_coordinate_space`）；`x1,y1,x2,y2 ∈ [0,1000]` 整数（越界 → `coordinate_out_of_range`）；`x1<x2 且 y1<y2`（不满足 → `coordinate_out_of_range`） |
| `anchors` | list[string] | 否，默认 `[]` | 每项引用已存在 element，悬空 → `dangling_reference` |
| `neighbors` | list[object] | 否，默认 `[]` | 每项 `{direction ∈ {up,down,left,right,near}, element_id}`；`element_id` 悬空 → `dangling_reference` |
| `expected_effects` | list[string] | 否，默认 `[]` | 自由文本，仅 Verifier 参考 |
| `source_evidence` | string \| null | 否 | 仅离线溯源 |
| `confidence` | Confidence 对象 | 是 | |
| `metadata` | map \| null | 否 | |

**`normalized_bounds` 的运行时约束（消费方强制，非 wire-format 校验，写在此处便于生产方
理解用途）**：只能作为 Grounder 候选区域的**先验**参与融合排序，消费方 MUST NOT 将其数值
直接作为最终点击坐标下发执行。

## 5. `transitions.jsonl`

```json
{"transition_id": "tr.checkout.submit", "from_screen_id": "screen.checkout", "trigger_element_id": "el.checkout.submit_btn", "trigger_action": "click", "guards": [{"element_id": "el.checkout.submit_btn", "condition": "enabled"}], "to_screen_id": "screen.order_confirmed", "transition_type": "replace", "expected_visible": ["订单号"], "expected_hidden": ["结账表单"], "expected_state_changes": [], "confidence": {"level": "confirmed", "score": 0.9}}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `transition_id` | string | 是 | bundle 内唯一 |
| `from_screen_id` | string | 是 | 引用已存在 screen，悬空 → `dangling_reference` |
| `trigger_element_id` | string | 是 | 引用已存在 element，悬空 → `dangling_reference` |
| `trigger_action` | string，`^[a-z][a-z0-9_]*$` | 是 | 开放词表 |
| `guards` | list[object] | 否，默认 `[]` | 每项二选一：`{element_id, condition ∈ {visible,enabled,hidden,disabled}}`（`element_id` 悬空 → `dangling_guard_reference`）或 `{name, description?}`（仅本记录内联有效，不跨记录共享） |
| `to_screen_id` | string | 是 | 引用已存在 screen，悬空 → `dangling_reference` |
| `transition_type` | string枚举 | 是 | `modal\|replace\|overlay\|state_change`，封闭枚举 |
| `expected_visible` | list[string] | 否，默认 `[]` | 仅 Verifier 参考线索 |
| `expected_hidden` | list[string] | 否，默认 `[]` | 同上 |
| `expected_state_changes` | list[string] | 否，默认 `[]` | 同上 |
| `source_evidence` | string \| null | 否 | 仅离线溯源 |
| `confidence` | Confidence 对象 | 是 | |

## 6. `flows.jsonl`（可选）

```json
{"flow_id": "flow.checkout_to_confirmation", "name": "结账完成流程", "start_screen_id": "screen.checkout", "steps": [{"transition_id": "tr.checkout.submit"}], "completion_screen_id": "screen.order_confirmed", "preconditions": [], "confidence": {"level": "statically_inferred", "score": 0.6}}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `flow_id` | string | 是 | bundle 内唯一 |
| `name` | string | 是 | |
| `start_screen_id` | string | 是 | 引用已存在 screen，悬空 → `dangling_reference` |
| `steps` | list[object]，**有序** | 是（至少 1 项） | 每项二选一：`{transition_id}`（悬空 → `dangling_reference`）或 `{element_id, action}`（`element_id` 悬空 → `dangling_reference`） |
| `completion_screen_id` | string | 是 | 引用已存在 screen，悬空 → `dangling_reference` |
| `preconditions` | list[object] | 否，默认 `[]` | 复用 §5 `guards` 判别联合规则 |
| `confidence` | Confidence 对象 | 是 | |

## 7. `diagnostics.jsonl`（可选）

```json
{"diagnostic_id": "diag.001", "category": "uncertain_transition", "target_ref": {"transition_id": "tr.checkout.submit"}, "reason": "guard 条件仅通过静态分析推断，未真实运行验证", "confidence": {"level": "requires_runtime_verification", "score": null}}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `diagnostic_id` | string | 是 | bundle 内唯一 |
| `category` | string枚举 | 是 | `unconfirmed_screen\|unconfirmed_element\|dynamic_element\|uncertain_transition\|unparsed_text\|requires_runtime_calibration` |
| `target_ref` | object \| null | 否 | 非空字段（`screen_id`/`element_id`/`transition_id` 中出现的）MUST 引用已存在记录，悬空 → `dangling_reference` |
| `reason` | string | 是 | 非空 |
| `confidence` | Confidence 对象 | 是 | `level == "confirmed"` → `invalid_diagnostic_confidence`（诊断项按定义不可标记为已确认） |
| `source_evidence` | string \| null | 否 | |

## 8. `Confidence` 对象（跨文件共享，Screen/Element/Transition/Flow/Diagnostic 均引用本节）

```json
{"level": "confirmed", "score": 0.92}
```

| 字段 | 类型 | 必填 | 校验规则 |
|---|---|---|---|
| `level` | string枚举 | 是 | `confirmed \| statically_inferred \| visually_confirmed \| requires_runtime_verification`；不在此集合 → `invalid_confidence` |
| `score` | number \| null | 否 | 提供时 MUST ∈ `[0.0, 1.0]`，越界 → `invalid_confidence` |

**四类语义**（供生产方标注参考，来自 spec.md Clarifications）：

- `confirmed`：已通过真实运行观察确认（例如生产方对被测应用做过真实交互验证）。
- `statically_inferred`：仅通过源码/设计资料静态分析得出，未做任何运行时或视觉验证。
- `visually_confirmed`：通过截图/设计稿等视觉资料确认存在，但未验证交互行为。
- `requires_runtime_verification`：生产方明确认为该项需要消费方/使用者在真实环境中校准，
  不得被当作可直接信任的事实。

生产方 MUST NOT 将 `statically_inferred`/`visually_confirmed`/
`requires_runtime_verification` 的数据标注为 `confirmed`（spec.md FR-026）。

## 9. 错误码总表

| error_code | 触发条件 |
|---|---|
| `bundle_dir_not_found` | 配置目录不存在或不可读 |
| `schema_unsupported_major` | `manifest.schema_version` 的 MAJOR 不在受支持集合 |
| `manifest_missing` | `manifest.yaml` 不存在 |
| `content_file_missing` | `content_files` 标记 `required: true` 的文件在磁盘上缺失 |
| `jsonl_syntax_error` | `.jsonl` 文件某行不是合法 JSON 对象，或整份文件是单一 JSON 数组 |
| `field_type_error` | 字段值类型与本契约不符 |
| `duplicate_id` | 同一 ID 命名空间（screen_id/element_id/transition_id/flow_id/diagnostic_id 各自独立）内出现重复值 |
| `dangling_reference` | 引用了不存在的 screen/element/transition，或 parent 引用自引用/成环 |
| `parent_cycle` | element parent 链形成循环（不含直接自引用，直接自引用同样归入本码或 `dangling_reference`，消费方实现二选一但需在实现内保持一致） |
| `dangling_guard_reference` | `guards`/`preconditions` 中 element 引用型变体的 `element_id` 不存在 |
| `missing_coordinate_space` | `normalized_bounds` 存在但未声明合法 `coordinate_space` |
| `coordinate_out_of_range` | 坐标数值越界，或 `x1>=x2`/`y1>=y2` |
| `invalid_confidence` | `confidence.level` 不在四类枚举，或 `score` 越界 |
| `invalid_diagnostic_confidence` | `Diagnostic.confidence.level == "confirmed"` |
| `path_traversal` | `content_files` 的 key 解析后逃逸 bundle 根目录 |
| `resource_limit_exceeded` | 单文件/bundle 总体超出消费方配置的资源上限 |
| `checksum_mismatch` | `content_files.<name>.sha256` 提供且与实际内容不符 |

`ValidationIssue`（消费方内部表示，见 [../data-model.md](../data-model.md) §2）的
`error_code` 取值即上表，`file`/`line`/`field_path` 尽最大努力填充，`message` 为人类可读文本。
