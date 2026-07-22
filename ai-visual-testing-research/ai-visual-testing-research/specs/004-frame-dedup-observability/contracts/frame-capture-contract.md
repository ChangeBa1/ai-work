# Contract: Logical Frame Capture and Physical Deduplication

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

## Purpose

定义 `ObservationPipeline`、`StabilityEngine`、运行时和报告共同依赖的逻辑帧捕获契约。该契约是内部通用 Protocol，不暴露被测场景语义。

## Capture request

每次请求必须提供：

- `run_id`
- `vnc_session_id`
- `step_id`（允许 null）
- capture kind：`full_screen` 或 `roi`
- ROI 全局坐标与尺寸（full-screen 使用明确零偏移）
- 完整安全遮罩配置身份与实际 rectangles
- `private_persistence_allowed`；禁止时未遮罩像素只能在当前允许的分析中短暂驻留内存

调用方不得传入上一帧、自行决定去重或自行追加逻辑帧；共享捕获服务维护唯一的全局相邻序列和 TestRun frame recorder。

## Capture response

成功时先由共享 recorder 把新逻辑帧追加到 `TestRun.frames`，再返回：

- 新的逻辑 `ScreenFrame`；
- 仅供当前分析/严格比较使用的规范化像素视图；
- 当前帧实际写入或避免写入的事件引用。

失败时不得返回部分 `ScreenFrame`。错误进入现有确定性错误/恢复流程，并留下 measurement/log。

## Exact duplicate decision

只有以下条件全部满足才允许 `deduplicated=true`：

1. 当前帧与 run 内全局上一逻辑帧 capture sequence 相邻；
2. run id 与 VNC session id 相同；
3. capture kind 相同；
4. ROI/global coordinates、width、height、resolution 相同；
5. pixel format 相同；
6. mask identity 相同；
7. `private_persistence_allowed` 相同；
8. 遮罩前规范化像素 SHA-256 相同；
9. 规范化 ndarray shape/dtype 相同且 `array_equal` 为 true。

任一条件缺失、异常或 false 均按 unique 处理。hash 相同不得绕过第 9 项。

## Logical/physical invariants

- 每次成功 capture 都生成新的 frame id、capture sequence 和 timestamp。
- duplicate 必须设置 `duplicate_of_frame_id` 为直接上一逻辑 frame id，并只复用当前持久化策略允许的 safe/model physical refs。
- unique 必须设置 `duplicate_of_frame_id=null`，并成功持久化所需物理制品后才返回。
- duplicate 必须设置严格 `changed_since_last=false`；首帧为 comparison unavailable。
- Pipeline、StabilityEngine、重试和验证产生的 duplicate 均由同一 recorder 进入 TestRun.frames、stable count、early-exit callback 和审计事件。
- run/session rotation 必须清空 previous；不同范围的中间帧也必须推进 previous，禁止回看更早同范围图片。

## Artifact safety

- safe evidence 必须在内存完成遮罩并通过编码后才可提交。
- private model image 绝不能替代 safe evidence 或进入报告链接。
- 无遮罩时 safe/model 可引用同一实际文件，物理计数只计一个。
- 有遮罩且 `private_persistence_allowed=true` 时 safe/model 是两个实际文件，分别计数。
- `private_persistence_allowed=false` 时只允许 safe evidence 物理文件；不得创建或复用 private_model 文件，内存中的未遮罩像素在当前分析结束后释放。
- 所需文件以临时路径写入并原子提交；任一写入失败不得提交逻辑帧，临时/部分文件应尽力清理。
- `physical_write_avoided` 按本应发生的实际文件用途逐项记录，byte basis 来自复用文件的实际大小。

## Failure matrix

| Failure | Required behavior | Forbidden accounting |
|---|---|---|
| hash | unique fallback + full analysis | dedup/cache hit/avoided/skipped |
| candidate compare | unique fallback + full analysis | dedup/cache hit |
| cache get/put | miss/full analysis；结果仍可用于当前帧 | cache hit/skipped |
| decode with no mask | 若原 raw PNG 可安全持久化则 unique fallback；分析失败如实记录 | 虚构 content hash |
| decode/mask encode with mask | capture failed, fail closed | 把 raw bytes 写入 safe path |
| required persistence | capture failed, existing error flow | 成功 ScreenFrame/physical event |
| private persistence forbidden | persist safe only + release unmasked pixels | private_model write/reuse/avoided event |

## Compatibility

现有 `capture_full_screen`/`capture_region` 可保留为 wrapper，但生产装配必须使用共享 capture service；wrapper 不得建立模块全局缓存。
