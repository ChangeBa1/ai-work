<!--
Sync Impact Report
====================
Version: 1.0.1 → 2.0.0 [MAJOR · Full Japanese-ification + re-derivation from first principles]
Ratification: 2026-07-16 | Last Amended: 2026-07-18

Rationale (user directive 2026-07-18, "major improvement of the SDD workflow"):
  1. Governance language switched to Japanese across the board — new "Language
     Conventions" section. SDD artifacts, process files, and code comments now
     align with the conventions of stpos-backend-kugelpos (the formal code
     repository, which is in Japanese). All templates/skills/knowledge files
     were Japanese-ified in the same commit.
  2. First principles (F1–F5) made explicit; the 8 core principles are
     re-derived from them. The substance of principles I–VIII is preserved
     from v1.0.1 — that version was user-ratified and the measured facts
     have not changed.
  3. Workflow gains a "human gates" table (not replaceable by AI) and a
     commit convention (Conventional Commits + [spec:] traceability tag).

Why MAJOR: changing the governance language is a backward-incompatible
governance change (it applies to all artifacts from now on).
-->

# POS4U (trialpos) Development Constitution (English · reference translation)

> **This is a reference translation.** The authoritative source is `trialpos-snapshots/.specify/memory/constitution.md` (**v2.0.0, in Japanese**). On any discrepancy, **the source prevails**; edits here do not propagate to the source. The three language versions (zh/ja/en) are kept in sync manually.

