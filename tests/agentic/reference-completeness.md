# Test: reference-completeness

**The question this test answers:** does user-facing product surface exist that
the reference documentation never mentions?

Where `reference-review` catches "documented but wrong", this test catches
"exists but undocumented".

The shared rules in `reference-common.md` govern evidence, ownership, coverage,
unavailable sources, de-duplication, and reporting. This file adds only what is
specific to this test.

## Prefer the deterministic check where the surface is machine-enumerable

Where the surface can be enumerated mechanically — a CLI's `--help`, an
OpenAPI/Swagger spec, an exported JSON Schema — the built-in
`undocumented-surface` check is more precise and repeatable than this review, and
it runs before you. Concentrate this test on surface that is **not** machine
enumerable: prose-documented concepts, roles, states, and workflows.

## Procedure

1. Resolve the in-scope files from the test's `docs` and `exclude`.
2. For each area, enumerate the **user-facing documentable surface** from its
   owning source — only things that belong in reference documentation:
   - CLI commands and subcommands, and their flags, options, and arguments;
   - configuration keys, sections, and environment variables;
   - public API endpoints, methods, and parameters;
   - user-visible settings, roles, permissions, states, or enums;
   - installed executables, services, or scheduled jobs.
3. For each element, check whether the in-scope documentation covers it.
4. Flag every user-facing element the source exposes but the documentation does
   not cover.
5. Respect `generated.mode`: if generated reference covers part of the surface,
   treat that surface as covered or skipped per the policy rather than reporting
   it as missing.

## Deciding what is user-facing

This judgment is where the test is most likely to produce false positives. Apply
these signals explicitly, and err strongly toward **not** flagging.

**May be user-facing:** appears in a machine-readable public interface (`--help`,
OpenAPI, an exported JSON Schema); exported from a public module or `__all__`;
ships in the packaged default or sample configuration; has a stable name
referenced in user-facing help text.

**Treat as internal — do not flag:** a leading underscore, or an
`internal`/`private`/`debug`/`experimental`/`dev`/`test` name; gated behind a
debug, experimental, or feature flag; referenced only from tests; marked
deprecated or hidden; not reachable through any user-facing entry point.

Not every symbol beside a setting is a setting. Class-level constants that
describe the schema rather than form part of it — a `ClassVar`, a section name, a
model config block — are machinery. Flagging them was the single largest source
of false positives when this test was validated, so confirm a candidate is
something a user can actually set before reporting it.

When the signals conflict, or you cannot tell, do not flag.

## Severity

- `warning` by default — undocumented surface is a coverage gap, not a broken
  claim.
- `error` only when the absence blocks a documented workflow: a required option,
  or a step a reader cannot complete without the missing element.

## What not to report here

- Documented items that no longer exist in the source. That is
  `reference-review`'s direction; keep this test to "missing".
- Elements already reported by the deterministic `undocumented-surface` check.
