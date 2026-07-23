# Implementation Plan: 截图去重、分析复用、性能可观测性与中文报告

**Branch**: `004-frame-dedup-observability` | **Date**: 2026-07-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-frame-dedup-observability/spec.md`

## Summary

在现有 Python 单进程模块化运行时中，引入由 `ObservationPipeline` 与 `StabilityEngine` 共享的 run/VNC-session 级截图捕获服务和唯一逻辑帧记录器：VNC 返回 PNG 后只解码一次，在任何图片写盘前对遮罩前的规范化像素计算 SHA-256，并以完整作用域匹配、哈希匹配和逐像素相等三层门禁确认相邻帧重复。每次成功采集都立即持久化新的逻辑 `ScreenFrame`；重复帧通过内容寻址复用安全证据以及策略允许时的私有模型图片路径，唯一帧才由 `ArtifactStore` 写入新图片。

感知层把 OCR、模板、diff、视觉描述拆成有独立键的纯结果缓存，每个逻辑帧重新组装 `StructuredScreen`；缓存窗口默认 5、配置只允许 3～5，并且不缓存 Planner、Grounder 或 Verifier 的上下文敏感决定。新增追加式遥测事件和运行级汇总，JSON 只做增量扩展，HTML 通过集中 `zh-CN` 资源字典生成展示值。报告直接引用已认证的安全物理路径，不再常规创建 `report_frames` 副本。

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: OpenCV、NumPy、Pydantic 2、RapidOCR、Jinja2、structlog、SQLAlchemy/aiosqlite；不增加新的运行时依赖

**Storage**: 本地 PNG 制品、UTF-8 JSON/HTML、结构化 JSON Lines 日志、SQLite 中的 `TestRun` JSON payload

**Testing**: pytest、pytest-asyncio、现有 fake VNC/provider；新增注入式 Spy、固定 PNG、HTML/JSON golden、离线性能标记

**Target Platform**: 单 Agent 进程连接单一 VNC 会话；弱配置主机，无独立显卡要求

**Project Type**: Python CLI + 单进程模块化单体

**Performance Goals**: 10 次相同无掩码全屏采集产生 10 条逻辑帧、1 个物理 PNG、9 次避免写入；OCR/template/vision 各实际执行 1 次。第 11 帧单像素变化必须形成第二个唯一帧并重新分析

**Constraints**: 仅严格像素相等；物理去重和本 feature 内容缓存均不跨 run/session/非相邻帧；验证仍基于操作后独立采集；缓存最近 3～5 帧；禁止 private 持久化的步骤不得写入或复用未遮罩物理图片；优化异常可降级，安全持久化异常必须中止采集

**Scale/Scope**: MVP 同时一个 run、一个 VNC session、一个测试任务；完整逻辑轨迹可增长并持久化，内存仅保存最多 5 个近期帧条目且不保存无界 PNG bytes/完整 `StructuredScreen`

## Constitution Check

*GATE: Phase 0 前检查，并在 Phase 1 设计后复核。*

### Pre-Design Gate

- [x] **确定性运行时**：去重资格、缓存命中、模型路由、失败回退、计数和报告均由代码规则决定；模型不能改变流程或最终状态。
- [x] **职责分离**：内容缓存不包含 Planner、Grounder、Verifier 决策；三个角色的现有边界不变。
- [x] **键盘优先**：本功能不改变动作路由顺序，也不新增任何模型升级路径。
- [x] **独立 Observe → Act → Verify**：每次采集都创建逻辑帧；操作后相同画面仍进入 ActionEffect/Verifier，不因缓存自动通过。
- [x] **受控演进**：不修改正式断言、基线、模型版本或回放脚本。
- [x] **黑盒边界**：数据仅来自 VNC 屏幕像素与既有键鼠事件，不读取被测系统内部信息。
- [x] **单进程资源约束**：共享内存窗口限制为 3～5 帧；每次采集立即持久化逻辑记录，合格 duplicate 内容寻址复用物理图片，不引入分布式组件或本地大型模型。
- [x] **凭据与隐私**：哈希基于遮罩前像素但报告只暴露安全路径；遮罩失败不得回退写入未遮罩证据；`private_persistence_allowed=false` 时不创建或复用未遮罩物理制品。
- [x] **可审计性**：所有捕获调用方通过唯一 recorder 写入逻辑帧；缓存、模型调用及其脱敏请求/响应、持久化与阶段测量来自同一事件源，并进入日志与报告。

**Domain-Agnostic Core gate (Principle VI)**:

- [x] 核心模块不增加任何场景专用字段、关键词、状态、动作类别、期望值或流程分支。
- [x] 两个跨场景测试的输入只存在于通用 fixture/测试用例中，核心只消费通用像素、配置和断言接口。
- [x] 至少两个互不相关 GUI 场景复用同一捕获、缓存、验证和报告契约。

### Post-Design Re-check

- [x] `data-model.md` 只定义帧、物理制品、分析结果、遥测和本地化等通用实体。
- [x] 所有契约以 run/session/scope/config/model/request identity 建模，没有场景特例。
- [x] `quickstart.md` 的两个跨场景验收走相同公共运行时接口，并包含静态核心词汇扫描门禁。
- [x] 没有 Constitution 偏离，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/004-frame-dedup-observability/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── frame-capture-contract.md
│   ├── perception-cache-contract.md
│   ├── telemetry-contract.md
│   └── report-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── config/
│   └── agent.yaml
├── src/vnc_agent/
│   ├── api/cli.py
│   ├── config.py
│   ├── domain/
│   │   ├── observation.py
│   │   └── run.py
│   ├── perception/
│   │   ├── screenshot.py
│   │   ├── pipeline.py
│   │   ├── stability.py
│   │   ├── structured_screen.py
│   │   ├── screen_diff.py
│   │   ├── cache.py                 # 新增：有界组件缓存与键
│   │   ├── ocr/engine.py
│   │   └── template/matcher.py
│   ├── runtime/
│   │   ├── agent_runtime.py
│   │   └── telemetry.py             # 新增：追加式测量/计数收集器
│   ├── storage/
│   │   ├── artifact_store.py
│   │   └── repositories.py
│   └── reporting/
│       ├── report_builder.py
│       ├── json_report.py
│       ├── html_report.py
│       └── localization.py          # 新增：locale 资源注册表与展示映射
└── tests/
    ├── unit/
    ├── fixtures/
    │   └── images/frame_dedup/
    ├── integration/
    ├── e2e/
    ├── performance/
    └── snapshots/
```

