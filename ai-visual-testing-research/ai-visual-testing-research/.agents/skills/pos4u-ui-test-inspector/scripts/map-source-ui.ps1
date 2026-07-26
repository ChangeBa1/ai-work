[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,

    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Get-LineNumber {
    param([string]$Text, [int]$Index)
    if ($Index -le 0) { return 1 }
    return ([regex]::Matches($Text.Substring(0, $Index), "`n")).Count + 1
}

function Get-AttributeValue {
    param([string]$Attributes, [string]$Name)
    $escaped = [regex]::Escape($Name)
    $match = [regex]::Match(
        $Attributes,
        "(?<![\w:.-])$escaped\s*=\s*(?:""(?<double>[^""]*)""|'(?<single>[^']*)')",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if (-not $match.Success) { return $null }
    if ($match.Groups['double'].Success) { return $match.Groups['double'].Value }
    return $match.Groups['single'].Value
}

function Get-RelativePath {
    param([string]$BasePath, [string]$Path)
    $baseUri = [Uri]((Resolve-Path -LiteralPath $BasePath).Path.TrimEnd('\') + '\')
    $pathUri = [Uri](Resolve-Path -LiteralPath $Path).Path
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
}

function Get-HandlerTrace {
    param(
        [string]$CodePath,
        [string]$Handler
    )

    $empty = [ordered]@{
        handlerSourceFile = $null
        handlerSourceLine = $null
        businessCallCandidates = @()
    }
    if ([string]::IsNullOrWhiteSpace($Handler) -or -not (Test-Path -LiteralPath $CodePath)) {
        return [pscustomobject]$empty
    }

    $text = [IO.File]::ReadAllText($CodePath)
    $definition = [regex]::Match(
        $text,
        "(?m)^\s*(?:public|private|protected|internal)?\s*(?:async\s+)?[\w<>,\[\]\.?]+\s+" +
        [regex]::Escape($Handler) +
        "\s*\(")
    if (-not $definition.Success) { return [pscustomobject]$empty }

    $braceStart = $text.IndexOf('{', $definition.Index)
    if ($braceStart -lt 0) { return [pscustomobject]$empty }
    $depth = 0
    $braceEnd = $braceStart
    for ($i = $braceStart; $i -lt $text.Length; $i++) {
        if ($text[$i] -eq '{') { $depth++ }
        elseif ($text[$i] -eq '}') {
            $depth--
            if ($depth -eq 0) {
                $braceEnd = $i
                break
            }
        }
    }
    $body = $text.Substring($braceStart, $braceEnd - $braceStart + 1)
    $calls = New-Object System.Collections.Generic.List[string]
    $callMatches = [regex]::Matches(
        $body,
        "(?<!new\s)(?<call>(?:this\.)?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(")
    foreach ($callMatch in $callMatches) {
        $call = $callMatch.Groups['call'].Value
        if ($call -match '(?i)(Business|Logic|Service|Payment|Point|Cash|Changer|Device|Print|Transaction|Repository|Controller|Manager)') {
            if (-not $calls.Contains($call)) { $calls.Add($call) }
        }
    }

    return [pscustomobject][ordered]@{
        handlerSourceFile = $CodePath
        handlerSourceLine = Get-LineNumber -Text $text -Index $definition.Index
        businessCallCandidates = $calls.ToArray()
    }
}

$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
$controls = New-Object System.Collections.Generic.List[object]
$excluded = '\\(?:bin|obj|packages|\.git|TestResults)\\'
$eventNames = @(
    'Click', 'Checked', 'Unchecked', 'SelectionChanged', 'TextChanged',
    'ValueChanged', 'Loaded', 'MouseDown', 'MouseUp', 'TouchDown',
    'PreviewMouseDown', 'ButtonBase.Click'
)

$xamlFiles = Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File -Filter '*.xaml' |
    Where-Object { $_.FullName -notmatch $excluded }

foreach ($file in $xamlFiles) {
    $text = [IO.File]::ReadAllText($file.FullName)
    $rootClass = Get-AttributeValue -Attributes $text -Name 'x:Class'
    $screen = if ($rootClass) { ($rootClass -split '\.')[-1] } else { $file.BaseName }
    $codePath = $file.FullName + '.cs'
    $elementMatches = [regex]::Matches(
        $text,
        '<(?<tag>[A-Za-z_][\w:.-]*)(?<attrs>(?:"[^"]*"|''[^'']*''|[^''">])*)/?>',
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )

    foreach ($elementMatch in $elementMatches) {
        $tag = $elementMatch.Groups['tag'].Value
        if ($tag -in @('ResourceDictionary', 'Style', 'Setter', 'Trigger', 'DataTrigger')) { continue }
        $attrs = $elementMatch.Groups['attrs'].Value
        $sourceName = Get-AttributeValue -Attributes $attrs -Name 'x:Name'
        if (-not $sourceName) { $sourceName = Get-AttributeValue -Attributes $attrs -Name 'Name' }
        $automationId = Get-AttributeValue -Attributes $attrs -Name 'AutomationProperties.AutomationId'
        $accessibleName = Get-AttributeValue -Attributes $attrs -Name 'AutomationProperties.Name'
        $displayText = Get-AttributeValue -Attributes $attrs -Name 'Content'
        if (-not $displayText) { $displayText = Get-AttributeValue -Attributes $attrs -Name 'Text' }
        $command = Get-AttributeValue -Attributes $attrs -Name 'Command'
        $bindings = New-Object System.Collections.Generic.List[object]

        foreach ($eventName in $eventNames) {
            $handler = Get-AttributeValue -Attributes $attrs -Name $eventName
            if ($handler) {
                $bindings.Add([pscustomobject][ordered]@{
                    eventName = $eventName
                    handler = $handler
                })
            }
        }

        if (-not $sourceName -and -not $automationId -and -not $command -and $bindings.Count -eq 0) {
            continue
        }

        $businessCandidates = New-Object System.Collections.Generic.List[string]
        $handlerFile = $null
        $handlerLine = $null
        foreach ($binding in $bindings) {
            $trace = Get-HandlerTrace -CodePath $codePath -Handler $binding.handler
            if ($trace.handlerSourceLine -and -not $handlerLine) {
                $handlerFile = Get-RelativePath -BasePath $resolvedRoot -Path $trace.handlerSourceFile
                $handlerLine = $trace.handlerSourceLine
            }
            foreach ($candidate in $trace.businessCallCandidates) {
                if (-not $businessCandidates.Contains($candidate)) { $businessCandidates.Add($candidate) }
            }
        }

        $firstBinding = $null
        if ($bindings.Count -gt 0) { $firstBinding = $bindings.Item(0) }
        $controls.Add([pscustomobject][ordered]@{
            screen = $screen
            framework = 'WPF'
            controlType = ($tag -split ':')[-1]
            automationId = $automationId
            sourceName = $sourceName
            name = if ($accessibleName) { $accessibleName } else { $displayText }
            sourceFile = Get-RelativePath -BasePath $resolvedRoot -Path $file.FullName
            sourceLine = Get-LineNumber -Text $text -Index $elementMatch.Index
            eventName = if ($firstBinding) { $firstBinding.eventName } else { $null }
            eventHandler = if ($firstBinding) { $firstBinding.handler } else { $null }
            eventBindings = $bindings.ToArray()
            command = $command
            handlerSourceFile = $handlerFile
            handlerSourceLine = $handlerLine
            businessCall = $null
            businessCallCandidates = $businessCandidates.ToArray()
            sourceMappingConfidence = 'source-only'
        })
    }
}

$designerFiles = Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File -Filter '*.Designer.cs' |
    Where-Object {
        $_.FullName -notmatch $excluded -and
        $_.Name -notmatch '^(Resources|Settings)\.Designer\.cs$'
    }

foreach ($file in $designerFiles) {
    $text = [IO.File]::ReadAllText($file.FullName)
    if ($text -notmatch 'System\.Windows\.Forms|\.Location\s*=|\.Controls\.Add\s*\(') { continue }
    $screen = $file.Name -replace '\.Designer\.cs$', ''
    $codePath = $file.FullName -replace '\.Designer\.cs$', '.cs'
    $assignments = [regex]::Matches(
        $text,
        '(?m)^\s*this\.(?<id>[A-Za-z_]\w*)\s*=\s*new\s+(?<type>[\w\.]+)\s*\('
    )

    for ($index = 0; $index -lt $assignments.Count; $index++) {
        $assignment = $assignments[$index]
        $id = $assignment.Groups['id'].Value
        $type = $assignment.Groups['type'].Value
        $blockEnd = if ($index + 1 -lt $assignments.Count) { $assignments[$index + 1].Index } else { $text.Length }
        $block = $text.Substring($assignment.Index, $blockEnd - $assignment.Index)
        $escapedId = [regex]::Escape($id)
        $isUi = $type -match 'Windows\.Forms' -or
            $block -match "this\.$escapedId\.(?:Location|Size|Dock|Anchor|TabIndex|Name|AccessibleName)\s*="
        if (-not $isUi) { continue }

        $nameMatch = [regex]::Match($block, "this\.$escapedId\.Name\s*=\s*""(?<v>[^""]*)""")
        $accessibleMatch = [regex]::Match($block, "this\.$escapedId\.AccessibleName\s*=\s*""(?<v>[^""]*)""")
        $textMatch = [regex]::Match($block, "this\.$escapedId\.Text\s*=\s*""(?<v>[^""]*)""")
        $eventMatches = [regex]::Matches(
            $block,
            "this\.$escapedId\.(?<event>[A-Za-z_]\w*)\s*\+=.*?this\.(?<handler>[A-Za-z_]\w*)"
        )
        $bindings = New-Object System.Collections.Generic.List[object]
        foreach ($eventMatch in $eventMatches) {
            $bindings.Add([pscustomobject][ordered]@{
                eventName = $eventMatch.Groups['event'].Value
                handler = $eventMatch.Groups['handler'].Value
            })
        }
        $firstBinding = $null
        if ($bindings.Count -gt 0) { $firstBinding = $bindings.Item(0) }
        $trace = if ($firstBinding) {
            Get-HandlerTrace -CodePath $codePath -Handler $firstBinding.handler
        } else {
            [pscustomobject]@{
                handlerSourceFile = $null
                handlerSourceLine = $null
                businessCallCandidates = @()
            }
        }

        $controls.Add([pscustomobject][ordered]@{
            screen = $screen
            framework = 'WinForms'
            controlType = ($type -split '\.')[-1]
            automationId = $null
            sourceName = if ($nameMatch.Success) { $nameMatch.Groups['v'].Value } else { $id }
            name = if ($accessibleMatch.Success) {
                $accessibleMatch.Groups['v'].Value
            } elseif ($textMatch.Success) {
                $textMatch.Groups['v'].Value
            } else {
                $null
            }
            sourceFile = Get-RelativePath -BasePath $resolvedRoot -Path $file.FullName
            sourceLine = Get-LineNumber -Text $text -Index $assignment.Index
            eventName = if ($firstBinding) { $firstBinding.eventName } else { $null }
            eventHandler = if ($firstBinding) { $firstBinding.handler } else { $null }
            eventBindings = $bindings.ToArray()
            command = $null
            handlerSourceFile = if ($trace.handlerSourceFile) {
                Get-RelativePath -BasePath $resolvedRoot -Path $trace.handlerSourceFile
            } else {
                $null
            }
            handlerSourceLine = $trace.handlerSourceLine
            businessCall = $null
            businessCallCandidates = @($trace.businessCallCandidates)
            sourceMappingConfidence = 'source-only'
        })
    }
}

$result = [pscustomobject][ordered]@{
    schemaVersion = '1.0-source-map'
    generatedAtUtc = [DateTime]::UtcNow.ToString('o')
    repositoryRoot = $resolvedRoot
    controls = $controls.ToArray()
}
$json = $result | ConvertTo-Json -Depth 10

if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
    Write-Output "Wrote $($controls.Count) source controls to $OutputPath"
} else {
    Write-Output $json
}
