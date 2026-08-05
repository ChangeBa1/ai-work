# App-perception profiles (feature 024)

Each `*.yaml` here describes **exactly one sub-window** of an application under
test. These files are **data**, not code: they are the only place in the
feature where application vocabulary (window titles, control labels) may
appear. Core code stays business-agnostic (Constitution VI) — adding a new
application means adding a file here, never editing `src/`.

Deleting a profile makes the corresponding scope fall back to the unchanged
full-frame path.

## How enhancement gets switched on

Three independent levels — all must agree:

| Level | Where | What it says |
|---|---|---|
| Deployment | `config/agent.yaml` → `app_perception.enabled` / `.allowed_plugins` | is the feature on for this machine, and which profiles may be used |
| Test case | `perception_plugins: [...]` (optional) | allow-list; catches typos at load time |
| **Step** | `perception_scope: <profile-name>` | **the only thing that actually activates it** |

A step without `perception_scope` is never enhanced — detecting a window is a
*precondition*, never a reason. That default is what makes "the window is on
screen but this step clicks the main screen behind it" safe with no work from
the test author.

## Adding a new sub-window

### 1. Generate a draft from the UI definition

```bash
cd vnc_agent

# inspect what the designer file contains first
python scripts/gen_app_profile_from_designer.py \
    /path/to/App/MyWindowForm.Designer.cs --list

# then emit a draft profile
python scripts/gen_app_profile_from_designer.py \
    /path/to/App/MyWindowForm.Designer.cs \
    --name my-window \
    --anchors "Label A:,Label B:,SomeButton" \
    -o profiles/app_perception/my-window.yaml
```

The script is **read-only** with respect to the application source tree — it
only reads the designer file and writes YAML inside this repository.

### 2. Review the draft by hand — four things the generator cannot know

1. **Anchors must be text OCR actually reads on the live screen.** Prefer
   ASCII, digits and kanji. The deployed OCR model garbles some kana, so a
   kana anchor makes detection intermittent.
2. **Anchors must not also appear outside the window.** If they do, the anchor
   union gets dragged off-window and detection either fails plausibility or
   produces a wrong region. (Concrete example: `cash-changer-sim` deliberately
   avoids its own `合計` label, because the main POS screen has one too.)
3. **Drop anchors whose text changes at runtime** — table contents, counters,
   timestamps, status values.
4. **Check `padding_ratio` against a real screenshot.** Padding is relative to
   the *anchor union*, so a window whose labels cluster in one corner needs
   much more padding than one whose labels span it. Compare the two shipped
   profiles: `scanner-sim` needs `right: 0.05`, `cash-changer-sim` needs
   `right: 0.62`.

Also verify `source_geometry.client_size` against a capture: DPI scaling means
design-time pixels rarely equal on-screen pixels. That is fine — the mapping
absorbs a uniform scale — but a wildly different aspect means you are looking
at the wrong form.

### 3. Enable it and annotate the steps

```yaml
# config/agent.yaml
app_perception:
  enabled: true
  allowed_plugins:
    win10-test-01: ["my-window"]
```

```yaml
# your test case — ONLY on steps that click inside that window
- id: click-something-inside-the-window
  perception_scope: my-window
```

Leave every other step alone.

## Field reference

Shape-related fields are **optional** and have **no core defaults**. The
surveyed target environment spans aspect ratios 0.73–5.34 and 3.3%–77.1% of
screen area, so any built-in shape default would be wrong for someone. Declare
ranges only when you want the extra safety for *this* window.

| Field | Required | Notes |
|---|---|---|
| `name` | yes | `[a-z0-9-]+`; the value steps put in `perception_scope` |
| `required_anchors` | yes | ≥1 text; all must hit unless `min_required_anchor_hits` says otherwise |
| `min_required_anchor_hits` | no | default = all. Requiring all fails open on a partial OCR read (safe direction) |
| `padding_ratio` | no | per-side, relative to the anchor union's own width/height |
| `area_ratio_range` / `aspect_ratio_range` / `min_size_px` | no | per-window plausibility |
| `zoom.scale` | no | override the fixed default scale |
| `anchor_constraints` | no | see below |
| `source_geometry` | no | design-time layout snapshot |

### `anchor_constraints`

Generic geometric relations (`same_row`, `same_column`, `right_of`, `left_of`,
`above`, `below`, `between`) between a grounding candidate and profile anchors.

Each constraint carries its own `enforce` flag:

- `enforce: true` — **strong prior**: a violating candidate is rejected. Use it
  when the layout genuinely guarantees the relation (e.g. "the Scan button is
  on the same row as the TopMost checkbox, to its right"). This is what stops
  the click landing in the table below.
- `enforce: false` (default) — **weak hint**: violations are recorded in the
  run audit only, never rejected.

Deployment can downgrade everything with
`app_perception.anchor_constraint_mode: record_only` if a constraint misfires.

### `source_geometry`

A design-time snapshot: client size plus per-control rectangles and anchor
edges. At runtime the rectangles are mapped onto the *detected* window bounds
(uniform scale absorbs DPI; the residual is distributed per anchor semantics,
so a `[bottom, right]` control stays pinned to the bottom-right when the window
is resized).

**Red line:** mapped rectangles are only ever **hints and constraint inputs**.
They never become click coordinates. Source geometry is a prior, not a
position — the final click always comes from the grounding result through the
unchanged strict restoration chain (Constitution II/IV).
