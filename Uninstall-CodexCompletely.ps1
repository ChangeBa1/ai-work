#Requires -Version 5.1
<#
.SYNOPSIS
  彻底清理 Windows 本机上的 OpenAI Codex。

.DESCRIPTION
  默认只做预览，不会修改系统。加 -Execute 后才会执行。

  覆盖范围：
  - Codex CLI：官方独立安装、npm、pnpm、yarn、bun、winget、Chocolatey、Scoop
  - 名称明确为 Codex/OpenAI Codex 的 Appx/MSIX 或“已安装的应用”
  - Codex 进程、登录凭据、用户配置、历史、日志、缓存、残留启动器
  - VS Code/Cursor/Windsurf/VSCodium 中的 OpenAI Codex/ChatGPT 扩展及其状态
  - Process/User/Machine 三个作用域中的 CODEX_* 环境变量
  - PATH 中由 Codex 独立安装器加入的专用目录

  不默认删除：
  - ChatGPT 桌面应用（它不是 Codex 专用程序）
  - OPENAI_*/AZURE_* 等可能被其他程序共用的变量
  - 项目仓库中的 .codex 目录
  - WSL/Linux 内安装的 Codex

.EXAMPLE
  .\Uninstall-CodexCompletely.ps1
  只预览将要执行的操作。

.EXAMPLE
  .\Uninstall-CodexCompletely.ps1 -Execute
  交互确认一次后执行标准的完整清理。

.EXAMPLE
  .\Uninstall-CodexCompletely.ps1 -Execute -Force -RemoveOpenAIEnvironmentVariables
  无交互执行，并同时删除 OPENAI_* 环境变量。

