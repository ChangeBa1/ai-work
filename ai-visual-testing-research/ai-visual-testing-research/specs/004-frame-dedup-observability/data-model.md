# Data Model: 截图去重、分析复用、性能可观测性与中文报告

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## 1. CaptureScope

表示一次截图的严格空间与安全边界，参与去重和缓存身份。

| Field | Type | Required | Rules |
|---|---|---:|---|
| `capture_kind` | enum(`full_screen`,`roi`) | yes | full-screen 与等尺寸 ROI 仍是不同范围 |
| `x`,`y` | integer | yes | full-screen 固定为 0；ROI 为全局左上角 |
| `width`,`height` | positive integer | yes | 必须与规范化像素 shape 一致 |
| `resolution` | tuple[int,int] | yes | 实际捕获分辨率 |
| `pixel_format` | string | yes | 由 dtype/channel order 规范化产生；格式不同不得去重 |
| `mask_identity` | string | yes | 配置版本与规范化全局 mask rectangles 的 SHA-256 |
| `private_persistence_allowed` | boolean | yes | false 时未遮罩像素只能短暂驻留内存，不得创建或复用 private_model 文件 |

`scope_identity` 是以上字段的稳定 canonical serialization hash，不包含 step id 或 timestamp。

## 2. DecodedCapture（内部瞬态）

一次 VNC capture 在内存中的临时工作对象，不进入 JSON/SQLite。

| Field | Type | Lifecycle |
|---|---|---|
| `raw_png` | bytes | 捕获后存在；唯一帧持久化完成或重复判定结束即释放 |
| `pixels` | read-only C-contiguous ndarray | 唯一解码结果；当前分析与严格比较共享 |
| `pixel_format` | string | 与 pixels 一致 |
| `content_hash` | string or null | 规范化像素载荷的 SHA-256；hash 优化失败时 null |
| `scope` | CaptureScope | 当前范围 |
| `captured_at` | UTC datetime | driver 返回后立即记录 |

**Invariant**: 组件缓存不得保存 `raw_png`；窗口逐出后不得保留无其他用途的 `pixels` 引用。

**Canonical hash preimage**: “规范化像素载荷”唯一指 `frame-pixels-v1 || width || height || canonical pixel_format || C-contiguous unmasked normalized pixel bytes`；width/height 使用固定宽度编码，pixel format 使用长度前缀。完整 `scope_identity` 仍是独立去重/缓存维度；除载荷中的 width/height/pixel format 外，capture kind、坐标、resolution、mask identity 与 `private_persistence_allowed` 不属于 `content_hash` 前像。hash 只筛选候选，严格相等仍由 ndarray shape/dtype 与 `array_equal` 决定。

## 3. PhysicalImageRef

一个实际成功持久化的截图文件。

| Field | Type | Required | Rules |
|---|---|---:|---|
| `physical_image_id` | UUID/string | yes | 文件审计身份 |
| `owner_frame_id` | UUID/string | yes | 首次创建该文件的唯一逻辑帧 |
| `artifact_bundle_id` | UUID/string | yes | safe/private 成组发布事务身份；同一 unique frame 的文件共享该值 |
| `purpose` | enum(`safe_evidence`,`private_model`,`report_copy`) | yes | 常规报告不得创建 report_copy |
| `path` | string | yes | 规范化绝对路径；报告只允许 safe_evidence |
| `byte_size` | non-negative integer | yes | 来自成功写入文件实际大小 |
| `artifact_sha256` | string | yes | 对最终编码文件精确 bytes 计算；报告完整性校验使用，独立于 content_hash |
| `content_hash` | string or null | yes | 与 owner frame 一致；优化失败可为 null |
| `mask_identity` | string | yes | safe_evidence 必须与逻辑帧一致 |
| `created_at` | UTC datetime | yes | 成功原子提交时刻 |

