[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RuntimeJson,

    [Parameter(Mandatory = $true)]
    [string]$SourceJson,

    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Get-Controls {
    param($Document)
    if ($null -ne $Document.controls) { return @($Document.controls) }
    if ($Document -is [System.Array]) { return @($Document) }
    return @($Document)
}

function Same-Text {
    param($Left, $Right)
    return -not [string]::IsNullOrWhiteSpace([string]$Left) -and
        -not [string]::IsNullOrWhiteSpace([string]$Right) -and
        [string]::Equals([string]$Left, [string]$Right, [StringComparison]::OrdinalIgnoreCase)
}

function Get-MatchScore {
    param($Runtime, $Source)
    $score = 0
    $evidence = New-Object System.Collections.Generic.List[string]

    if ((Same-Text $Runtime.automationId $Source.automationId)) {
        $score += 120
        $evidence.Add('explicit AutomationId matched')
    }
    if ((Same-Text $Runtime.sourceName $Source.sourceName) -or
        (Same-Text $Runtime.xamlName $Source.sourceName) -or
        (Same-Text $Runtime.automationId $Source.sourceName)) {
        $score += 80
        $evidence.Add('source name matched')
    }
    if ((Same-Text $Runtime.controlType $Source.controlType) -or
        (Same-Text $Runtime.className $Source.controlType)) {
        $score += 20
        $evidence.Add('control type matched')
    }
    if ((Same-Text $Runtime.screen $Source.screen)) {
        $score += 15
        $evidence.Add('screen matched')
    }
    if ((Same-Text $Runtime.name $Source.name)) {
        $score += 10
        $evidence.Add('display/accessibility name matched')
    }
    return [pscustomobject]@{ score = $score; evidence = $evidence.ToArray() }
}

$runtimeDocument = Get-Content -Raw -LiteralPath $RuntimeJson | ConvertFrom-Json
$sourceDocument = Get-Content -Raw -LiteralPath $SourceJson | ConvertFrom-Json
$runtimeControls = Get-Controls $runtimeDocument
$sourceControls = Get-Controls $sourceDocument
$merged = New-Object System.Collections.Generic.List[object]
$unmapped = New-Object System.Collections.Generic.List[object]
$matchedSourceKeys = New-Object System.Collections.Generic.HashSet[string]

foreach ($runtime in $runtimeControls) {
    $best = $null
    $bestScore = -1
    $bestEvidence = @()
    $bestIndex = -1
    for ($i = 0; $i -lt $sourceControls.Count; $i++) {
        $match = Get-MatchScore -Runtime $runtime -Source $sourceControls[$i]
        if ($match.score -gt $bestScore) {
            $best = $sourceControls[$i]
            $bestScore = $match.score
            $bestEvidence = $match.evidence
            $bestIndex = $i
        }
    }

    if ($bestScore -lt 60) {
        $unmapped.Add($runtime)
        continue
    }

    $matchedSourceKeys.Add([string]$bestIndex) | Out-Null
    $record = [ordered]@{}
    foreach ($property in $runtime.PSObject.Properties) {
        $record[$property.Name] = $property.Value
    }
    foreach ($property in $best.PSObject.Properties) {
        if (-not $record.Contains($property.Name) -or $null -eq $record[$property.Name] -or $record[$property.Name] -eq '') {
            $record[$property.Name] = $property.Value
        }
    }

    $confidence = if ($bestEvidence -contains 'explicit AutomationId matched') {
        'high'
    } elseif ($bestEvidence -contains 'source name matched' -and
        $bestEvidence -contains 'control type matched') {
        'medium'
    } else {
        'low'
    }
    $record['sourceMappingConfidence'] = $confidence
    $record['sourceMappingEvidence'] = @($bestEvidence)
    $record['matchScore'] = $bestScore
    if (-not $record.Contains('businessCall')) { $record['businessCall'] = $null }
    $merged.Add([pscustomobject]$record)
}

$sourceOnly = New-Object System.Collections.Generic.List[object]
for ($i = 0; $i -lt $sourceControls.Count; $i++) {
    if (-not $matchedSourceKeys.Contains([string]$i)) {
        $sourceOnly.Add($sourceControls[$i])
    }
}

$capture = if ($null -ne $runtimeDocument.capture) {
    $runtimeDocument.capture
} else {
    [pscustomobject][ordered]@{
        capturedAtUtc = [DateTime]::UtcNow.ToString('o')
        coordinateSpace = 'must-be-specified-by-runtime-capture'
    }
}
$result = [pscustomobject][ordered]@{
    schemaVersion = '1.0'
    capture = $capture
    controls = $merged.ToArray()
    unmappedRuntimeControls = $unmapped.ToArray()
    sourceOnlyControls = $sourceOnly.ToArray()
    automationGaps = @()
    actions = @()
}
$json = $result | ConvertTo-Json -Depth 15

if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
    Write-Output "Wrote $($merged.Count) merged controls to $OutputPath"
} else {
    Write-Output $json
}