**Structure Decision**: 保持现有 `vnc_agent/` 单项目布局。新增的缓存、遥测和本地化模块分别位于已有 perception/runtime/reporting 边界；不新建服务进程、数据库表或外部缓存。`RunRepository` 继续以 Pydantic JSON payload 往返新增字段。

## Targeted Code Impact

| Existing path | Planned change |
|---|---|
| `vnc_agent/src/vnc_agent/perception/screenshot.py` | 建立共享 `FrameCaptureService`、一次解码、规范化 hash、严格相邻判等、逻辑帧创建与失败回退 |
| `vnc_agent/src/vnc_agent/perception/pipeline.py` | 注入共享捕获服务和组件缓存；移除遮罩分支的双重 assembly；每帧重新组装 StructuredScreen |
| `vnc_agent/src/vnc_agent/perception/stability.py` | 按逻辑 ScreenFrame 累计稳定采样；duplicate 快路径不再重读同一路径 |
| `vnc_agent/src/vnc_agent/domain/observation.py` | 扩展 ScreenFrame/CaptureScope/StructuredScreen 的 hash、去重、比较与来源字段 |
| `vnc_agent/src/vnc_agent/storage/artifact_store.py` | 提供显式用途、实际字节数与 artifact SHA-256、可选 private 持久化、staging bundle 单次原子发布及孤儿恢复；移除路径字符串安全推断 |
| `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` | 管理 capture session 生命周期，记录 Planner/Grounder/Verifier 真实调用与阶段测量 |
| `vnc_agent/src/vnc_agent/reporting/report_builder.py` | 安全证据零副本解析、单次共享报告视图和 report_build 边界 |
| `vnc_agent/src/vnc_agent/reporting/json_report.py` | 保留旧投影，追加 frames/stage measurements/performance/display 字段 |
| `vnc_agent/src/vnc_agent/reporting/html_report.py` | 消费本地化 view-model，保持 machine CSS/data marker，启用 autoescape |
| `vnc_agent/src/vnc_agent/config.py` | 增加 3～5 帧缓存限制和 locale registry 校验 |
| `vnc_agent/config/agent.yaml` | 新增 `perception.cache_max_frames: 5` 与 `reporting.locale: zh-CN` 默认配置 |

