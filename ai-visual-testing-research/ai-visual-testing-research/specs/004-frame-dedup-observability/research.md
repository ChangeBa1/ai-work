# Phase 0 Research: 截图去重、分析复用、性能可观测性与中文报告

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-07-22

本研究以现有 `vnc_agent/` 代码、feature 004 澄清结论与 Constitution v1.2.0 为依据。所有技术未知项均已收敛，无未决技术问题。

## R1. 捕获后只解码一次，并在写盘前哈希

**Decision**: VNC PNG bytes 只执行一次 `cv2.imdecode(..., IMREAD_UNCHANGED)`，规范化为只读、C-contiguous 像素数组并派生稳定 `pixel_format`。使用 SHA-256 对带域分隔的尺寸/格式元数据与遮罩前像素 bytes 计算 `content_hash`，再做去重决定。相同数组直接传给遮罩、OCR、模板与 diff 的内存入口。

**Rationale**: 当前 `screenshot.py` 先写盘，遮罩又解码/编码；OCR、模板和 diff 随后按路径多次读取。`pipeline.py` 在启用遮罩时还会调用两次 `assemble_structured_screen`。一次解码同时解决写盘前无法去重和重复分析问题。

**Alternatives considered**:

- 对 PNG bytes 哈希：编码元数据或压缩差异会把相同像素误判为不同。
- 写盘后再哈希：不能避免重复写入。
- 保留所有按路径读取入口：无法满足避免重复解码的目标。

## R2. 哈希只筛选候选，逐像素比较最终裁决

**Decision**: 去重依次检查 run、VNC session、全局相邻 capture sequence、capture kind、ROI、分辨率、pixel format、mask identity、content hash，最后使用 `np.array_equal` 确认规范化数组完全一致。哈希碰撞时必须建立独立候选，不覆盖或复用错误结果。

**Rationale**: 规范明确要求一个像素变化就保存新图片，且 content hash 不是充分条件。现有阈值 diff 会灰度化并忽略小差异，不可承担物理去重判定。

**Alternatives considered**:

- 仅信任 SHA-256：概率虽低，但不满足逐像素验收契约。
- 复用稳定性 diff：其阈值与动态区域遮罩语义不同。
- 使用感知 hash：超出严格相等范围。

## R3. Pipeline 与 StabilityEngine 共用捕获会话

**Decision**: 创建 run/session 作用域的 `FrameCaptureService`，由 `ObservationPipeline`、`StabilityEngine`、重试与验证采集共享。服务拥有唯一逻辑帧 recorder，在成功返回捕获结果前把每个 ScreenFrame 追加到 `TestRun.frames`；它维护单调 capture sequence、上一逻辑帧与有界窗口，run 完成、disconnect 或 reconnect 时清空，reconnect 使用新的 `vnc_session_id`。

**Rationale**: 当前两个模块直接调用无状态 capture 函数，各自缓存会漏掉跨模块的真实相邻关系。按 scope 维护多个 previous lane 会绕过中间不同范围的采样，违反相邻帧限定。

**Alternatives considered**:

- 模块级全局缓存：run/session 隔离差，测试污染风险高。
- Pipeline 与 StabilityEngine 分别缓存：无法形成全运行相邻序列。
- 每个 ROI 一条缓存链：会错误匹配非相邻图片。

## R4. 原始像素判等，安全/私有制品成对管理

**Decision**: `content_hash` 基于遮罩前像素，去重身份另含规范化全局 mask identity 与 `private_persistence_allowed`。唯一帧先在内存完成安全遮罩编码，再由 `ArtifactStore` 原子持久化安全证据和策略允许时的私有模型图片；禁止 private 持久化时不创建或复用未遮罩文件，模型只短暂使用内存像素。重复帧只复用当前策略允许的物理引用。遮罩或安全编码失败时 fail closed。

**Rationale**: 基于遮罩后像素会忽略遮罩区域内影响模型分析的真实变化。当前遮罩失败会返回原始 bytes，且两类文件不是原子提交，存在把未遮罩图片写入安全位置或留下部分制品的风险。

**Alternatives considered**:

- 遮罩后 hash：会错误复用私有模型结果。
- 无条件持久化 private 路径：会违反敏感输入步骤的 no-persist 策略。
- 遮罩失败时写原图：不满足隐私边界。

## R5. ScreenFrame 是逻辑采样，不是文件别名

**Decision**: 每次成功 capture 创建新的 `ScreenFrame.id`、timestamp、step id 与 sequence。新增 `content_hash`、`deduplicated`、`duplicate_of_frame_id`、session/scope/pixel/mask/comparison 元数据和显式物理引用。重复帧的 `duplicate_of_frame_id` 指向直接上一逻辑帧，但路径复用；首帧标记不可比较，不声称 changed。