> **Scope**: SDD code development of `trialpos-snapshots` (the POS4U codebase; C#/.NET Framework + SQL Server).
> **Nature**: POS4U is TRIAL's **currently-in-operation** POS system; this repository is a clone of the internal GitLab source of record. This constitution governs its code development (**new features + bug fixes**); the project's remaining lifecycle is about **2–3 years** (to be replaced by ST-POS).
> **Guiding spirit**: On a live legacy system, practice **behavior-preserving incremental development** — not a rewrite, but disciplined change.
> **Authority**: This constitution is the supreme governance document; facts about the baseline defer to the actual code in `trialpos-snapshots` (baseline branch `release20260728_Local` = the 202607 release).

---

## First Principles

Every principle in this constitution derives from the following five immovable facts. When the interpretation of a principle is in doubt, return here.

- **F1 — The system is live**: POS4U is running in every store right now. A regression is an operational incident (checkout stoppage, accounting inconsistency). The supreme value to protect is "never stop, never corrupt, store accounting."
- **F2 — Short remaining life**: Replacement by ST-POS is expected within 2–3 years. Large-scale rebuilds and deep modernization cannot pay back; minimal, incremental change is the economically rational mode.
- **F3 — Full verification is impossible**: 173 projects, zero existing tests, `POS4U.Framework.dll` has no source, and terminals span Windows XP through 11. The premise "everything can be verified" does not hold; the only honest option is to treat the verifiability boundary explicitly.
- **F4 — Knowledge is scattered**: Knowledge of current behavior lives in tribal knowledge and reverse-engineering documents. Development that does not record decisions and lessons repeats the same accidents. **Recorded judgment = knowledge asset.**
- **F5 — The source of record belongs to a Japanese-speaking team**: The upstream is on the internal GitLab; the team's working language and code conventions are Japanese. Artifacts that cannot flow back upstream (in Japanese, following team conventions) lose half their value.

---

## Core Principles

### I. Behavior Preservation First [NON-NEGOTIABLE]

[Derived from F1] The POS is in production; regression risk is production incident risk. By default, no change may alter observable behavior — UI flows, transaction results, state transitions, data persistence, aggregation results.

- **Before** modifying legacy code, pin current behavior with **characterization tests**, then change.
- Behavior changes are allowed **only** as intents explicitly stated in a spec and approved; never smuggled in as "drive-by optimization."
- Legacy areas that cannot be tested before change (e.g., tightly-coupled UI) must declare the risk and a manual verification plan in spec/plan.

### II. Incremental & Respect AS-IS

[Derived from F2] No big-bang rewrite or deep modernization for a system with 2–3 years to live (it does not pay back). New code works within the existing framework and layering.

- **Layers (measured)**: Business(22) / Device(78) / WinPOS(38) / LogicService(6) / POS4ULogicService(11 controllers) / POS4UBackground(16); framework base classes live in `POS4U.Framework.dll`.
- **Existing decisions (ADRs, binding)**: ADR-0001 five-part composite PK · ADR-0002 WCF net.tcp local IPC · ADR-0003 offline degradation · ADR-0004 TransactionLog XML persistence.
- Need to deviate from the existing architecture → **stop work and consult via `/speckit-adr`**. No self-approved "small exceptions."

### III. Testing Strategy: Characterization + Touch-Only (not full TDD)

[Derived from F1×F3] Zero existing tests + 173 projects make full test retrofitting unrealistic and uneconomical. Rules:

- **Legacy logic you touch**: pin behavior with characterization tests before changing.
- **New/changed logic**: its behavioral contract must be covered by tests (no tautological assertions; one test = one contract).
- Do **not** write tests for untouched code (touch-only).
- **No numeric coverage gate** (neither global nor local). The only requirement is "everything you touched is tested," enforced by code review + `/speckit-analyze` — no number games.
- **Test framework = NUnit** (good .NET Framework 4.x compatibility; friendly to characterization/parameterization). Test projects are named `<ProjectUnderTest>.Tests` and never mixed into production projects.
- **Platform separation**: spec/plan/coding/analyze may happen anywhere; **build + tests must pass on Windows + MSBuild/VS** before merging (authoring ↔ build-verify separation).
- Details in `.claude/knowledge/testing-strategy.md`.

### IV. Data Contract Stability

[Derived from F1×F2] The data layer is SQL Server, **stored-procedure centric** (measured: 160 tables / 405+ SPs / 24 views / 19 UDTs).

- The **five-part composite primary key** (CompanyCode / StoreCode / TerminalNo / ManagedNo / TransactionNo) is the root of transaction identity; do not touch it casually.
- Table / SP / UDT contract changes must stay **backward compatible** and be reviewed. **When changing/creating an SP, state which database it lives in** (Master / Tran dual DB).
- Cross-side BO backend SPs (`usp_BO*`) live in the **store-side tran DB**; changes must assess both store and cloud sides.

### V. Offline Resilience Is Inviolable

[Derived from F1] Stores keep operating through network outages — a core POS property (ADR-0003 offline degradation). Changes must not break offline execution paths or their subsequent sync/aggregation.

- Classic pitfall (known gotcha): adding a payment method without the paired changes to Azure / Background aggregation loses offline reconciliation / daily aggregation.

### VI. Process & IPC Discipline

[Derived from F1×F2] Process topology (measured): `POS4U` (WPF front) ↔ `TRAN4U` (WinForms daemon / peripheral host) over **WCF net.tcp:8012 (5-minute timeout, ADR-0002)**; plus `POS4UTwoOperatorsCH` (dual-operator sub-screen).

- **WCF net.tcp only between processes on the same machine; anything cross-machine is HTTP Web API, never WCF** (`.svc` is a URL-compatibility relic).
- Cross-process / WCF contract changes must stay **version compatible**. **Device-related changes require review before commit** (known gotcha).

### VII. Uncheckable Boundary Honesty

[Derived from F3] `Application/POS4UCloud/ExternalModule/Framework/POS4U.Framework.dll` has **no source** → its internals are **`uncheckable`**.

- Never assert its internals from guesswork. Extend **only through public hook points** (`TranBase` / `CommandBase` / `Observer` / `EventCode` / `CheckDigitM10W31`).
- Assumptions about framework behavior must be **verified on real machines/measurements**; otherwise mark `[NEEDS CLARIFICATION]` / `unverified` in spec/plan.

### VIII. Compliance & Audit Traceability

[Derived from F1] POS handles tax, transactions, and settlement; auditability must not be damaged.

- Do not break `TransactionLog` integrity or the consistency of the sales state machines (measured: SalesTranStates 28 / SelfStates 39 / CloseCountTranStates 28).
- Amount / quantity / tax handling follows existing domain rules (money columns are `[money]`; see `.claude/knowledge/domain-knowledge/`).
- No credentials in code; all SQL parameterized (SP calls guard against injection).

---

## Mandatory Stack (measured)

| Item | Constraint |
|---|---|
| Language/runtime | C# on **.NET Framework** (mostly v4.0 + v4.6.1). ⚠️ **Target version MUST NOT change**: the terminal fleet spans **Windows XP / 7 / 10 / 11**; **v4.0 is the XP-compatibility ceiling**; raising it bricks XP terminals. New code follows its project's current target; a genuinely new project picks a target compatible with its deployment OS (anything reaching XP terminals must be v4.0). |
| Front-end UI | **WPF** (POS4U) + **WinForms** (TRAN4U) |
| Cloud BO | **ASP.NET MVC5** (POS4UBO, Backoffice) |
| IPC | **WCF net.tcp** (in-store, inter-process only) |
| Edge API | **ASP.NET Web API (HTTP)** (POS4ULogicService — not WCF) |
| Data | **SQL Server (SQLEXPRESS)**, SP-centric; dual DB on one instance (Master / Tran) |
| Testing | **NUnit**; characterization + touch-only, no numeric coverage gate (Principle III / testing-strategy.md) |
| Code style | **StyleCop** (`POS4U.ruleset`); 1 class 1 file; strong-named assemblies throughout |
| Build | **Visual Studio / MSBuild (Windows)**; 3 slns: `POS4U_V4` / `POS4UBackground` / `POS4UBO_V4` |
| CI | None today → future work (GitLab CI / Azure) |

---

## Language Conventions

[Derived from F5] Artifacts must be able to flow back to the upstream team (Japanese). Aligned with the conventions of `stpos-backend-kugelpos` (formal code repository = Japanese).

| Target | Language |
|---|---|
| SDD artifacts (under `specs/`: spec / plan / tasks / research / data-model / contracts / quickstart / test-spec / test-results / spec_review / checklists) | **Japanese** |
| SDD process files (`.specify/` templates & ledger, `.claude/skills/`, `.claude/knowledge/`, `CLAUDE.md`) | **Japanese** |
| Constitution, ADRs, knowledge layer | **Japanese** |
| Code comments | **Japanese** (follow existing code conventions; explain the "why," let code express the "what") |
| Variable / function / class names | **English** |
| Log messages | Follow existing conventions (new code matches surrounding patterns) |
| Commit messages | **Conventional Commits**: type/scope in English, description in Japanese, with a `[spec:NNN-name]` tag (see Workflow below) |
| IDs & technical tags | English as-is (FR/SC/TC/BP/ADR; verified / unverified / uncheckable; characterization / touch-only, etc.) |
| Conversation language | Per user preference (default = Simplified Chinese) — **independent of artifact language** |

> Boundary note: `trialpos-trec-docs` (the team-internal knowledge library) is primarily Simplified Chinese and outside this convention. Do not conflate the two language domains — that library vs. this (formal code-side) repository. `/speckit-analyze` checks artifact language consistency (violation = MEDIUM).

---

## SDD Workflow

- **Command chain**: `/speckit-specify` → `clarify` → `plan` (after_plan hook auto-generates `test-spec`) → `tasks` → `implement` (after_implement hook auto-generates the `test-results` scaffold) → `analyze` (**mandatory before PR**, CRITICAL must be zero). Cross-cutting: `adr` / `approve-adr` / `feedback` / `approve-spec` / `checklist` (optional) / `constitution`.
- **Preloading**: before each command, the mandatory `context-preload` hook loads this constitution + `architecture-principles.md` + ADRs + relevant approved-specs + the module's `domain-knowledge`.
- **Human gates (not replaceable by AI)**: AI only drafts artifacts and detects inconsistencies. The final "this is good" judgment is always a human responsibility.

| Gate | Phase | Owner | Output |
|---|---|---|---|
| Spec approval | End of specify | Reviewer / PO | spec.md → Approved + registered in index via `/speckit-approve-spec` |
| test-spec review | After plan | Reviewer / QA | test-spec.md → Approved |
| test-results review | After implement (after Windows run) | Reviewer / QA | test-results.md → Approved (**fixed in the last commit before merge**; no post-merge backfilling) |
| ADR approval | Any time | Reviewer | ADR → Approved + reflected into architecture-principles |
| Consistency verification | Before PR | Implementer (runs it) | `/speckit-analyze` CRITICAL = 0 |

- **Commit convention**: Conventional Commits (type/scope in English, description in Japanese) + `[spec:NNN-name]` traceability tag. As a rule **1 task = 1 commit**. Example: `fix(discount): 小計値引の按分額を LineTotal に反映 [spec:001-fix-discount]`
- **Artifacts**: `specs/<NNN>-<name>/` (sequential numbering), index-link model, merged into the main line as permanent SDD artifacts.
- **Branching/merging**: SDD work happens on `sdd/main`; feature branches fork from `sdd/main`; **merge commits (no squash)** — keeping SpecKit sub-commit granularity so design decisions stay traceable. `release*` mirror branches stay clean against `origin`.
- **Push prohibition**: origin points at the internal GitLab source of record and is **fetch/version-switch only; push is disabled**. **Any push requires explicit prior permission** (changes flow back upstream via the team's established channel).

---

## Governance

- **Order of authority**: this constitution > `architecture-principles.md` > ADRs > explanatory docs. Lower layers must not contradict this constitution.
- **Amendments (SemVer)**: MAJOR = removing/redefining a principle or a backward-incompatible governance change; MINOR = new principle / major expansion; PATCH = wording clarification / factual correction. Every amendment updates the **Sync Impact Report** at the top and syncs dependent artifacts (templates/skills/knowledge).
- **Compliance verification**: `/speckit-analyze` verifies spec/plan/tasks against this constitution before PR. CRITICAL violations must be cleared before a PR is allowed.
- **Exceptions become ADRs**: no self-approved "small exceptions" — recording moments that required judgment is the core of this project's knowledge assets (F4). Clear violation of an explicit clause → stop work → `/speckit-adr`; a gray-zone fork in the road → record inline and continue (two-speed ADR, `legacy-sdd-disciplines.md` §6).
- **Right-size principle**: governance investment stays proportional to the 2–3-year remaining life (F2). The center of gravity is discipline and behavior preservation for new features/bug fixes — no over-engineering institutions for a distant future.

---

**Version**: 2.0.0 | **Ratified**: 2026-07-16 | **Last Amended**: 2026-07-18

> The source document is managed by the SDD tool base (standard github/spec-kit) and can be amended via `/speckit-constitution`. Based on v1.0.1 (user-ratified), it was re-derived from first principles and fully Japanese-ified per the user directive of 2026-07-18 (v2.0.0).