**Relationship**: 一个唯一 `ScreenFrame` 对应一个 safe PhysicalImageRef，并在策略允许时对应第二个 private PhysicalImageRef；它们由同一 `artifact_bundle_id` 的 manifest 成组发布。多个连续重复 ScreenFrame 只能引用当前策略允许的同一组 PhysicalImageRef。

### FrameArtifactBundle（磁盘事务单元）

bundle 位于当前 run artifact 根内，staging 与 final 目录必须处于同一文件系统。staging manifest 至少包含 `artifact_bundle_id`、`run_id`、`owner_frame_id`、预期 purpose 集合，以及每个文件的相对路径、`byte_size`、`artifact_sha256` 和 mask identity。状态转换为：

```text
STAGING --files+manifest synced--> READY --single directory rename--> PUBLISHED
PUBLISHED --ScreenFrame committed--> REFERENCED
STAGING failure --> REMOVED
PUBLISHED + logical commit failure/crash --> QUARANTINED
```

final bundle 在目录 rename 前不得可见；不得通过逐个 final-file replace 模拟成组原子提交。run 启动/恢复时必须删除残留 staging，并以 manifest 与 `TestRun.frames`/PhysicalImageRef 对账，把无逻辑引用的 published bundle 整体移入 run 内非报告隔离区并记录 recovery audit。报告 resolver 只接受 `REFERENCED` bundle 中与 manifest 一致的 safe evidence。

## 4. ScreenFrame（逻辑帧）

每次成功采集恰好创建一条，不等同于物理文件。

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | UUID/string | yes | 每个逻辑采样唯一 |
| `run_id` | string | yes | 不得跨 run 复用 |
| `vnc_session_id` | string | yes | connect/reconnect 生成；不得跨 session 复用 |
| `step_id` | string or null | yes | 稳定等待等运行级采样允许 null |
| `capture_sequence` | integer | yes | run 内严格递增，JSON frames 以此排序 |
| `capture_source` | enum(`observation`,`stability_wait`,`retry`,`recovery`,`post_action_verification`) | yes | 允许按来源重建完整采集轨迹；不表达业务语义 |
| `timestamp` | UTC datetime | yes | 每次捕获独立，即使物理去重 |
| `scope` | CaptureScope | yes | 去重边界 |
| `content_hash` | string or null | yes | 上述遮罩前规范化像素载荷 SHA-256；hash 失败为 null |
| `deduplicated` | boolean | yes | 只有完整边界、hash 与逐像素均通过才为 true |
| `duplicate_of_frame_id` | string or null | yes | duplicate 时指向直接上一逻辑帧；unique 时必须 null |
| `comparison_available` | boolean | yes | 首帧或优化失败为 false |
| `changed_since_last` | boolean or null | yes | duplicate=false；首帧/不可比较=null；严格不同=true |
| `safe_image` | PhysicalImageRef | yes | 报告唯一可用图片 |
| `model_image` | PhysicalImageRef or null | yes | 可与 safe_image 相同；禁止 private 持久化且模型使用未遮罩内存像素时为 null |
| `optimization_errors` | list[OptimizationError] | yes | 默认为空，不改变成功持久化语义 |

### Validation invariants

- `deduplicated=true` ⇒ `duplicate_of_frame_id != null`、`content_hash != null`、`changed_since_last=false`。
- `deduplicated=false` ⇒ `duplicate_of_frame_id=null`。
- duplicate 与 source 必须同 run/session、capture sequence 相邻、scope 完全相同、content hash 相同，并由逐像素确认。
- duplicate 的 safe path/physical id 与 source 相同；model_image 仅在双方策略都允许且 source 存在该引用时复用，但 frame id/timestamp/step id/sequence 必须独立。
- safe_image purpose 永远是 `safe_evidence`；model_image 只能为 null、safe_evidence 或 private_model。`scope.private_persistence_allowed=false` ⇒ model_image 不得为 private_model。
- 每个 PhysicalImageRef 的 path、purpose、byte_size、artifact_sha256 与 artifact_bundle_id 必须和已发布 manifest 一致；`content_hash` 不得替代 artifact_sha256。
- 物理持久化未完整成功时不得创建成功 ScreenFrame。
- 每个成功 ScreenFrame 在返回 Pipeline、StabilityEngine、重试或验证调用方前，必须由唯一 recorder 追加到 `TestRun.frames`。
- 唯一帧提交顺序固定为 physical artifacts committed → immutable ScreenFrame recorded → response returned；duplicate 为 refs validated → immutable ScreenFrame recorded → response returned。