Supporting changes：`domain/run.py` 保存 frames/telemetry/summary；`api/cli.py` 在 execute 路径装配共享 capture service、telemetry 和 locale，在离线/部分失败/兼容 report 路径仅装配 locale、telemetry/frozen report view、safe evidence resolver 与 renderer/output；`structured_screen.py`、`screen_diff.py`、OCR/template 入口接受已解码数组；`storage/repositories.py` 增加 JSON payload round-trip 验证但不迁移表。

## Implementation Strategy

### 1. 写盘前一次解码、哈希与严格判等

在 `perception/screenshot.py` 增加内部 `DecodedCapture` 与共享 `FrameCaptureService`。捕获顺序固定为：

1. `driver.capture_screen/capture_region` 获取 PNG bytes，并记录 `capture` 测量。
2. 使用 `cv2.imdecode(..., IMREAD_UNCHANGED)` 一次解码，规范化为只读、C-contiguous 数组；从 shape/dtype/channel order 得到稳定 `pixel_format`。若无法得到可信数组/格式，立即记录 capture failure 并终止本次成功路径，不进入哈希、持久化、分析或验证；有遮罩时 fail closed。
3. 构造唯一版本化前像 `frame-pixels-v1 || width || height || canonical pixel_format || C-contiguous unmasked normalized pixel bytes`（整数固定宽度编码、字符串带长度前缀），对其计算 SHA-256 并记录 `pixel_hash` 测量。这里的完整前像统一称为“规范化像素载荷”；完整 CaptureScope identity 仍是独立去重/缓存维度，除载荷中的 width/height/pixel format 外，capture kind、坐标、resolution、mask identity 与 private policy 不混入 `content_hash`。
4. 仅与共享会话中的上一逻辑帧比较：先比较 run/session/capture kind/ROI/分辨率/pixel format/mask identity，再比较 hash，最后用 `np.array_equal` 排除碰撞。
5. 唯一帧把同一解码数组交给遮罩、OCR、模板和 diff 的数组入口；不再从新写文件重新 `imread`。现有路径入口保留为离线兼容 wrapper。

`pipeline.py` 遮罩分支不再先后调用两次 `assemble_structured_screen`；`structured_screen.py` 接收预计算组件，只组装一次。`screen_diff.py`、OCR 与模板入口增加数组形式，路径形式内部只负责兼容读取。

### 2. 逻辑帧与物理图片分离

`domain/observation.py` 的 `ScreenFrame` 增加 `content_hash`、`deduplicated`、`duplicate_of_frame_id`，并补齐 `vnc_session_id`、capture sequence、scope/capture kind、pixel format、mask identity、comparison state 与显式安全/私有物理引用。

- 每次成功捕获均创建新的 frame id、step id、capture source 和 UTC timestamp，并由 FrameCaptureService 内部唯一 recorder 在返回调用方前追加到 `TestRun.frames`；Pipeline、StabilityEngine、重试、恢复和验证调用方不得各自维护不完整的轨迹。
- 重复帧的 `duplicate_of_frame_id` 指向直接上一逻辑帧；安全路径与策略允许的 private 路径复用上一帧，capture sequence 仍递增。捕获策略身份包含 `private_persistence_allowed`，权限不同不得复用。
- 唯一帧才调用 `ArtifactStore.persist_frame_pair`。无遮罩时安全与模型用途可指向同一文件；有遮罩且允许 private 持久化时分别写安全和私有文件；禁止 private 持久化时只写安全文件，未遮罩像素仅在当前允许的内存分析期间存在。
- `ArtifactStore` 为每个 unique frame 在最终 run artifact 根的同一文件系统内建立 staging bundle，把全部策略要求的 safe/private 文件及 manifest 写入其中；manifest 记录 `artifact_bundle_id`、owner frame、purpose、实际 byte size 和对每个最终编码文件 bytes 计算的 `artifact_sha256`。全部文件与 staging 目录同步成功后，以一次目录 rename 原子发布到不可变 final bundle 路径，禁止逐个 final-file replace 暴露半组文件。顺序固定为：(1) bundle 原子发布并返回 pending refs/events；(2) 不可变逻辑帧、对应 PhysicalImageRef 与 `physical_image_written` 事件在同一 TestRun 更新中提交；(3) 向调用方返回。发布前失败清理 staging；发布后逻辑提交失败不提交成功 physical event，并把整个未引用 bundle 移入 run 内非报告隔离区记录失败。run 启动/恢复时按 manifest 与 TestRun 引用确定性清理残留 staging、隔离已发布但无逻辑引用的 bundle并追加 recovery audit；不得让 orphan 成为报告证据或成功 physical count。路径用途为显式元数据，不再根据目录名猜测。
- `TestRun.frames` 按 capture sequence 保存观察、等待、重试、恢复和操作后验证产生的所有成功逻辑帧；失败尝试以 run/step/source/attempt/time/error/duration 可关联的 measurement、counter 和结构化日志进入事件流，而不伪造成功 `ScreenFrame`。