**Rationale**: 当前 `ScreenFrame` 用路径隐式承担逻辑身份，无法表达 10 条逻辑采样共享一个文件。独立 id/time 是稳定性和审计的基础。

**Alternatives considered**:

- 命中时返回旧 `ScreenFrame`：丢失时间戳和步骤关联。
- 从相同路径推断重复：无法表达来源、范围或失败。
- 把阈值 diff 的 changed 当作严格相等：两者语义不一致。

## R6. 分组件缓存，每帧重新组装 StructuredScreen

**Decision**: OCR、template、diff、vision describe 分别缓存纯结果；只有当前帧已被严格相邻判等标记为 `deduplicated=true` 且 source 是直接上一逻辑帧时才允许 lookup，A→B→A 必须 miss。缓存值不含 frame id、captured_at、路径或完整 `StructuredScreen`。键包含组件/算法 revision、content hash、scope、pixel format、mask identity、感知配置 fingerprint，并按组件加入 OCR backend、模板集合内容 fingerprint、前后帧 identity、requested model/version、mode、prompt/schema 与 structured hint fingerprint。Planner、Grounder、Verifier 和带验证语义的回答不进入图片缓存；确定性路由以请求语义和完整上下文身份决定实际调用或 skip，操作后 Verifier 始终执行。

**Rationale**: 当前 `StructuredScreen` 同时包含内容结果与当前逻辑帧字段。整体复用会带入旧时间和路径；只用 content hash 又会跨 ROI、配置和模型版本误命中。

**Alternatives considered**:

- 缓存完整 `StructuredScreen`：污染逻辑上下文。
- 一个组合缓存键/结果包：不能分别计数，也降低部分命中能力。
- 缓存所有模型回答：会破坏独立验证关系。

## R7. 最近帧窗口固定上界，默认 5

**Decision**: `perception.cache_max_frames` 默认 5，配置校验为 3～5。窗口按最近逻辑 frame references 淘汰，不按任意 key 访问形成 LRU；连续 duplicate 为每个新逻辑帧登记对同一纯结果的轻量引用，因此 10 张相同帧不会在第 6 张重新分析。非相邻 unique 会关闭连续引用链。条目不持有 PNG bytes 或完整屏幕对象；重复帧共享上一不可变数组，逐出、run 结束和 session reset 均显式释放引用。

**Rationale**: Constitution 限制内存只保留最近 3～5 帧。现有 stability deque 默认 5，但 Pipeline 的 previous path 无会话生命周期；无界 content cache 不可接受。

**Alternatives considered**:

- 无界内容缓存：违反资源约束并增加跨上下文风险。
- 只留 hash 不留像素：无法执行碰撞后的严格比较。
- 按访问 LRU：热点旧帧可长期驻留，不符合“最近帧”。

## R8. 稳定性按逻辑帧计数，重复帧只短路像素工作

**Decision**: 每次 capture 都进入 `early_exit`、逻辑轨迹和稳定计数。重复帧确定性产生 unchanged 并增加一次 consecutive stable；唯一帧继续使用既有阈值 diff。保留 N 帧需要 N-1 次稳定转移的公式。

**Rationale**: 如果缓存命中跳过采样，`stable_frame_count=3` 无法达成；如果按同一路径重新 diff，又会无意义读盘。严格相等只是阈值稳定性的安全快路径，不替换其余稳定规则。

**Alternatives considered**:

- 重复帧不计数：违反验收。
- 缓存整个 WaitResult：丢失新观察。
- 所有稳定性都只看 content hash：改变既有阈值与动态遮罩语义。

## R9. 优化错误降级，安全持久化错误中止

**Decision**: hash、候选比较、cache get/put 异常记录 optimization failure，并按 unique/cache miss 进行安全持久化和完整分析，不增加命中、跳过或避免写入计数。有遮罩时 decode/遮罩编码失败以及任一必需物理写入失败均不返回成功帧，清理临时文件并进入既有确定性错误流程。vision best-effort 可降级，但必须记录失败测量。

**Rationale**: 优化故障不应扩大为运行失败；证据缺失或隐私失败则不能继续验证。现有 vision 异常被静默吞掉，无法诊断真实耗时和调用。

**Alternatives considered**:

- 所有异常继续：可能无证据验证或泄漏图片。
- 所有异常中止：优化故障域过大。
- 异常仍记命中/跳过：指标不可审计。

## R10. 追加式遥测事件与同源汇总