## 5. AnalysisCacheKey

组件级纯分析身份。

| Field | Type | Required | Notes |
|---|---|---:|---|
| `component` | enum(`ocr`,`template`,`diff`,`vision_describe`) | yes | 独立缓存与计数 |
| `algorithm_revision` | string | yes | 代码/输出 schema 变化时递增 |
| `content_hash` | string | yes | hash 失败不得缓存 |
| `scope_identity` | string | yes | 阻止跨 ROI/full-screen |
| `pixel_format` | string | yes | 格式隔离 |
| `mask_identity` | string | yes | 安全/感知配置隔离 |
| `perception_config_fingerprint` | string | yes | 组件启用、阈值、预处理等 canonical hash |
| `component_identity` | object | yes | 组件专属身份，见下表 |

| Component | Additional identity |
|---|---|
| OCR | backend、版本、语言与 preprocessing fingerprint |
| template | matcher revision、thresholds、模板集合内容 fingerprint |
| diff | previous/current frame identity、threshold、dynamic mask、min blob pixels |
| vision_describe | provider、requested model/version、mode、prompt/schema revision、structured hint fingerprint |

Planner/Grounder/Verifier 或验证问题回答不属于此 key 枚举；本 feature 不为它们建立内容缓存。

**Lookup eligibility**: `AnalysisCacheKey` 仅在当前 `ScreenFrame.deduplicated=true`、`duplicate_of_frame_id` 为直接上一逻辑帧且 source entry 来自该帧时参与 lookup。最近窗口中的 A→B→A 不具备资格，即使 key 其他字段相同也必须 miss。

## 6. AnalysisCacheEntry

| Field | Type | Rules |
|---|---|---|
| `key` | AnalysisCacheKey | 唯一身份 |
| `result` | OCR/template/diff/vision pure result | 不含逻辑 frame id/time/path |
| `source_frame_id` | string | 首次实际分析帧 |
| `created_sequence` | integer | 窗口生命周期依据 |
| `referencing_sequences` | bounded deque[integer] | 最近逻辑帧对该结果的轻量引用；duplicate hit 追加当前 sequence，不是任意访问 LRU |
| `actual_invocation_id` | string | 指向实际分析/模型事件 |

**Eviction**: 只保留配置的最近 3～5 个逻辑 frame window 所引用条目；连续 duplicate 每次都把当前 sequence 加入 `referencing_sequences`，因此源分析可服务超过 5 个连续 duplicate。非相邻 unique 终止连续引用链；任意 cache get 不得刷新窗口。

## 6A. ContextSensitiveIdentity

上下文敏感角色不进入 `AnalysisCacheKey`。确定性路由使用稳定 canonical serialization 生成 `request_identity` 与 `context_identity`；以下字段是完整性门禁，而非业务固定字段：

| Role | Required identity fields |
|---|---|
| Planner | normalized request semantics、step intent、action/history state、retry/iteration state、current StructuredScreen identity、requested model/version/config、relevant deterministic route state |
| Grounder | target semantics、candidate-set/current StructuredScreen identity、capture scope/coordinate-transform identity、requested model/version/config、retry/grounding state |
| Verifier | visual question/assertion、before/after frame identities、action audit/ActionEffect context、retry/iteration state、requested model/version/config |

