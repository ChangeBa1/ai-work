# Specification Quality Checklist: 通用动作身份、目标一致性与坐标空间安全

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-21
**Last validated**: 2026-07-22 (post Constitution v1.1.0 rebaseline + /speckit-clarify pass)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Business-Agnostic Core (Constitution v1.1.0, Principle VI) — MANDATORY

- [x] Core-scoped requirements (FR/SC/Key Entities) contain no fields, keywords,
      states, action categories, or expected values specific to a single tested
      application, industry, page, or test scenario (e.g., no `confirmed_cart`,
      `cart_items`, `cart_amount`, `add_to_bag`, `subtotal`, `clear_or_reset`, or
      equivalent fixed business fields)
- [x] All business/scenario semantics (e.g., the POS bag-checkout incident) appear
      only in Background (non-normative), as non-normative Examples, or as a named
      offline regression fixture reference — never as a normative entity, field, or
      Success Criterion in its own right
- [x] Preconditions, audit categories, and counters are expressed as generic
      user-declared key/value facts, tags, matchers, or assertions — not as fixed
      per-business fields baked into core requirements
- [x] Any requirement claiming a generic/reusable framework capability is backed by
      at least two unrelated scenario acceptance/Success-Criteria references (not
      solely the single historical incident scenario)

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **2026-07-22 rebaseline**: spec.md was rewritten end-to-end per Constitution
  v1.1.0 Principle VI to remove all normative POS-specific entities/fields
  (`confirmed_cart_items`, `confirmed_cart_amount`, `cart_items`/`cart_amount`,
  `add_to_bag`/`subtotal`/`payment`/`clear_or_reset` categories,
  `extract_cart_state`, and the 1-件/5-円/レジ袋/小計 fixed acceptance values).
  FR/SC were renumbered from FR-001/SC-001. Two safety corrections were folded
  directly into requirements rather than left as narrative: (A) a matching
  `action_id` proves only "same logical action attempt," never target safety —
  FR-003/FR-004; (B) an `action_type` change is a risk signal, not an automatic
  `dangerous_drift` verdict — FR-012/FR-013. Declarative run preconditions
  (FR-024～026) and declarative action-tag audit (FR-027～028) replace the prior
  hardcoded start-state/click-category mechanics. Success Criteria now require
  at least three unrelated offline scenarios (form-submit dedup, icon-only menu
  grounding, popup/scroll legitimate micro-action), with the POS bag-checkout
  fixture retained only as a fourth, non-exclusive regression check (SC-012/013).
  `rg -n "confirmed_cart|cart_items|cart_amount|add_to_bag|subtotal|clear_or_reset"
  specs/003-action-identity-grounding/spec.md` returns no matches.
- Pre-rebaseline history (2026-07-21 remediation passes on the POS-specific
  version) is preserved in git history; `checklists/requirements-safety.md` was
  written against that pre-rebaseline FR/SC numbering and needs re-validation
  against the new numbering before being trusted as current evidence.
- **2026-07-22 `/speckit-clarify` pass** (3 questions asked/answered, targeted at
  the six high-impact areas requested): (1) the new declarative run-precondition
  facts (FR-024) MUST share one underlying fact/assertion mechanism with the
  existing `verification_mode` business-result assertions, differing only in
  trigger timing — not a second parallel syntax; (2) FR-013's `dangerous_drift`
  classification MUST combine declared purpose / declared risk level / step-
  intent-consistency with AND semantics, with risk-driven human-confirmation
  routed through the existing FR-034 six-field recovery-policy contract rather
  than a new veto mechanism; (3) "场景 profile" is confirmed as a fully optional,
  non-normative declaration container — core MUST work correctly with zero
  registered profiles, and this feature does not introduce a new profile
  registration interface. All three answers were integrated directly into
  FR-013/FR-014/FR-024, the two affected Key Entities, and Assumptions — no
  checklist item changed state (all were already passing pre-clarify).
