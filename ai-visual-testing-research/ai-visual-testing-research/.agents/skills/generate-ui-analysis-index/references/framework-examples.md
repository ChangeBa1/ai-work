# Framework concept mapping (illustrative only)

These examples show **how to think** when mapping foreign UI concepts into bundle records. They are not parsers, scripts, or toolchain instructions.

## Desktop markup-style UI (Window / Control / Click)

Imagine a desktop app where top-level **Windows** host **Controls** wired to **Click** handlers.

| Source concept | Bundle mapping |
|---|---|
| Main window titled "Settings" | `Screen`: `screen_id="screen.settings"`, `visible_titles=["Settings"]`, `screen_type="page"` |
| Primary action button "Save" | `Element`: `role="button"`, `visible_texts=["Save"]`, `supported_actions=["click"]` |
| Click handler navigates to a confirmation view | `Transition`: `trigger_action="click"`, `from_screen_id` → `to_screen_id`, `transition_type="replace"` |

**Tips**

- Treat each distinct window or dialog surface as its own `Screen`.
- Controls with the same label on different screens need distinct `element_id` values.
- Modal overlays often map to `screen_type="modal"` and `transition_type="overlay"`.

## Web component UI (Component / onClick)

Imagine a single-page app built from reusable **Components** with **onClick** props.

| Source concept | Bundle mapping |
|---|---|
| Route `/checkout` rendering a page component | `Screen`: `screen_id="screen.checkout"`, aliases may include route paths |
| `<button onClick={submit}>` labeled "Submit" | `Element`: `role="button"`, `trigger_action` on transitions uses `"click"` |
| Submit replaces the view with an order summary | `Transition`: `transition_type="replace"`, link `trigger_element_id` to the submit button |

**Tips**

- Route changes without full page reload still produce `Transition` records when the visible screen identity changes.
- Icon-only controls: use `role="icon_button"` and empty `visible_texts` if no stable text exists.
- Multi-step wizards: optional `flows.jsonl` with ordered `steps` referencing `transition_id` values.

## What not to do

- Do not call or embed any language-specific parser, compiler API, or build workspace.
- Do not assume a particular repository layout — map **observed UI behavior and structure**, not file paths.
- Do not hard-code domain vocabulary (retail, payment, POS-specific terms) into IDs or visible text placeholders; use neutral demo names unless mirroring the user's actual product copy.
