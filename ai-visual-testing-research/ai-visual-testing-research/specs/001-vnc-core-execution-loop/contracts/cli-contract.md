# Contract: CLI 命令契约

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

本功能不对外暴露 HTTP API（FastAPI 推迟到 MVP 后半阶段）；测试工程师通过 Typer 构建的
命令行入口驱动整条闭环。以下为本切片必须提供的命令契约。

## `vnc-agent run`

**用途**：加载一份声明式测试用例并执行（对应用户故事一）。

```text
vnc-agent run <test-case-file> [--target <vnc-target-id>] [--config <config-dir>]
              [--dry-run] [--json-only]
```

**输入**：

| 参数 | 必填 | 说明 |
|---|---|---|
| `<test-case-file>` | 是 | 指向一份 YAML 测试用例文件（结构见 `test-case-schema.md`） |
| `--target` | 否 | 覆盖用例中声明的 `target_id` |
| `--config` | 否 | 配置目录，默认 `./config` |
| `--dry-run` | 否 | 仅执行 FR-003 的用例格式校验，不连接 VNC、不执行任何动作 |
| `--json-only` | 否 | 只生成 JSON 报告，跳过 HTML 报告渲染 |

**输出（stdout）**：运行过程中的结构化进度行（JSON Lines，与 `structlog` 日志同构）。

**退出码**：

| 退出码 | 含义 |
|---|---|
| `0` | 测试运行状态为 `passed` |
| `1` | 测试运行状态为 `failed` |
| `2` | 用例格式校验失败（FR-003），未开始执行 |
| `3` | 运行被取消（`cancelled`） |
| `4` | 无法建立 VNC 连接（重连耗尽后仍失败） |

**产物**：`artifacts/runs/<run-id>/report.json`、`artifacts/runs/<run-id>/report.html`
（除非 `--json-only`）、`artifacts/runs/<run-id>/logs/events.jsonl`。

**契约保证**：

- 命令 MUST 在开始执行任何 VNC 动作前完成用例校验（对应 FR-003）；校验失败时 MUST 不产生
  任何测试运行记录，仅输出字段级错误。
- 命令的退出码 MUST 与 `TestRun.status` 一一对应，不允许"实际失败但退出码为 0"的情况
  （对应 spec Success Criteria SC-007）。

## `vnc-agent report`

**用途**：基于已有的运行制品重新渲染报告（不重新连接 VNC 或重新执行测试）。

```text
vnc-agent report <run-id> [--format json|html|both]
```

**契约保证**：报告内容 MUST 完全来自已落库的 `TestRun`/`StepRecord` 数据，不得触发任何新的
观察、动作或验证。
