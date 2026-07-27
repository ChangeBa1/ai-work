# Orca 中文使用教程

> 基于 Orca 官方文档整理与重写，覆盖官方文档截至 2026-07-19 的全部 54 个主题页。命令、路径和产品名保留英文，界面名称同时给出英文，便于对照。Orca 更新较快，具体界面与参数应以[官方文档](https://www.onorca.dev/docs)和 `orca <command> --help` 为准。

## 目录

1. [Orca 是什么](#1-orca-是什么)
2. [安装、更新与首次启动](#2-安装更新与首次启动)
3. [五分钟完成第一次三代理会话](#3-五分钟完成第一次三代理会话)
4. [核心模型：仓库、worktree、标签与会话](#4-核心模型仓库worktree标签与会话)
5. [代理：支持范围、配置、账户与生命周期](#5-代理支持范围配置账户与生命周期)
6. [代码编辑、文件浏览和内置查看器](#6-代码编辑文件浏览和内置查看器)
7. [浏览器、Design Mode 与浏览器身份](#7-浏览器design-mode-与浏览器身份)
8. [终端](#8-终端)
9. [审查、提交、推送与托管平台](#9-审查提交推送与托管平台)
10. [远程开发：SSH 与 Remote Orca Server](#10-远程开发ssh-与-remote-orca-server)
11. [Orca CLI 完整教程](#11-orca-cli-完整教程)
12. [多代理编排 Orchestration](#12-多代理编排-orchestration)
13. [定时自动化、技能与 MCP](#13-定时自动化技能与-mcp)
14. [桌面 Computer Use 与 iOS 模拟器](#14-桌面-computer-use-与-ios-模拟器)
15. [移动端、通知与 Agents Feed](#15-移动端通知与-agents-feed)
16. [典型工作流配方](#16-典型工作流配方)
17. [设置参考](#17-设置参考)
18. [隐私与遥测](#18-隐私与遥测)
19. [故障排查](#19-故障排查)
20. [官方页面覆盖索引](#20-官方页面覆盖索引)

---

## 1. Orca 是什么

Orca 是为并行运行多个 AI 编码代理而设计的桌面 IDE。每个任务拥有独立的真实 Git worktree、代理终端和浏览器标签，因此 Claude Code、Codex、Cursor CLI 等代理可以同时工作，不必频繁 stash、切分支，也不会互相覆盖文件。

适合的使用场景：

- 让三个代理并行尝试同一个 bug，再选择最好的实现。
- 对 AI 生成的 diff 做严肃、逐行的审查。
- 已订阅 Claude Code、Codex、Cursor CLI 等，希望集中管理。
- 让代理在自有远程机器上运行，同时保留本地 IDE 体验。

Orca 面向会读 diff、重视提交质量并保持 worktree 整洁的专业开发者；它不是无代码工具。它也不是模型、不是 Git 替代品、不是纯云产品：模型与订阅由你提供，worktree 是标准 Git worktree，本地运行；远程执行通过你控制的 SSH 主机或 Orca Server 完成。

---

## 2. 安装、更新与首次启动

### 2.1 下载

| 平台 | 安装方式 |
|---|---|
| macOS Apple Silicon | [DMG](https://github.com/stablyai/orca/releases/latest/download/orca-macos-arm64.dmg) |
| macOS Intel | [DMG](https://github.com/stablyai/orca/releases/latest/download/orca-macos-x64.dmg) |
| Windows | [安装程序](https://github.com/stablyai/orca/releases/latest/download/orca-windows-setup.exe) |
| Linux | [AppImage](https://github.com/stablyai/orca/releases/latest/download/orca-linux.AppImage) 或 [`.deb`/Releases](https://github.com/stablyai/orca/releases) |
| 旧版本/RC | [GitHub Releases](https://github.com/stablyai/orca/releases) |

macOS 也可用 Homebrew：

```bash
brew install --cask stablyai/orca/orca
brew upgrade --cask orca
```

Homebrew cask 跟随稳定版。RC 版需从 Releases 下载，或按住 Shift 点击 **Check for Updates**；普通检查只跟随稳定通道。按住 Cmd（macOS）或 Ctrl（Windows/Linux）点击更新检查，则包含最新的 perf 标签预发布版。

### 2.2 首次启动

Orca 会请求访问主目录以添加仓库；若发现 `~/.claude`、`~/.codex` 或 Ghostty 配置，会询问是否导入；随后进入空白首页供你添加仓库。

- macOS 包已签名并公证，首次打开仍可能出现 Electron 应用确认。
- Windows 可在 **Settings → Terminal** 选择 PowerShell、CMD 或 WSL，通常推荐 PowerShell。
- Linux 提供 AppImage 与 Debian 包。

---

## 3. 五分钟完成第一次三代理会话

1. 在侧栏点 **Add Repo**，选择本地 Git checkout。Orca 自动识别默认分支为仓库的 base ref，之后可在仓库设置更改。
2. 点仓库旁的 **+**，输入任务名，如 `fix-login-race`。留空时会用海洋生物命名。选择 start-from ref，通常是 `origin/main`，也可选任意分支或提交。
3. 启动器会预选默认代理（在 **Settings → Agents** 修改），也可先开空终端。Orca 在托管目录创建真实 worktree 和分支。
4. 从终端的代理下拉框选择 Claude Code、Codex、Cursor CLI 或其他代理。Orca 设置正确 cwd，并复用相应订阅凭据。
5. 再创建两个同起点 worktree，例如：

   - `fix-login-race` → Claude Code
   - `fix-login-race-2` → Codex
   - `fix-login-race-3` → Cursor CLI

6. 向三个代理发送相同提示。拖动标签到窗格右边或下边，分屏观察。
7. 比较三个 diff，选择最佳方案；用 **Annotate AI Diff** 留下逐行意见并批量发回代理。
8. 在 Orca 内 stage、commit、push 并创建 PR；删除另外两个 worktree，相关目录和分支会一并删除（需确认）。

---

## 4. 核心模型：仓库、worktree、标签与会话

### 4.1 Worktree 模型与生命周期

- 每个 repo 有 base ref，通常是 `origin/main`。
- 每个 worktree 有自己的 start-from ref、分支、磁盘文件和代理终端。
- 生命周期是：创建 → 工作 → 审查 → 提交/推送/PR → 归档或删除。
- 创建对话框提交后立即关闭，`git fetch` 与 `git worktree add` 在后台运行；侧栏显示进度，标签页显示实时 setup 状态，可取消、失败后重试。
- start-from 可用 base ref、本地分支、具体 SHA 或远程分支。
- 默认分支名来自工作区名，或关联的 GitHub PR、GitLab MR、Linear/Jira issue。高级区域可显式填写 `feature/my-branch`；对由受跟踪工作项创建的 workspace，Orca 为避免无效覆盖会隐藏该字段。

所有 worktree 都可直接使用 `git status`、`git rebase`、`git cherry-pick` 等普通 Git 命令。外部用 `git worktree add` 创建的 worktree 需导入；若隐藏外部 worktree，新检测项会出现在 inbox 中供导入或继续隐藏。

### 4.2 侧栏与项目组

默认按 project/repo 分组。可用侧栏自身的过滤框、置顶 worktree、拖动 repo 排序；双击标题就地重命名。Cmd/Ctrl 点击多选，Shift 点击连续多选，右键可批量归档、睡眠或删除。未读项用粗体显示，状态栏内联代理活动。

导入包含多个 Git repo 的父目录时，可分别导入或归入一个 project group。组标题的 **+** 可创建 folder workspace：选择负责该 workspace 任务来源的子 repo，再填写名称和关联 issue/PR。删除 project group 时可同时注销其中的 projects。

### 4.3 标签、窗格和分屏

一个标签承载终端、编辑器、浏览器、diff 或 PR。可在组内排序、跨组拖动；将标签拖到右边形成左右分屏，拖到底部形成上下分屏，分屏可嵌套。终端还可在标签内部向右/向下分裂。边界位置、每个 worktree 的整棵窗格树都会保存。

- macOS `Cmd+Option+W` / Windows/Linux `Ctrl+Alt+W`：关闭当前 worktree 所有编辑器文件标签。
- 活跃标签的颜色条表示当前焦点窗格。
- 每个 worktree 独立保存标签布局；切换回来时完整恢复。

### 4.4 快速导航

- **Quick Open**：`Cmd-P`，搜索当前 worktree 文件；按最近使用与匹配度排序，Git ignored 文件作为第二批结果。
- **Jump Palette**：`Cmd-J`，跨全部 worktree、project、repo 和打开的标签搜索。空查询先显示最近 worktree；可匹配已缓存的 GitHub PR `#123` 或 GitLab MR `!123`。`Shift-Enter` 在新分屏打开。无匹配时提供用输入文字创建 worktree 的选项。

### 4.5 会话恢复

退出再启动时，Orca 恢复打开的 worktree、嵌套分屏、焦点标签、终端 scrollback。后台 daemon 持有 PTY，因此正常退出、自动更新重启、桌面应用崩溃时，代理仍可继续运行，重开后热重连。

主机重启、断电、内核崩溃或 daemon 自身崩溃会结束代理进程，但布局和最后持久化的 scrollback 仍会恢复。

---

## 5. 代理：支持范围、配置、账户与生命周期

### 5.1 内置代理

Orca 可运行任何 CLI 代理。官方预配置列表包括：

| 类型 | 代理 |
|---|---|
| 深度集成 | Claude Code、Codex、Cursor CLI |
| 自动安装/状态/Hook 等不同程度集成 | Grok、GitHub Copilot CLI、OpenCode、Pi、OMP、Gemini、Antigravity、Ante、Aider、Goose、Amp、Kilocode、Kiro、Charm Crush、Auggie、Autohand、Cline、Codebuff、Command Code、Continue、Devin、Droid、Kimi、Mistral Vibe、MiniMax、Qwen Code、Rovo Dev、Hermes、OpenClaw |
| 可选 | Claude Agent Teams（设置中启用，使用 `orca claude-teams`，各 teammate 使用原生窗格） |

MiniMax 有用量和限额跟踪；Claude/Codex 有账户、用量、热切换等更深集成。完整外部链接见[官方 Supported agents 页](https://www.onorca.dev/docs/agents/supported)。

### 5.2 权限默认值：重要安全提示

新启动默认填写各 CLI 的完全自主参数，例如 Claude 的 `--dangerously-skip-permissions`、Codex 的 `--dangerously-bypass-approvals-and-sandbox`，Gemini/Cursor 等的 `--yolo` 或等价参数。官方理念是以可丢弃 worktree 作为隔离边界，但这并不等同于操作系统沙箱。

在 **Settings → Agents → Agent Permissions** 可把未自定义代理统一切换为 **Yolo** 或 **Manual**。若某代理已有自定义启动参数或环境，Orca 不会用全局迁移覆盖；清空/重置自定义值可恢复受全局策略管理。

### 5.3 Claude Code

先安装并登录：

```bash
npm i -g @anthropic-ai/claude-code
```

Orca 自动读取 `~/.claude`。从代理下拉框启动后，会添加状态行 hook，通过 OSC title 更新状态点。状态栏展示本地用量和限额；可管理多个账户并热切换；仓库内 `.claude/` hook 和 `CLAUDE.md` 均继续生效。

### 5.4 Codex

按 OpenAI 官方方式安装并登录，Orca 读取 `~/.codex`。从下拉框启动后使用当前所选账户。进程退出后 **Restart** 使用同一账户；若想改为新账户，先切换账户再 restart。

Windows 可使用 host 安装或 WSL distro 中的 Codex。添加 WSL 账户时，Orca 在 distro 内创建隔离 home：`~/.local/share/orca/codex-accounts/<id>/home`，并映射为 `\\wsl.localhost\<distro>\...` 供 host 读取认证；启动、切换和限额读取均路由至该 distro。若未安装 Codex，对话框会明确指出缺失 binary 的 distro。

### 5.5 Codex/Claude 多账户热切换

在各账户至少登录一次，然后到 **Settings → Agents → Codex Accounts**（Claude 流程同形）识别账户并设置友好标签。在状态栏点击账户 chip 选择：

- 切换通过改写活跃凭据指针完成，不重新认证。
- 已运行进程保持原账户，直到重启。
- 新会话和状态栏用量跟随当前活跃账户。
- Restart 会使用重启时的活跃账户。

### 5.6 Cursor 与自定义 CLI

Cursor CLI 安装登录后，只要 binary 在 `PATH`，即可从下拉框启动。模型由 Cursor 自己的设置决定，Orca 不覆盖。

添加任意 CLI：**Settings → Agents → Add custom agent**，填写名称、binary/命令、默认参数，可选启动前 shell hook（如 `source .envrc`）。自定义代理会出现在所有终端的下拉框，cwd 总是当前 worktree，退出后有 Restart。若 CLI 发出 `working`/`idle` 等 OSC title，Orca 还能显示实时状态点；否则仍是完整终端，但无状态点。

### 5.7 GLM-5.2

Orca 负责 worktree、终端、浏览器、审查与会话；模型访问由 Z.ai CodePlan 和具体 harness 配置提供。

Claude Code 的 `~/.claude/settings.json` 示例：

```json
{
  "env": {
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.5-air",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.2[1m]",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.2[1m]"
  }
}
```

重启会话并用 `/status` 验证。`[1m]` 代表 100 万上下文；若提示不存在，先更新 Claude Code。编码任务建议 `/effort` 设为 `max`；Claude 的 `xhigh`、`max`、`ultracode` 映射到 GLM 最大 effort。

OpenCode、Cline、Kilo Code、Roo Code、Droid 等：选择 Z.ai 或 OpenAI-compatible provider，base URL 为 `https://api.z.ai/api/coding/paas/v4`，填 API key，模型 `glm-5.2`，上下文 `1000000`；除非 harness 明确支持，否则关闭图像输入。

OpenClaw 若列表中没有模型，在 `~/.openclaw/openclaw.json` 的 `models.providers.zai.models` 添加 `glm-5.2`（`reasoning: true`、`input: ["text"]`、`contextWindow: 1000000`、`maxTokens: 131072`），默认 primary 设 `zai/glm-5.2`、fallback `zai/glm-4.7`，并在 `agents.defaults.models` 添加 alias；随后：

```bash
openclaw gateway restart
```

其他 harness 先在其自身配置中设置 provider/model，再作为 custom CLI 加入 Orca。

### 5.8 状态、会话历史与休眠

状态点：绿色脉动=工作中，黄色=等待输入，灰色=空闲，无点=普通 shell/未识别代理。状态来自 OSC title。侧栏每个 worktree 卡片会内联会话状态，未查看项保持粗体。进程正常退出或崩溃后出现 Restart。

右侧栏 **Agents → Agent Session History** 扫描各 CLI 自己的本地记录，可按 Workspace/Project/All，按代理启停扫描，按更新时间/创建时间排序，按 Project/Folder/Agent 分组，并隐藏空会话。可按标题、cwd、分支、模型、预览搜索。

会话详情包括 cwd、分支、模型、消息数、token、最初请求和最近对话。操作包括 Resume、复制 resume 命令/ID/log 路径、打开或 reveal log、打开 cwd。支持 Claude、Codex、Cursor、Gemini、Hermes、Pi、Copilot、OpenCode、Grok、OpenClaw、Droid、Rovo Dev 等；Codex 恢复时也会还原原会话的 `CODEX_HOME`。远程 workspace 可浏览本地历史，但仅本地 workspace 能执行恢复。可手动 Refresh 重新扫描。

**Agent hibernation** 是实验功能：空闲完成的后台代理默认 30 分钟后暂停，回到 worktree 时用原 resume 参数自动恢复。范围 1 分钟到 24 小时；按键、新输出或打开终端会重置计时。只有可恢复的 Claude、Codex、Gemini、Antigravity、OpenCode、Droid、Grok 支持；Cursor、Hermes、Pi、Copilot 等不会休眠。移动端正在驱动、等待输入、前台显示等情况不会休眠；同一 worktree 多代理作为整体休眠。侧栏过滤器可显示/隐藏 sleeping worktree，并可给 **Toggle Sleeping Workspaces** 绑定快捷键。

### 5.9 Hook、Memory 与用量

- Orca 尊重 repo 的 `.claude/`、`.codex/` 配置。
- **Settings → Repository → Hooks** 可设置 worktree 创建后执行 `pnpm install`、`direnv allow`、恢复 `.env` 等。
- `CLAUDE.md` 和 `AGENTS.md` 不被改写，可在文件树中编辑。
- Hook endpoint 持久化在 POSIX 的 `{userData}/agent-hooks/endpoint.env` 或 Windows 的 `endpoint.cmd`，应用重启后长会话仍能连接新 Orca server。
- 状态栏从本地文件读取 Claude、Codex、Gemini、OpenCode、Kimi、MiniMax 的用量，显示 5 小时/日/周及 Claude Fable 周窗口的重置时间；超过 80% 显示警告。没有额外 API 调用，刷新速度取决于 CLI 自己写盘。多账户只在状态栏显示当前账户，其他账户在切换器中查看。

---

## 6. 代码编辑、文件浏览和内置查看器

### 6.1 文件树

左侧文件树实时映射磁盘的创建、重命名、删除、移动，代理或外部程序改动会立即出现。文件按 untracked、modified、staged、ignored 着色；右键可 discard、stage、rename，单文件还可复制到 OS 剪贴板。SSH 文件会先暂存到本地再复制，远程目录不支持。

外部拖放：

- Finder/Explorer → 文件树：复制文件。
- 图片 → Markdown 编辑器：在光标处插图。
- 文件 → 代理终端：粘贴路径。
- SSH worktree：Orca 先上传远端，再把真实远端路径交给代理。

文件夹右键 **Find in Folder**，或选中后按 macOS `Cmd-Shift-F` / Windows/Linux `Ctrl-Shift-F`。

### 6.2 Monaco

代码编辑器使用 Monaco。短时空闲或失焦自动保存，通常没有未保存状态点。常用键：

- `Cmd-D`：选择下一处相同内容。
- `Cmd-F` / `Cmd-Shift-F`：当前文件/当前 worktree 查找。
- `Cmd-Click`：语言扩展支持时跳转定义。

**Changes view mode** 可在原标签切为 HEAD 对 working tree 的 diff，保持光标位置；`n/p` 跳 hunk，`s` stage。源码默认换行，可在 General 关闭 **Editor Word Wrap**；与 Diff Word Wrap 相互独立。Appearance 可启用 minimap、选择独立编辑器字体。Orca 定位为 editor-first，类型检查与 lint 建议在终端运行。

### 6.3 Rich Markdown

Markdown 默认以富文本模式打开，`Cmd-Shift-M` 切换原始 Monaco。空行输入 `/` 可插入标题、列表、代码、callout、图片、Mermaid、toggle；`/toggle-text` 和 `/toggle-h1` 保存为可移植 `<details>/<summary>`。输入 `[[` 自动补全 worktree 内相对链接。

搜索匹配渲染文本；可选中渲染文字添加审查 annotation，仍绑定源范围。YAML/TOML front matter 默认显示，可在 **… → Hide/Show front matter** 对单文件切换。标题树按钮可在 rich/preview 模式固定目录。

### 6.4 查看器

- Mermaid：Markdown 内渲染；`.mmd` 用可平移缩放专用查看器。
- PDF：滚动、缩放、选择文字。
- 图片：PNG/JPG/SVG/WebP/GIF；图片 diff 支持并排、滑块、洋葱皮。
- CSV/TSV：可排序、快速搜索表格；工具栏切回 raw text 编辑。
- Jupyter `.ipynb`：渲染 Markdown、代码高亮和保存的输出；编辑会保持 nbformat，减少脏 diff。

---

## 7. 浏览器、Design Mode 与浏览器身份

每个 worktree 有独立的嵌入式 Chromium 浏览器，带地址栏、历史、模糊 URL 补全、后退/前进/刷新/停止和 DevTools。标签、滚动位置、登录会话随 worktree 恢复。

- `Cmd-F` 页内查找；`Cmd-T` 新标签；`Cmd-Shift-T` 恢复关闭标签。
- 下载 shelf 可取消、打开、在文件夹显示或移除。
- 自定义 viewport 使用 Chrome DevTools Protocol 设备模拟，因此 `window.innerWidth` 和 media query 都看到模拟尺寸。
- CLI 可控制同一浏览器：`orca snapshot/click/fill` 等。

### 7.1 Design Mode

在浏览器工具栏开启后，鼠标变为元素选择器。点击元素会把以下内容作为附件送入活跃代理终端：

- 元素 outer HTML 及少量邻域；
- 计算后 CSS（颜色、字体、间距等）；
- 元素裁剪截图；
- dev source map 可用时的源文件/行。

告诉代理如何修改，热更新后再次点击验证，形成“指向元素 → 改源码 → 复核”的循环。

### 7.2 Browser-use profiles

在 **Settings → Browser → Profiles** 新建身份，可设置 cookie、User-Agent、viewport。工具栏选择后，该窗格所有标签以及代理驱动命令都继承身份。每个 profile 使用独立 storage partition，cookie、localStorage、cache 不互通。

---

## 8. 终端

Orca 终端基于 xterm.js，面向代理工作流增强。代理标签显示身份、工作/等待/完成/未读状态。

- `Cmd-F` 搜索 scrollback，支持大小写、正则与上下匹配。
- 右键 **Copy Context** 复制有界的最近 transcript。
- 可导入 Ghostty 的主题、字体、光标；也可自动扫描 Warp 主题目录或从任意 Warp YAML 目录导入。
- Windows 默认 shell 可选 PowerShell、CMD、WSL；`+` 菜单可临时用其他 shell。WSL repo 通过 `wsl.exe -d <distro>` 启动，Windows path 会转成 `/mnt/<drive>/...`。
- 终端实现 kitty keyboard protocol，`Shift+Enter`、`Ctrl+Enter` 等组合键可准确传入 TUI。
- macOS 日文 JIS 键盘可开启 **JIS Yen (¥) to Backslash (\\)**。

快捷键：

| 操作 | 快捷键 |
|---|---|
| 新终端 | `Cmd-T` |
| 新默认代理标签 | macOS `Cmd-Alt-T`；Windows/Linux 默认未绑定 |
| 关闭标签 | `Cmd-W` |
| 向右分屏 | `Cmd-\\` |
| 向下分屏 | `Cmd-Shift-\\` |

每个代理还有独立的 “New agent tab” action，可在 Shortcuts 绑定。

### 8.1 Floating terminal 与 Quick Commands

全局浮动终端默认启用，macOS `Cmd+Option+A` / Windows/Linux `Ctrl+Alt+A` 切换、聚焦或关闭。触发按钮可放窗口边缘或状态栏；起始 cwd 默认 `~`，可配置。它有独立标签并支持 orchestration setup。

Quick Commands 可保存 `npm run dev`、`pnpm test` 等命令，也可保存 Claude/Codex 这类启动时接收提示的可复用 prompt。可设 Global 或 Project scope；从 tab bar 会新开终端运行，从上下文菜单可插入当前终端。

---

## 9. 审查、提交、推送与托管平台

### 9.1 Diff Viewer

默认比较 worktree 与 start-from ref，可改为任意 commit、branch 或 base ref。它合并显示 staged、unstaged、untracked 文件，支持双侧行号、按行/hunk stage、三方冲突解决，以及图片并排/滑块/洋葱皮 diff。Diff Word Wrap 默认关闭，可在 **…** 或 General 全局切换。

| 键 | 操作 |
|---|---|
| `j/k` | 下/上一个变更文件 |
| `n/p` | 下/上一个 hunk |
| `F7/Shift+F7` | 编辑器下一/上一变更 |
| `s` | stage 当前 hunk |
| `c` | 添加 AI diff 评论 |

### 9.2 Annotate AI Diff 与 Attribution

悬停 diff 行点 gutter 的 **+**，或按 `c` 添加 Markdown 评论；`Cmd-Enter` 保存、`Esc` 取消。评论跟踪实际行，即使 diff 移动也尽量随行。审完点 **Send to agent**，Orca 把所有行锚定评论组成一条提示，再选择已有或新代理；批量反馈能减少来回摆动。修改后评论仍保留，可 Resolve；未解决项会进入下一批。

Attribution 记录代理工具触碰过的行，并在 gutter 标记；人类再修改会转回 human。它只存本地，不写入 Git；需要持久化时从 diff toolbar 导出 metadata。

### 9.3 Commit、Push、冲突

可按文件或 hunk stage，手写或用 AI 生成 commit message，`Cmd-Enter` 提交。正常运行 pre-commit hook；失败时内联输出。**Fix with AI** 会把 hook 输出、尝试的消息、staged 文件交给默认代理修复，但不会要求绕过 hook、commit、push 或开 PR。

首次 Push 自动设置 upstream；落后时不会静默 force push。改写历史后会单独显示 **Force push with lease**，明确将替换的 commit 数和 upstream，底层用 `--force-with-lease`。Amend 是显式操作，已推送提交需确认。

Source Control 面板可 stage/discard、Commit、Push、Pull、Sync，主按钮随状态变为 Stage Files → Commit → Push/Pull/Sync。合并、rebase、cherry-pick、revert 冲突时，可 **Resolve with AI** 或 **Review conflicts**；还可 Abort merge/rebase。非 ASCII 路径以 UTF-8 显示。

推送后创建 PR/MR，确认 base、title、description、draft。AI 可生成 PR 详情；若创建流程中的后续 commit 失败，会显示 hook 与后续选项。Source Control 的 Generate/Fix/Resolve AI 动作都由 action recipe 控制，可在 **Settings → Git & Source Control → Action recipes** 设置全局或 repo override；全局修改不会覆盖已有 repo override。

### 9.4 GitHub、GitLab 等托管平台

在 **Settings → Integrations** 连接。GitHub 支持最深；GitLab 使用相同 MR/issue 流程。Bitbucket、Azure DevOps、Gitea 的 PR 也会显示在侧栏/Checks，创建 worktree 推送前会检查远端冲突。

- 关联 review 在侧栏显示 open/merged/closed，可直接打开外部页面。
- GitHub PR 菜单可复制、关闭、重开；Checks、review、评论在线打开，可回复 thread 中任意评论。
- 失败 Actions 以红 chip 显示，可看 job log，并用 **Fix broken checks** 把失败名称和链接交给代理。
- GitHub 自动合并支持 squash/merge commit/rebase，取决于仓库允许项；merge queue 显示 **Merge when ready**。draft、closed、conflicting、unstable 或仓库禁用时不显示。
- issue drawer 可浏览、过滤、编辑 GitHub/GitLab issue；GitHub Activity 混合显示评论、分配、mention、交叉引用、状态、project column 变动；GitLab 可按“分配给我”过滤。
- Tasks 侧栏提供 GitHub Projects 视图，可跨 repo 看卡片、draft PR 状态并直接创建 worktree。

### 9.5 Linear 与 Jira

Linear：在 **Integrations → Linear** 填写 [Personal API token](https://linear.app/settings/api) 并选 team。任务 drawer 统一展示 GitHub/Linear；可改状态、assignee、priority、label、estimate。Issue 的 description、评论、子 issue 中内嵌媒体会随代理提示提供。长列表 Load more，Orca 按 repo 记忆上次任务来源。

Jira Cloud：Tasks 选择 Jira → **Connect Jira**，填写 `https://example.atlassian.net`、Atlassian 邮箱和 [API token](https://id.atlassian.com/manage-profile/security/api-tokens)。可连多个 site 并选 All sites。可查看 description、评论、metadata，按可用 transition 改状态，并改 priority、assignee、custom field、添加评论。由 issue 创建 worktree 会预填名称并关联。完全不用 Jira 时可在 **Settings → Tasks** 隐藏。

---

## 10. 远程开发：SSH 与 Remote Orca Server

### 10.1 SSH worktree

**Settings → SSH** 添加 host、user、port、可选 identity file；Orca 会导入 OpenSSH config 及 `Include` 文件。首次使用加密 key 会询问 passphrase，默认只在本次 Orca 会话内存中保存，也可设更长 TTL。

创建 worktree 时选择 SSH target。Git worktree、代理都在远端运行，编辑器、diff、浏览器仍在本地 UI；连接断开不会结束代理，状态点与 Agents feed 实时同步。高级选项支持 proxy、jump host、SSH multiplexing；macOS/Linux 默认复用连接，只有目标策略拒绝 multiplex 时关闭。

关闭桌面应用后，远端 relay 租赁 PTY，使其继续运行；重开后恢复 attached 状态和 scrollback。默认 5 分钟 grace period 可按 target 配置。远程文件右键 **Download** 使用原 SSH provider 和原生保存对话框，仅桌面端、仅文件。远程目录需先压缩。

右侧 **Ports**（`Cmd+Shift+I`）扫描远端 `/proc/net/tcp`，一键转发，也可手动增删改；跨重启/重连保留。特权端口会本地重映射，如 80 → 10080。

### 10.2 Remote Orca Server

区别在运行时归属：

| 模式 | Orca runtime 在哪里 | 适合 |
|---|---|---|
| SSH worktree | 笔记本；远端只是执行目标 | 只有本机 Orca 管理远端工作 |
| Remote Orca Server | 远端；拥有 repo、worktree、PTY、tab、代理与 provider check | 桌面、浏览器、手机或后端共享远端会话 |

服务端安装 Orca 和所有要用的代理 CLI，并在服务端登录。Arch 可 `yay -S stably-orca-bin` 或 `stably-orca-git`；其他 Linux 可用 AppImage。若 `orca` 不在 `PATH`，先在服务端 GUI 的 **General → Orca CLI** 注册；某些包命令名是 `orca-ide`。

无头启动：

```bash
orca serve --pairing-address <可达IP或Tailscale主机名>
orca serve --port 6768 --pairing-address devbox.tailnet-name.ts.net
```

进程前台运行，`Ctrl-C` 停止。pairing address 必须是客户端可访问地址，除非同机否则不要用 `127.0.0.1`。移动端加 `--mobile-pairing`，扫描专用 QR/链接；Tailscale 手机需在同一 tailnet 且 ACL 允许。

若远端已开桌面 Orca，可在 **Remote Orca Servers → Advertise this app as a server → New Link** 共享，不另开 `serve`。客户端在同设置页 **Add Server**，填写名字和 pairing/access link；只有希望新的 server-routed 项目、终端、provider check 默认走远端时，才开启 **Advanced → Default runtime**。

自动化机器先保存 pairing：

```bash
orca environment add --name server-b --pairing-code '<orca://pair?...>'
orca terminal create --environment server-b \
  --worktree path:/srv/my-app --command "codex"
orca worktree create --environment server-b \
  --repo id:<repo-id> --name task-123 \
  --agent codex --prompt "Implement this change"
```

远端应使用显式 server-side selector：`path:/...`、`id:...`、`name:...`、`branch:...`、`issue:...`；避免 `active/current`。多用户产品应由已认证后端调用服务端本地 Orca CLI，不要把 pairing URL/主机凭据发给每个调用者。

连接问题可用 `nc -vz <server-address> 6768`；检查防火墙、VPN ACL、隧道。找不到代理时应在服务端安装、登录并检查服务端 `PATH`/home，而非笔记本配置。

---

## 11. Orca CLI 完整教程

在 **Settings → Experimental/General → CLI（Orca CLI）** 注册随桌面应用提供的命令，然后：

```bash
command -v orca
orca status --json
orca open --json       # Orca 尚未运行时启动
```

脚本和代理一律优先使用 `--json`。

### 11.1 选择器

```bash
orca repo show --repo id:<repoId> --json
orca worktree show --worktree active --json
orca worktree show --worktree path:/abs/path --json
orca worktree show --worktree branch:feature-name --json
orca worktree show --worktree issue:123 --json
```

`active/current` 依据当前目录或终端上下文解析；离开目标 worktree 的脚本应显式选择。远端优先 `id:<repoId>::<absolute-worktree-path>` 或 `path:<server-path>`。

### 11.2 Runtime、repo、worktree

```bash
orca serve --port 6768 --pairing-address 100.64.1.20 --json
orca repo list --json
orca repo add --path /abs/path/to/repo --json
orca repo set-base-ref --repo id:<repoId> --ref origin/main --json
orca repo search-refs --repo id:<repoId> --query main --limit 10 --json

orca worktree list --repo id:<repoId> --json
orca worktree ps --json
orca worktree current --json
orca worktree create --repo id:<repoId> --name fix-login --json
orca worktree create --name child-task --agent codex \
  --prompt "Investigate the flaky login test" --json
orca worktree set --worktree active --comment "testing token refresh" --json
orca worktree rm --worktree id:<worktreeId> --force --json
```

从 Orca worktree 内创建时会尽量记录父子关系；`--parent-worktree active` 显式指定，`--no-parent` 表示独立。`--agent` 启动首个代理，`--prompt` 发送初始任务，`--setup run|skip|inherit` 控制 repo setup hook。

### 11.3 Terminal

```bash
orca terminal list --worktree active --json
orca terminal show --terminal <handle> --json
orca terminal read --terminal <handle> --json
orca terminal read --terminal <handle> --cursor <cursor> --limit 1000 --json
orca terminal send --terminal <handle> --text "continue" --enter --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 300000 --json
orca terminal create --worktree active --title tests --command "npm test" --json
orca terminal split --terminal <handle> --direction horizontal \
  --command "npm run dev" --json
orca terminal rename --terminal <handle> --title runner --json
orca terminal switch --terminal <handle> --json
orca terminal close --terminal <handle> --json
```

未指定 `--terminal` 时使用当前 worktree 活跃终端。不确定状态时先 read 再 send。长输出保存 `nextCursor`，后续仅取增量。

### 11.4 Files 与浏览器

```bash
orca file open src/App.tsx --worktree active --json
orca file diff src/App.tsx --staged --worktree active --json
orca file open-changed --mode both --worktree active --json

orca goto --url http://localhost:3000 --worktree active --json
orca snapshot --worktree active --json
orca click --element @e3 --worktree active --json
orca fill --element @e1 --value "user@example.com" --worktree active --json
orca wait --text "Welcome" --worktree active --json
orca screenshot --worktree active --json
```

浏览器必须遵循 snapshot → action → snapshot；导航、换标签、页面变化或 stale ref 后重新 snapshot。

```bash
orca tab list --json
orca tab create --url http://localhost:3000 --json
orca tab switch --index 1 --json
orca capture start --json
orca console --limit 50 --json
orca network --limit 50 --json
orca full-screenshot --json
orca pdf --json
orca set device --name "iPhone 12" --json
```

`orca exec --command "<agent-browser command>"` 仅用于尚无类型化命令的浏览器动作。Profile 使用 `orca tab profile list/create/set/clone/use-default`。

### 11.5 Linear、环境与 Hook

```bash
orca linear issue --current --full --json
orca linear issue ENG-123 --comments --children --json
orca linear search "auth bug" --workspace all --json
orca linear team states --team ENG --json
orca linear status set --current --to "In Progress" --json
orca linear assignee set --current --me --json
orca linear priority set ENG-123 --to high --json
orca linear estimate set --current --to 3 --json
orca linear due-date set --current --to 2026-08-01 --json
orca linear label add --current --label backend --json
orca linear comment add --current --body "Investigating" --json
orca linear attach --current --url https://example.com/repro --title Repro --json
orca linear create --title "Flaky login test" --team ENG --priority high --json

orca environment list --json
orca environment rm --environment <selector> --json
orca agent hooks status --json
orca agent hooks on --json
orca agent hooks off --json
```

脚本离开关联 worktree 时不要依赖 `--current`，显式传 issue ID。

### 11.6 Worktree checkpoint

```bash
orca worktree set --worktree active \
  --comment "added debounce to SearchBar; ready for review
goal: reduce redundant API calls per #298" --json
```

在完成有意义阶段、验证假设、审查完成、遇阻或阶段切换时更新。第一行说明动作、位置、状态/下一步。写前先 `orca worktree current --json`，保留仍有效的用户上下文，避免覆盖目标。

---

## 12. 多代理编排 Orchestration

Orchestration 用持久消息、任务、dispatch 和决策门协调代理。轻量输入用 `orca terminal send`；需要所有权、依赖、完成报告时用 orchestration。

核心对象：

- Message：`status`、`dispatch`、`worker_done`、`escalation`、`decision_gate`、`heartbeat`。
- Task：`pending`、`ready`、`dispatched`、`completed`、`failed`、`blocked`。
- Dispatch：task 对 terminal 的一次分配；重试会产生新上下文。
- Decision gate：由 coordinator 管理、阻塞 task 的问题。

worker 完成权来自当前 dispatch，完成与 heartbeat 必须带 `taskId` 和 `dispatchId`。终端中的 `task_...` 可点击并跳到当前被分配终端，包括远端。

### 12.1 发现与消息

```bash
orca worktree ps --json
orca terminal list --json
orca orchestration task-list --json
orca orchestration inbox --limit 20 --json

orca orchestration send --to @all --subject "Heads up" \
  --body "Pausing dispatches" --json
```

群组地址有 `@all`、`@idle`、`@codex`、`@cursor`、`@grok`、`@droid`、`@worktree:<id>`；PowerShell 中要加引号。

```bash
orca orchestration send --to <handle> --subject "Review API" \
  --body "Focus on compatibility" --type status --json
orca orchestration check --terminal <handle> --unread --json
orca orchestration check --terminal <handle> --all \
  --types worker_done,escalation --json
orca orchestration reply --id <messageId> --body "Approved" --json
orca orchestration inbox --limit 50 --full --json
orca orchestration check --wait \
  --types worker_done,escalation,decision_gate \
  --timeout-ms 900000 --json
```

`check --unread` 默认并标记已读；`--all` 不标记。长等待每 15 秒向 stderr 发 heartbeat JSON，stdout 只输出最终结果；超时是检查点，不等于失败。

### 12.2 手动 dispatch

```bash
orca orchestration task-create \
  --task-title "Billing mobile audit" \
  --display-name "Billing audit worker" \
  --spec "Audit mobile layout; report files and screenshots." --json

orca worktree create --name billing-mobile-audit --agent codex --json
orca terminal wait --terminal <workerHandle> \
  --for tui-idle --timeout-ms 60000 --json
orca orchestration dispatch --task <taskId> \
  --to <workerHandle> --inject --json
```

worker 合约：无论成功失败只发送一次 `worker_done`；简述完成、发现、剩余工作；携带 task/dispatch ID；长任务发 heartbeat；阻塞问题用 `ask`，不要留在本地 TUI。

```bash
orca orchestration send --to <coordinatorHandle> \
  --type worker_done --subject "Completed audit" \
  --body "Fixed footer overlap; no follow-up." \
  --task-id <taskId> --dispatch-id <dispatchId> \
  --files-modified "src/app/Billing.tsx" \
  --report-path "artifacts/audit.md" --json

orca orchestration send --to <coordinatorHandle> \
  --type heartbeat --subject alive \
  --task-id <taskId> --dispatch-id <dispatchId> \
  --phase implementing --json

orca orchestration ask --to <coordinatorHandle> \
  --question "Update shared component?" \
  --options "shared,page-only" --timeout-ms 600000 --json
```

### 12.3 Coordinator、gate 与恢复

```bash
orca orchestration run \
  --spec "Split checkout QA across agents and summarize blockers." \
  --max-concurrent 3 --worktree active --json
orca orchestration task-list --ready --json
orca orchestration gate-list --status pending --json
orca orchestration run-stop --json

orca orchestration gate-create --task <taskId> \
  --question "Merge shared change?" --options '["yes","no"]' --json
orca orchestration gate-resolve --id <gateId> --resolution yes --json

orca orchestration dispatch-show --task <taskId> --preamble --json
orca orchestration task-update --id <taskId> --status blocked \
  --result '{"reason":"waiting on credentials"}' --json
```

`reset --tasks/messages/all` 清理的是 runtime-global 编排状态；其他 coordinator 活跃时不要运行，除非明确要整体清理。

---

## 13. 定时自动化、技能与 MCP

### 13.1 Scheduled automations

先用 `--disabled` 创建和调试：

```bash
orca automations create --name "Weekday triage" \
  --trigger weekdays --time 09:00 \
  --prompt "Triage new issues and summarize blockers" \
  --provider codex --repo my-repo --disabled --json
```

`--trigger` 支持 `hourly/daily/weekdays/weekly`、cron 和 RRULE；`--timezone <IANA tz>` 指定时区。`--repo` 每次在 repo 创建/选择工作；`--workspace` 在已有 worktree 运行；都省略时尽量从 cwd 推断。

已有 workspace 可加 `--reuse-session` 继续上次 live automation terminal；改回每次新终端：

```bash
orca automations edit <id> --fresh-session --json
orca automations list --json
orca automations show <id> --json
orca automations edit <id> --enabled --json
orca automations run <id> --json
orca automations runs --id <id> --json
```

`edit` 可改名称、prompt、provider、target、schedule、enabled；`remove` 删除自动化及运行历史。若运行在打开 workspace/重连目标前失败，可在 Orca 中打开 run 并点 Rerun。

### 13.2 Skills 与 MCP

```bash
npx skills add https://github.com/stablyai/orca --skill orca-cli
npx skills add https://github.com/stablyai/orca --skill orchestration
npx skills add https://github.com/stablyai/orca --skill computer-use
npx skills add https://github.com/stablyai/orca --skill orca-linear
npx skills add https://github.com/stablyai/orca --skill orca-emulator

orca skills list
orca skills get orca-cli
orca skills get orchestration --full
```

`skills show` 是 `skills get` 别名；可加 `--json`。自有 repo 只要含 `skills/<name>/SKILL.md` 也可用 `npx skills add` 安装。MCP endpoint 在 **Settings → Integrations → MCP** 注册，支持 MCP 的代理 CLI 会看到工具。

---

## 14. 桌面 Computer Use 与 iOS 模拟器

### 14.1 Computer Use

它控制内置浏览器之外的原生桌面应用。首次：

```bash
orca status --json
orca computer permissions --json
orca computer capabilities --json
```

macOS 需给 **Orca Computer Use** Accessibility 与 Screen Recording。标准循环：

```bash
orca computer list-apps --json
orca computer get-app-state --app com.spotify.client --json
orca computer click --app com.spotify.client \
  --element-index 42 --json
```

优先用 bundle ID；名称需唯一，冲突时 `pid:<number>`。element index 只对最近一次 state 有效；导航、焦点、滚动或重渲染后必须刷新。

动作包括 `click`、`set-value`、`type-text`、`press-key`、`hotkey`、`paste-text`、`scroll`、`drag`、`perform-secondary-action`。优先语义动作，较不依赖焦点。秘密通过 stdin，避免 shell history：

```bash
printf '%s' "$TEXT" | orca computer set-value \
  --app com.apple.Safari --element-index 7 \
  --value-stdin --json
```

`type-text/paste-text` 用 `--text-stdin`。`get-app-state --json` 默认截图写磁盘并返回 `screenshot.path`；`--no-screenshot` 提速，`--restore-window` 先恢复隐藏/最小化窗口。

### 14.2 iOS Simulator

```bash
orca emulator list --json
orca emulator attach "<device-name-or-udid>" --json
orca emulator tap 0.5 0.7 --json
orca emulator type "hello" --json
orca emulator gesture \
  '[{"type":"begin","x":0.5,"y":0.8},{"type":"move","x":0.5,"y":0.4},{"type":"end","x":0.5,"y":0.2}]' --json
orca emulator button home --json
orca emulator rotate landscape_left --json
orca emulator exec --command "tap 0.5 0.7" --json
orca emulator kill --json
orca emulator shutdown --json
```

坐标为 0–1 归一化；单击用 `tap`，拖动/多步触控用 `gesture`。可用 `--worktree`、`--device`、`--emulator` 显式指定目标。

---

## 15. 移动端、通知与 Agents Feed

### 15.1 Mobile companion

iOS/Android companion 是桌面 Orca 的遥控器，不是完整编辑器。一次配对，桌面始终是真实来源。它可：

- 汇总多个本地/远程 host 的 worktree 和工作/完成/等待状态；
- 浏览完整文件树和最近 terminal scrollback；
- 选择复制粘贴，使用 Tab/Shift+Tab 附件键；Live 模式逐字符发送；
- 回复 `continue/yes` 或自由文本，附照片/文件、语音听写（Live 听写不自动 Return）；
- Web/Mobile 视图查看响应式页面；
- 查看 source control、stage/unstage、commit，关联已有 GitHub PR；
- 切换代理账户并看用量/重置倒计时；
- 用 Smart、GitHub、Linear、GitLab、Branch、Name 来源创建 workspace，并在 Advanced 控制命名/分支；
- 接收代理完成 push notification。

桌面账户/状态菜单生成一次性 pairing code，手机选择 Pair 粘贴或使用 deep link。手机和桌面需登录同一 Orca account；code 数分钟过期。连接为手机与桌面直连，没有 cloud relay；桌面关闭会断开，重开自动连接。

移动终端文字大小为 50%–200%，pinch 会吸附并记住预设，仅影响当前设备。autocomplete/autocorrect 默认关，防止改写命令；可手动开启。

异常状态 spinner 可强制刷新；配对失败先核对同账户并生成新 code。

### 15.2 Notifications 与 Inbox

代理从 working 变 idle 时触发 system notification、声音和 worktree chip。顶部 bell 保留跨 worktree 未读，点击跳到对应窗格；macOS Dock 同步 badge。通知可右键 Mark unread。

在 Notifications 设置按类别关闭 system/sound/chip，或用内置/自定义 MP3、WAV、OGG、M4A、AAC、FLAC 声音并调音量。

### 15.3 Agents Feed

侧栏 **Agents** 默认开启，按时间聚合所有 worktree 的完成、阻塞问题、未读、新建 worktree 和最近回复预览；运行中固定顶部，并按状态分组。`Cmd-F`/`Ctrl-F` 聚焦过滤，但嵌入终端有焦点时快捷键留给终端。点击事件跳至对应 worktree/pane。

Feed 是离开后集中追踪面，不能取代 header bell 或 system notification。

---

## 16. 典型工作流配方

### 16.1 三代理竞速

从同一 ref 建三个 worktree，分别启动 Claude/Codex/Cursor，发送同一 prompt；分屏观察，逐一审 diff，给胜者批注，提交推送并开 PR，删除两条失败分支。代理意见一致处通常置信度更高，分歧处暴露真正难点。

### 16.2 逐行审 AI diff

在 diff 用 `j/k` 遍历文件，检查变更是否必要、最小并符合现有风格；`c` 写完整评论；一次 Send to agent。代理修改后重新打开 diff，解决已修复评论，继续反馈，直至干净再提交。

### 16.3 Design Mode 修 UI

打开 worktree browser → Design Mode → 点问题元素 → 描述期望间距/颜色等 → 代理改代码 → 热更新 → 再点验证 → 提交。

### 16.4 管理十个 worktree

`Cmd-J` 搜索跳转，`Shift-Enter` 分屏；从侧栏状态点先处理等待输入项；退出代理用 Restart；从 bell 依次处理完成通知。已合并 worktree 及时删除，避免 palette 和 watcher 膨胀。

### 16.5 远程机器工作

添加 SSH target 并测试 → 添加远程 repo/文件夹 → 创建远程 worktree → 启动远端代理 → 本地编辑审查提交。睡眠/断网时代理继续，重连后 reattach。

---

## 17. 设置参考

| 设置页 | 主要内容 |
|---|---|
| General | Orca CLI、更新/RC/perf、UI zoom、新 worktree 默认名称 |
| Appearance | 主题、accent、density、UI/editor 字体、minimap、状态栏、Classic/Watercolor/Blue 图标、System/English/简中/韩/日/西语 |
| Git | base ref resolver、commit signing、外部 Git 编辑器、按工作自动重命名海洋生物分支 |
| Terminal | 字体/主题/光标/padding、Ghostty/Warp 导入、JIS ¥→\\、Windows shell、浮动终端 |
| Quick Commands | 全局或 project 命令及 scope 过滤 |
| Agents | 检测/自定义代理、启停、Yolo/Manual 权限、Claude/Codex 账户、startup hook |
| Browser | Profile、新标签默认 zoom、Design Mode 默认值、DevTools opt-in |
| Integrations | GitHub OAuth、Linear token、Jira site/email/token、MiniMax cookie/group/model、MCP |
| Notifications | agent finished 的 system/sound/chip、自定义声音、PR check failure、更新 |
| Voice | OpenAI transcription API key；仅本地保存，只调用转写 API |
| SSH | target、passphrase、identity、远程 worktree |
| Remote Orca Servers | 配对连接、把桌面作为 server、撤销 access link、默认 runtime |
| Shortcuts | 全部可重映射；Sleeping Workspaces 默认无键；关闭全部编辑器键 |
| Repository | repo base ref/hook、创建后命令、sidebar 图标/emoji/上传图/favicon/GitHub avatar/badge 色、Source Control AI override |
| Experimental | Agents Feed/Activity、紧凑 worktree 卡、Agent hibernation；行为可能变化 |

MiniMax 用量跟踪需在 Integrations 填 `platform.minimax.io/console/usage` 的 session cookie；group ID 和 usage model 可覆盖 cookie 推断默认值。

---

## 18. 隐私与遥测

打包版默认只发送匿名产品使用事件。使用本机随机 ID，不采集账户、邮箱、用户名、精确 IP；只带 Orca 版本、`darwin/win32/linux`、CPU 架构、粗粒度 OS release、stable/rc 通道。

采集类别：应用启动；以何种方式添加 repo/workspace；启动的代理固定类型和入口；粗粒度代理错误类别；白名单布尔/枚举设置变化；遥测同意开关。字段为固定枚举、版本或匿名 ID，不发送自由文本。

明确不发送：文件内容/路径、repo/branch 名、URL、cwd、commit message、prompt、代理输出、终端输出、原始错误和 stack。单次诊断 trace 留在本机，只有你主动分享诊断包才上传。没有 Orca 账户画像；请求仅可能派生国家级地理信号。

三种任一方式可关闭：

1. **Settings → Privacy → Share anonymous usage data** 关闭；
2. 启动环境设置 `DO_NOT_TRACK=1`；
3. 设置 `ORCA_TELEMETRY_DISABLED=1`。

环境变量只影响该次启动，取消后恢复持久设置。数据进入美国区 PostHog Cloud，保留期使用其方案默认值，仅少数 Orca 维护者有项目权限。

---

## 19. 故障排查

| 问题 | 处理 |
|---|---|
| 代理无法启动 | 在 Orca 终端手动运行 CLI；失败通常是安装/认证。检查 Settings → Agents 所见 `PATH`，再试 Restart。 |
| Diff 错乱/卡住 | 点 diff toolbar 刷新；rebase/reset 等外部 Git 操作可能发生在两次刷新间。 |
| Worktree 创建失败 | `git fetch origin`；检查分支是否已有 worktree/目标目录，换分支名或删除冲突项。 |
| `orca: command not found` | 在设置注册 CLI；macOS shim 通常在 `~/.local/bin`，确保进入 `PATH`。 |
| `browser_no_tab` | 当前 worktree 没有浏览器标签；运行 `orca tab create --url ...` 或手动打开。 |
| 内存/性能高 | 关闭不用的 worktree 以减少 watcher；多个浏览器分屏最吃内存，关闭不用的标签；可启用 hibernation。 |
| 远端连不上 | 检查地址/端口、`nc -vz`、防火墙、VPN ACL、隧道和 pairing address。 |
| 日志 | **Help → Open Logs**，报告 bug 时附上。 |

反馈渠道：[GitHub Issues](https://github.com/stablyai/orca/issues)；实时帮助见[Discord](https://discord.gg/fzjDKHxv8Q)。

---

## 20. 官方页面覆盖索引

本教程覆盖以下官方页面，便于验证是否遗漏：

- Start Here：[What is Orca](https://www.onorca.dev/docs)、[Install](https://www.onorca.dev/docs/install)、[First session](https://www.onorca.dev/docs/first-session)
- The Orca Model：[Worktrees](https://www.onorca.dev/docs/model/worktrees)、[Tabs/panes/splits](https://www.onorca.dev/docs/model/tabs-panes-splits)、[Agents/sessions](https://www.onorca.dev/docs/model/agents-sessions)、[Session restore](https://www.onorca.dev/docs/model/session-restore)、[Quick Open](https://www.onorca.dev/docs/model/quick-open)
- Agents：[Supported](https://www.onorca.dev/docs/agents/supported)、[Claude](https://www.onorca.dev/docs/agents/claude-code)、[GLM](https://www.onorca.dev/docs/agents/glm-agent)、[Codex](https://www.onorca.dev/docs/agents/codex)、[Cursor](https://www.onorca.dev/docs/agents/cursor-cli)、[Custom CLI](https://www.onorca.dev/docs/agents/custom-cli)、[Hot swap](https://www.onorca.dev/docs/agents/codex-hot-swap)、[History](https://www.onorca.dev/docs/agents/session-history)、[Hibernation](https://www.onorca.dev/docs/agents/hibernation)、[Usage](https://www.onorca.dev/docs/agents/usage-tracking)、[Hooks](https://www.onorca.dev/docs/agents/hooks-memory)
- Review：[Diff](https://www.onorca.dev/docs/review/diff-viewer)、[Annotate](https://www.onorca.dev/docs/review/annotate-ai-diff)、[Attribution](https://www.onorca.dev/docs/review/attribution)、[Commit](https://www.onorca.dev/docs/review/commit-push)、[Hosted reviews](https://www.onorca.dev/docs/review/github)、[Linear](https://www.onorca.dev/docs/review/linear)、[Jira](https://www.onorca.dev/docs/review/jira)
- Editing：[Monaco](https://www.onorca.dev/docs/editing/monaco)、[Markdown](https://www.onorca.dev/docs/editing/markdown)、[Viewers](https://www.onorca.dev/docs/editing/viewers)、[Explorer](https://www.onorca.dev/docs/editing/file-explorer)
- Browser：[Overview](https://www.onorca.dev/docs/browser/overview)、[Design Mode](https://www.onorca.dev/docs/browser/design-mode)、[Profiles](https://www.onorca.dev/docs/browser/profiles)
- Remote/CLI：[Terminal](https://www.onorca.dev/docs/terminal)、[SSH](https://www.onorca.dev/docs/ssh)、[Remote Servers](https://www.onorca.dev/docs/remote-servers)、[CLI overview](https://www.onorca.dev/docs/cli/overview)、[Reference](https://www.onorca.dev/docs/cli/reference)、[Orchestration](https://www.onorca.dev/docs/cli/orchestration)、[Automations](https://www.onorca.dev/docs/cli/automations)、[Computer use](https://www.onorca.dev/docs/cli/computer-use)、[Checkpoints](https://www.onorca.dev/docs/cli/worktree-checkpoints)、[Skills](https://www.onorca.dev/docs/cli/skills)
- Other：[Mobile](https://www.onorca.dev/docs/mobile)、[Notifications](https://www.onorca.dev/docs/notifications)、[Agents Feed](https://www.onorca.dev/docs/activity)、[Settings](https://www.onorca.dev/docs/settings)、[Privacy](https://www.onorca.dev/docs/telemetry)、[Troubleshooting](https://www.onorca.dev/docs/troubleshooting)
- Recipes：[Parallel agents](https://www.onorca.dev/docs/recipes/parallel-agents)、[Review diff](https://www.onorca.dev/docs/recipes/review-ai-diff)、[Jump worktrees](https://www.onorca.dev/docs/recipes/jump-worktrees)、[Design fix](https://www.onorca.dev/docs/recipes/design-mode-fix)、[Remote worktrees](https://www.onorca.dev/docs/recipes/remote-worktrees)

---

文档来源：[Orca 官方文档](https://www.onorca.dev/docs)。本文为中文结构化教程与释义，不是官方逐字翻译。