任一必需字段缺失、不可规范化或变化时，`same_context=false`，不得复用结果或以同一身份记录 skip；若确定性路由判定该角色当前适用，则必须实际调用。上下文变化不强制调用本来不适用的角色，但每个操作后的 Verifier 始终适用并实际执行。

## 7. StructuredScreen

保留现有字段，并添加 `content_hash`、`deduplicated`、`duplicate_of_frame_id`、`comparison_available` 与每组件 `analysis_source_refs`。每次逻辑帧重新实例化：

- frame identity/time/path 来自当前 ScreenFrame；
- OCR/template/diff/vision 值来自实际执行或 AnalysisCacheEntry；
- duplicate 的 diff 结果为 `changed_since_last=false`、ratio=0、regions/blobs 为空；
- 缓存值不得覆盖当前 frame identity/time/path。

## 8. OptimizationError

| Field | Type | Rules |
|---|---|---|
| `stage` | enum(`decode`,`pixel_hash`,`pixel_compare`,`cache_get`,`cache_put`) | 仅优化/规范化阶段 |
| `error_type` | string | 脱敏后的稳定类别 |
| `message` | string | 经日志敏感过滤；不得包含图片 bytes |
| `occurred_at` | UTC datetime | 必填 |
| `fallback` | enum(`unique_full_analysis`,`cache_miss_full_analysis`,`capture_failed`) | 明确实际行为 |

## 9. StageMeasurement

每次阶段执行追加一条。

| Field | Type | Required | Rules |
|---|---|---:|---|
| `measurement_id` | UUID/string | yes | 唯一 |
| `run_id` | string | yes | 关联运行 |
| `step_id` | string or null | yes | 可空 |
| `frame_id` | string or null | yes | 可空 |
| `iteration_index` | integer or null | yes | 可空 |
| `stage` | stable enum | yes | capture/pixel_hash/persistence/OCR/template/vision/planner/grounder/verification/report_build；可追加 report_output |
| `started_at` | UTC datetime | yes | 展示/审计时间 |
| `duration_ms` | non-negative number or null | yes | monotonic 计算；unavailable 为 null |
| `status` | enum(`completed`,`failed`,`cancelled`,`unavailable`) | yes | 不得用 completed 伪装异常 |
| `actual_call` | boolean | yes | provider/分析是否真实进入边界 |
| `cache_hit` | boolean | yes | 与 actual_call 互斥 |
| `source_ref` | string or null | yes | cache hit 指向源分析 |
| `error_type`,`error_message` | string or null | yes | 脱敏；成功时 null |

`report_output` 失败也使用本模型：`status=failed`、保留实际 `duration_ms` 与错误；不得产生成功 report path。规定但未开始的输出为 `unavailable/null`，不能补零。

## 10. CounterEvent

不可变计数事实，`PerformanceSummary` 只能从这些事件与 frames 推导。

| `kind` | Required fields |
|---|---|
| `analysis_cache_hit` | component、frame_id、source_ref |
| `analysis_invocation` | component、invocation_id、status |
| `model_call` | model_role、invocation_id、status |
| `model_call_skipped` | model_role、reason、request_identity |
| `physical_image_written` | PhysicalImageRef |
| `physical_write_avoided` | frame_id、purpose、source physical id、actual byte basis |
| `frame_dedup_decision` | frame_id、eligible、deduplicated、reason |
| `capture_attempt_failed` | run_id、step_id、capture_source、attempt_sequence、occurred_at、error_type、measurement_id、state/retry/recovery ref |

OCR/template 是 analysis invocation；vision/planner/grounder/verification provider 请求才是 model call。

### ModelCallAudit

每次上下文敏感实际调用或确定性 skip 都保留一条脱敏审计记录：`audit_id`、`run_id`、`step_id`、`frame_id`、`iteration_index`、`model_role`、`request_identity`、`context_identity`、`sanitized_request`、`sanitized_response`、`outcome`（actual/skipped）、`source_ref` 与 `reason`。actual 必须关联 `model_call` 事件；skipped 必须关联 `model_call_skipped` 事件。图片 bytes、凭据和未遮罩路径不得进入该记录。

