<!--
Sync Impact Report
- Version change: template (unversioned) → 1.0.0
- Modified principles: all five template placeholders replaced (initial ratification)
  - [PRINCIPLE_1_NAME] → I. Deterministic Pure Scoring
  - [PRINCIPLE_2_NAME] → II. Spec-Traceable Rules
  - [PRINCIPLE_3_NAME] → III. Test-First With a Harness (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Explicit Missing-Data Semantics
  - [PRINCIPLE_5_NAME] → V. Simplicity and Isolation
- Added sections: Technical Constraints, Development Workflow
- Removed sections: none
- Templates: plan/spec/tasks templates read this file at runtime; no template edits needed
- Follow-up TODOs: none
-->

# GIS Scorer Constitution

## Core Principles

### I. Deterministic Pure Scoring

The scorer MUST be a pure function of its explicit inputs. The same input MUST always yield a
byte-identical result. It MUST NOT read the clock, environment variables, files, a network or a
database, and MUST NOT use randomness. All data a score depends on is passed in by the caller.

Rationale: a score that depends on hidden state cannot be verified by a test harness, and
reproducibility is the point of re-implementing the method.

### II. Spec-Traceable Rules

Every threshold, weight, boundary operator (`>` vs `>=`) and penalty MUST be written down in the
feature specification before it is implemented, and each MUST trace to the reference method
(`Assignment-1/GIS_REFERENCE.md`, derived from myportfolio-web's General Investor Score). Any
intentional deviation from the reference MUST be recorded in the spec's Assumptions with its reason.
No scoring constant may exist in code that is absent from the spec.

Rationale: spec-driven development only works if the spec, not the code, is the source of truth.

### III. Test-First With a Harness (NON-NEGOTIABLE)

Acceptance tests derived from the spec's scenarios MUST be written and seen to fail before the
corresponding behaviour is implemented (red → green → refactor). Every threshold boundary MUST have
a test on each side of it. Every functional requirement MUST be covered by at least one test, and
the test suite MUST pass in full before any task is marked complete.

Rationale: the assignment's test harness is the evidence that the implementation matches the spec.

### IV. Explicit Missing-Data Semantics

A missing input MUST never be silently treated as zero. A scoring item whose input is missing MUST
be excluded from both the earned and the available points, and the result MUST say so. Zero and
negative values are real measurements and MUST be scored as such. Invalid input (non-numeric,
non-finite, or out of its stated range) MUST be rejected with a clear error naming the field,
rather than guessed at.

Rationale: in the reference system, conflating "missing" with "zero" was a recurring source of
wrong scores.

### V. Simplicity and Isolation

The module MUST stay small and self-contained: a library with a thin command-line entry point,
using only the language's standard library at runtime. Features outside the spec's scope (sector
percentile thresholds, lenders and insurers, capital deployment, red flags) MUST NOT be added
"just in case". The module MUST NOT import from or modify myportfolio-web.

Rationale: YAGNI; a small surface keeps the spec, tests and code reviewable.

## Technical Constraints

- Language: Python 3 (3.12 or newer); runtime dependencies: standard library only.
- Environment: all Python commands run inside `Assignment-1/Part-1A/.venv`.
- Tooling: `pytest` for tests and `ruff` for linting, installed into the venv as dev dependencies.
- Inputs and outputs are plain data (dictionaries / JSON). The result MUST be serialisable to JSON
  with stable key order.
- No secrets, credentials or `.env` values are committed; nothing is pushed without the owner's say-so.

## Development Workflow

- Follow the Spec Kit flow in order: constitution → specify → (clarify) → plan → tasks → implement.
- Each phase's artefact is reviewed by the owner before the next phase starts.
- A change to a scoring rule starts with a spec change, then a failing test, then the code.
- Quality gates before a task is done: tests pass, lint is clean, and the requirement-to-test
  traceability stays complete.

## Governance

This constitution supersedes other practices for Part-1A. Amendments are made by editing this file
with a Sync Impact Report and a version bump: MAJOR for removing or redefining a principle, MINOR for
adding a principle or section, PATCH for wording. Every plan produced by `/speckit-plan` MUST include
a Constitution Check against these principles, and any violation MUST be justified in that plan's
Complexity Tracking section or removed.

**Version**: 1.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22