.EXAMPLE
  .\Uninstall-CodexCompletely.ps1 -Execute -RemoveProjectConfiguration `
    -ProjectRoot 'D:\work\repo1','D:\work\repo2'
  另外删除所列项目根目录中的 .codex 文件夹。

.NOTES
  建议在“以管理员身份运行”的 PowerShell 中执行，这样才能清理 Machine
  环境变量、系统级 MSI 和所有用户 Appx 包。普通权限下脚本会继续清理
  当前用户范围，并报告无法处理的系统范围项目。
#>

[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$Force,
    [switch]$KeepIDEExtensions,
    [switch]$RemoveOpenAIEnvironmentVariables,
    [switch]$RemoveSharedEnvironmentVariables,
    [switch]$RemoveProjectConfiguration,
    [string[]]$ProjectRoot = @()
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:HadWarning = $false
$script:RemovedCount = 0
$script:PlannedCount = 0

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Plan([string]$Message) {
    $script:PlannedCount++
    Write-Host "[PLAN] $Message" -ForegroundColor Yellow
}

function Write-Done([string]$Message) {
    $script:RemovedCount++
    Write-Host "[ OK ] $Message" -ForegroundColor Green
}

function Write-WarningMessage([string]$Message) {
    $script:HadWarning = $true
    Write-Host "[WARN] $Message" -ForegroundColor Magenta
}

function Invoke-Removal {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    if (-not $Execute) {
        Write-Plan $Description
        return
    }

    try {
        & $Action
        Write-Done $Description
    }
    catch {
        Write-WarningMessage "$Description 失败：$($_.Exception.Message)"
    }
}

function Test-IsAdministrator {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

function Get-FullPathSafe([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    try {
        return [IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"'))
        ).TrimEnd('\')
    }
    catch {
        return $null
    }
}

function Test-SafeRemovalPath([string]$Path) {
    $full = Get-FullPathSafe $Path
    if (-not $full) { return $false }

    $root = [IO.Path]::GetPathRoot($full)
    $blocked = @(
        (Get-FullPathSafe $root),
        (Get-FullPathSafe $env:USERPROFILE),
        (Get-FullPathSafe $env:SystemDrive),
        (Get-FullPathSafe $env:ProgramFiles),
        (Get-FullPathSafe ${env:ProgramFiles(x86)}),
        (Get-FullPathSafe $env:LOCALAPPDATA),
        (Get-FullPathSafe $env:APPDATA)
    ) | Where-Object { $_ }

    return -not ($blocked -contains $full)
}

function Remove-LiteralTarget([string]$Path, [string]$Reason) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $full = Get-FullPathSafe $Path
    if (-not $full) {
        Write-WarningMessage "路径无效，已跳过：$Path"
        return
    }
    if (-not (Test-Path -LiteralPath $full)) { return }
    if (-not (Test-SafeRemovalPath $full)) {
        Write-WarningMessage "安全检查拒绝删除过宽路径：$full"
        return
    }

    Invoke-Removal "删除 $Reason：$full" {
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
    }
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description,
        [int[]]$AcceptExitCode = @(0)
    )

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $resolved) { return }

    Invoke-Removal $Description {
        & $resolved.Source @Arguments
        if ($AcceptExitCode -notcontains $LASTEXITCODE) {
            throw "$Command 退出代码为 $LASTEXITCODE"
        }
    }
}

function Get-EnvironmentVariableNames([EnvironmentVariableTarget]$Target) {
    try {
        return @([Environment]::GetEnvironmentVariables($Target).Keys |
            ForEach-Object { [string]$_ })
    }
    catch {
        Write-WarningMessage "无法读取 $Target 环境变量：$($_.Exception.Message)"
        return @()
    }
}

function Remove-EnvironmentVariableEverywhere([string]$Name) {
    foreach ($target in @(
        [EnvironmentVariableTarget]::Process,
        [EnvironmentVariableTarget]::User,
        [EnvironmentVariableTarget]::Machine
    )) {
        $current = $null
        try {
            $current = [Environment]::GetEnvironmentVariable($Name, $target)
        }
        catch {
            Write-WarningMessage "无法读取 $target 环境变量 $Name：$($_.Exception.Message)"
            continue
        }
        if ($null -eq $current) { continue }

        Invoke-Removal "删除 $target 环境变量 $Name" {
            [Environment]::SetEnvironmentVariable($Name, $null, $target)
        }
    }
}

function Get-NormalizedPathEntry([string]$Entry) {
    if ([string]::IsNullOrWhiteSpace($Entry)) { return $null }
    $expanded = [Environment]::ExpandEnvironmentVariables($Entry.Trim().Trim('"'))
    try {
        return [IO.Path]::GetFullPath($expanded).TrimEnd('\')
    }
    catch {
        return $expanded.TrimEnd('\')
    }
}

function Remove-PathEntries {
    param([string[]]$EntriesToRemove)

    $removeSet = @{}
    foreach ($entry in $EntriesToRemove) {
        $normalized = Get-NormalizedPathEntry $entry
        if ($normalized) { $removeSet[$normalized.ToLowerInvariant()] = $true }
    }

    foreach ($target in @(
        [EnvironmentVariableTarget]::Process,
        [EnvironmentVariableTarget]::User,
        [EnvironmentVariableTarget]::Machine
    )) {
        try {
            $oldPath = [Environment]::GetEnvironmentVariable('Path', $target)
        }
        catch {
            Write-WarningMessage "无法读取 $target PATH：$($_.Exception.Message)"
            continue
        }
        if ([string]::IsNullOrWhiteSpace($oldPath)) { continue }

        $oldEntries = @($oldPath -split ';' | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        })
        $newEntries = @($oldEntries | Where-Object {
            $normalized = Get-NormalizedPathEntry $_
            -not ($normalized -and $removeSet.ContainsKey($normalized.ToLowerInvariant()))
        })
        if ($newEntries.Count -eq $oldEntries.Count) { continue }

        Invoke-Removal "从 $target PATH 删除 Codex 专用目录" {
            [Environment]::SetEnvironmentVariable(
                'Path',
                ($newEntries -join ';'),
                $target
            )
        }
    }
}

function Get-CodexEnvironmentValues([string]$Name) {
    $values = New-Object System.Collections.Generic.List[string]
    foreach ($target in @(
        [EnvironmentVariableTarget]::Process,
        [EnvironmentVariableTarget]::User,
        [EnvironmentVariableTarget]::Machine
    )) {
        try {
            $value = [Environment]::GetEnvironmentVariable($Name, $target)
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $values.Add($value)
            }
        }
        catch {
            Write-WarningMessage "无法读取 $target 环境变量 $Name：$($_.Exception.Message)"
        }
    }
    return @($values | Select-Object -Unique)
}

function Test-CodexSpecificDirectory([string]$Path) {
    $full = Get-FullPathSafe $Path
    if (-not $full -or -not (Test-SafeRemovalPath $full)) { return $false }
    $leaf = Split-Path -Leaf $full
    return ($leaf -match '^(?i)\.?codex(?:[-_. ].*)?$')
}

function Test-CodexStateDirectory([string]$Path) {
    $full = Get-FullPathSafe $Path
    if (-not $full -or -not (Test-SafeRemovalPath $full)) { return $false }
    if (Test-CodexSpecificDirectory $full) { return $true }
    if (-not (Test-Path -LiteralPath $full -PathType Container)) { return $false }

    # 自定义 CODEX_HOME 可能名为 home。至少两个官方状态标记同时存在才允许整目录删除。
    $markerCount = 0
    foreach ($marker in @(
        'config.toml', 'auth.json', 'history.jsonl', 'sessions', 'packages', 'skills'
    )) {
        if (Test-Path -LiteralPath (Join-Path $full $marker)) {
            $markerCount++
        }
    }
    return ($markerCount -ge 2)
}

function Remove-CodexLaunchersFromDirectory([string]$Directory) {
    $full = Get-FullPathSafe $Directory
    if (-not $full -or -not (Test-Path -LiteralPath $full -PathType Container)) {
        return
    }

    foreach ($name in @('codex.exe', 'codex.cmd', 'codex.ps1', 'codex')) {
        Remove-LiteralTarget (Join-Path $full $name) 'Codex 启动器残留'
    }
}

function Get-UninstallEntries {
    $roots = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $items = foreach ($root in $roots) {
        Get-ItemProperty $root -ErrorAction SilentlyContinue |
            Where-Object {
                $displayNameProperty = $_.PSObject.Properties['DisplayName']
                $displayNameProperty -and
                $displayNameProperty.Value -match '^(?i)(?:OpenAI\s+)?Codex(?:\s+(?:CLI|Desktop|App))?$'
            }
    }
    return @($items | Sort-Object PSPath -Unique)
}

function Invoke-RegisteredUninstaller($Entry) {
    $displayName = [string]$Entry.PSObject.Properties['DisplayName'].Value
    $quietProperty = $Entry.PSObject.Properties['QuietUninstallString']
    $uninstallProperty = $Entry.PSObject.Properties['UninstallString']
    $line = if ($quietProperty -and $quietProperty.Value) {
        [string]$quietProperty.Value
    } elseif ($uninstallProperty) {
        [string]$uninstallProperty.Value
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($line)) {
        Write-WarningMessage "$displayName 没有可用的卸载命令"
        return
    }

    if ($line -match '(?i)msiexec(?:\.exe)?\s+/(?:i|x)\s*[\x22\x27]?(\{[0-9a-f-]+\})') {
        $productCode = $Matches[1]
        Invoke-ExternalCommand 'msiexec.exe' @(
            '/x', $productCode, '/qn', '/norestart'
        ) "卸载已注册的应用：$displayName"
        return
    }

    $exe = $null
    $argumentLine = ''
    if ($line -match '^\s*"([^"]+)"\s*(.*)$') {
        $exe = $Matches[1]
        $argumentLine = $Matches[2]
    }
    elseif ($line -match '^\s*(\S+)\s*(.*)$') {
        $exe = $Matches[1]
        $argumentLine = $Matches[2]
    }

    if (-not $exe) {
        Write-WarningMessage "无法安全解析 $displayName 的卸载命令：$line"
        return
    }

    Invoke-Removal "卸载已注册的应用：$displayName" {
        $process = Start-Process -FilePath $exe -ArgumentList $argumentLine `
            -Wait -PassThru -ErrorAction Stop
        if ($process.ExitCode -ne 0) {
            throw "卸载器退出代码为 $($process.ExitCode)"
        }
    }
}

