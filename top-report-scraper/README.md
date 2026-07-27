# TOP Report Scraper

公司内部 TOP Report 系统的只读 HTTP API 客户端，包含：

- 可安装的 `top-report` 命令行工具
- 可直接放入 Codex 的 `trial-top-reports` Skill

报告数据均通过 HTTP API 获取。Skill 仅在没有可用员工编号时使用 Orca 打开登录页，
完成身份发现后仍通过 API 获取报告。

## 安装

```bash
cd /home/bcz/ai-work/top-report-scraper
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

设置自己的员工编号（不要把编号或令牌提交到 Git）：

```bash
export TOP_REPORT_USER_ID='你的员工编号'
```

CLI 会调用 `generateToken` 获取短期 Bearer token。也可临时设置
`TOP_REPORT_TOKEN` 使用已有令牌。

## 使用

查看某人的所有周报（参数可用员工编号或姓名片段）：

```bash
top-report person 12345678 --type weekly
top-report --json person '山田' --type weekly > reports.json
```

查看多人的本周周报：

```bash
top-report current 12345678 87654321 --type weekly
top-report --json current '山田' '佐藤' --type weekly
```

其他用法：

```bash
top-report weeks
top-report current 12345678 --week 2026-24 --type both
top-report --no-detail person 12345678 --type top
```

`person` 默认遍历 API 返回的全部可用周次；`current` 默认使用最新一个实际已有报告数据的周次
（例如新一周已开始但尚无人提交时，会自动回退到上一报告周）。
API 查询本身按周分页，人员匹配在返回列表中按员工编号精确匹配或姓名片段匹配。

## Codex Skill

完整 Skill 位于 [`skills/trial-top-reports`](skills/trial-top-reports)，包含：

```text
skills/trial-top-reports/
├── SKILL.md
├── agents/openai.yaml
├── references/api.md
└── scripts/top_reports.py
```

将目录复制到 Codex Skills 目录即可安装：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/trial-top-reports "${CODEX_HOME:-$HOME/.codex}/skills/"
```

Skill 脚本也可以直接在项目中运行：

```bash
python3 skills/trial-top-reports/scripts/top_reports.py --help
python3 skills/trial-top-reports/scripts/top_reports.py latest 12345678 --type weekly
python3 skills/trial-top-reports/scripts/top_reports.py history 12345678 --type weekly
python3 skills/trial-top-reports/scripts/top_reports.py --json organization 'T.R.E.-China'
```

与基础 CLI 相比，Skill 还支持最新报告、历史报告、组织 TOP 报告及交互式登录。
详细行为和安全约束参见
[`skills/trial-top-reports/SKILL.md`](skills/trial-top-reports/SKILL.md)。

## 安全说明

- 只调用报告查询相关的只读接口，不调用点赞、评论、收藏或修改接口。
- 不要提交员工编号、Bearer token、导出的报告 JSON 或 `.env` 文件。
- 登录密码只应输入登录页面，不要写入终端命令、配置文件或对话内容。

## 测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m py_compile skills/trial-top-reports/scripts/top_reports.py
```