### 3. 共享捕获会话与有界缓存

execute CLI 装配一个 `FrameCaptureService`，同时注入 `ObservationPipeline` 与 `StabilityEngine`。`AgentRuntime` 在 connect 后开启 run/session，在成功 reconnect 后旋转 `vnc_session_id` 并清空 previous/cache；run 完成或 disconnect 时显式 `clear()`。离线重建、部分失败报告与兼容 report 入口不得创建、连接或注入 `FrameCaptureService`，只装配 locale registry/config、已有 telemetry 的冻结 report view、safe evidence resolver 与 renderer/output stage；它们消费已持久化逻辑帧，不产生新的 capture sequence。

`perception/cache.py` 提供按 capture sequence 淘汰的有界窗口，`perception.cache_max_frames` 默认 5、校验范围 3～5：

- 只缓存 OCR、模板、diff、vision describe 的不可变纯结果，不缓存完整 `StructuredScreen`；lookup 的首要门禁是当前帧 `deduplicated=true` 且 source 为直接上一逻辑帧，A→B→A 必须 miss。
- 公共键包含 component、算法/schema revision、content hash、完整 scope、pixel format、mask identity、感知配置 fingerprint。
- OCR 再含 backend/version/preprocess；模板再含模板集合内容 fingerprint；diff 再含前后帧 identity、阈值与动态 mask；vision 再含请求模型 identity、mode、prompt/schema revision 与 structured hint fingerprint。
- Planner、Grounder、Verifier 以及带步骤意图/验证问题的回答不进入图片内容缓存。角色专属 identity 使用稳定 canonical serialization：Planner 包含请求语义、步骤意图、动作/历史状态、重试/迭代状态、当前 StructuredScreen、请求侧模型/配置和确定性路由状态；Grounder 包含目标语义、候选集合/StructuredScreen、scope/坐标变换、请求侧模型/配置和重试/定位状态；Verifier 包含验证问题/断言、前后 frame、动作审计/ActionEffect、重试/迭代以及请求侧模型/配置。任一必需字段缺失或变化都禁止按相同上下文复用/skip；角色是否适用仍由确定性路由决定，操作后 Verifier 始终适用并实际执行。
- 缓存不持有 PNG bytes、证据路径或完整 `StructuredScreen`；最近 3～5 个逻辑帧保存对纯结果的引用，因此连续 10 个 duplicate 可共享同一结果而不会因 source sequence 变旧重新调用。非相邻 unique 会关闭该引用链；逐出和 session reset 时解除 ndarray/结果引用。

### 4. StabilityEngine 保留逻辑采样语义

`stability.py` 改为消费 `FrameCaptureService` 返回的 `ScreenFrame`/捕获结果，而不是自行按路径管理上一帧：

- 每次由当前活动 StabilityEngine 等待循环发起的真实 capture 都写逻辑轨迹、调用该等待的 `early_exit` 并参与该等待的 `stable_frame_count`；其他观察、重试、恢复和操作后验证 capture 只进入全局逻辑轨迹与采集总数，不得污染任何稳定等待的局部计数或 callback。
- `deduplicated=true` 时确定性得到本次 unchanged，累计一次稳定转移，不再读取同一路径做 diff。
- 唯一帧继续执行既有阈值 diff；严格像素变化与稳定性阈值变化保持两个独立信号。
- 保留 `stable_frame_count - 1` 次连续稳定转移的现有公式；`buffer_paths()` 作为轻量帧窗口的兼容投影。

### 5. 追加式遥测与运行级汇总

新增 `runtime/telemetry.py`，使用 `time.perf_counter_ns()` 测 duration、UTC 记录 started_at；每次执行追加 `StageMeasurement`，不再用字典覆盖完整历史。必须埋点：`capture`、`pixel_hash`、`persistence`、`OCR`、`template`、`vision`、`planner`、`grounder`、`verification`、`report_build`。

