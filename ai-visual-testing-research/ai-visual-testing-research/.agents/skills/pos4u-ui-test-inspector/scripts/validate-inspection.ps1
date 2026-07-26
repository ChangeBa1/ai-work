[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = 'Stop'
$document = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

if ($document.schemaVersion -ne '1.0') {
    $errors.Add("schemaVersion must be '1.0'")
}
if ($null -eq $document.capture) {
    $errors.Add('capture is required')
} elseif ($document.capture.coordinateSpace -ne 'physical-screen-pixels') {
    $warnings.Add("capture.coordinateSpace should be 'physical-screen-pixels' after runtime capture")
}
if ($null -eq $document.controls) {
    $errors.Add('controls array is required')
}

$index = 0
foreach ($control in @($document.controls)) {
    $label = "controls[$index]"
    foreach ($required in @('screen', 'framework', 'controlType')) {
        if ([string]::IsNullOrWhiteSpace([string]$control.$required)) {
            $errors.Add("$label.$required is required")
        }
    }

    if ($null -ne $control.screenBoundsPhysical) {
        foreach ($dimension in @('x', 'y', 'width', 'height')) {
            if ($null -eq $control.screenBoundsPhysical.$dimension) {
                $errors.Add("$label.screenBoundsPhysical.$dimension is required when bounds are present")
            }
        }
        if ($control.screenBoundsPhysical.width -le 0 -or $control.screenBoundsPhysical.height -le 0) {
            $warnings.Add("$label has non-positive runtime bounds")
        }
    } elseif ($control.isVisible -eq $true -and $control.isOffscreen -ne $true) {
        $warnings.Add("$label is visible but has no physical runtime bounds")
    }

    if ($null -ne $control.runtimeId -and $control.stableLocator.strategy -eq 'RuntimeId') {
        $errors.Add("$label uses session-scoped RuntimeId as stableLocator")
    }
    if ($control.stableLocator.strategy -match '(?i)coordinate|bounds|point') {
        $warnings.Add("$label uses snapshot-scoped coordinates as stableLocator")
    }
    if ($control.stableLocator.strategy -match '(?i)name|text' -and
        [string]::IsNullOrWhiteSpace([string]$control.automationId) -and
        [string]::IsNullOrWhiteSpace([string]$control.sourceName)) {
        $warnings.Add("$label may rely only on localized text")
    }
    if ($control.businessCall -and
        $control.sourceMappingConfidence -in @('low', 'source-only', 'unmapped')) {
        $warnings.Add("$label claims businessCall with weak source mapping confidence")
    }
    $index++
}

$report = [pscustomobject][ordered]@{
    valid = ($errors.Count -eq 0)
    controlCount = @($document.controls).Count
    errorCount = $errors.Count
    warningCount = $warnings.Count
    errors = $errors.ToArray()
    warnings = $warnings.ToArray()
}
$report | ConvertTo-Json -Depth 6
if ($errors.Count -gt 0) { exit 1 }