function Get-ProviderEnvironmentVariableNames([string[]]$ConfigFiles) {
    $names = New-Object System.Collections.Generic.List[string]
    foreach ($file in $ConfigFiles | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        try {
            $text = Get-Content -LiteralPath $file -Raw -ErrorAction Stop
            $matches = [regex]::Matches(
                $text,
                '(?im)^\s*env_key\s*=\s*[\x22\x27]([A-Za-z_][A-Za-z0-9_]*)[\x22\x27]'
            )
            foreach ($match in $matches) {
                $names.Add($match.Groups[1].Value)
            }
        }
        catch {
            Write-WarningMessage "无法检查配置中的 env_key：$file"
        }
    }
    return @($names | Sort-Object -Unique)
}

Write-Host ''
Write-Host '=== OpenAI Codex Windows 完整清理 ===' -ForegroundColor White
if ($Execute) {
    Write-Info '模式：执行删除'
} else {
    Write-Info '模式：仅预览；未传入 -Execute，不会修改任何内容'
}

$isAdmin = Test-IsAdministrator
if (-not $isAdmin) {
    Write-WarningMessage '当前不是管理员；Machine 环境变量、系统级应用可能无法清理。'
}

if ($Execute -and -not $Force) {
    Write-Host ''
    Write-Host '将永久删除 Codex 的程序、登录凭据、配置、历史和缓存。' `
        -ForegroundColor Red
    $answer = Read-Host '请输入 DELETE CODEX 继续'
    if ($answer -cne 'DELETE CODEX') {
        Write-Info '输入不匹配，操作已取消。'
        exit 2
    }
}

# 在删环境变量前保存自定义路径。
$codexHomes = @(@(
    (Join-Path $env:USERPROFILE '.codex')
    Get-CodexEnvironmentValues 'CODEX_HOME'
) | Where-Object { $_ } | Select-Object -Unique)

$sqliteHomes = @(@(Get-CodexEnvironmentValues 'CODEX_SQLITE_HOME') |
    Where-Object { $_ } | Select-Object -Unique)

$defaultInstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\OpenAI\Codex'
$defaultInstallBin = Join-Path $defaultInstallRoot 'bin'
$installDirectories = @(@(
    $defaultInstallBin
    Get-CodexEnvironmentValues 'CODEX_INSTALL_DIR'
) | Where-Object { $_ } | Select-Object -Unique)

$configFiles = foreach ($codexHomePath in $codexHomes) {
    Join-Path $codexHomePath 'config.toml'
    if (Test-Path -LiteralPath $codexHomePath -PathType Container) {
        Get-ChildItem -LiteralPath $codexHomePath -Filter '*.config.toml' `
            -File -ErrorAction SilentlyContinue |
            ForEach-Object { $_.FullName }
    }
}
$providerVariables = @(Get-ProviderEnvironmentVariableNames $configFiles)

