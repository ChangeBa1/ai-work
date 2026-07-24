# Tasks: 截图去重、分析复用、性能可观测性与中文报告

**Input**: `specs/004-frame-dedup-observability/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 与 `quickstart.md`

**Tests**: 本功能强制测试先行。每个用户故事必须先完成对应 RED 任务并观察指定断言失败，再开始该故事的生产代码；验收不得依赖真实 VNC、在线模型或网络耗时。

**Organization**: 任务按用户故事组织。每条任务都给出仓库根目录相对路径、直接依赖与可独立执行的验收方法；所有 `uv` 命令均从 `vnc_agent/` 目录运行。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：修改不同文件，且不依赖尚未完成的同阶段任务，可并行执行
- **[Story]**：映射到 `spec.md` 中的 US1～US4
- **依赖**：完成该任务前必须完成的任务 ID；“无”表示可立即开始
- **验收**：该任务自身的独立完成判据或命令

---

## Phase 1: Setup（测试基础设施）

**Purpose**: 建立确定性 Spy、固定截图和快照工具，使后续测试能以调用次数和离线数据作为独立事实源。

- [X] T001 在 `vnc_agent/tests/support/frame_dedup_spies.py` 与 `vnc_agent/tests/support/__init__.py` 新增可注入的 SpyOCR、SpyTemplateAnalyzer、SpyVisionProvider、SpyPlannerProvider、SpyGrounder、SpyVerifier 和 DeterministicClock，所有替身记录调用身份、脱敏请求/响应、上下文、参数与次数且不访问网络（依赖：无；验收：在 `vnc_agent/` 执行 `uv run python -c "from tests.support.frame_dedup_spies import SpyOCR, DeterministicClock; assert SpyOCR().call_count == 0"` 成功）
- [X] T002 [P] 在 `vnc_agent/tests/fixtures/images/frame_dedup/generate_fixtures.py` 与 `vnc_agent/tests/fixtures/images/frame_dedup/README.md` 建立可重复生成的基准图、不同 PNG 编码同像素图、单像素变化图、ROI 图和遮罩图，分别记录 PNG bytes 的 `fixture_file_sha256` 与 `frame-pixels-v1` 的 `content_hash`（依赖：无；验收：连续执行两次 `uv run python tests/fixtures/images/frame_dedup/generate_fixtures.py --check` 均成功且工作树无新增差异，并证明不同编码可有不同 fixture_file_sha256 但相同 content_hash）
- [X] T003 [P] 在 `vnc_agent/tests/support/report_assertions.py` 新增稳定化时间、UUID、绝对路径的 HTML/JSON 快照辅助函数以及 DOM 可见文本提取器（依赖：无；验收：在 `vnc_agent/` 执行 `uv run python -c "from tests.support.report_assertions import normalize_report_snapshot"` 成功）
- [X] T004 [P] 在 `vnc_agent/pyproject.toml` 注册 `performance` pytest marker，并确保离线默认测试可排除真实 VNC/网络（依赖：无；验收：在 `vnc_agent/` 执行 `uv run pytest --markers` 可见 `performance` 且 `uv run pytest -q tests/unit/test_no_real_vnc_in_offline_tests.py` 通过）

**Checkpoint**: 后续测试可用固定输入、可控时钟和独立调用计数证明行为。

---

## Phase 2: Foundational（共享模型与配置）

**Purpose**: 先锁定逻辑帧、物理图片、遥测和配置契约；此阶段完成前不得开始用户故事实现。

### Tests first — RED

- [X] T005 [P] 在 `vnc_agent/tests/unit/test_frame_trace_models.py` 先编写失败测试，锁定 CaptureScope 的 `private_persistence_allowed`、PhysicalImageRef 的 `artifact_bundle_id`/实际文件 `artifact_sha256`/byte_size 与 manifest 一致性、ScreenFrame 的 `content_hash`、`deduplicated`、`duplicate_of_frame_id`、独立 frame id/timestamp、必需 safe 与可空 model_image 及 no-private 校验不变量，并禁止以 content_hash 代替 artifact_sha256（依赖：T001；验收：生产模型修改前执行 `uv run pytest -q tests/unit/test_frame_trace_models.py` 因缺少新字段/校验而失败，且失败原因与契约一致）
- [X] T006 [P] 在 `vnc_agent/tests/unit/test_frame_dedup_config.py` 先编写失败测试，锁定 `perception.cache_max_frames` 默认 5、仅允许 3～5，以及 `reporting.locale` 默认 `zh-CN`、未知 locale 拒绝加载（依赖：T001；验收：生产配置修改前执行 `uv run pytest -q tests/unit/test_frame_dedup_config.py` 因缺少配置而失败）
- [X] T007 [P] 在 `vnc_agent/tests/unit/test_telemetry_models.py` 先编写失败测试，锁定 StageMeasurement、CounterEvent、ModelCallAudit、PerformanceSummary 的稳定枚举、脱敏 request/response/context 关联、null duration、守恒错误和追加式序列化（依赖：T001；验收：生产模型修改前执行 `uv run pytest -q tests/unit/test_telemetry_models.py` 因缺少类型而失败）

### Shared implementation — GREEN

- [X] T008 在 `vnc_agent/src/vnc_agent/domain/observation.py` 实现带 `private_persistence_allowed` 的 CaptureScope、PhysicalImageRef、OptimizationError，并扩展 ScreenFrame/StructuredScreen 的哈希、去重、来源、比较、必需 safe/可空 model 引用及 no-private 不变量（依赖：T005；验收：`uv run pytest -q tests/unit/test_frame_trace_models.py` 通过）
- [X] T009 [P] 在 `vnc_agent/src/vnc_agent/runtime/telemetry.py` 定义 StageMeasurement、CounterEvent、ModelCallAudit、PerformanceSummary、规范阶段/状态枚举、脱敏审计字段与可注入时钟接口，但暂不接入业务边界（依赖：T007；验收：`uv run pytest -q tests/unit/test_telemetry_models.py` 通过且 failed/unavailable 不被序列化为 completed/0ms、审计不接受图片 bytes/凭据/private path）
- [X] T010 在 `vnc_agent/src/vnc_agent/domain/run.py` 为 TestRun 增加默认空的 `frames`、`stage_measurements`、`counter_events`、`model_call_audits` 与可空 `performance_summary`，保持现有 StepRecord/ActionIteration 字段和枚举不变（依赖：T008、T009；验收：`uv run pytest -q tests/unit/test_frame_trace_models.py tests/unit/test_telemetry_models.py tests/unit/test_report_status_consistency.py` 通过）
- [X] T011 [P] 在 `vnc_agent/src/vnc_agent/config.py` 增加感知缓存窗口和报告 locale 配置模型、3～5 范围校验及已登记 locale 校验入口（依赖：T006；验收：`uv run pytest -q tests/unit/test_frame_dedup_config.py` 通过）
- [X] T012 在 `vnc_agent/config/agent.yaml` 写入 `perception.cache_max_frames: 5` 与 `reporting.locale: zh-CN` 默认值且不改变现有键语义（依赖：T011；验收：`uv run pytest -q tests/unit/test_frame_dedup_config.py tests/fixtures/test_feature003_config.py` 通过）

**Checkpoint**: 共享数据契约和默认配置稳定，所有故事可在其上开发。

---

## Phase 3: User Story 1 — 连续截图只保存一次物理图片并保留每次逻辑采样（Priority: P1）🎯 MVP

**Goal**: 在同一 run/session 的严格相邻且同范围帧上做写盘前像素去重；每次捕获仍产生可审计逻辑帧，安全遮罩与稳定性语义不变。

**Independent Test**: 离线送入 10 张完全相同全屏图和第 11 张单像素变化图，应得到 11 个逻辑帧、2 个唯一帧、9 个重复帧和 2 个无掩码物理文件；ROI/范围/分辨率/格式/遮罩变化不去重，`stable_frame_count=3` 在第三次逻辑采样达成。

### Tests first — RED

- [X] T013 [P] [US1] 在 `vnc_agent/tests/unit/test_frame_pixel_identity.py` 先编写规范化单次解码、规范前像 `frame-pixels-v1 || width || height || canonical pixel_format || C-contiguous unmasked normalized pixel bytes` 的域分隔 SHA-256、不同 PNG 编码同像素、宽高/格式/单像素变化及注入 hash collision 后仍执行 `np.array_equal` 的失败测试（依赖：T002、T008；验收：实现前执行 `uv run pytest -q tests/unit/test_frame_pixel_identity.py` 因缺少像素身份实现而失败，测试不得用 PNG bytes 相等替代像素相等，且 capture kind/坐标/resolution/mask/private policy 只作为独立 scope/key 维度而不混入 content hash）
- [X] T014 [P] [US1] 在 `vnc_agent/tests/unit/test_artifact_store_dedup.py` 先编写 ArtifactStore Spy 测试，断言连续重复帧只提交一次无掩码文件；遮罩且允许 private 时 safe/private 与 manifest 位于同一 bundle 并经一次目录 rename 发布，禁止 private 时 bundle 只含 safe 且不记录 private avoided event；逐文件核对 byte_size、实际编码 bytes 的 artifact_sha256、共同 artifact_bundle_id 及 avoided count/bytes（依赖：T001、T008；验收：实现前执行 `uv run pytest -q tests/unit/test_artifact_store_dedup.py` 因重复写盘、逐个 final-file 发布、hash/manifest 不一致或违反 no-private 策略而失败）
- [X] T015 [P] [US1] 在 `vnc_agent/tests/fixtures/test_frame_dedup_sequence.py` 先编写固定截图离线序列测试，覆盖 10 张相同、第 11 张单像素变化、不同 full-screen/ROI 坐标、分辨率、像素格式、mask identity、private 持久化权限、run、session 和非相邻帧不得误去重（依赖：T001、T002、T008；验收：实现前执行 `uv run pytest -q tests/fixtures/test_frame_dedup_sequence.py` 至少在物理文件数与边界隔离断言上失败）
- [X] T016 [P] [US1] 在 `vnc_agent/tests/fixtures/test_stability_deduplicated_frames.py` 先编写 `stable_frame_count=3`、活动 StabilityEngine 等待中的每个逻辑采样调用该等待的 early_exit、重复帧 `changed_since_last=false` 和唯一阈值 diff 保持原语义的失败测试；另断言普通观察、重试、恢复和操作后验证帧虽进入全局轨迹但不增加该等待计数、不触发其 callback（依赖：T001、T002、T008；验收：实现前执行 `uv run pytest -q tests/fixtures/test_stability_deduplicated_frames.py` 因重复等待帧未累计或非等待帧污染稳定状态而失败）
- [X] T017 [P] [US1] 在 `vnc_agent/tests/unit/test_capture_fallback.py`、`vnc_agent/tests/unit/test_artifact_persistence_failure.py` 与 `vnc_agent/tests/unit/test_cli_capture_service_wiring.py` 先编写失败测试：decode/规范化失败中止采集且不生成 ScreenFrame/分析/验证，hash/compare 异常仅在像素可用后安全降级，mask encode fail-closed；分别注入第二个文件写入、file/dir sync、bundle rename、bundle 发布后逻辑记录失败和模拟重启孤儿恢复，断言无半组 final 文件、无成功 frame、staging 被清理、published orphan 被整体隔离并有 recovery audit，no-private 回退不产生未遮罩文件；另以 factory/VNC Spy 锁定 execute 只创建一个共享 FrameCaptureService，而离线/部分失败/兼容 report 的 capture-service factory/VNC 调用均为 0、TestRun.frames 不增加（依赖：T001、T008；验收：实现前执行 `uv run pytest -q tests/unit/test_capture_fallback.py tests/unit/test_artifact_persistence_failure.py tests/unit/test_cli_capture_service_wiring.py` 因缺少 decode 中止、事务发布/恢复、隐私门禁或装配隔离而失败）

### Implementation — GREEN

- [X] T018 [US1] 在 `vnc_agent/src/vnc_agent/perception/screenshot.py` 实现 DecodedCapture、只读 C-contiguous 规范化像素、稳定 pixel format 与写盘前版本化规范前像 SHA-256，并让同一 ndarray 供 `np.array_equal` 和下游分析使用以避免重复解码（依赖：T013；验收：`uv run pytest -q tests/unit/test_frame_pixel_identity.py` 通过并由 decode Spy 证明每次 capture 只解码一次，content hash 前像逐字段符合 data-model.md）
- [X] T019 [US1] 在 `vnc_agent/src/vnc_agent/storage/artifact_store.py` 实现 FrameArtifactBundle：在 final run 根同文件系统的 staging 目录写入 safe、策略可选 private 和 manifest，计算每个最终编码文件的 byte_size/artifact_sha256，完成 file+directory sync 后以一次目录 rename 发布；实现发布前 staging 清理、发布后逻辑失败整包隔离，以及启动/恢复时按 manifest 与 TestRun refs 对账的 orphan recovery audit。`private_persistence_allowed=false` 时不得接受或生成 private bytes/path/event，禁止根据目录名推断安全性（依赖：T014、T017、T018；验收：`uv run pytest -q tests/unit/test_artifact_store_dedup.py tests/unit/test_artifact_persistence_failure.py` 的唯一写入、no-private、单次发布、第二文件/sync/rename/逻辑提交失败和模拟重启恢复断言全部通过）
- [X] T020 [US1] 在 `vnc_agent/src/vnc_agent/perception/screenshot.py` 实现 run/session 级 FrameCaptureService 与唯一逻辑帧 recorder：只比较全局上一逻辑帧，按包含 private 权限的完整 scope→hash→逐像素门禁裁决，重复帧创建新 id/time/sequence、只复用策略允许且 manifest/reference 有效的 PhysicalImageRef；严格执行“unique bundle 单次发布或 duplicate 引用校验 → 不可变逻辑帧持久化并追加 TestRun.frames → 返回调用方”的顺序，逻辑提交失败调用整包隔离（依赖：T018、T019；验收：`uv run pytest -q tests/fixtures/test_frame_dedup_sequence.py tests/unit/test_artifact_store_dedup.py tests/unit/test_artifact_persistence_failure.py` 通过，故障注入证明任一步在逻辑提交前失败均无成功 frame/可报告 orphan，且 Pipeline/StabilityEngine 均不能绕过 recorder）
- [X] T021 [US1] 在 `vnc_agent/src/vnc_agent/perception/pipeline.py` 注入 FrameCaptureService，移除遮罩分支的重复 StructuredScreen assembly/路径重读和调用方自行追加 frames 的逻辑，统一消费 recorder 已登记的 ScreenFrame（依赖：T020；验收：`uv run pytest -q tests/fixtures/test_frame_dedup_sequence.py tests/fixtures/test_screenshot.py` 通过且 10 次 capture 只产生 10 条、不重不漏的逻辑记录）
- [X] T022 [US1] 在 `vnc_agent/src/vnc_agent/perception/stability.py` 改为消费 recorder 已登记且 capture_source 属于当前活动等待的共享逻辑帧；该等待的 duplicate 快路径累计稳定转移且不重读文件，unique 保留既有阈值 diff、动态遮罩与 `stable_frame_count - 1` 公式，其他来源只保留全局轨迹、不得改变该等待局部状态（依赖：T016、T020；验收：`uv run pytest -q tests/fixtures/test_stability_deduplicated_frames.py tests/fixtures/test_stability.py` 通过，JSON 轨迹包含全部来源但 stable count/early_exit 调用只对应当前等待采集）
- [X] T023 [US1] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 管理 capture run/session 生命周期：加载 TestRun 引用后、任何新 capture 前调用 ArtifactStore bundle recovery，清理 staging、隔离无引用 published bundle并追加 recovery audit；connect 后启动，reconnect 后再次对账、旋转 session 并清空 previous，disconnect/run 结束时释放，不改变确定性状态机和 Observe→Act→Verify 顺序（依赖：T021、T022；验收：`uv run pytest -q tests/unit/test_artifact_persistence_failure.py tests/fixtures/test_frame_dedup_sequence.py tests/integration/test_execution.py` 通过，模拟重启时 recovery 先于 capture，跨 session 首帧不去重且 report-only CLI 不触发恢复写入）
- [X] T024 [US1] 在 `vnc_agent/src/vnc_agent/api/cli.py` 仅为 execute 路径装配一个 FrameCaptureService 实例并共享给 ObservationPipeline/StabilityEngine；离线/部分失败/兼容 report 路径只需在本阶段保持既有报告依赖，明确不得创建、连接或注入 capture service，完整 locale/frozen view/safe resolver/renderer 装配留给 T059（依赖：T012、T017、T023；验收：`uv run pytest -q tests/unit/test_cli_capture_service_wiring.py tests/integration/test_execution.py tests/e2e/test_scenario_06_wait_dynamic.py` 通过，测试替身观察到 execute 两个消费者共享同一 capture sequence，且各 report-only 入口 capture-service factory/VNC 调用均为 0、TestRun.frames 不增加）
- [X] T025 [US1] 在 `vnc_agent/tests/fixtures/test_frame_dedup_sequence.py` 补齐 US1 GREEN 守恒断言：未遮罩 10 identical→10 logical/1 unique/9 duplicate/1 physical、像素变化→第 2 physical、duplicate_of 指向直接上一逻辑帧、独立时间戳且同一安全路径；分别证明观察、等待、重试、恢复、操作后验证五类采集以全局 sequence 进入同一 recorder，失败尝试以可关联 measurement/counter/log 留痕，且 no-private 场景没有未遮罩文件（依赖：T020、T024；验收：`uv run pytest -q tests/fixtures/test_frame_dedup_sequence.py tests/fixtures/test_stability_deduplicated_frames.py tests/unit/test_capture_fallback.py tests/unit/test_artifact_persistence_failure.py` 全部通过，并按 capture_source 集合精确等于五类来源）

**Checkpoint**: US1 可独立交付为 MVP；物理去重不减少逻辑采样、不跨边界且不泄露未遮罩图。

---

## Phase 4: User Story 2 — 完全相同图片复用内容分析而不绕过独立验证（Priority: P1）

**Goal**: 复用 OCR、模板、diff、vision describe 的纯内容结果，每个逻辑帧重新组装 StructuredScreen，同时 Planner、Grounder、Verifier 和不同语义问题仍独立执行。

**Independent Test**: 10 个重复逻辑帧使 OCR/template/describe_screen 各只实际调用 1 次；第 11 个单像素变化重新调用。相同画面但不同 step intent 或 visual_question 必须分别验证，操作前后画面相同不得自动通过。

### Tests first — RED

- [X] T026 [P] [US2] 在 `vnc_agent/tests/unit/test_analysis_cache_keys.py` 先编写缓存键与 lookup 资格失败测试，覆盖当前帧必须 `deduplicated=true` 且 source 为直接上一逻辑帧、full-screen/ROI 类型与坐标、分辨率、pixel format、mask/private 权限、感知配置、OCR backend/version、模板集合 fingerprint、diff 前后帧/阈值及 vision 请求 model/version/prompt/schema/hint（依赖：T001、T008；验收：实现前执行 `uv run pytest -q tests/unit/test_analysis_cache_keys.py` 因缺少完整键或相邻资格门禁而失败）
- [X] T027 [P] [US2] 在 `vnc_agent/tests/unit/test_analysis_cache_window.py` 先编写容量 3 和 5、最近逻辑 frame references 非访问 LRU 淘汰、10 个连续 duplicate 只保留一份结果且不重调、non-adjacent unique 关闭引用链、run/session reset 以及 weakref 释放的失败测试（依赖：T001、T008；验收：实现前执行 `uv run pytest -q tests/unit/test_analysis_cache_window.py` 因缺少有界引用生命周期而失败）
- [X] T028 [P] [US2] 在 `vnc_agent/tests/fixtures/test_structured_screen_cache_reuse.py` 先编写仅相邻 `deduplicated=true` 帧复用组件结果但创建新 StructuredScreen、保留当前 frame id/time/path、analysis_source_refs 和 deterministic diff=false 的失败测试，并断言 unique 帧绝不 lookup（依赖：T001、T002、T025；验收：实现前执行 `uv run pytest -q tests/fixtures/test_structured_screen_cache_reuse.py` 因复用旧对象、重复分析或跨 unique lookup 而失败）
- [X] T029 [P] [US2] 在 `vnc_agent/tests/fixtures/test_analysis_call_counts.py` 先用 Spy 独立统计 10 identical + 1 changed 序列中 OCR、template、describe_screen 实际调用数为 2、前 9 次各命中 9，并断言 A→B→A 第三帧重新调用且不以耗时或报告计数自证；同时在 `vnc_agent/tests/fixtures/test_ocr.py`、`vnc_agent/tests/fixtures/test_template_matching.py`、`vnc_agent/tests/fixtures/test_screen_diff.py` 分别新增 ndarray 入口、身份字段及不二次解码的隔离 RED 用例，供 T034–T036 独立转绿（依赖：T001、T002、T025；验收：实现前分别运行 `uv run pytest -q tests/fixtures/test_ocr.py -k ndarray`、`uv run pytest -q tests/fixtures/test_template_matching.py -k ndarray`、`uv run pytest -q tests/fixtures/test_screen_diff.py -k ndarray` 和完整 `test_analysis_call_counts.py`，均因对应入口/复用尚未实现而失败）
- [X] T030 [P] [US2] 在 `vnc_agent/tests/unit/test_context_sensitive_cache_guards.py` 先编写角色专属确定性决策矩阵失败测试：Planner 身份覆盖请求语义、step intent、动作/历史、重试/迭代、StructuredScreen、请求模型/配置和路由状态；Grounder 覆盖目标语义、候选/StructuredScreen、scope/坐标变换、模型/配置和定位状态；Verifier 覆盖 `visual_question`/断言、前后 frame、动作审计/ActionEffect、重试/迭代和模型/配置。逐字段变化或缺失时禁止 reuse/同一身份 skip，角色适用时必须实际调用；角色不适用仍由确定性路由记录，语义及完整 Planner 身份相同且无需新计划时记录 skip，每个操作后 Verifier 始终实际执行（依赖：T001、T008；验收：实现前执行 `uv run pytest -q tests/unit/test_context_sensitive_cache_guards.py` 因任一身份字段隔离、路由适用性、Planner skip 或独立 Verifier 未实现而失败）
- [X] T031 [P] [US2] 在 `vnc_agent/tests/fixtures/test_action_effect.py` 增加操作前后像素完全相同且分析命中的回归用例，锁定 ActionEffect/Verifier 仍产生现有 `no_effect`、`failed` 或 `uncertain` 而非自动 `passed`（依赖：T001、T025；验收：实现前执行 `uv run pytest -q tests/fixtures/test_action_effect.py` 新用例失败且既有用例仍通过）
- [X] T032 [P] [US2] 在 `vnc_agent/tests/unit/test_analysis_cache_fallback.py` 先编写 cache key/get/put/eviction 异常均按 miss 做完整分析、不得增加 hit/skipped/avoided 且当前结果仍可使用的失败测试（依赖：T001、T009；验收：实现前执行 `uv run pytest -q tests/unit/test_analysis_cache_fallback.py` 因缺少异常回退而失败）

### Implementation — GREEN

- [X] T033 [US2] 在 `vnc_agent/src/vnc_agent/perception/cache.py` 实现严格相邻 duplicate eligibility、稳定 canonical AnalysisCacheKey、分组件不可变结果条目、hash collision 内容身份校验、3～5 最近逻辑引用窗口、non-adjacent 链终止和 clear/reset 释放引用（依赖：T026、T027；验收：`uv run pytest -q tests/unit/test_analysis_cache_keys.py tests/unit/test_analysis_cache_window.py` 通过且 10 duplicate 只分析一次、A→B→A 必 miss）
- [X] T034 [P] [US2] 在 `vnc_agent/src/vnc_agent/perception/ocr/engine.py` 增加接受已解码 ndarray 的 OCR 入口，路径 API 仅保留为离线兼容 wrapper，并暴露 backend/version/language/preprocess identity（依赖：T018、T026、T029；验收：仅执行隔离用例 `uv run pytest -q tests/fixtures/test_ocr.py -k ndarray` 通过且 decode Spy 不出现二次解码；完整缓存调用次数留给 T038）
- [X] T035 [P] [US2] 在 `vnc_agent/src/vnc_agent/perception/template/matcher.py` 增加接受已解码 ndarray 的模板入口与模板集合内容 fingerprint，不以文件路径/mtime 作为唯一身份（依赖：T018、T026、T029；验收：仅执行隔离用例 `uv run pytest -q tests/fixtures/test_template_matching.py -k ndarray` 通过并精确核对模板集合 fingerprint；完整缓存调用次数留给 T038）
- [X] T036 [P] [US2] 在 `vnc_agent/src/vnc_agent/perception/screen_diff.py` 增加 ndarray diff 入口和完整前后帧/threshold/dynamic-mask identity，exact duplicate 返回 ratio=0、空 regions/blobs 且不读盘（依赖：T018、T026、T029；验收：仅执行隔离用例 `uv run pytest -q tests/fixtures/test_screen_diff.py -k ndarray` 通过且路径读取 Spy 为 0；StructuredScreen 集成留给 T037）
- [X] T037 [US2] 在 `vnc_agent/src/vnc_agent/perception/structured_screen.py` 将组件计算与组装分离，使每个 ScreenFrame 都新建 StructuredScreen，并只从缓存纯结果复制 OCR/template/diff/vision 值和来源引用（依赖：T028、T034、T035、T036；验收：`uv run pytest -q tests/fixtures/test_structured_screen_cache_reuse.py` 通过且对象身份、frame id、时间戳均不同）
- [X] T038 [US2] 在 `vnc_agent/src/vnc_agent/perception/pipeline.py` 仅为 recorder 标记的严格相邻 duplicate 接入组件缓存与 requested model identity，unique/A→B→A 直接完整分析；分别记录 hit/miss/actual invocation，hash 为空或缓存异常走完整分析，禁止缓存完整 StructuredScreen（依赖：T029、T032、T033、T037；验收：`uv run pytest -q tests/fixtures/test_analysis_call_counts.py tests/unit/test_analysis_cache_fallback.py` 通过）
- [X] T039 [US2] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 实现 T030 的 Planner/Grounder/Verifier 角色专属 canonical request/context identity 与确定性适用性矩阵：任一必需字段变化/缺失禁止复用或同一身份 skip，角色适用时执行实际调用；完整 Planner 身份相同且无需新计划时记录 skip，每个操作后 Verifier 始终执行。实际调用保存脱敏 request/response/context audit 并关联 run/step/frame/iteration，不用图片缓存替代操作后观察（依赖：T030、T031、T038；验收：`uv run pytest -q tests/unit/test_context_sensitive_cache_guards.py tests/fixtures/test_action_effect.py tests/e2e/test_scenario_04_verify_gate.py` 通过，三角色逐字段矩阵与 Spy/审计一一对应）
- [X] T040 [US2] 在 `vnc_agent/tests/fixtures/test_analysis_call_counts.py` 补齐 US2 GREEN 断言和 Spy/缓存/模型审计交叉核对，证明前 10 张 OCR/template/describe_screen 各 1 次、第 11 张各第 2 次、A→B→A 第三帧重调；不同上下文实际调用、相同上下文 Planner skip、操作后 Verifier 实际调用均有完整来源记录（依赖：T038、T039；验收：`uv run pytest -q tests/fixtures/test_analysis_call_counts.py tests/unit/test_context_sensitive_cache_guards.py tests/fixtures/test_structured_screen_cache_reuse.py tests/fixtures/test_action_effect.py` 全部通过）

**Checkpoint**: US2 可独立证明内容分析节省，同时 Observe→Act→Verify 和 no-effect 语义保持。

---

## Phase 5: User Story 3 — 分阶段性能诊断与可核对的运行度量（Priority: P2）

**Goal**: 以同一追加式事件源记录所有规定阶段的真实耗时、去重/写盘/缓存/模型调用计数，并在异常时明确标记数据不完整。

**Independent Test**: 对包含 unique、duplicate、cache hit、真实 provider 调用和注入异常的固定负载，结构化日志、TestRun、JSON 与 HTML 的事件/汇总一致，守恒成立且 failed/unavailable 阶段没有伪造 0ms。

### Tests first — RED

- [X] T041 [P] [US3] 在 `vnc_agent/tests/unit/test_performance_metrics.py` 先编写所有要求计数、`dedup_ratio` 零分母、safe/private/report_copy 分类、avoided bytes 依据、cache hits、analysis/model/skipped calls 和守恒错误的失败测试；另断言 physical_image_written 只与成功逻辑帧同一 TestRun 更新提交，staging/quarantined/orphan 仅有失败/recovery audit 且不计 physical_image_count（依赖：T009、T025、T040；验收：实现前执行 `uv run pytest -q tests/unit/test_performance_metrics.py` 因缺少事件汇总或错误计入 orphan 而失败）
- [X] T042 [P] [US3] 在 `vnc_agent/tests/unit/test_stage_timings.py` 先用 DeterministicClock 编写 capture、pixel_hash、persistence、OCR、template、vision、planner、grounder、verification、report_build 追加测量及 completed/failed/cancelled/unavailable 语义失败测试；另覆盖可选 `report_output` 编码/原子写盘失败保留真实 duration、无成功路径且不改写既有事实（依赖：T001、T009；验收：实现前执行 `uv run pytest -q tests/unit/test_stage_timings.py` 因阶段未埋点、异常被记 0ms 或输出失败被伪装成功而失败）
- [X] T043 [P] [US3] 在 `vnc_agent/tests/integration/test_telemetry_structured_logging.py` 先编写同一事件对象进入 TestRun 与 structlog JSON Lines、带 run/step/frame/iteration 关联的失败测试；失败 capture attempt 必须带 source/attempt/time/error/duration 和状态/重试/恢复引用，artifact bundle recovery 必须带 bundle/manifest/ref 对账与隔离结果，实际上下文模型调用必须保留脱敏 request/response/context identity，skip 保留规则/原因，且不得泄漏图片 bytes、凭据或私有路径（依赖：T001、T009；验收：实现前执行 `uv run pytest -q tests/integration/test_telemetry_structured_logging.py` 因日志与运行轨迹不同源、失败/恢复尝试不可关联或模型审计不完整而失败）

### Implementation — GREEN

- [X] T044 [US3] 在 `vnc_agent/src/vnc_agent/runtime/telemetry.py` 实现 context-manager/async 边界测量、append-only 事件收集、真实 invocation/hit/skip/write/dedup/recovery 事件与从事件和 frames 推导的 PerformanceSummary 守恒检查；只接受随成功逻辑帧同一 TestRun 更新提交且属于 referenced bundle 的 physical event（依赖：T041、T042；验收：`uv run pytest -q tests/unit/test_performance_metrics.py tests/unit/test_stage_timings.py` 通过，orphan 不进入成功计数）
- [X] T045 [US3] 在 `vnc_agent/src/vnc_agent/perception/screenshot.py`、`vnc_agent/src/vnc_agent/storage/artifact_store.py` 和 `vnc_agent/src/vnc_agent/perception/pipeline.py` 接入 capture/pixel_hash/persistence/OCR/template/vision 测量及 dedup/cache/physical 计数，异常保留已观测 duration/status（依赖：T044、T020、T038；验收：`uv run pytest -q tests/unit/test_stage_timings.py tests/unit/test_performance_metrics.py tests/fixtures/test_analysis_call_counts.py` 通过且各事件与 Spy 次数相等）
- [X] T046 [US3] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 对实际 Planner、Grounder、verification provider 边界分别计时并在请求进入时计真实 model call，即使请求随后失败；把脱敏 request/response/request-context identity 和 actual/skipped outcome 写入同源审计，保留原 `stage_durations_ms` 语义（依赖：T044、T039；验收：`uv run pytest -q tests/unit/test_stage_timings.py tests/unit/test_context_sensitive_cache_guards.py tests/integration/test_telemetry_structured_logging.py` 通过且状态驻留时间不冒充 provider 时间）
- [X] T047 [US3] 在 `vnc_agent/src/vnc_agent/logging_setup.py` 让规范 `stage_measurement`、`frame_dedup_decision`、`analysis_cache_event`、`model_call_event`、`physical_image_event`、`artifact_bundle_recovery`、`performance_summary` 事件以稳定 JSON Lines 输出并执行敏感字段过滤（依赖：T043、T044；验收：`uv run pytest -q tests/integration/test_telemetry_structured_logging.py` 通过）
- [X] T048 [US3] 在 `vnc_agent/src/vnc_agent/reporting/report_builder.py` 实现无自引用两阶段 `report_build`：计时安全证据解析与 machine/localized 草稿，结束并追加 measurement 后只注入该 measurement 并冻结唯一共享视图；最终编码/原子写盘单列 `report_output`，失败时无成功路径、不改写既有事实且不复制证据回退（依赖：T042、T044；验收：`uv run pytest -q tests/unit/test_stage_timings.py -k "report_build or report_output"` 通过，当前报告包含自身真实 measurement 且无二次事实计算/渲染）
- [X] T049 [US3] 在 `vnc_agent/tests/performance/test_frame_dedup_performance.py` 建立固定数组、Spy、warm-up 和多轮中位数测试；主门禁断言 100 identical 只有 1 组策略允许的物理写入与 1 次各内容分析，并核对 report_build 自身 measurement、模型审计、阶段完整性/计数守恒而不使用网络绝对耗时（依赖：T045、T046、T047、T048；验收：`uv run pytest -q -m performance tests/performance/test_frame_dedup_performance.py` 可重复通过）

**Checkpoint**: US3 的每个汇总值都可追溯到逻辑帧或追加事件，异常不会伪造性能数据。

---

## Phase 6: User Story 4 — 获取完整、清晰且机器兼容的中文测试报告（Priority: P2）

**Goal**: HTML 默认完整显示简体中文，机器枚举/CSS/JSON 老契约稳定；同一安全证据零副本引用，中文及错误详情以 UTF-8 正确输出。

**Independent Test**: 对固定 TestRun 生成 HTML/JSON，DOM 和完整快照覆盖主要标签/状态/错误/性能摘要；非路径旧 JSON 投影逐字段相等，旧前后路径字段解析为可读取且 physical identity/content hash 等价的 safe evidence，重复证据路径相同且 `report_frames` 无新增 PNG。

### Tests first — RED

- [X] T050 [P] [US4] 在 `vnc_agent/tests/unit/test_reporting_resources.py` 先编写 `zh-CN` 资源完整性测试，覆盖标题、用例、状态、时间、步骤、迭代、验证、动作效果、失败、恢复、证据、前置条件、动作审计、性能、空值、证据错误及全部稳定 status/error code（依赖：T003、T012；验收：实现前执行 `uv run pytest -q tests/unit/test_reporting_resources.py` 因缺少集中资源注册表而失败）
- [X] T051 [P] [US4] 在 `vnc_agent/tests/fixtures/test_reporting_localization.py` 与 `vnc_agent/tests/snapshots/report_zh_cn.html` 先编写完整 HTML 快照/DOM 失败测试，断言除原始 code/detail、明确 machine enum/data marker、模型/provider/产品标识和诊断必需路径片段白名单外，全部静态 UI/帮助/状态/错误说明无遗漏英文；machine CSS/data-status 稳定、`lang=zh-CN`、charset 与 autoescape 正确（依赖：T003、T010；验收：实现前执行 `uv run pytest -q tests/fixtures/test_reporting_localization.py` 因英文模板、白名单外文本或缺少快照而失败）
- [X] T052 [P] [US4] 在 `vnc_agent/tests/fixtures/test_json_report_compatibility.py`、`vnc_agent/tests/support/legacy_report_consumer.py` 与 `vnc_agent/tests/snapshots/report_legacy_projection.json` 先编写递归旧投影及代表性旧消费者/旧 schema 兼容失败测试，逐层锁定旧英文键、required/optional、类型、enum、null/缺省、数组顺序、status 聚合与非路径 steps/iterations 值不变；`before_frame_path`/`after_frame_path` 单独锁定字段/类型/null、可读取性、safe purpose、前后关联和解析后的 physical id/content hash 等价，不要求旧 `report_frames` 文本值相等（依赖：T003、T010；验收：实现前执行 `uv run pytest -q tests/fixtures/test_json_report_compatibility.py` 因缺少允许的增量字段、非路径投影破坏、路径证据不等价或旧消费者解析失败而失败）
- [X] T053 [P] [US4] 在 `vnc_agent/tests/fixtures/test_report_utf8_errors.py` 先编写中文用例名、资源字典、已知/未知错误 code+原 detail、HTML 特殊字符、JSON `ensure_ascii=False` 的 UTF-8 落盘再读取逐码点测试，并分别注入 U+FFFD、字符丢失、错误 HTML/JSON 转义负例（依赖：T003、T010；验收：实现前执行 `uv run pytest -q tests/fixtures/test_report_utf8_errors.py` 因未本地化、编码/转义不符或未识别任一负例而失败）
- [X] T054 [P] [US4] 在 `vnc_agent/tests/fixtures/test_report_safe_evidence_dedup.py` 先编写重复逻辑证据共享同一 safe physical path 的参数化失败测试，覆盖正常执行、离线重建、部分失败报告和兼容 CLI/旧入口：report 构建只允许追加契约规定的 `report_build` measurement，不得改写既有运行事实或创建 copy/hardlink/symlink；分别注入 private、越界、缺失、截断、随机损坏、byte-size mismatch、artifact_sha256 mismatch、不可解码、mask mismatch、staging/quarantined/orphan bundle，断言均显示本地化不可用且不生成链接/不回退 private；no-private 帧的 model_image=null 且机器/HTML 报告均无未遮罩路径（依赖：T019、T025、T048；验收：实现前执行 `uv run pytest -q tests/fixtures/test_report_safe_evidence_dedup.py` 因任一入口复制文件、改写事实、漏检完整性/事务状态或 private 泄漏而失败）

### Implementation — GREEN

- [X] T055 [US4] 在 `vnc_agent/src/vnc_agent/reporting/localization.py` 实现 locale registry、完整 `zh-CN` 资源包、machine/display/css 三元展示值和已知/未知错误本地化，模板之外集中所有翻译逻辑（依赖：T050；验收：`uv run pytest -q tests/unit/test_reporting_resources.py` 通过且未知 locale/缺键在配置或构建时明确失败）
- [X] T056 [US4] 在 `vnc_agent/src/vnc_agent/reporting/report_builder.py` 实现 safe evidence purpose/run-root/referenced-bundle/manifest/path/existence/mask identity/byte_size/artifact_sha256 校验及图片可解码性检查；仅完整匹配时生成零副本相对链接，多逻辑证据引用同一 physical id，任何缺失、损坏、hash mismatch、不可解码或 orphan 状态均本地化为不可用且不创建或回退到 private/report_copy（依赖：T048、T054、T055；验收：`uv run pytest -q tests/fixtures/test_report_safe_evidence_dedup.py tests/fixtures/test_report_builder.py` 通过且所有负例无链接、报告目录无新增 evidence PNG）
- [X] T057 [US4] 在 `vnc_agent/src/vnc_agent/reporting/json_report.py` 保持原 machine dict 非路径字段逐层投影（含 null/缺省、数组顺序和聚合）不变，将旧 `before_frame_path`/`after_frame_path` 从冻结 view 解析为通过 T056 完整性门禁的 safe physical path，并仅追加按 sequence 排序且含 `safe_artifact_sha256`/`artifact_bundle_id` 的 `frames`、`stage_measurements`、`performance_summary` 及可选 display 字段；frames 必须分别覆盖五类 recorder 来源，永不输出 private path，证据不可用时保持旧字段 null/缺省契约并给出兼容增量诊断（依赖：T041、T048、T052、T056；验收：`uv run pytest -q tests/fixtures/test_json_report_compatibility.py tests/fixtures/test_report_safe_evidence_dedup.py tests/fixtures/test_frame_dedup_sequence.py` 通过，旧消费者业务结果相等且有效旧路径解析为同一预期 safe physical identity）
- [X] T058 [US4] 在 `vnc_agent/src/vnc_agent/reporting/html_report.py` 使用 autoescape Jinja 环境和 localized view-model 渲染全部简体中文可见标签/状态/错误/性能摘要，保留稳定 machine CSS/data marker 并以 UTF-8 写出（依赖：T051、T053、T055、T056、T057；验收：`uv run pytest -q tests/fixtures/test_reporting_localization.py tests/fixtures/test_report_utf8_errors.py` 通过且模板中不存在 enum/error 翻译分支）
- [X] T059 [US4] 在 `vnc_agent/src/vnc_agent/api/cli.py` 将 `reporting.locale` 传给 execute、离线 report、部分失败 report 和兼容入口，并确保所有路径共同使用冻结 report view 与同一 safe zero-copy resolver，同时保持 T024 的 report-only 零 capture-service 装配边界（依赖：T012、T024、T058；验收：`uv run pytest -q tests/unit/test_cli_capture_service_wiring.py tests/fixtures/test_reporting_localization.py tests/fixtures/test_report_safe_evidence_dedup.py tests/integration/test_execution.py` 通过且所有入口输出 `lang="zh-CN"`、report_copy=0，report-only 入口 capture/VNC 调用仍为 0）
- [X] T060 [US4] 在 `vnc_agent/tests/snapshots/report_zh_cn.html` 与 `vnc_agent/tests/snapshots/report_legacy_projection.json` 审核并提交稳定 golden，确认所有主要标签中文化、原始机器值仍存在、错误详情未丢失且重复证据只有一个路径（依赖：T057、T058、T059；验收：删除 pytest 缓存后连续两次执行 `uv run pytest -q tests/fixtures/test_reporting_localization.py tests/fixtures/test_json_report_compatibility.py tests/fixtures/test_report_utf8_errors.py tests/fixtures/test_report_safe_evidence_dedup.py` 均无快照漂移）

**Checkpoint**: US4 的 HTML 完整中文化，JSON 与既有消费者兼容，报告证据安全且零副本。

---

## Phase 7: Polish & Cross-Cutting Concerns（契约、跨场景与文档）

**Purpose**: 完成持久化、跨场景、业务无关、性能和文档门禁，形成可直接交付的全链路证据。

- [X] T061 [P] 在 `vnc_agent/tests/integration/test_frame_trace_repository.py` 覆盖 TestRun 中五类 frames、失败 capture attempt、共享 PhysicalImageRef 的 artifact_bundle_id/artifact_sha256/byte_size/manifest identity、可空 model_image、独立时间戳、duplicate relation、bundle recovery audit、stage measurements、counter events、脱敏模型 audits 和 summary 的 SQLite JSON payload 往返（依赖：T010、T057；验收：`uv run pytest -q tests/integration/test_frame_trace_repository.py` 通过，五类 capture_source、失败 attempt、物理完整性字段及 recovery audit 逐项相等且无需数据库表迁移）
- [X] T062 [P] 在 `vnc_agent/tests/e2e/test_frame_dedup_cross_scenario.py` 与 `vnc_agent/tests/fixtures/testcases/generic-form-flow.yaml`、`vnc_agent/tests/fixtures/testcases/generic-icon-menu-flow.yaml` 建立两个互不相关 GUI 流程的同一 capture→observe→act→verify→report 契约测试：前者使用表单式可见结构与键盘/文本输入主路径，后者使用图标/弹层结构与视觉目标主路径；两者都保留独立操作后验证证据，场景词汇仅存在于 fixture，拒绝仅换名称/图片的同构替身（依赖：T025、T040、T049、T060；验收：`uv run pytest -q tests/e2e/test_frame_dedup_cross_scenario.py` 通过，测试只依据固定 VNC 截图的可见布局 fingerprint、声明式 fixture 元数据与主要 action-kind 集合证明结构/交互不同，显式断言未调用 UIA、浏览器 DOM、进程/文件系统或被测应用内部接口，再核对全部 recorder 来源、A→B→A miss、上下文调用/skip、操作后 Verifier、模型审计、no-private 和报告）
- [X] T063 [P] 扩展 `vnc_agent/tests/unit/test_no_business_keywords_in_core.py`，扫描 feature 004 修改的 domain/runtime/perception/reporting/config 核心模块，拒绝用户禁止的场景专用关键词或基于 fixture id/可见文本的分支（依赖：T025、T040、T060；验收：`uv run pytest -q tests/unit/test_no_business_keywords_in_core.py` 通过且对注入禁词的临时样本能失败）
- [X] T064 [P] 更新 `vnc_agent/README.md`，说明严格像素去重边界、逻辑/物理帧差异、缓存安全、性能摘要、中文报告、离线验收命令和安全回退（依赖：T049、T060；验收：README 中的所有命令可复制执行，且 `rg -n "cache_max_frames|reporting.locale|performance_summary" README.md` 从 `vnc_agent/` 返回匹配）
- [X] T065 [P] 更新 `vnc_agent/config/README.md`，记录 `perception.cache_max_frames` 的 3～5 约束、`reporting.locale: zh-CN`、缓存失效维度和未知 locale 失败行为（依赖：T012、T055；验收：`rg -n "cache_max_frames|zh-CN|3.*5" vnc_agent/config/README.md` 返回匹配且示例能通过配置加载测试）
- [X] T066 [P] 更新 `specs/001-vnc-core-execution-loop/contracts/report-schema.md`，以向后兼容增量章节定义 `frames`（含 safe_artifact_sha256/artifact_bundle_id）、`stage_measurements`、`performance_summary`、display fields、稳定英文枚举和禁止 private path/report copy 的规则，并明确旧 `before_frame_path`/`after_frame_path` 只承诺对应通过完整性门禁的可读取安全证据、不承诺 `report_frames` 目录/固定文件名/独立副本，feature 004 以 safe physical identity/content hash 等价保持语义（依赖：T057、T060；验收：`uv run pytest -q tests/fixtures/test_json_report_compatibility.py` 通过且 schema 文档中的路径/完整性语义、新增字段与实际 JSON golden 一致）
- [X] T067 [P] 更新 `specs/004-frame-dedup-observability/quickstart.md`，校准最终测试文件、命令、10+1 固定截图预期、五类捕获来源与失败 attempt、故障注入、所有报告入口零副本、HTML 白名单/UTF-8、旧消费者兼容、性能 marker 和两个结构/交互均不同的通用跨场景验收步骤（依赖：T049、T060、T061、T062；验收：从 `vnc_agent/` 逐条执行 quickstart 的离线命令全部通过且不访问网络）
- [X] T068 在 `vnc_agent/tests/fixtures/test_frame_dedup_sequence.py`、`vnc_agent/tests/fixtures/test_analysis_call_counts.py`、`vnc_agent/tests/integration/test_telemetry_report_consistency.py`、`vnc_agent/tests/performance/test_frame_dedup_performance.py` 和 `vnc_agent/tests/e2e/test_frame_dedup_cross_scenario.py` 完成最终交叉断言：由同一 TestRun/事件集产生 JSON Lines、JSON 和 HTML，逐项核对阶段状态/耗时、去重计数、缓存命中和模型调用数后运行全量回归与静态检查（依赖：T061、T062、T063、T064、T065、T066、T067；验收：从 `vnc_agent/` 执行 `uv run pytest -q tests/integration/test_telemetry_report_consistency.py`、`uv run pytest -q tests/unit tests/fixtures tests/integration tests/e2e`、`uv run pytest -q -m performance tests/performance/test_frame_dedup_performance.py`、`uv run ruff check src tests` 全部通过）

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Direct dependency | Gate |
|---|---|---|
| Phase 1 Setup | None | Spy、固定图片、快照工具和 marker 可用 |
| Phase 2 Foundational | Phase 1 | 共享模型与配置测试由 RED 转 GREEN；阻塞所有故事 |
| Phase 3 US1 | Phase 2 | 先完成 capture/artifact/stability 测试，再实现物理去重 |
| Phase 4 US2 | Phase 2；完整集成依赖 US1 logical frame contract | 先完成 cache/call-count/context tests，再接入分析复用 |
| Phase 5 US3 | Phase 2；汇总验收依赖 US1/US2 事件 | 先完成 metrics/timing/log tests，再接入全阶段测量 |
| Phase 6 US4 | Phase 2；报告内容依赖 US1/US3 数据 | 先完成 resource/snapshot/compat/safety tests，再实现报告 |
| Phase 7 Final | 所有目标故事 | repository、跨场景、业务无关、文档与全回归全部通过 |

### User Story Dependency Graph

```text
Setup → Foundational → US1 (MVP)
                    ├─→ US2 ─┐
                    └────────┼─→ US3 ─┐
                    └────────┴────────┼─→ US4 → Final
                                     └────────→ Final