- 状态为 completed/failed/cancelled/unavailable；未开始阶段的 duration 为 null，不能补 0。
- provider 请求开始时才增加实际模型调用，即使随后失败；OCR/template 是分析调用，不冒充模型调用。
- 缓存命中、确定性跳过、实际调用、物理写入和避免写入分别发事件，汇总从事件推导并检查守恒。
- 同一事件既保存在 `TestRun`，又通过 structlog 输出稳定 JSON Lines 事件，避免日志与报告各自累计。实际 Planner/Grounder/Verifier 请求还保留脱敏 request、response、request/context identity 及 run/step/frame/iteration 关联；skip 保留规则和原因。
- 保留 `StepRecord.stage_durations_ms` 原字段与既有语义；新增明细不替换旧字段。

`agent_runtime.py` 在实际 Planner/Grounder/Verifier 边界计时，不能用整个 planning/resolving/verifying 状态时长替代。测试可注入 verifier 与时钟，生产默认行为不变。

### 6. 报告零副本、共享视图与计时边界

`report_builder.py` 不再改写 iteration 业务事实或调用 `copy_masked_for_report`。正常执行、离线重建、部分失败报告和兼容 CLI/旧入口全部装配同一个 safe evidence resolver：从逻辑帧的显式 safe artifact 引用解析证据，验证路径位于当前 run 安全根、用途正确、文件存在、mask identity 匹配、实际 byte size 和文件 bytes 的 `artifact_sha256` 匹配，并确认图片可解码，然后生成相对 HTML 链接；缺失、截断、损坏、hash mismatch 或解码失败均显示明确本地化不可用状态且不生成链接，绝不回退引用私有图片，也不通过 copy/hardlink/symlink 在 `report_frames` 或其他报告目录生成证据副本。`content_hash` 仍表示遮罩前规范化像素，不能用于代替 safe 文件完整性校验。旧 JSON `before_frame_path`/`after_frame_path` 继续表示对应操作前/后可读取安全证据，但从 renderer view 中解析为该逻辑帧的 safe physical path；基础 schema 未承诺 `report_frames` 目录或独立副本，因此该规范化不改变字段类型、null/缺省或前后证据语义。

`report_build` 采用两阶段、无自引用边界：计时阶段完成“安全证据解析 + 基础机器 report dict + 本地化 view-model 草稿组装”，随后立即结束测量并把该 measurement 追加到 TestRun；最后只执行确定性的 measurement 注入与不可变冻结，JSON/HTML renderer 共同消费该唯一冻结视图。最终编码/原子写盘另记 `report_output`，不属于 `report_build`；失败时记录 failed 与真实 duration，不返回成功输出路径、不改写既有运行事实，也不复制证据进行回退。

### 7. `zh-CN` 资源字典与稳定机器值

新增 `reporting/localization.py`：locale registry 集中保存页面标签、状态、验证标签、动作效果、已知错误码和空值/警告文案。`ReportingConfig.locale` 默认 `zh-CN`；当前未知 locale 在配置校验阶段失败，未来增加语言只需登记完整资源包。

展示 view-model 同时提供 `machine_value`、`display_value`、稳定 CSS class/data-marker。Jinja 模板只消费资源键和展示值，不包含状态/错误翻译分支。静态 UI、帮助、状态和错误说明必须来自中文资源；允许保留英文的可见白名单仅为原始 code/detail、明确标识的 machine enum/data marker、模型/provider/产品标识和诊断必需的文件/路径片段。未知错误使用通用中文说明并完整保留原始 code/detail。Jinja Environment 开启 autoescape；JSON/HTML/资源文件显式 UTF-8，JSON 保持 `ensure_ascii=False`，测试按码点核对落盘再读取并分别拒绝 U+FFFD、丢字和错误转义。

### 8. JSON 向后兼容

`json_report.py` 保持现有顶层键、steps/iterations 及其嵌套结构、英文字段、required/optional、枚举、类型、null/缺省语义、数组顺序、status 聚合和其他语义不变；`before_frame_path`/`after_frame_path` 保持“对应前/后安全证据路径”语义并解析为 safe physical path，而不保留非契约性的 `report_frames` 目录/文件名，仅追加：

- `frames`：所有成功逻辑采样，按 capture sequence 排序，只暴露安全证据路径；
- `stage_measurements`：追加式阶段审计；
- `performance_summary`：去重、物理文件、缓存与调用汇总；
- 可选 `display_status`、`localized_message`。

