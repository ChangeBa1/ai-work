# GitLab Wiki 镜像 — AIPOS

> 本目录是公司内网 GitLab 上 **AIPOS Wiki** 的本地镜像，属于 `pj-trial-pos` 的「来源层」（与 `01-confluence-cloud/` 的 POSSYS Confluence 镜像平级）。
> 本文件（`README-SYNC.md`）为本地维护说明，**不在** wiki 仓库中，不会被 `git pull` 覆盖。

## 来源

- **Wiki 仓库**：`https://code.trechina.cn/gitlab/project-trial/aipos/aipos-wiki.wiki.git`
- **项目页面**：`https://code.trechina.cn/gitlab/project-trial/aipos/aipos-wiki`
  （项目代码仓库 `aipos-wiki.git` 当前账号无 download_code 权限，返回 403；仅 wiki 可访问）
- **认证**：`code.trechina.cn` 的凭据已存于 macOS 钥匙串（osxkeychain），克隆/拉取无需再输密码。

## 本次同步

- **首次全量**：2026-07-11
- **同步到的提交**：`cdd5951bed9ff575b6611f2f9c57fe76be9dcf2d`（2025-08-19 10:16，白明鑫）
- **内容**：157 个 wiki 页面（`.md`，中日文混合，POS4U 开发/环境搭建/业务知识/C# 知识点等）
- **附件**：20 个文件在 `uploads/`（png / xlsx / zip，随仓库一起下载，无需额外抓取）
- **首页/目录**：`home.md`（含各页链接的 TOC）

## 目录与镜像方式

- 本目录**就是 wiki 仓库的完整 git 克隆**（含 `.git/`），工作树保持与远端一致、**不做任何改写**。
- 页面文件名即 GitLab wiki 的 slug，用 `_` 表示层级、`.` 前缀表示序号（如 `1_1_9.-オーダーキッチン.md`）。
- `.gitlab/redirects.yml` 是 wiki 的重定向配置。

## 已知瑕疵（源仓库自带，忠实保留）

- `*-[13.-rm商品api](./1_12.-rm商品api).md`：源头一个坏掉的 markdown 链接被误存成了页面（4 字节），文件名含 `*[]()`。
- `test.md`：2 字节测试残留页。
- **图片/页面链接不适合本地直接渲染**：图片写作 wiki 根绝对路径 `/uploads/<hash>/image.png`，页面互链用人类标题（`[12. RM商品API](./1_12. RM商品API)`），均由 GitLab 的 wiki 引擎解析。用普通 markdown 阅读器打开时图片/内链不会自动解析——本镜像定位为「原文归档 + grep 检索 + 差分基线」，浏览渲染版请看 GitLab。如需本地可渲染副本（改写 `/uploads/` 为相对路径等），可另行生成，不要动本镜像。

## 再同步（差分更新）

wiki 是原生 git 仓库，更新即拉取：

```bash
cd "07-strategic-knowledge-base/pj-trial-pos/03-gitlab-wiki"
git pull --ff-only            # 拉取远端新提交
git log --oneline -10         # 看新增/变更页面
```

查看自上次同步以来的差异（把 `cdd5951` 换成上次记录的提交）：

```bash
git diff --stat cdd5951 HEAD  # 概览
git log cdd5951..HEAD --name-status
```

拉取后请更新本文件「本次同步」一节的提交 SHA 与日期。
