# Contract: Bounded Perception Result Cache

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

## Cacheable components

| Component | Cacheable value | Minimum component identity |
|---|---|---|
| `ocr` | OCR items | backend/version/language/preprocess |
| `template` | template matches | matcher revision/threshold/template content set |
| `diff` | changed/ratio/regions/blobs | previous+current identity/threshold/dynamic mask/algorithm revision |
| `vision_describe` | description/confidence/model | provider/requested model+version/mode/prompt/schema/hint fingerprint |

所有键另含 content hash、scope identity、pixel format、mask identity 和 perception config fingerprint。

## Explicit exclusions

以下结果不得仅凭图片 content hash 进入本缓存：

- Planner 决策；
- Grounder 目标定位；
- Verifier 结论；
- 带验证问题、步骤意图、动作历史、重试策略或其他运行上下文的回答。

这些结果始终走确定性上下文路由。任一请求语义或相关上下文变化时必须产生所需独立请求；全部相同且当前阶段无需新计划时记录 Planner skip。每个操作后的 Verifier 始终基于独立采集证据执行。

### Role-specific request/context identity

| Role | Required canonical identity |
|---|---|
| Planner | request semantics、step intent、action/history state、retry/iteration state、current StructuredScreen identity、requested model/version/config、deterministic route state |
| Grounder | target semantics、candidate set/current StructuredScreen identity、scope/coordinate transform、requested model/version/config、retry/grounding state |
| Verifier | visual question/assertion、before/after frame identities、action audit/ActionEffect context、retry/iteration state、requested model/version/config |

任一必需字段缺失、不可规范化或变化都必须判定 `same_context=false`，禁止结果复用或基于同一身份 skip；若确定性路由判定该角色在当前阶段适用，则执行实际调用。上下文变化不使原本不适用的角色变为必调，但操作后的 Verifier 始终适用，必须用独立新捕获证据实际执行。

## Lookup contract

1. 当前 frame 不是 `deduplicated=true`，或 `duplicate_of_frame_id` 不是直接上一逻辑 frame ⇒ miss；A→B→A 不具备 lookup 资格。
2. `content_hash=null` ⇒ miss，不允许 cache get/put。
3. key 全字段稳定序列化后查找直接上一逻辑 frame 的 source entry。
4. 物理去重候选已由 frame contract 逐像素确认；hash 碰撞不得覆盖已有条目。
5. hit 返回纯组件结果与 `source_frame_id/actual_invocation_id`。
6. 每个逻辑 frame 用当前 frame 元数据和组件结果新建 `StructuredScreen`。
7. hit 记录 `analysis_cache_event`，不得记录实际调用；miss 的真实边界记录 `analysis_invocation`。

## Diff special case

当前 frame 是上一逻辑 frame 的 exact duplicate 时，diff 可确定性短路为：

- `changed_since_last=false`
- `global_diff_ratio=0`
- `changed_regions=[]`
- `local_blobs=[]`

该短路仍是一条可审计 cache/deterministic result，不执行路径读取或 OpenCV diff。

## Capacity and lifecycle

- 配置字段：`perception.cache_max_frames`；默认 5，允许 3～5。
- 淘汰顺序按最近逻辑 frame references 的 capture sequence；任意 cache get 不形成访问 LRU。
- 窗口按逻辑 frame 推进，包括 duplicate frame；每个连续 duplicate 登记对同一 source result 的轻量引用，因此超过窗口长度的连续重复序列仍只实际分析一次。
- 任一非相邻 unique 终止先前连续引用链，即使更早内容仍位于窗口中也不得 hit。
- duplicate 可共享不可变像素引用，不保留第二份相同数组。
- cache entry 不得持有 raw PNG、证据路径或完整 `StructuredScreen`。
- run/session reset、disconnect 和 close 必须清空全部条目与 previous。
- eviction 后无其他引用的 pixels/结果必须可被回收。

## Configuration/model invalidation

以下任一变化必须 miss：ROI/capture kind、pixel format、mask identity、OCR backend/version、模板集合内容、diff threshold/dynamic mask、vision provider/requested model/version、prompt/schema revision、structured hint fingerprint。

只使用模型响应中的 `model_name` 不能完成 lookup；生产装配必须传入请求侧模型 identity。

## Error behavior

cache get/put/serialization/eviction callback 异常必须记录 failed measurement，然后对当前组件执行 full analysis；不得改变 ScreenFrame 去重决定，也不得影响 Verifier 的独立执行。