# 1. 停止运行实例并优先注销，让 CLI 清掉文件或系统凭据库中的令牌。
$codexProcesses = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -match '^(?i)codex(?:[-_.].*)?$'
})
foreach ($process in $codexProcesses) {
    $processId = $process.Id
    $processName = $process.ProcessName
    Invoke-Removal "停止进程 $processName (PID $processId)" {
        Stop-Process -Id $processId -Force -ErrorAction Stop
    }
}

if (Get-Command codex -ErrorAction SilentlyContinue) {
    Invoke-ExternalCommand 'codex' @('logout') '注销 Codex 并清除 CLI 凭据' @(0, 1)
}

# CLI 损坏时，继续清理 Windows 凭据管理器中名称含 Codex 的条目。
if (Get-Command cmdkey.exe -ErrorAction SilentlyContinue) {
    try {
        $credentialTargets = @(& cmdkey.exe /list 2>$null |
            Where-Object { $_ -match '(?i)codex' } |
            ForEach-Object {
                if ($_ -match '^\s*[^:：]+[:：]\s*(.+)$') {
                    $Matches[1].Trim()
                }
            } |
            Where-Object { $_ -match '(?i)codex' } |
            Sort-Object -Unique)
        foreach ($credentialTarget in $credentialTargets) {
            Invoke-ExternalCommand 'cmdkey.exe' @(
                "/delete:$credentialTarget"
            ) "删除 Windows 凭据管理器中的 Codex 凭据：$credentialTarget"
        }
    }
    catch {
        Write-WarningMessage "无法枚举 Windows 凭据管理器：$($_.Exception.Message)"
    }
}

