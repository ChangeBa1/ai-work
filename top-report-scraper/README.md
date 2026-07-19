# TOP Report Scraper

公司内部 TOP Report 系统的直接 HTTP API CLI。运行时不会启动或模拟浏览器。

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
