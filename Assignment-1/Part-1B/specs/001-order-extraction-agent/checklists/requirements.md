# Specification Quality Checklist: New-Order Announcement Extraction Agent

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
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

- Validation iteration 1 (2026-11-22): all items pass.
- **Implementation-detail exception (accepted)**: FR-020 to FR-022 and FR-024/FR-030 name the model
  (`qwen3.5:4b`, digest `d8b0f5e9760c`), runner (Ollama 0.32.14), generation settings, `.env`/`.env.example`,
  `evals/dataset.json` and the judge endpoint. These are owner-mandated constraints in the feature input and are
  required by constitution Principle VI (pinned, recorded model settings); they are not design choices. They are
  isolated in the "Production model and configuration (owner-mandated constraints)" and "Evaluation Requirements"
  subsections. No language, framework, library or code structure is specified.
- **Testability**: every FR is backed by an AC id or an invariant (INV-1..INV-9) or a layer-3 rule; ambiguous terms
  ("garbled", "over-length", "ambiguous value", "unnamed client", order-type precedence, top-level ranking) are given
  concrete deterministic definitions (FR-006, FR-007, FR-009, FR-012, FR-016, FR-017).
- **Pre-declared evaluation (Principle III)**: scoring formulas, thresholds (100% / 100% / ≥ 80%), normalisation rules,
  verdict order and integrity rules are written before any evaluation exists.
- **Additions beyond the owner's input (all stricter, none looser)**: `rejection_reason` field; INV-4 second clause
  (client string must appear in its quote); INV-8 (evidence coverage); INV-9 (top-level selection); FAIL takes
  precedence over INCONCLUSIVE when a layer 1/2 failure already exists; pinned-model mismatch → INCONCLUSIVE.
  These are listed in Assumptions / FR-028 for review in `/speckit-clarify`.
- Defaults worth confirming in `/speckit-clarify`: 20,000-character limit; garbled thresholds; L1-bidder/MoU as
  `not_an_order`; unnamed client as missing; reference FX rates for ranking only; context-length formula (deferred to
  plan because myportfolio-web was not readable from this workspace).