# 2. 卸载所有常见安装来源。未安装某个包时的非零退出码不会中断后续清理。
$packageManagers = @(
    @{ Command = 'npm';   Args = @('uninstall', '--global', '@openai/codex'); Description = '通过 npm 卸载 @openai/codex' },
    @{ Command = 'pnpm';  Args = @('remove', '--global', '@openai/codex');    Description = '通过 pnpm 卸载 @openai/codex' },
    @{ Command = 'yarn';  Args = @('global', 'remove', '@openai/codex');      Description = '通过 yarn 卸载 @openai/codex' },
    @{ Command = 'bun';   Args = @('remove', '--global', '@openai/codex');    Description = '通过 bun 卸载 @openai/codex' },
    @{ Command = 'scoop'; Args = @('uninstall', 'codex');                    Description = '通过 Scoop 卸载 codex' },
    @{ Command = 'choco'; Args = @('uninstall', 'codex', '-y');              Description = '通过 Chocolatey 卸载 codex' }
)
foreach ($manager in $packageManagers) {
    if (Get-Command $manager.Command -ErrorAction SilentlyContinue) {
        Invoke-ExternalCommand $manager.Command $manager.Args $manager.Description @(0, 1)
    }
}

if (Get-Command winget -ErrorAction SilentlyContinue) {
    Invoke-ExternalCommand 'winget' @(
        'uninstall', '--name', 'Codex', '--exact', '--silent',
        '--disable-interactivity', '--accept-source-agreements'
    ) '通过 winget 卸载名称精确为 Codex 的应用' @(0, -1978335212)
}

$appxPackages = @(Get-AppxPackage -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^(?i)(?:OpenAI[._-])?Codex(?:[._-].*)?$'
})
foreach ($package in $appxPackages) {
    $packageFullName = $package.PackageFullName
    Invoke-Removal "卸载 Appx/MSIX：$packageFullName" {
        Remove-AppxPackage -Package $packageFullName -ErrorAction Stop
    }
}

foreach ($entry in Get-UninstallEntries) {
    Invoke-RegisteredUninstaller $entry
}

# 3. IDE 扩展。openai.chatgpt 是 VS Code 系 Codex 扩展使用过的正式扩展 ID。
if (-not $KeepIDEExtensions) {
    foreach ($editor in @(
        'code', 'code-insiders', 'cursor', 'windsurf', 'codium'
    )) {
        $editorCommand = Get-Command $editor -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $editorCommand) { continue }
        try {
            $extensions = @(& $editorCommand.Source --list-extensions 2>$null)
        }
        catch {
            $extensions = @()
        }
        foreach ($extensionId in @('openai.chatgpt', 'openai.codex')) {
            if ($extensions -contains $extensionId) {
                Invoke-ExternalCommand $editor @(
                    '--uninstall-extension', $extensionId
                ) "从 $editor 卸载扩展 $extensionId"
            }
        }
    }

    $extensionRoots = @(
        (Join-Path $env:USERPROFILE '.vscode\extensions'),
        (Join-Path $env:USERPROFILE '.vscode-insiders\extensions'),
        (Join-Path $env:USERPROFILE '.cursor\extensions'),
        (Join-Path $env:USERPROFILE '.windsurf\extensions'),
        (Join-Path $env:USERPROFILE '.vscode-oss\extensions')
    )
    foreach ($root in $extensionRoots) {
        if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
        Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match '^(?i)openai\.(?:chatgpt|codex)(?:-|$)'
            } |
            ForEach-Object {
                Remove-LiteralTarget $_.FullName 'IDE 扩展残留'
            }
    }

    foreach ($statePath in @(
        (Join-Path $env:APPDATA 'Code\User\globalStorage\openai.chatgpt'),
        (Join-Path $env:APPDATA 'Code - Insiders\User\globalStorage\openai.chatgpt'),
        (Join-Path $env:APPDATA 'Cursor\User\globalStorage\openai.chatgpt'),
        (Join-Path $env:APPDATA 'Windsurf\User\globalStorage\openai.chatgpt'),
        (Join-Path $env:APPDATA 'VSCodium\User\globalStorage\openai.chatgpt'),
        (Join-Path $env:APPDATA 'Code\User\globalStorage\openai.codex'),
        (Join-Path $env:APPDATA 'Cursor\User\globalStorage\openai.codex')
    )) {
        Remove-LiteralTarget $statePath 'IDE 中的 Codex 扩展状态'
    }
}