`RunRepository` 继续保存整个 `TestRun` JSON payload，无需表结构迁移；增加 round-trip 测试证明多逻辑帧共享路径和独立时间戳可完整恢复。旧 JSON golden 对非路径旧字段采用递归兼容投影逐字段比较；`before_frame_path`/`after_frame_path` 以 safe purpose、可读取性、前后关联及解析后的 physical id/content hash 等价比较，不要求保留旧 `report_frames` 文本路径。另以代表性 feature 001 旧消费者/旧 schema 校验器忽略未知字段后解析新报告，证明新增字段和零副本路径不会破坏实际消费者。

### 9. 安全回退

- decode/规范化异常：记录 failed capture measurement/attempt，因没有可信规范化像素而不创建 ScreenFrame、不执行图片分析或验证；有遮罩时不得把原始 bytes 写入 safe path。
- 规范化像素已可用后的 hash/逐像素比较/cache get/cache put 异常：记录 optimization failure，按唯一帧/cache miss 走完整安全持久化和分析；不得增加 hit、avoided 或 skipped 指标，也不得绕过 `private_persistence_allowed=false`。
- 有遮罩时 decode/遮罩编码失败：fail closed，不允许把原始 bytes 写到安全路径。
- 任一 staging 文件写入、同步或 bundle rename 失败：不发布 final bundle、不返回成功 `ScreenFrame`，清理 staging 并进入现有确定性错误/恢复路径；bundle 已发布但逻辑提交失败时整体隔离，下一次启动/恢复再次通过 manifest 与 TestRun 引用对账，记录 recovery audit，禁止孤儿文件进入报告。
- vision best-effort 失败仍可降级，但必须记录真实调用、耗时与失败状态，不再静默丢失诊断。

### 10. 测试策略

所有缓存与性能验收使用本地 `SpyOCR`、`SpyTemplateAnalyzer`、`SpyPlannerProvider`、`SpyGrounder`、`SpyVerifier` 和确定性时钟；调用次数在替身边界独立统计，并与报告计数交叉核对，不使用网络时延推断。

测试层次：

1. 单元测试：一次解码、decode/规范化失败中止、像素 hash、碰撞、单像素变化、scope/mask/model/config key、容量 3/5、内存释放、第二个 bundle 文件写入/同步/rename/逻辑提交失败与孤儿恢复故障注入、指标守恒、locale 资源覆盖。
2. 固定截图离线测试：10 相同 + 第 11 单像素、A→B→A 非相邻 miss、不同编码同像素、不同 ROI/遮罩、禁止 private 持久化、`stable_frame_count=3`，并核对观察/等待/重试/恢复/操作后验证帧全部进入同一轨迹。
3. 报告测试：中文 HTML 完整快照与 DOM 白名单扫描、UTF-8 逐码点 round-trip/autoescape、旧 JSON golden 递归兼容投影与代表性旧消费者、正常/离线/部分失败/兼容入口同一证据路径零副本，以及 safe 文件缺失、截断、损坏、byte-size/hash mismatch、不可解码、路径越界与 mask mismatch 负例、`report_output` 失败。
4. 集成测试：`TestRun.frames`/telemetry/脱敏模型请求响应 SQLite payload 往返、CLI 配置接线及同一事件在 JSON Lines/JSON/HTML 中的关联。
5. 性能测试：本地固定数组、warm-up 后多轮中位数，主门禁使用工作量不变量与 90% 调用/写入减少，不使用在线服务绝对延迟。
6. 跨场景契约：`generic-form-flow` 与 `generic-icon-menu-flow` 具有不同可见结构，并分别以键盘/文本输入和视觉目标/弹层为主要交互路径运行同一 capture→observe→act→verify→report 契约；两者都保留独立操作后验证证据，核心实现不得读取 fixture 名称或内容词汇，仅换名称/文字/图片的同构 fixture 不计为第二场景。

## Implementation Order

1. **模型与契约先行**：扩展 `ScreenFrame`/`TestRun`、新增 telemetry models 和配置校验，锁定 JSON delta。
2. **捕获与制品边界**：实现一次解码、严格判等、共享 session、原子写入和物理计数；先通过固定截图测试。
3. **感知缓存与稳定性**：数组入口、分组件缓存、fresh `StructuredScreen`、重复帧稳定计数和内存释放。
4. **运行时可观测性**：接入 provider/verification/report_build 计时以及同源结构化事件。
5. **报告与本地化**：零副本证据、单次 report dict、JSON delta、资源字典和 HTML 快照。
6. **全链路门禁**：故障注入、repository/CLI 集成、性能基准、两个跨场景契约、核心业务无关静态扫描。
