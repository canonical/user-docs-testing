# Reference documentation permissions

A shipped agentic test. It verifies documented **authentication, privilege, and
permission** requirements against how the source actually enforces them. Wrong
permission docs are high-cost — either users hit avoidable failures, or they
under-provision or over-trust security-relevant access — so this test errs toward
precision and flags mismatches in **both** directions.

Enable it from your `docs-testing.config.yml`, point its `targets` at your
reference docs, and its `sources` at what they describe.

## Inputs available to you

- The documentation repository is checked out at the workspace root.
- Each configured source of truth is checked out under `sources/<name>/`. A
  source directory may be missing or empty if that source could not be cloned,
  authenticated, or read.
- The project configuration is in `docs-testing.config.yml`. This test's entry in
  the `tests` list tells you:
  - `targets` / `exclude` — which files are in scope.
  - `generated` — auto-generated material and how to treat it.
  - `sources` — which sources of truth (by name) to compare against.
  - `source_map` (optional) — an explicit ownership map associating in-scope
    files / claim categories with the source(s) most likely to be AUTHORITATIVE
    for them. When present, prefer it when deciding which source enforces a claim.
- The `sources:` list marks each source `required` (default) or optional
  (`required: false`).
- Any deterministic findings are in `results/all.json`.

## Establish source ownership first

For each documented access requirement, decide which configured source *enforces*
it (use `source_map` when present, otherwise infer). The authority is the component
that performs the check, not a caller that happens to pass a credential. A
requirement absent from one source may be enforced by a different component.

## What to do

1. Resolve the in-scope files from this test's `targets` and `exclude`, and respect
   `generated.mode` (skip / deterministic-only / annotate).
2. In the in-scope docs, find claims about **access requirements**: "must run as
   root / sudo", a required user or role (e.g. Administrator, Operator), a required
   permission or capability, a required token scope (e.g. Contents: Read), an
   authentication method, or whether a command / endpoint is restricted.
3. Locate the **enforcement** in the owning source: privilege checks (e.g. EUID /
   root checks), role or permission guards, auth decorators or middleware, required
   scopes, or access-control declarations.
4. Compare and flag mismatches, distinguishing the **risk direction**:
   - Doc requires LESS than the source enforces → users following the doc will be
     denied (usability bug).
   - Doc requires MORE than the source enforces, or OMITS a requirement the source
     enforces → security-relevant; the reader may under- or over-grant access.
5. Also flag documented permissions, roles, or scopes that do not exist in the
   source (renamed or removed).
6. Only flag with a concrete enforcement pointer. Do NOT infer enforcement from a doc
   example or from a consumer that merely supplies a credential. When unsure, prefer
   not to flag. Treat this as security-sensitive — see "Handling private sources".

### Target falsifiable claims

This test earns its keep on **procedural and interface** reference — CLI commands
("must run as root"), API endpoints (required scope/role), and admin operations —
where a claim maps to a concrete enforcement point. Conceptual pages (glossaries,
role/term overviews) often make no falsifiable enforcement claim; scanning them
rarely yields findings and risks over-reading. Prefer to scope `targets` at the
procedural/interface pages, and on a conceptual page only flag a claim you can tie
to a specific enforcement location. Absence of a falsifiable claim is
reviewed-and-supported, not a finding.

### Respect version and source ref

The source is a single `ref`. Do not flag a permission or scope whose documented
scope is a different product version than the checked-out source; note the version
skew instead.

### Deduplicate against other tests

If `skip_deterministically_covered` is true, read `results/all.json` first and skip
anything already listed there (match `covered_topic`).

## Missing or unavailable sources

A source directory under `sources/<name>/` may be missing or empty.

- If a claim's only enforcing source is REQUIRED and unavailable, mark that file /
  claim category **blocked** — do NOT report it as passing, and do NOT invent a
  finding to explain the gap.
- If the unavailable source is OPTIONAL and no in-scope claim depends on it, proceed.
- Continue checking every claim enforced by an available source. Never reduce the
  run to a single pass/fail because one source was missing.

## Output

Contribute your findings to the single check run produced by the workflow.

Classify each in-scope file (or claim category) into exactly one coverage state (see
[RESULTS-SCHEMA.md](../../RESULTS-SCHEMA.md)):

- **reviewed-and-supported** — its documented access requirements match enforcement.
- **reviewed-with-conflicting-evidence** — a requirement disagrees with enforcement
  (a finding).
- **skipped-by-policy** — excluded by `exclude` or by the `generated` policy.
- **unsupported-by-configured-sources** — no configured source enforces it.
- **blocked-required-source-unavailable** — a required source was unavailable.

Then report:

- `failure` if you found at least one mismatch and `reporting.fail_on_findings` is
  true; otherwise `neutral`.
- `success` only if every in-scope file is reviewed-and-supported or
  skipped-by-policy. Never report `success` for a blocked or unsupported area.
- For each finding include: the documented claim, the enforcement location and what
  it actually requires (`sources/<name>/<path>`, symbol), and the **risk direction**
  (usability vs security). Prefer `severity: error` for mismatches with a security
  or access-denial impact.
- Group findings by file; list blocked / unsupported areas separately.

### Handling private sources safely

This test reads security-relevant code, so be especially careful:

- Prefer source paths, symbols, and short paraphrases over copying substantial
  private code — never reproduce credential-handling or access-control logic
  verbatim in the report.
- Identify the private repository and location only to the extent appropriate for
  the repository where the check runs (a public check run must not leak private
  source contents).
- If you could not access a required source, report that the review is incomplete
  rather than guessing at its enforcement.
