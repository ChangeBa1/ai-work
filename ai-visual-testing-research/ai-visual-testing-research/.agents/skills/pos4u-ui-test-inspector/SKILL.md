---
name: pos4u-ui-test-inspector
description: Inspect, map, and automate controls in legacy C# 6/.NET Framework POS4U desktop applications that mix WPF, WinForms, WindowsFormsHost, Win32, and device UI. Use when Codex must correlate XAML or Designer.cs controls with a running UI tree, extract DPI-aware physical screen bounds, build stable multilingual locators, trace events into business or device calls, diagnose missing automation metadata, prepare/execute safe POS desktop UI tests with WPFVisualTreeMcp, FlaUI/UI Automation, MSAA, AwdUI, or screenshot fallback, or supply POS4U-specific evidence to generate-ui-analysis-index for a validated ui-analysis-bundle-v1.
---

# POS4U UI Test Inspector

Build a joined view of source structure, runtime accessibility/visual trees, and current screen geometry. Treat source positions as intent and runtime bounds as the only evidence of current on-screen position.

In a `Planner → Element Detector → Grounder → Executor` pipeline, act as the Element Detector and structural Grounder. Produce stable identities and current geometry for the Executor. Invoke visual grounding only when automation/visual trees cannot identify the target.

Own POS4U-specific discovery and evidence. When the requested deliverable is a UI analysis index for vnc-agent, cooperate with `generate-ui-analysis-index`: use this skill to inspect the application, then use that skill as the authoritative bundle contract and producer workflow. Do not redefine or fork its contract here.

## Read supporting guidance

- Read [references/runtime-adapters.md](references/runtime-adapters.md) before attaching to a process or choosing an inspection backend.
- Read [references/source-mapping.md](references/source-mapping.md) before tracing handlers, business calls, templates, or hosted WinForms controls.
- Read [references/output-contract.md](references/output-contract.md) before emitting or validating inspection JSON.
- Read [references/ui-analysis-bundle-handoff.md](references/ui-analysis-bundle-handoff.md) before converting POS4U evidence into `ui-analysis-bundle-v1`.

## Enforce safety

1. Determine whether the target is a development/test instance before injection or interaction.
2. Ask for explicit authorization before attaching an injector to a production POS process, performing payment/refund/void/settlement actions, or operating physical devices.
3. Inspect read-only by default. Separate discovery from action.
4. Prefer test doubles or training mode for cash changers, card terminals, printers, and customer displays.
5. Capture the target process ID, executable path, architecture, top-level HWND, window title, monitor, resolution, DPI, locale, and app state in the result metadata.

## Execute the workflow

### 1. Map source UI

Run:

```powershell
& "<skill-dir>\scripts\map-source-ui.ps1" -Root "<repo-root>" -OutputPath "<artifact-dir>\source-ui.json"
```

Use the script output as candidates, not proof. Supplement it with focused `rg` searches for dynamic control creation, templates, styles, commands, event subscriptions, navigation, and device/business calls.

### 2. Inspect the running UI

Select adapters per [references/runtime-adapters.md](references/runtime-adapters.md):

- Use WPFVisualTreeMcp for the real WPF visual/logical tree, bindings, DataContext, templates, popups, layout, and WPF element screenshots.
- Use UIA3/FlaUI for standard WPF automation properties and patterns.
- Use UIA2, MSAA, Win32 HWND, or AwdUI for old WinForms, traditional controls, external dialogs, and device/vendor windows.
- Inspect each `WindowsFormsHost` boundary as a separate HWND/tree, then join it to the WPF host using ancestry and physical bounds.
- Use screenshots/OCR only for owner-drawn elements that expose no useful automation node.

Discover available tools first. If an adapter is unavailable, report the missing layer and continue with the remaining evidence; never fabricate runtime coordinates from XAML.

Collect at minimum:

```text
processId, hwnd, parentHwnd, runtimeId, frameworkId, className
controlType, automationId, name, visible text
physical screen bounds, clickable point, offscreen/enabled/focusable state
supported patterns, z-order/occlusion evidence, parent path
```

For WPF, also collect `x:Name`, visual parent path, logical parent path, binding state, DataContext type, applied template/style, and popup owner when available.

### 3. Normalize geometry

Keep physical screen coordinates as the canonical click coordinate space. Record logical/DIP values only as additional evidence.

Compute:

```text
windowRelativeX = elementPhysicalX - clientOriginPhysicalX
windowRelativeY = elementPhysicalY - clientOriginPhysicalY
dpiScaleX = dpiX / 96
dpiScaleY = dpiY / 96
```

