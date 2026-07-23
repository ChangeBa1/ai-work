# Quickstart Validation: 截图去重、分析复用、性能可观测性与中文报告

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/](contracts/)

本指南用于实现完成后的离线验收。所有命令从仓库的 `vnc_agent/` 目录执行；核心验收不得连接真实 VNC 或在线模型服务。

## 1. Prerequisites

```powershell
uv sync --extra dev
```

确认默认配置包含：

```yaml
perception:
  cache_max_frames: 5

reporting:
  locale: zh-CN
```

`cache_max_frames` 只允许 3～5；未登记 locale 应在配置加载时失败。

## 2. Unit gates

```powershell
uv run pytest -q tests/unit/test_frame_pixel_identity.py tests/unit/test_analysis_cache_keys.py tests/unit/test_analysis_cache_window.py tests/unit/test_analysis_cache_fallback.py tests/unit/test_context_sensitive_cache_guards.py tests/unit/test_performance_metrics.py tests/unit/test_reporting_resources.py
```

Expected:

- 不同 PNG 编码但相同 `frame-pixels-v1` 规范化像素载荷得到相同 content hash，width/height/canonical pixel format/单像素任一变化都会改变载荷；
- 单像素差异和注入式 hash collision 均不能去重；
- full-screen/ROI、坐标、pixel format、mask identity、配置或模型版本变化均 cache miss；
- 容量 3 与 5 均按 capture sequence 淘汰，run/session reset 后不保留 pixels；
- 计数守恒，失败阶段不伪造 completed/0ms；
- `zh-CN` 资源键与状态/错误映射完整。
- execute 中 Pipeline 与 StabilityEngine 共享一个 capture service；离线/部分失败/兼容 report 不构造 capture service、不连接 VNC，也不追加逻辑帧。

## 3. Fixed-screenshot offline sequence

```powershell
uv run pytest -q tests/fixtures/test_frame_dedup_sequence.py tests/fixtures/test_stability_deduplicated_frames.py
```

主序列预期：

- 前 10 张完全相同：10 logical、1 unique、9 duplicate、1 个无掩码物理 PNG；
- 10 个 frame id/timestamp 独立，后 9 个复用同一安全路径；
- OCR/template/vision describe 各实际调用 1 次、命中 9 次；
- 第 11 张单像素变化：累计 11 logical、2 unique、9 duplicate、2 个物理 PNG，各内容分析累计 2 次；
- A→B→A 序列的第三帧是 non-adjacent unique，不得复用第一帧 OCR/template/vision 结果；
- `stable_frame_count=3` 在活动稳定等待的第 3 个逻辑采样后稳定，即使后两帧物理去重；
- `early_exit` 对该活动等待的每个逻辑采样调用；普通观察、重试、恢复和操作后验证帧进入全局轨迹，但不污染该等待计数/callback。

遮罩且允许 private 持久化时，首个 unique 产生 safe/private 两个实际文件；禁止 private 持久化时只产生 safe 文件，model_image 为 null，未遮罩像素在分析后释放。报告始终只能引用 safe 文件，避免写入与字节只按策略实际允许的用途核对。

逻辑轨迹必须分别包含 ObservationPipeline 观察、StabilityEngine 等待、重试、恢复和操作后验证的成功采集，且全部由同一 capture sequence 排序；未生成成功 frame 的失败尝试必须能由 source/attempt/time/error/duration 关联到状态、重试或恢复事件。

## 4. Fault fallback

```powershell
uv run pytest -q tests/unit/test_capture_fallback.py tests/unit/test_artifact_persistence_failure.py tests/unit/test_cli_capture_service_wiring.py
```

Expected:

- decode/规范化失败：capture failed，无成功 ScreenFrame、下游图片分析或验证；有遮罩时不得持久化 raw bytes；
- 规范化像素已可用后的 hasher/array compare/cache get/cache put 异常：unique/cache miss + 完整分析；
- optimization failure 不增加 hit、skipped 或 avoided；
- safe/private 第二文件写入、file/directory sync 或 bundle rename 失败：不产生成功 ScreenFrame、不进入 Verifier、不暴露半组 final 文件；
- bundle 发布后逻辑提交失败时整包进入非报告隔离区；模拟重启后 staging 被清理、无引用 published bundle 被隔离并产生 recovery audit；
- 遮罩编码失败不得把原始图片写入安全证据路径；
- `private_persistence_allowed=false` 时任何故障回退都不得产生 private_model 文件或对应 avoided event；
- measurement 保留 failed 状态和真实已观测 duration。

