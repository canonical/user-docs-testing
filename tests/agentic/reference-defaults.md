# Reference defaults and constraints

A shipped agentic test. It verifies documented **default values, types, allowed
values, ranges, units, and required/optional status** against the source that
defines them. Defaults and constraints rot quietly; this test pins them to the
producer.

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
    for them. When present, prefer it when deciding which source owns a claim.
- The `sources:` list marks each source `required` (default) or optional
  (`required: false`).
- Any deterministic findings are in `results/all.json`.

## Establish source ownership first

For each documented value or constraint, decide which configured source *produces*
it (use `source_map` when present, otherwise infer). Prefer the producer's schema
or validator over any consumer or example. A value absent from one source may
belong to a different component.

## What to do

1. Resolve the in-scope files from this test's `targets` and `exclude`, and respect
   `generated.mode` (skip / deterministic-only / annotate).
2. In the in-scope docs, find every claim that states: a **default value**, a
   **data type**, an **allowed set / enum**, a **minimum / maximum or range**, a
   **unit or format**, or whether something is **required vs optional**.
3. Locate the AUTHORITATIVE definition in the owning source — a schema, a validator,
   a `default=`, a constant, or an option/argument declaration. Prefer the
   producer's schema/validator over a sample or example: a sample config shows one
   deployment's values, not necessarily the code default.
4. Compare and flag mismatches: wrong default, wrong type, wrong allowed values,
   wrong range/limit, wrong unit/format, or wrong required-ness.
5. Watch for override layers: a code default may be overridden by a packaged or
   deployment default, or by an environment variable. When they differ, identify
   which layer the doc claims to describe and check against that; if the doc is
   ambiguous about which layer it means, note the ambiguity instead of guessing.
6. Distinguish a real user-facing default from a development or placeholder default.
   A schema default that is clearly a local/dev value — `localhost`, `127.0.0.1`, a
   `/tmp` path, `example.com`, a `devmode`/`debug` flag, or an obvious placeholder —
   is often NOT the value a production user receives; the docs may correctly describe
   it as unset, `None`, or "set at deployment". When the only default in the source is
   such a placeholder, treat a documented `None` / "must be set" / "deployment-set" as
   consistent, not a mismatch; at most note the nuance with `severity: warning`.
   Reserve a hard mismatch for a genuine, production-facing default that disagrees.
7. Only flag where the source unambiguously defines the value. A test fixture default
   does not outweigh the schema. When unsure, prefer not to flag.

### Respect version and source ref

Documented defaults are often version-scoped ("default changed in 26.04"), while the
source is a single `ref`. Do not flag a value whose documented scope is a version
other than the one the source `ref` represents; note the version skew instead.

### Deduplicate against other tests

If this test's `skip_deterministically_covered` is true, read `results/all.json`
first and do not re-report anything already listed there (match `covered_topic`,
`doc_file`, and `message`). A wrong value that is really a broader accuracy or
naming problem is the general `reference-review` test's remit — keep this test to
the value/type/constraint layer so the same issue is not reported twice.

## Missing or unavailable sources

A source directory under `sources/<name>/` may be missing or empty.

- If a claim's only authoritative source is REQUIRED and unavailable, mark that
  file / claim category **blocked** — do NOT report it as passing, and do NOT invent
  a finding to explain the gap.
- If the unavailable source is OPTIONAL and no in-scope claim depends on it, proceed.
- Continue checking every claim supported by an available source. Never reduce the
  run to a single pass/fail because one source was missing.

## Output

Contribute your findings to the single check run produced by the workflow.

Classify each in-scope file (or claim category) into exactly one coverage state (see
[RESULTS-SCHEMA.md](../../RESULTS-SCHEMA.md)):

- **reviewed-and-supported** — its documented defaults/constraints match the source.
- **reviewed-with-conflicting-evidence** — a default or constraint disagrees with
  the source (a finding).
- **skipped-by-policy** — excluded by `exclude` or by the `generated` policy.
- **unsupported-by-configured-sources** — no configured source defines its values.
- **blocked-required-source-unavailable** — a required source was unavailable.

Then report:

- `failure` if you found at least one mismatch and `reporting.fail_on_findings` is
  true; otherwise `neutral`.
- `success` only if every in-scope file is reviewed-and-supported or
  skipped-by-policy. Never report `success` for a blocked or unsupported area.
- For each finding include: the option/key/parameter, the **documented** value or
  constraint, the **source** value or constraint, and the source location
  (`sources/<name>/<path>`, symbol). Keep it to a compact "documented vs source" pair.
- Set severity by impact: `error` for a wrong default, type, allowed value, range,
  or required-ness that would break a user's configuration; `warning` for a
  deployment-set nuance or a cosmetic discrepancy.
- Group findings by file; list blocked / unsupported areas separately.

### Handling private sources safely

A source may be a private repository. When reporting against one:

- Prefer source paths, symbols, and short paraphrases over copying substantial
  private code into the report.
- Identify the private repository and location only to the extent appropriate for
  the repository where the check runs (a public check run must not leak private
  source contents).
- If you could not access a required source, report that the review is incomplete
  rather than guessing at its contents.
