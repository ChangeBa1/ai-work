# Runtime adapter selection

## Decision table

| UI surface | Primary adapter | Secondary adapter | Last resort |
|---|---|---|---|
| WPF window/control | WPFVisualTreeMcp visual tree | FlaUI/UIA3 | Screenshot/OCR |
| Standard WPF action patterns | FlaUI/UIA3 | WPFVisualTreeMcp interaction | Physical click |
| WinForms control | FlaUI/UIA2 | MSAA/AwdUI/Win32 | Screenshot/OCR |
| `WindowsFormsHost` child | UIA2/MSAA from hosted HWND | WPF host visual tree | Screenshot/OCR |
| Win32/vendor/device dialog | Win32/UIA/MSAA/AwdUI | FlaUI UIA2/3 comparison | Screenshot/OCR |
| Owner-drawn/custom control | Custom AutomationPeer/provider | Element-at-point + screenshot | OCR/visual match |
| WPF popup/context menu | WPF deep search/screen capture | UIA3 top-level popup tree | Screenshot |

Use more than one adapter when the trees disagree. Record the adapter that supplied each field.

## WPFVisualTreeMcp

Use it to inspect WPF internals that UI Automation does not expose: real visual/logical trees, dependency properties, binding state/errors, DataContext, styles/templates, resources, popup/adorner content, and layout.

Useful operations include process listing/attachment, element search/deep search, visual tree export, layout inspection, binding inspection, screenshots, condition waits, semantic clicking, value setting, and keyboard input.

Install in a disposable test environment:

```powershell
dotnet tool install -g WpfVisualTreeMcp
```

Register the installed executable or a downloaded release as an MCP stdio server. Resolve its actual path with `Get-Command wpfinspect` or from the extracted release; do not assume a hard-coded path.

Treat runtime injection as invasive:

- Confirm process ID and executable path.
- Match x86/x64 architecture.
- Avoid production tills unless explicitly authorized.
- Capture a before/after tree or screenshot.
- Detach/restart the test process if inspection changes behavior.

Project: <https://github.com/faze79/WPFVisualTreeMcp>

## FlaUI

Use FlaUI as the durable C# automation layer. Prefer:

- UIA3 for WPF and newer automation providers.
- UIA2 for WinForms controls that UIA3 exposes poorly.
- A dual-pass comparison for mixed screens.

Capture `AutomationId`, `Name`, `ControlType`, `ClassName`, `FrameworkId`, `RuntimeId`, `BoundingRectangle`, `ClickablePoint`, `IsOffscreen`, `IsEnabled`, and supported patterns.

Never equate `BoundingRectangle` with clickability. UI Automation returns physical screen coordinates, but points can be obscured or outside an irregular clickable region.

Project: <https://github.com/FlaUI/FlaUI>

## AwdUI-MCP

Use AwdUI for broad desktop discovery across UIA, MSAA, Win32 HWND, optional FlaUI, OCR, screenshots, DPI normalization, element-at-point queries, and object-repository lookup.

Prefer property-based repository objects (`AutomationId`, role/type, stable parent) to stored coordinates. Treat OCR or visual results as fallback evidence. The project describes itself as alpha software; expect retries and independently verify consequential actions.

Project: <https://github.com/aostapow/AwdUI-MCP>

Claude Code plugin setup, when that client is in use:

```text
claude plugin marketplace add aostapow/AwdUI-MCP
claude plugin install awdui-mcp
```

## Tree joining

Join separate adapter trees with:

1. Process ID and top-level HWND.
2. Parent/owner HWND chain.
3. Framework/class boundaries such as `WindowsFormsHost`.
4. Ancestor path and sibling order.
5. Physical rectangle containment/intersection.
6. Stable identifiers and control types.

Do not deduplicate nodes solely by equal rectangles; template children and overlays often share bounds.

Represent provenance per field when conflicts exist:

```json
{
  "screenBoundsPhysical": {
    "value": { "x": 100, "y": 200, "width": 180, "height": 90 },
    "source": "UIA3",
    "capturedAtUtc": "2026-07-25T13:00:00Z"
  }
}
```

Flatten provenance only for the final compact contract and keep the raw snapshots as supporting artifacts.

## DPI and monitor checks

Record:

- process DPI-awareness mode;
- monitor device name and work area;
- monitor DPI X/Y;
- window/client physical bounds;
- whether the backend reports DIP or physical pixels.

Convert only after identifying the source coordinate space. Prefer per-monitor DPI APIs over a global desktop scale. Re-query after crossing monitors.

## Platform guidance

Do not make WinAppDriver the default foundation. Use it only when an existing Selenium/Appium protocol dependency outweighs maintenance and coverage concerns.

Primary references:

- Physical UIA bounds and clickability caveat: <https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.boundingrectangleproperty>
- UI Automation identifiers and localized `Name`: <https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-usefortesting>
- WPF custom-control AutomationPeer guidance: <https://learn.microsoft.com/en-us/dotnet/desktop/wpf/controls/ui-automation-of-a-wpf-custom-control>
- WinAppDriver repository: <https://github.com/microsoft/WinAppDriver>