## 11. PerformanceSummary

| Field | Type | Derivation |
|---|---|---|
| `total_capture_count` | int | 成功 ScreenFrame 数 |
| `unique_frame_count` | int | deduplicated=false |
| `duplicate_frame_count` | int | deduplicated=true |
| `dedup_ratio` | float or null | duplicate/total；total=0 时 null |
| `physical_image_count` | int | 与成功逻辑帧同一 TestRun 更新提交、且属于 referenced bundle 的 physical_image_written 事件数；staging/quarantined/orphan 不计 |
| `physical_images_by_purpose` | map[str,int] | safe/private/report 分类 |
| `avoided_write_count` | int | physical_write_avoided 事件数 |
| `avoided_write_bytes` | int | 事件实际 byte basis 求和 |
| `cache_hits` | map[component,int] | OCR/template/vision 必有键；diff 可追加 |
| `analysis_invocations` | map[component,int] | 实际分析边界 |
| `model_calls` | map[role,int] | vision/planner/grounder/verification |
| `actual_model_call_count` | int | model_calls 求和 |
| `skipped_model_call_count` | int | model_call_skipped 事件数 |
| `stage_totals_ms` | map[stage,number/null] | 仅汇总真实 measurements |
| `completeness` | enum(`complete`,`partial`) | 任一规定阶段 unavailable/failed 可为 partial |
| `consistency_errors` | list[string] | 守恒失败时记录，不自动修正 |

**Conservation**: `unique_frame_count + duplicate_frame_count == total_capture_count`。正常执行、离线重建、部分失败和兼容入口的报告构建均要求 `physical_images_by_purpose.report_copy == 0`。

## 12. TestRun additive fields

在 `domain/run.py` 的 `TestRun` 追加：

- `frames: list[ScreenFrame] = []`
- `stage_measurements: list[StageMeasurement] = []`
- `counter_events: list[CounterEvent] = []`（内部/持久化；JSON 可只暴露规范化明细）
- `model_call_audits: list[ModelCallAudit] = []`
- `performance_summary: PerformanceSummary | null`

现有字段、枚举与 StepRecord/ActionIteration 结构不变。Repository 继续使用 JSON payload，无数据库 schema 迁移。

## 13. Capture state transitions

```text
CAPTURED_BYTES
  ├─ decode/normalization failure ──> CAPTURE_FAILED
  └─ NORMALIZED
       ├─ hash/compare optimization failure ──> UNIQUE_FALLBACK
       └─ SCOPE_CHECK ──> HASH_CHECK ──> PIXEL_EQUAL_CHECK
                                             ├─ true  ──> DUPLICATE_REUSE
                                             └─ false ──> UNIQUE_PERSIST

UNIQUE_FALLBACK ──> BUNDLE_STAGING [safe + optional private + manifest]
BUNDLE_STAGING ──> BUNDLE_PUBLISHED [single same-filesystem directory rename]
BUNDLE_PUBLISHED ──> LOGICAL_FRAME_RECORDED ──> ANALYZE/ASSEMBLE ──> RELEASE/ENQUEUE
DUPLICATE_REUSE ──> LOGICAL_FRAME_RECORDED ──> CACHE/ASSEMBLE ──> RELEASE/ENQUEUE

decode/mask/staging/publish failure ──> CAPTURE_FAILED ──> cleanup staging + existing deterministic error/recovery
published bundle + logical commit failure/crash ──> QUARANTINED/RECOVERY_AUDIT
```

只有 `LOGICAL_FRAME_RECORDED` 状态进入 JSON `frames`；失败尝试通过带 run/step/source/attempt/time/error/duration 和状态/重试/恢复引用的 measurement/counter/log 保持审计。
