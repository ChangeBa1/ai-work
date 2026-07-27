# Inspection output contract

This contract is the rich POS4U inspection/evidence format, not the vnc-agent exchange format. When the requested deliverable is `ui-analysis-bundle-v1`, keep this JSON outside the bundle and follow [ui-analysis-bundle-handoff.md](ui-analysis-bundle-handoff.md) plus `generate-ui-analysis-index`.

## Top-level shape

Emit:

```json
{
  "schemaVersion": "1.0",
  "capture": {
    "capturedAtUtc": "2026-07-25T13:00:00Z",
    "repositoryRoot": "D:\\PROJ\\NoteType",
    "processId": 1234,
    "executablePath": "D:\\Test\\POS4U.exe",
    "architecture": "x86",
    "topLevelHwnd": "0x001204AC",
    "windowTitle": "POS4U",
    "locale": "ja-JP",
    "monitor": "\\\\.\\DISPLAY1",
    "dpiX": 120,
    "dpiY": 120,
    "dpiScaleX": 1.25,
    "dpiScaleY": 1.25,
    "coordinateSpace": "physical-screen-pixels",
    "adapters": ["WPFVisualTreeMcp", "UIA3", "UIA2"]
  },
  "controls": [],
  "unmappedRuntimeControls": [],
  "sourceOnlyControls": [],
  "automationGaps": [],
  "actions": []
}
```

Use `null` for unknown values. Do not use `0,0,0,0` as a substitute for unknown bounds.

## Control record

```json
{
  "screen": "PaymentWindow",
  "framework": "WPF",
  "controlType": "Button",
  "className": "Button",
  "frameworkId": "WPF",
  "processId": 1234,
  "hwnd": "0x001204AC",
  "parentHwnd": null,
  "runtimeId": [42, 1234, 7],
  "automationId": "Payment.Cash",
  "sourceName": "btnCashPayment",
  "name": "現金",
  "sourceFile": "PaymentWindow.xaml",
  "sourceLine": 142,
  "screenBoundsPhysical": {
    "x": 1180,
    "y": 720,
    "width": 180,
    "height": 90
  },
  "windowRelativeBoundsPhysical": {
    "x": 980,
    "y": 610,
    "width": 180,
    "height": 90
  },
  "clickablePointPhysical": {
    "x": 1270,
    "y": 765
  },
  "dpiScaleX": 1.25,
  "dpiScaleY": 1.25,
  "isVisible": true,
  "isOffscreen": false,
  "isEnabled": true,
  "isOccluded": false,
  "actionPatterns": ["Invoke"],
  "stableLocator": {
    "strategy": "AutomationId",
    "value": "Payment.Cash"
  },
  "locatorFallbacks": [
    {
      "strategy": "ControlType+SourceName+ParentPath",
      "value": "Button|btnCashPayment|PaymentWindow/Grid[2]"
    }
  ],
  "eventName": "Click",
  "eventHandler": "BtnCashPayment_Click",
  "command": null,
  "businessCall": "Business.Payment.PayByCash",
  "businessCallChain": [
    "BtnCashPayment_Click",
    "paymentService.PayByCash",
    "Business.Payment.PayByCash"
  ],
  "sourceMappingConfidence": "high",
  "sourceMappingEvidence": [
    "explicit AutomationId matched",
    "source name and control type matched"
  ],
  "fieldProvenance": {
    "screenBoundsPhysical": "UIA3",
    "eventHandler": "source",
    "businessCall": "manual-trace"
  },
  "warnings": []
}
```

## Required semantics

- `screenBoundsPhysical`: current physical desktop coordinates from runtime evidence.
- `windowRelativeBoundsPhysical`: physical offset from the top-level client origin; state the chosen origin.
- `clickablePointPhysical`: provider-supplied or verified point, not automatically rectangle center.
- `sourceLine`: 1-based line at the element/event declaration.
- `runtimeId`: opaque, session-scoped value; never persist as a cross-run locator.
- `businessCall`: definitive traced domain/device call or `null`.
- `businessCallChain`: ordered evidence; allow candidate entries only when marked in `warnings`.
- `stableLocator`: strongest non-coordinate locator available.
- `sourceMappingConfidence`: `high`, `medium`, `low`, or `unmapped`.
- `fieldProvenance`: identify the adapter or manual/source analysis for consequential fields.

## Action record

```json
{
  "atUtc": "2026-07-25T13:01:00Z",
  "target": "Payment.Cash",
  "method": "InvokePattern",
  "authorizedScope": "test/training mode",
  "precondition": "enabled and visible",
  "observedOutcome": "Cash payment confirmation dialog opened",
  "screenshotBefore": "before-cash.png",
  "screenshotAfter": "after-cash.png"
}
```

Do not log card data, PINs, credentials, personal data, or full receipt/customer information.