# 4. 配置、历史、缓存和程序残留。
foreach ($codexHomePath in $codexHomes) {
    if (Test-CodexStateDirectory $codexHomePath) {
        Remove-LiteralTarget $codexHomePath 'Codex 用户状态目录'
    }
    else {
        Write-WarningMessage "自定义 CODEX_HOME 不是 Codex 专用目录名，未整目录删除：$codexHomePath"
        foreach ($child in @(
            'auth.json', 'config.toml', 'history.jsonl', 'log', 'logs',
            'sessions', 'packages\standalone'
        )) {
            Remove-LiteralTarget (Join-Path $codexHomePath $child) '自定义 CODEX_HOME 中的已知 Codex 数据'
        }
    }
}

foreach ($sqliteHome in $sqliteHomes) {
    $normalized = Get-FullPathSafe $sqliteHome
    $insideCodexHome = $false
    foreach ($codexHomePath in $codexHomes) {
        $normalizedHome = Get-FullPathSafe $codexHomePath
        if ($normalized -and $normalizedHome -and
            $normalized.StartsWith($normalizedHome + '\', [StringComparison]::OrdinalIgnoreCase)) {
            $insideCodexHome = $true
        }
    }
    if (-not $insideCodexHome -and (Test-CodexSpecificDirectory $sqliteHome)) {
        Remove-LiteralTarget $sqliteHome 'CODEX_SQLITE_HOME 状态目录'
    }
    elseif (-not $insideCodexHome -and (Test-Path -LiteralPath $sqliteHome)) {
        $sqliteFiles = @(Get-ChildItem -LiteralPath $sqliteHome -File `
            -ErrorAction SilentlyContinue | Where-Object {
                $_.Name -match '^(?i)(?:codex|state).*\.sqlite(?:-(?:wal|shm))?$'
            })
        foreach ($sqliteFile in $sqliteFiles) {
            Remove-LiteralTarget $sqliteFile.FullName '自定义 CODEX_SQLITE_HOME 中的 Codex 数据库'
        }
        Write-WarningMessage "自定义 CODEX_SQLITE_HOME 不是 Codex 专用目录名，只清理了可明确识别的数据库：$sqliteHome"
    }
}

foreach ($installDirectory in $installDirectories) {
    Remove-CodexLaunchersFromDirectory $installDirectory
}

foreach ($path in @(
    $defaultInstallRoot,
    (Join-Path $env:ProgramFiles 'OpenAI\Codex'),
    (Join-Path ${env:ProgramFiles(x86)} 'OpenAI\Codex'),
    (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex'),
    (Join-Path $env:APPDATA 'OpenAI\Codex'),
    (Join-Path $env:LOCALAPPDATA 'Codex'),
    (Join-Path $env:APPDATA 'Codex'),
    (Join-Path $env:APPDATA 'npm\node_modules\@openai\codex'),
    (Join-Path $env:APPDATA 'npm\codex'),
    (Join-Path $env:APPDATA 'npm\codex.cmd'),
    (Join-Path $env:APPDATA 'npm\codex.ps1'),
    (Join-Path $env:LOCALAPPDATA 'pnpm\codex'),
    (Join-Path $env:LOCALAPPDATA 'pnpm\codex.cmd'),
    (Join-Path $env:LOCALAPPDATA 'pnpm\codex.ps1'),
    (Join-Path $env:USERPROFILE '.bun\bin\codex.exe'),
    (Join-Path $env:USERPROFILE '.bun\bin\codex'),
    (Join-Path $env:USERPROFILE '.local\bin\codex.exe'),
    (Join-Path $env:USERPROFILE '.local\bin\codex'),
    (Join-Path $env:LOCALAPPDATA 'Yarn\bin\codex'),
    (Join-Path $env:LOCALAPPDATA 'Yarn\bin\codex.cmd')
)) {
    Remove-LiteralTarget $path 'Codex 程序或包管理器残留'
}

# 清理自定义 npm 全局前缀中的精确包目录和启动器，不触碰其他全局包。
if (Get-Command npm -ErrorAction SilentlyContinue) {
    try {
        $npmRoot = [string](@(& npm root --global 2>$null) | Select-Object -Last 1)
        if (-not [string]::IsNullOrWhiteSpace($npmRoot)) {
            Remove-LiteralTarget (Join-Path $npmRoot.Trim() '@openai\codex') `
                '自定义 npm 全局目录中的 @openai/codex'
        }
        $npmPrefix = [string](@(& npm prefix --global 2>$null) | Select-Object -Last 1)
        if (-not [string]::IsNullOrWhiteSpace($npmPrefix)) {
            Remove-CodexLaunchersFromDirectory $npmPrefix.Trim()
        }
    }
    catch {
        Write-WarningMessage "无法检查 npm 全局目录：$($_.Exception.Message)"
    }
}

# pnpm 的全局版本目录中可能存在多个版本号，只枚举固定包名，不删除 pnpm 共享目录。
$pnpmGlobal = Join-Path $env:LOCALAPPDATA 'pnpm\global'
if (Test-Path -LiteralPath $pnpmGlobal -PathType Container) {
    Get-ChildItem -LiteralPath $pnpmGlobal -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -match '(?i)[\\/]node_modules[\\/]@openai[\\/]codex$'
        } |
        ForEach-Object {
            Remove-LiteralTarget $_.FullName 'pnpm 中的 @openai/codex 残留'
        }
}