**Decision**: 新增 `StageMeasurement`、`CounterEvent`、`PhysicalImageEvent` 和从事件推导的 `PerformanceSummary`。monotonic clock 测 duration，UTC wall clock 记 started_at；completed/failed/cancelled/unavailable 明确区分，未知 duration 为 null。事件同时写入 TestRun 与 structlog JSON Lines，报告不另建计数器。上下文敏感实际调用另保存脱敏 request/response、request/context identity 及 run/step/frame/iteration 关联；skip 保存确定性规则与原因。

**Rationale**: 当前 `stage_durations_ms` 是每步骤字典，后续迭代覆盖同名阶段，也没有异常状态或 report build。追加事件能逐次关联 run/step/frame/iteration，并支持守恒检查。

**Alternatives considered**:

- 扩大原字典：仍不能表达重复调用与异常。
- 只存聚合值：无法审计。
- 从日志事后重算：报告与日志易漂移。

## R11. 报告零副本与明确 report_build 边界

**Decision**: ReportBuilder 验证显式 safe artifact purpose、run 安全根、文件存在和 mask identity 后直接引用，不修改 TestRun、不创建常规 `report_frames`。`report_build` 先测安全证据解析、基础 machine dict 与本地化 view-model 草稿组装；停止计时并追加 measurement 后，再执行无业务计算的 measurement 注入与不可变冻结。JSON/HTML 共用该唯一冻结视图；最终编码写盘另记可选 `report_output`。

**Rationale**: 当前 ReportBuilder 逐 iteration 复制并改写路径，且依赖目录名猜测安全性；JSON/HTML 分别调用 report dict 构建。将最终文件写入包含在自身报告的 report_build 会产生计时自引用。

**Alternatives considered**:

- 每个 iteration 复制：重复制品且修改运行记录。
- hardlink/symlink：仍新增制品入口并带来路径风险。
- 二次渲染报告以写入最终耗时：口径不清且额外开销。

## R12. JSON 增量扩展与集中本地化

**Decision**: 保持 feature 001 报告契约的原顶层/step/iteration 英文键、类型、枚举和语义，只新增 `frames`、`stage_measurements`、`performance_summary` 与可选 display 字段。新增 locale 资源注册表，默认 `zh-CN`；未知 locale 配置失败。Python 展示层生成 machine/display/css 三元信息，模板不翻译枚举或错误。UTF-8、`ensure_ascii=False` 与 HTML autoescape 为固定契约。

**Rationale**: 当前 HTML 文案和状态直接散落在模板中；JSON 是现有机器消费者接口。资源字典可完整覆盖并为未来语言扩展保留单一入口，同时不改变机器值。

**Alternatives considered**:

- 本地化 JSON 键或枚举：破坏消费者。
- 在 Jinja 中分散映射：难以覆盖和扩展。
- 未知 locale 静默回退：容易产生混合语言。

## R13. 测试以独立调用计数证明复用

**Decision**: 注入 `SpyOCR`、`SpyTemplateAnalyzer`、`SpyPlannerProvider`、`SpyGrounder`、`SpyVerifier` 与确定性时钟；调用次数及脱敏请求/响应审计在独立替身边界统计，并与 telemetry 汇总交叉核对。固定 PNG 与程序生成图片共同覆盖编码差异、单像素、碰撞、A→B→A 非相邻 miss、相同上下文 Planner skip、不同上下文实际调用和操作后 Verifier。性能门禁以工作量减少和多轮本地中位数为主，不依赖网络延迟。

**Rationale**: 网络耗时不能可靠证明调用是否发生；汇总指标自我断言也可能共同出错。现有 provider Protocol 与 OCR/模板函数边界可安全注入 Spy。

**Alternatives considered**:

- 根据 wall-clock 推断调用：受机器与网络抖动影响。
- 只断言 performance summary：缺少独立事实来源。
- 引入新 benchmark/snapshot 依赖：当前可用 pytest 与 golden 文件完成目标。

## R14. 两个互不相关场景共享同一契约

**Decision**: 使用 `generic-form-flow` 与 `generic-icon-menu-flow` 两个不同交互路径的离线场景，复用同一 capture→observe→act→verify→report 契约套件；场景数据只存在于 fixture，核心代码不得检查 fixture 标识或可见文本。

**Rationale**: 单一图片序列不能证明功能与场景无关。一个以键盘/文本输入为主、另一个以视觉目标/弹层为主，可覆盖不同执行路径而不向核心引入场景词汇。

**Alternatives considered**:

- 仅替换图片的同构参数化用例：独立性证据弱。
- 把场景词汇写入核心分类：违反 Constitution。
