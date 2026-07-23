# Contract: Performance Telemetry and Counters

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

## Canonical stages

必须支持以下稳定 stage 值：

`capture`, `pixel_hash`, `persistence`, `OCR`, `template`, `vision`, `planner`, `grounder`, `verification`, `report_build`。

可追加 `report_output`，但不得用其替代 `report_build`。

## Measurement semantics

- 每次实际阶段执行追加一条 `StageMeasurement`，不覆盖以前记录。
- `duration_ms` 使用 monotonic clock 差值；`started_at` 使用 UTC wall clock。
- completed/failed/cancelled 必须保留实际已观测 duration。
- 规定但从未开始的阶段用 unavailable + `duration_ms=null`；禁止填 0 或估算。
- actual provider 请求在进入边界时计数，即使请求失败。
- cache hit 必须 `actual_call=false`, `cache_hit=true` 并带 source_ref。
- 错误信息先经敏感字段过滤，不记录图片 bytes、凭据或完整未遮罩路径内容。
- `report_output` 编码/原子写盘失败必须记录 failed 与已观测 duration，不得产生成功输出路径；已提交逻辑帧、物理图片和事件不回滚，也不得复制证据或回退到 private 路径。

## Stable structured-log events

| Event | Required payload |
|---|---|
| `stage_measurement` | run_id, step_id, state/status, stage, duration_ms, frame/iteration ids |
| `frame_dedup_decision` | frame_id, sequence, eligible, deduplicated, reason, source id |
| `analysis_cache_event` | component, key fingerprint, hit, source ref |
| `model_call_event` | model role, request identity, status, duration |
| `model_call_audit` | run/step/frame/iteration ids, model role, request/context identity, sanitized request/response, actual/skipped outcome, reason/source ref |
| `physical_image_event` | purpose, physical id, byte size, frame id |
| `artifact_bundle_recovery` | run/bundle ids, discovered state, action, manifest/ref outcome, status/error |
| `performance_summary` | all run-level counters, completeness, consistency errors |

日志与 TestRun 使用同一事件对象；JSON 与 HTML 的明细/汇总也从该 TestRun 事件集派生，禁止四个输出各自重新累计、补零或修平。

实际 Planner/Grounder/Verifier 调用必须产生脱敏 `model_call_audit` 并保留请求、响应和相关上下文身份；确定性 skip 必须记录规范化 request/context identity、命中的路由规则和原因。仅记录次数或 duration 不构成完整审计。

## Counter definitions

- `total_capture_count`: 成功逻辑 frames 数。
- `unique_frame_count`: frames 中 `deduplicated=false`。
- `duplicate_frame_count`: frames 中 `deduplicated=true`。
- `dedup_ratio`: duplicate/total；total=0 时 null。
- `physical_image_count`: 与成功逻辑帧同一 TestRun 更新提交、属于 referenced bundle 的 physical image events 数，按 purpose 分类；staging/quarantined/orphan 只记失败或 recovery audit，不计成功图片。
- `avoided_write_count`: actual physical write avoided events 数。
- `avoided_write_bytes`: 每个 avoided event 的复用实际 byte size 求和。
- `cache_hits.ocr/template/vision`: 对应组件 hit 数；diff 可追加。
- `analysis_invocations`: 进入 OCR/template/vision 等分析边界次数。
- `model_calls.vision/planner/grounder/verification`: 进入 provider/verification model 边界次数。
- `actual_model_call_count`: model_calls 求和。
- `skipped_model_call_count`: 确定性路由或模型结果缓存明确避免的 provider 请求；OCR/template cache hit 不计入。

## Conservation checks

1. `unique_frame_count + duplicate_frame_count == total_capture_count`
2. 每个 physical count 必须能找到成功 persistence event。
3. 每个 avoided byte 必须引用一个存在且 byte size 已知的 physical image。
4. cache hit 必须有 source invocation；actual invocation 不得同时标 hit。
5. 正常执行、离线重建、部分失败和兼容入口的报告构建均有 `physical_images_by_purpose.report_copy == 0`。
6. 每个报告可用 physical ref 必须指向 referenced bundle，且其 byte size/artifact SHA-256 与 manifest 一致；staging、quarantined 或无逻辑引用 bundle 不计入 physical image count。

任何不一致写入 `consistency_errors` 并将 completeness 标记 partial；不得自动修改原始事件来“修平”汇总。

## Report build boundary

`report_build` 从安全证据解析开始，覆盖基础 machine dict 与本地化 view-model 草稿组装；随后停止计时并把 measurement 追加到 TestRun。最终阶段只把该 measurement 注入草稿并执行不可变冻结，不再进行证据解析、事实计算或本地化映射。JSON/HTML 编码与原子写盘属于可选 `report_output`。该两阶段边界使当前报告包含自身真实 build measurement 而无需二次渲染。

## Test oracle

缓存与调用计数必须和独立 Spy 的真实调用数交叉核对；不得以 duration 是否大于零或网络耗时推断调用发生。

固定工作负载使用本地数组/fixture、可注入 monotonic/UTC 时钟和 Spy 边界；同一 run 的 JSON Lines、JSON、HTML 必须逐项核对 measurement id/status/duration、去重/物理/缓存事件及模型调用。异常阶段使用故障注入稳定复现，并保持 failed/unavailable 与 null/真实 duration 语义。