Do not assume the X and Y scales are identical. Re-snapshot geometry after moving/resizing a window, opening a popup, changing locale, switching monitor, or causing layout.

### 4. Join runtime and source

Use this match order:

1. Explicit `AutomationId`
2. `x:Name` or WinForms `Name`
3. Runtime class/control type plus source type and ancestor path
4. HWND/host ancestry plus intersecting physical bounds
5. Non-localized accessible name
6. Localized text plus neighboring label/container

Require multiple signals for ambiguous matches. Preserve all plausible candidates with confidence and evidence instead of forcing a single mapping.

Optionally merge normalized runtime JSON with source candidates:

```powershell
& "<skill-dir>\scripts\merge-inspection.ps1" `
  -RuntimeJson "<artifact-dir>\runtime-ui.json" `
  -SourceJson "<artifact-dir>\source-ui.json" `
  -OutputPath "<artifact-dir>\ui-inspection.json"
```

### 5. Choose stable locators

Rank locators:

```text
1. AutomationId
2. ControlType + AutomationId + stable parent path
3. x:Name / WinForms Name
4. AccessibleName / non-localized Name
5. Neighbor label + parent container
6. Current runtime BoundingRectangle
7. Screenshot/OCR/visual match
```

Do not use Japanese, English, or Chinese button text as the primary locator. Treat `RuntimeId` as opaque and session-scoped. Treat coordinates as snapshot-scoped.

Recommend explicit WPF metadata when absent:

```xml
AutomationProperties.AutomationId="Payment.Cash"
AutomationProperties.Name="{DynamicResource PaymentCashText}"
```

Recommend an appropriate `AutomationPeer` and provider patterns for custom WPF controls. Recommend `Name`, `AccessibleName`, and suitable accessibility roles for custom WinForms controls.

### 6. Select actions

Prefer semantic patterns:

```text
Invoke / Selection / Toggle / ExpandCollapse / Value
→ ClickablePoint
→ verified point inside an unobscured BoundingRectangle
→ screenshot-grounded click
```

Before a physical click, verify visibility, enabled state, offscreen state, current foreground window, popup ownership, and occlusion. Never assume the rectangle center is clickable.

After each action, wait for an observable condition and re-inspect affected elements. Avoid fixed sleeps when the backend supports condition waits.

### 7. Trace behavior

Map the runtime element to XAML or Designer.cs, then trace:

```text
control → event/command → handler/view model → logic/business service → device/data layer
```

Label regex-derived calls as candidates. Claim a definitive `businessCall` only after reading the handler and following indirection far enough to establish the call path.

### 8. Emit and validate inspection artifacts

Emit the contract in [references/output-contract.md](references/output-contract.md). Include unmapped runtime nodes and source-only controls in separate arrays.

Validate:

```powershell
& "<skill-dir>\scripts\validate-inspection.ps1" -Path "<artifact-dir>\ui-inspection.json"
```

Report:

- exact runtime state and coordinate space;
- stable locator and fallback chain;
- source/event/business mapping with confidence;
- unsupported or invisible elements;
- automation metadata gaps;
- actions performed, if any, and observed outcomes.

Never present a source-only estimate as `screenBoundsPhysical`.

### 9. Hand off a standard UI analysis bundle

Perform this step when the user asks for a UI analysis index/bundle, a vnc-agent-compatible export, or explicitly asks this skill to cooperate with `generate-ui-analysis-index`.

1. Preserve `source-ui.json`, raw runtime snapshots, and `ui-inspection.json` as supporting evidence outside the bundle directory.
2. Invoke `$generate-ui-analysis-index` and follow its `SKILL.md`, references, templates, confidence rules, and validation workflow as the authority.
3. Map POS4U evidence according to [references/ui-analysis-bundle-handoff.md](references/ui-analysis-bundle-handoff.md).
4. Deliver the flat `ui-analysis-bundle-v1` directory as the canonical consumer-facing artifact. Do not place inspection JSON, screenshots, or other private files inside it unless the bundle contract explicitly permits them.
5. Run `vnc-agent ui-index validate <bundle-dir>` exactly as directed by `generate-ui-analysis-index`. Fix every error before delivery.

Keep the two validation layers distinct:

- `validate-inspection.ps1` validates POS4U inspection evidence.
- `vnc-agent ui-index validate` validates the standard bundle.

If `generate-ui-analysis-index` is unavailable, retain the validated inspection artifacts and report that the standard bundle handoff could not be completed. Do not invent a substitute wire format.
