# ai-work

个人 AI 工作记录项目，用于归档日常工作与学习中通过 AI 完成的代码、文档、
问题排查和自动化工具，并沉淀可复用的 Codex Skills。

## 项目目的

- 记录与 AI 协作完成的工作内容，方便日后回顾和复用
- 沉淀常用的提示词（Prompt）、工作流程和最佳实践
- 保存可复用的 AI 工具与 Codex Skills
- 追踪任务进展与阶段性成果

## 目录结构

```
ai-work/
├── README.md                 # 项目总览
├── tech-docs/                # 技术文档与学习笔记归档
│   ├── 认知成长/              # AI 时代的开发与架构能力学习笔记
│   ├── WBS工作分解结构/        # WBS 与 Spec Kit 相关笔记
│   ├── orca-中文使用教程/      # Orca 中文教程
│   └── spec-kit-中文教程/     # GitHub Spec Kit 中文教程
└── top-report-scraper/       # TOP Report 只读 API 客户端与 Codex Skill
    ├── src/                  # Python CLI 源码
    ├── tests/                # 单元测试
    └── skills/
        └── trial-top-reports/ # 可独立安装的 TOP 报告 Skill
```

## TOP Report Scraper

[`top-report-scraper`](top-report-scraper) 是公司内部 TOP Report 系统的只读 HTTP API
客户端，提供可安装的 `top-report` CLI，以及项目内可复用的
[`trial-top-reports` Codex Skill](top-report-scraper/skills/trial-top-reports)。

Skill 支持查询个人最新或历史 TOP/周报、多人当前周报告、组织下最新 TOP 报告及可用周次。
报告内容通过 API 获取；浏览器仅在缺少身份信息时用于交互式登录。

安装、命令示例和安全说明请参阅
[`top-report-scraper/README.md`](top-report-scraper/README.md)。

## 使用说明

本仓库为个人记录用途，内容持续更新中。请勿提交员工编号、访问令牌、密码、
导出的内部报告或其他敏感信息。