## 5. Report and repository contracts

```powershell
uv run pytest -q tests/fixtures/test_reporting_localization.py tests/fixtures/test_json_report_compatibility.py tests/integration/test_frame_trace_repository.py
```

Expected:

- HTML 快照所有主要可见标签与状态为简体中文，machine CSS/data marker 稳定；
- 中文名称/错误详情 UTF-8 正常且 HTML autoescape；
- JSON 非路径旧投影字段/类型/enum 完全不变，只出现允许的增量字段；旧 `before_frame_path`/`after_frame_path` 保持前后 safe evidence 语义，并解析为可读取且 physical identity/content hash 等价的 safe physical path；
- 顶层 frames 包含观察、等待、重试、恢复和操作后验证的全部成功逻辑帧；
- 实际 Planner/Grounder/Verifier 调用的脱敏 request/response/context audit 可与 run、step、frame、iteration 和 model event 往返关联；
- 多个逻辑证据引用同一 safe path；正常执行、离线重建、部分失败和兼容入口均不在 `report_frames` 或其他报告目录产生 copy/hardlink/symlink；
- safe 文件缺失、截断、随机损坏、byte-size/artifact_sha256 mismatch、不可解码、mask mismatch 或来自 staging/quarantined/orphan bundle 时均显示本地化不可用且不生成链接；`content_hash` 不得代替实际编码文件完整性校验；
- HTML 除原始 code/detail、明确 machine marker、模型/provider/产品标识和诊断路径片段白名单外无英文 UI；中文资源与错误详情 UTF-8 逐码点往返一致；
- 递归旧投影及代表性旧消费者/旧 schema 均可读取新报告，null/缺省、数组顺序和 status 聚合不变；
- SQLite payload 往返后 frame id、timestamp、duplicate relation、路径和 telemetry 不丢失。

## 6. Cross-scenario contract

```powershell
uv run pytest -q tests/e2e/test_frame_dedup_cross_scenario.py tests/unit/test_no_business_keywords_in_core.py
```

Expected:

- `generic-form-flow` 与 `generic-icon-menu-flow` 分别完成 capture→observe→act→verify→report；
- 两个场景使用同一通用 frame/cache/telemetry/report contract；
- 场景独立性只由固定 VNC 截图的可见布局 fingerprint、声明式 fixture 元数据和 action-kind 集合证明；测试不得读取 UIA、浏览器 DOM、进程/文件系统或被测应用内部接口；
- 一个场景的 fixture id、可见文本或交互细节不会出现在核心分支或固定字段中；
- 操作后画面相同时仍得到现有 no-effect/failed/uncertain 语义，不因缓存自动通过。
- 相同画面但上下文变化时发生所需实际调用；上下文完全相同且无需新计划时 Planner 记录 skip；每个操作后 Verifier 仍实际执行。

## 7. Deterministic call-count performance gate

```powershell
uv run pytest -q -m performance tests/performance/test_frame_dedup_performance.py
```

该测试使用本地固定数组、注入式 Spy 与 warm-up 后多轮中位数，不访问网络。常驻门禁是工作量不变量：100 张完全相同帧只产生 1 组唯一制品与 1 次各内容分析；阶段 duration 只用于诊断，不作为实际调用次数的事实来源。

## 8. Full regression and lint

```powershell
uv run pytest -q tests/unit tests/fixtures tests/integration tests/e2e
uv run ruff check src tests
```

## 9. Manual artifact audit

对任一完成 run 检查：

1. `report.json` 的 `frames` 数量等于 `performance_summary.total_capture_count`；
2. `unique_frame_count + duplicate_frame_count == total_capture_count`；
3. `physical_image_count` 与 successful physical-image events 一致；
4. `report.html` 为 `lang="zh-CN"` 且不含私有模型路径；
5. run 目录不存在由正常、离线、部分失败或兼容入口报告构建新增的 evidence PNG/link；
6. JSON、HTML 与 JSON Lines 日志的 cache/model/write 计数来自同一事件集；
7. 任一失败或 unavailable 阶段没有用 0 或 estimated duration 冒充成功数据。
8. 每个可用 safe evidence 的实际 byte size 与 `artifact_sha256` 匹配 manifest，且所属 bundle 有已提交逻辑引用；staging、quarantined 或 orphan bundle 不可被报告引用。
