# ai-work

个人 AI 工作记录项目，用于归档日常工作与学习中通过 AI 完成的代码、文档、
问题排查和自动化工具，并沉淀可复用的 Skills 与工作流。

## 项目目的

- 记录与 AI 协作完成的工作内容，方便日后回顾和复用
- 沉淀常用的提示词（Prompt）、工作流程和最佳实践
- 保存可复用的 AI 工具、Codex / Agent Skills
- 追踪任务进展与阶段性成果

## 目录结构

```
ai-work/
├── README.md                          # 项目总览
├── ai-visual-testing-research/        # VNC 黑盒 GUI 自动化测试（主线研发）
│   └── ai-visual-testing-research/
│       ├── overall_design.md          # 总体设计说明书
│       ├── specs/                     # Spec Kit 功能规格 001–024
│       ├── vnc_agent/                 # Agent 实现、用例、测试与运行产物
│       └── vncdotool/                 # VNC 驱动依赖（vendored）
├── trialpos-trec-docs/                # POS4U / TREC 领域知识档案库
├── trialpos-docs-learn/               # 基于 trialpos-trec-docs 的学习笔记
├── top-report-scraper/                # TOP Report 只读 API 客户端与 Skill
├── tech-docs/                         # 技术文档与学习笔记归档
├── ui-analysis-output/                # UI 分析索引构建产物与校验证据
├── ui-analysis-bundle-v1/             # ui-analysis-bundle-v1 快照（供 vnc-agent 消费）
├── claude-archive/                    # Claude 会话导出归档
├── VNC Agent 业务流程图.html          # VNC Agent 业务流程图（本地）
└── VNC Agent 系统架构(008–023).html   # VNC Agent 系统架构图（本地）
```

---

## 主线：VNC 黑盒 GUI 自动化（ai-visual-testing-research）

[`ai-visual-testing-research`](ai-visual-testing-research/ai-visual-testing-research)
是本仓库当前的主研发线：通过 VNC 纯黑盒控制 Windows 被测环境，用
**Planner（下一步做什么） / Grounder（目标在哪里） / Executor / Verifier**
分离的状态机驱动 GUI 自动化测试。

| 入口 | 说明 |
|---|---|
| [总体设计](ai-visual-testing-research/ai-visual-testing-research/overall_design.md) | 设计目标、原则、组件边界 |
| [vnc_agent README](ai-visual-testing-research/ai-visual-testing-research/vnc_agent/README.md) | 安装、配置、CLI、运行方式 |
| [specs/](ai-visual-testing-research/ai-visual-testing-research/specs/) | Spec Kit 功能规格与实现计划 |

### 功能演进（specs 001–024）

| 区间 | 主题 |
|---|---|
| 001–006 | 核心执行环、动作效果验证、定位 grounding、帧去重、批量按键、文本输入修复 |
| 007–009 | UI 分析索引消费、视觉答案缓存、重复帧跳过重规划 |
| 010–014 | 日语 OCR、OCR 未命中仲裁、局部命中回退、安全点击点、缩放恢复 |
| 015–016 | 页面元素记忆、录制回放 |
| 017–020 | httpx 复用、图像缩放、Planner 请求瘦身、等待调参 |
| 021–023 | 难例导出、误点检测、点击事后纠正 |
| **024** | **应用感知插件（当前 feature）** |

当前 Spec Kit 活动 feature：`specs/024-app-perception-plugins`。

### 快速上手（vnc-agent）

```bash
cd ai-visual-testing-research/ai-visual-testing-research/vnc_agent
pip install -e ".[dev]"   # 或使用 uv

# 配置 config/vnc-targets.yaml、config/models.yaml
# 密钥走环境变量：VNC_AGENT_VNC_PASSWORD / VNC_AGENT_PLANNER_API_KEY / VNC_AGENT_GROUNDER_API_KEY

vnc-agent run testcases/smoke-connect.yaml --dry-run
vnc-agent run testcases/smoke-connect.yaml --config config
```

POS 场景用例见 `vnc_agent/testcases/`（结账、扫码、混合支付等）。

### 相关产物

- **UI 分析索引**（feature 007）：`ui-analysis-bundle-v1/`、`ui-analysis-output/`
  —— 屏幕 / 元素 / 转场 JSONL，供 vnc-agent 查询与校验
- **架构图本地 HTML**：根目录 `VNC Agent 业务流程图.html`、
  `VNC Agent 系统架构(008–023).html`

---

## POS 领域知识库

### trialpos-trec-docs

[`trialpos-trec-docs`](trialpos-trec-docs) 是 **POS4U（现行 TRIAL 自社 POS）→ ST-POS**
置换主线的本地知识档案（源码分析文档 + Confluence / GitLab Wiki 镜像 +
代码对照核查）。

| 目录 | 定位 |
|---|---|
| `01-trialpos-docs/` ⭐ | 代码锚定的权威 AS-IS 文档（C4/arc42 分层） |
| `10-confluence-cloud/` | 云上 Confluence 镜像 |
| `11-confluence-trec/` | 自建 Confluence 镜像 |
| `12-gitlab-wiki/` | GitLab Wiki 镜像 |
| `90-verification/` | 相对真实源码的精度核查 |

> 敏感：含未公开供应商资料，仅限本地 / 私有，勿推送公开仓库。

详见 [`trialpos-trec-docs/README.md`](trialpos-trec-docs/README.md)。

### trialpos-docs-learn

[`trialpos-docs-learn`](trialpos-docs-learn) 是对上述知识库的**学习笔记**，
两条主线：搞懂现行 POS 体系，以及文档驱动编程在该体系中的用法。

---

## TOP Report Scraper

[`top-report-scraper`](top-report-scraper) 是公司内部 TOP Report 系统的只读 HTTP API
客户端，提供可安装的 `top-report` CLI，以及
[`trial-top-reports` Skill](top-report-scraper/skills/trial-top-reports)。

Skill 支持查询个人最新或历史 TOP/周报、多人当前周报告、组织下最新 TOP 报告及可用周次。
报告内容通过 API 获取；浏览器仅在缺少身份信息时用于交互式登录。

安装、命令示例和安全说明请参阅
[`top-report-scraper/README.md`](top-report-scraper/README.md)。

---

## 技术文档归档（tech-docs）

| 目录 | 内容 |
|---|---|
| [`认知成长/`](tech-docs/认知成长/) | AI 时代的开发与架构能力学习笔记 |
| [`WBS工作分解结构/`](tech-docs/WBS工作分解结构/) | WBS 与 Spec Kit 相关笔记 |
| [`orca-中文使用教程/`](tech-docs/orca-中文使用教程/) | Orca 中文教程 |
| [`spec-kit-中文教程/`](tech-docs/spec-kit-中文教程/) | GitHub Spec Kit 中文教程 |

---

## 其他目录

| 路径 | 说明 |
|---|---|
| `claude-archive/` | Claude 会话 HTML 导出归档 |
| `ui-analysis-output/` | UI 索引生成脚本、校验报告与证据 |
| `ui-analysis-bundle-v1/` | 可被 vnc-agent 消费的 bundle 快照 |
| `_to_delete/` | 待清理的调试帧与临时文件（勿当正式产物依赖） |

---

## 使用说明

本仓库为个人记录用途，内容持续更新中。请勿提交员工编号、访问令牌、密码、
导出的内部报告、VNC 凭据或其他敏感信息。
`trialpos-trec-docs` 等含内部业务资料的目录仅限本地使用。
