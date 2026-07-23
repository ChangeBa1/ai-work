# Contract: Logical Frame Capture and Physical Deduplication

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

## Purpose

定义 `ObservationPipeline`、`StabilityEngine`、运行时和报告共同依赖的逻辑帧捕获契约。该契约是内部通用 Protocol，不暴露被测场景语义。

## Capture request

每次请求必须提供：

- `run_id`
- `vnc_session_id`
- `step_id`（允许 null）
- `capture_source`（observation/stability_wait/retry/recovery/post_action_verification）与本来源内的 attempt sequence
- capture kind：`full_screen` 或 `roi`
- ROI 全局坐标与尺寸（full-screen 使用明确零偏移）
- 完整安全遮罩配置身份与实际 rectangles
- `private_persistence_allowed`；禁止时未遮罩像素只能在当前允许的分析中短暂驻留内存

调用方不得传入上一帧、自行决定去重或自行追加逻辑帧；共享捕获服务维护唯一的全局相邻序列和 TestRun frame recorder。

## Capture response

成功顺序不可交换：

1. unique 的全部必需 safe/private 文件与 manifest 在同一 staging bundle 中同步完成，并以一次同文件系统目录 rename 原子发布；duplicate 的待复用物理引用通过当前 scope/safety/manifest 校验；
2. 共享 recorder 在同一 TestRun 更新中持久化不可变逻辑帧、PhysicalImageRef 与对应 `physical_image_written` 事件，并追加到 `TestRun.frames`；
3. 才向调用方返回响应。

成功响应包含：

- 新的逻辑 `ScreenFrame`；
- 仅供当前分析/严格比较使用的规范化像素视图；
- 当前帧实际写入或避免写入的事件引用。

上述第 2 步完成前任一失败都不得返回部分或成功 `ScreenFrame`。错误进入现有确定性错误/恢复流程，并留下可通过 run_id、step_id、capture_source、attempt sequence、时间、状态/重试/恢复引用关联的 measurement/counter/log；第 2 步已提交后返回传输失败不得回滚或复制物理制品。

## Exact duplicate decision

`content_hash` 的唯一前像是 `frame-pixels-v1 || width || height || canonical pixel_format || C-contiguous unmasked normalized pixel bytes`；整数固定宽度编码，字符串带长度前缀。本文所称“规范化像素 SHA-256”均指该完整版本化载荷。完整 scope identity 仍作为独立门禁；除载荷中的 width/height/pixel format 外，capture kind、坐标、resolution、mask identity 与 private policy 不混入 hash。hash 仅筛选候选，不能证明严格相等。

只有以下条件全部满足才允许 `deduplicated=true`：

1. 当前帧与 run 内全局上一逻辑帧 capture sequence 相邻；
2. run id 与 VNC session id 相同；
3. capture kind 相同；
4. ROI/global coordinates、width、height、resolution 相同；
5. pixel format 相同；
6. mask identity 相同；
7. `private_persistence_allowed` 相同；
8. 遮罩前规范化像素载荷 SHA-256 相同；
9. 规范化 ndarray shape/dtype 相同且 `array_equal` 为 true。

任一条件缺失、异常或 false 均按 unique 处理。hash 相同不得绕过第 9 项。

## Logical/physical invariants

- 每次成功 capture 都生成新的 frame id、capture sequence 和 timestamp。
- duplicate 必须设置 `duplicate_of_frame_id` 为直接上一逻辑 frame id，并只复用当前持久化策略允许的 safe/model physical refs。
- unique 必须设置 `duplicate_of_frame_id=null`，并成功持久化所需物理制品后才返回。
- duplicate 必须设置严格 `changed_since_last=false`；首帧为 comparison unavailable。
- Pipeline、StabilityEngine、重试、恢复和操作后验证产生的 duplicate 均由同一 recorder 进入 TestRun.frames 与审计事件；只有活动 StabilityEngine 等待循环自身发起的采样进入该等待的 stable count 和 early-exit callback，其他来源不得污染该局部状态。
- run/session rotation 必须清空 previous；不同范围的中间帧也必须推进 previous，禁止回看更早同范围图片。

## Artifact safety

- safe evidence 必须在内存完成遮罩并通过编码后才可提交。
- 每个最终编码文件必须计算独立 `artifact_sha256`，并与 byte_size、purpose、mask identity、owner frame 和 `artifact_bundle_id` 写入 manifest；该 hash 校验实际文件 bytes，不得用遮罩前 `content_hash` 替代。
- private model image 绝不能替代 safe evidence 或进入报告链接。
- 无遮罩时 safe/model 可引用同一实际文件，物理计数只计一个。
- 有遮罩且 `private_persistence_allowed=true` 时 safe/model 是两个实际文件，分别计数。
- `private_persistence_allowed=false` 时只允许 safe evidence 物理文件；不得创建或复用 private_model 文件，内存中的未遮罩像素在当前分析结束后释放。
- 所需文件和 manifest 必须写入最终 run 根内同文件系统的 staging bundle；全部同步成功后只允许一次目录 rename 发布 final bundle，禁止逐个 final-file replace。任一 staging/sync/rename 失败不得提交逻辑帧并必须清理 staging。
- final bundle 发布后逻辑记录失败时，整个 bundle 必须移入 run 内非报告隔离区；run 启动/恢复必须以 manifest 与 TestRun 引用清理残留 staging、隔离无引用 published bundle并记录 recovery audit。只有存在已提交逻辑引用的 bundle 才可被复用或报告。
- `physical_write_avoided` 按本应发生的实际文件用途逐项记录，byte basis 来自复用文件的实际大小。

## Failure matrix

| Failure | Required behavior | Forbidden accounting |
|---|---|---|
| hash | unique fallback + full analysis | dedup/cache hit/avoided/skipped |
| candidate compare | unique fallback + full analysis | dedup/cache hit |
| cache get/put | miss/full analysis；结果仍可用于当前帧 | cache hit/skipped |
| decode/normalization（无论是否有 mask） | capture failed；无 ScreenFrame、无下游图片分析/验证 | unique fallback、虚构 content hash/像素格式 |
| mask encode after successful decode | capture failed, fail closed | 把 raw bytes 写入 safe path |
| required persistence | capture failed, existing error flow | 成功 ScreenFrame/physical event |
| second file/manifest sync or bundle rename | remove staging, capture failed | 部分 final 文件/成功 ScreenFrame |
| logical record/event commit after bundle publish | no successful physical event; quarantine whole unreferenced bundle + failed attempt audit | 返回成功 frame/计入 physical count/把 orphan 用作证据 |
| startup/reconnect recovery | reconcile staging/published bundles against TestRun refs + recovery audit | 静默保留或报告 orphan |
| private persistence forbidden | persist safe only + release unmasked pixels | private_model write/reuse/avoided event |

## Compatibility

现有 `capture_full_screen`/`capture_region` 可保留为 wrapper，但生产装配必须使用共享 capture service；wrapper 不得建立模块全局缓存。
