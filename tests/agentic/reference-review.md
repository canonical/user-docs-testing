# Test: reference-review

**The question this test answers:** does the documentation state something that
the product owning that behaviour contradicts?

This is the general reference test. If you run only one, run this one. Its
companion, `reference-completeness`, covers the opposite direction — interface
that exists but is undocumented.

The shared rules in `reference-common.md` govern evidence, ownership, coverage,
unavailable sources, de-duplication, and reporting. This file adds only what is
specific to this test.

## Procedure

For each in-scope file (from the test's `docs` minus `exclude`, honouring
`generated.mode`), work claim by claim:

1. **State the claim.** Identify a specific, checkable assertion — a default, a
   flag, a path, an endpoint, a name, a limit, a described behaviour. Skip prose
   that asserts nothing checkable.
2. **Find the owner** of that claim, per the shared rules.
3. **Read the owning source.** Search `sources/<owner>/` for the implementation
   or design artifact that defines the claim. Follow cross-component references
   when an interface spans components.
4. **Compare, and cite.** Report a contradiction only when you can point at the
   specific location in the owning source that says something different.

## Severity

- `error` — a documented claim contradicts the owning source in a way that would
  mislead a reader following the documentation: a wrong default, a wrong flag or
  path, a removed option still documented as current, an incorrect limit.
- `warning` — the documentation is defensible but drifting: imprecise wording, a
  stale example that still works, terminology the product has since renamed.

## What not to report here

- Interface that exists in the source but is missing from the documentation.
  That is `reference-completeness`; reporting it here duplicates that test.
- Prose style, structure, tone, or formatting. This test is about factual
  agreement with the product, not about writing quality.