# 删除名称精确对应 Codex 的注册表残留；不删除 OpenAI/ChatGPT 共用父项。
foreach ($registryPath in @(
    'HKCU:\Software\OpenAI\Codex',
    'HKCU:\Software\Codex',
    'HKCU:\Software\Classes\codex',
    'HKCU:\Software\Classes\Applications\codex.exe',
    'HKLM:\Software\OpenAI\Codex',
    'HKLM:\Software\Codex',
    'HKLM:\Software\WOW6432Node\OpenAI\Codex',
    'HKLM:\Software\Classes\Applications\codex.exe'
)) {
    if (Test-Path -LiteralPath $registryPath) {
        Invoke-Removal "删除注册表残留：$registryPath" {
            Remove-Item -LiteralPath $registryPath -Recurse -Force -ErrorAction Stop
        }
    }
}

# 5. 环境变量与 PATH。
$codexVariableNames = New-Object System.Collections.Generic.HashSet[string](
    [StringComparer]::OrdinalIgnoreCase
)
foreach ($target in @(
    [EnvironmentVariableTarget]::Process,
    [EnvironmentVariableTarget]::User,
    [EnvironmentVariableTarget]::Machine
)) {
    foreach ($name in Get-EnvironmentVariableNames $target) {
        if ($name -match '^(?i)CODEX(?:_|$)') {
            [void]$codexVariableNames.Add($name)
        }
    }
}
foreach ($name in $codexVariableNames) {
    Remove-EnvironmentVariableEverywhere $name
}

if ($RemoveOpenAIEnvironmentVariables) {
    $openAIVariableNames = New-Object System.Collections.Generic.HashSet[string](
        [StringComparer]::OrdinalIgnoreCase
    )
    foreach ($target in @(
        [EnvironmentVariableTarget]::Process,
        [EnvironmentVariableTarget]::User,
        [EnvironmentVariableTarget]::Machine
    )) {
        foreach ($name in Get-EnvironmentVariableNames $target) {
            if ($name -match '^(?i)OPENAI_') {
                [void]$openAIVariableNames.Add($name)
            }
        }
    }
    foreach ($name in $openAIVariableNames) {
        Remove-EnvironmentVariableEverywhere $name
    }

    foreach ($name in $providerVariables) {
        if ($name -notmatch '^(?i)CODEX(?:_|$)' -and
            $name -notmatch '^(?i)OPENAI_') {
            Remove-EnvironmentVariableEverywhere $name
        }
    }
}
elseif ($providerVariables.Count -gt 0) {
    Write-WarningMessage (
        '配置曾引用以下提供商变量；因可能被其他程序共用，默认保留：' +
        ($providerVariables -join ', ') +
        '。如确认只供 Codex 使用，请加 -RemoveOpenAIEnvironmentVariables。'
    )
}