```

- **US1 (P1)**：在 Foundational 后可独立实现和验收，是逻辑帧/物理制品基础。
- **US2 (P1)**：键与缓存容器可在 Foundational 后开发；全链路复用依赖 US1 的 FrameCaptureService。
- **US3 (P2)**：遥测收集器可在 Foundational 后开发；完整计数验收依赖 US1/US2 产生的事实事件。
- **US4 (P2)**：资源与兼容投影可在 Foundational 后开发；完整报告验收依赖 US1 的安全引用和 US3 的性能摘要。

### TDD Order Within Each Story

1. 完成该故事全部 `Tests first — RED` 任务。
2. 运行每条指定命令，确认失败来自尚未实现的契约，而非 fixture/import/语法错误。
3. 按任务依赖实现最小生产代码，使测试逐步转 GREEN。
4. 运行故事 Checkpoint 的独立测试集，再进入下一故事或集成。

---

## Parallel Opportunities

### User Story 1

```text
T013 pixel identity ─┐
T014 artifact writes ├─→ T018/T019/T020 FrameCaptureService
T015 offline scopes  ┤
T016 stability       ┤
T017 failure safety ─┘
```

T013～T017 修改不同测试文件，可在基础模型完成后并行；实现阶段 T018 与 T019 按数据流收敛到 T020。

### User Story 2

```text
T026 key matrix ─────→ T033 cache
T027 window/release ─→ T033 cache
T028 fresh screen ─┐
T029 call counts ──┼→ T034/T035/T036 → T037 → T038
T030 context guard ┤                         └→ T039
T031 action effect ┤
T032 cache faults ─┘
```

T026～T032 可并行编写；T034 OCR、T035 template、T036 diff 位于不同模块，可并行实现。

### User Story 3

```text
T041 metrics ─┐
T042 timings ─┼→ T044 telemetry → T045/T046/T047/T048 → T049 performance
T043 logging ─┘
```

T041～T043 可并行；T045～T048 在 T044 后修改不同边界，可按文件所有权并行。

### User Story 4

```text
T050 resources ─────────────→ T055 localization
T051 HTML snapshot ─────────┐
T052 JSON compatibility ────┼→ T056/T057/T058 → T059 → T060
T053 UTF-8/errors ──────────┤
T054 evidence zero-copy ────┘
```

T050～T054 可并行；本地化、JSON 投影和安全证据解析在接口冻结后可分文件推进。

---

## Implementation Strategy

### MVP First（US1）

1. 完成 Phase 1 和 Phase 2。
2. 完成 T013～T017 并确认 RED 原因正确。
3. 完成 T018～T025，使 10 identical + 1 changed、范围隔离、遮罩安全和稳定性测试全部 GREEN。
4. 停止并独立审计：逻辑轨迹完整、物理文件数正确、未遮罩图片未进入公开制品。

### Incremental Delivery

1. **MVP / US1**：物理去重与完整逻辑采样。
2. **US2**：在不绕过 Planner/Grounder/Verifier 的前提下消除内容分析重复调用。
3. **US3**：加入可追溯性能事件与汇总，验证节省来自真实工作量而非推测。
4. **US4**：交付集中资源驱动的中文 HTML、兼容 JSON 和零副本安全证据。
5. **Final**：两个无关 GUI 场景、业务无关扫描、repository、文档和全回归门禁。

## Notes

- 所有缓存/调用次数验收以 Spy 边界为 oracle，不以网络耗时或 `duration_ms > 0` 推断调用。
- hash 仅是候选过滤器，逐像素相等才是最终去重裁决。
- duplicate 是新的逻辑采样，不是复用旧 ScreenFrame；不得从缓存带入旧时间戳、路径身份或验证结论。
- private model image 永远不能成为报告证据；优化失败可降级，遮罩/必需持久化失败必须 fail closed。
- 核心模块只处理通用像素、配置、事件、断言和报告契约；两个场景的词汇只存在于 fixture。

---

## Phase 8: Convergence

**Purpose**: `/speckit-converge` 复核 spec/plan/tasks 与代码现状后追加的剩余工作。

- [X] T069 在 `vnc_agent/tests/fixtures/test_report_utf8_errors.py` 新增断言：`ReportBuilder` 写出的 `report.json`/`report.html`（及 `logging_setup.py` 产生的 JSON Lines 日志文件，如可离线获取其落盘路径）实际字节不以 UTF-8 BOM（`EF BB BF`）开头，覆盖 FR-036 "MUST 以无 BOM 或明确受支持 BOM 的 UTF-8 读写" 中此前未被任何测试断言覆盖的 BOM 缺失要求（当前实现经 `encoding="utf-8"` 写入已天然满足该约束，但无回归测试防止未来引入 BOM 或切换到 `utf-8-sig`）（per FR-036, partial）