if ($RemoveSharedEnvironmentVariables) {
    foreach ($name in @('RUST_LOG', 'SSL_CERT_FILE')) {
        Remove-EnvironmentVariableEverywhere $name
    }
}

Remove-PathEntries $installDirectories

# 6. 可选：只删除用户明确列出的项目根目录内的 .codex。
if ($RemoveProjectConfiguration) {
    if ($ProjectRoot.Count -eq 0) {
        Write-WarningMessage '已指定 -RemoveProjectConfiguration，但没有提供 -ProjectRoot；未扫描磁盘。'
    }
    foreach ($root in $ProjectRoot) {
        $fullRoot = Get-FullPathSafe $root
        if (-not $fullRoot -or -not (Test-Path -LiteralPath $fullRoot -PathType Container)) {
            Write-WarningMessage "项目根目录不存在，已跳过：$root"
            continue
        }
        Remove-LiteralTarget (Join-Path $fullRoot '.codex') '项目级 .codex 配置'
    }
}

# 7. 执行后复查当前 Windows 环境。
if ($Execute) {
    $residuals = New-Object System.Collections.Generic.List[string]

    foreach ($command in @(Get-Command codex -All -ErrorAction SilentlyContinue)) {
        $commandPath = if ($command.Source) { $command.Source } else { $command.Name }
        $residuals.Add("命令仍可解析：$commandPath")
    }

    foreach ($target in @(
        [EnvironmentVariableTarget]::Process,
        [EnvironmentVariableTarget]::User,
        [EnvironmentVariableTarget]::Machine
    )) {
        foreach ($name in Get-EnvironmentVariableNames $target) {
            if ($name -match '^(?i)CODEX(?:_|$)') {
                $residuals.Add("$target 环境变量仍存在：$name")
            }
        }
    }

    foreach ($candidate in @($codexHomes + $installDirectories)) {
        if (Test-Path -LiteralPath $candidate) {
            $residuals.Add("路径仍存在：$candidate")
        }
    }

    foreach ($package in @(Get-AppxPackage -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^(?i)(?:OpenAI[._-])?Codex(?:[._-].*)?$'
        })) {
        $residuals.Add("Appx/MSIX 仍存在：$($package.PackageFullName)")
    }

    if ($residuals.Count -eq 0) {
        Write-Done '复查通过：未发现 Codex 命令、状态目录、Appx 或 CODEX_* 环境变量残留'
    }
    else {
        foreach ($residual in $residuals) {
            Write-WarningMessage "复查发现残留：$residual"
        }
    }
}

Write-Host ''
if (-not $Execute) {
    Write-Host "预览完成：计划操作 $script:PlannedCount 项，未删除任何内容。" `
        -ForegroundColor Yellow
    Write-Host '确认范围后运行：.\Uninstall-CodexCompletely.ps1 -Execute' `
        -ForegroundColor White
}
else {
    Write-Host "执行完成：成功处理 $script:RemovedCount 项。" -ForegroundColor Green
    if ($script:HadWarning) {
        Write-Host '存在警告，请查看上方 [WARN] 项；必要时以管理员身份重跑。' `
            -ForegroundColor Magenta
    }
    Write-Host '请关闭所有终端和编辑器后重新打开，使 PATH/环境变量刷新。' `
        -ForegroundColor White
}

Write-Host ''
Write-Host '说明：本脚本不会删除云端 Codex 任务、OpenAI/ChatGPT 账号、浏览器中的' `
    -ForegroundColor DarkGray
Write-Host 'ChatGPT 登录会话，也不会撤销已复制到其他机器或 CI 的 API Key。' `
    -ForegroundColor DarkGray

if ($Execute -and $script:HadWarning) { exit 1 }
exit 0
