# Reference documentation consistency

A shipped agentic test. It checks that the reference set is **consistent** — that
pages agree with each other, that cross-references resolve, that terminology is used
uniformly, and that components which share an interface do not contradict each other.

Unlike the other reference tests, it can run with **no source** (pure internal
consistency), and uses sources only to adjudicate disagreements when they are
available. Enable it from your `docs-testing.config.yml` and point its `targets` at
your reference docs.

## Inputs available to you

- The documentation repository is checked out at the workspace root.
- Each configured source of truth (if any) is checked out under `sources/<name>/`.
  A source directory may be missing or empty if it could not be cloned,
  authenticated, or read. Sources are OPTIONAL for this test.
- The project configuration is in `docs-testing.config.yml`. This test's entry in
  the `tests` list tells you:
  - `targets` / `exclude` — which files are in scope.
  - `generated` — auto-generated material and how to treat it.
  - `sources` — sources of truth (by name) used only to adjudicate, if configured.
  - `source_map` (optional) — an explicit ownership map; when present, use it to
    decide which source (if available) owns a contested claim.
- Any deterministic findings are in `results/all.json`.

## Establish source ownership first

Consistency findings do not require a source. But when you must decide which of two
conflicting statements is correct, identify the source that *produces* the contested
claim (use `source_map` when present, otherwise infer) and consult it if available.

## What to do

1. Resolve the in-scope files from this test's `targets` and `exclude`, and respect
   `generated.mode` (skip / deterministic-only / annotate).
2. **Internal consistency.** Find facts stated in more than one place — a default, a
   name, a path, a limit, an environment variable, a version — and flag where they
   **disagree** (e.g. two pages naming the same setting differently).
3. **Cross-reference integrity.** Check that references between reference pages
   resolve to real pages/anchors, and that a term or identifier is used with one
   consistent meaning throughout.
4. **Cross-component consistency.** Where a claim crosses component boundaries, flag
   when two components define incompatible expectations (a producer and a consumer
   disagreeing).
5. **Adjudication.** When a configured source is available and settles which side is
   correct, say so and point to it. When no source is available, still report the
   disagreement, but mark it as UNRESOLVED rather than blaming one side.
6. Flag genuine contradictions, not mere differences in wording or emphasis. When
   two statements can both be true in context, do not flag.

### Stay in your lane

Your unique remit is **doc-vs-doc**: two reference pages contradicting each other, a
broken cross-reference, or inconsistent terminology. A single page disagreeing with
the source (drift) is the general `reference-review` test's job, and wrong
default/constraint values are `reference-defaults`' job — do not re-report those
here. When two pages disagree and a source settles it, your finding is still the
inter-page contradiction: point to the source to say which side is right, but frame
it as one consistency finding, not a separate drift finding.

## Missing or unavailable sources

Sources are optional here.

- Internal-consistency and cross-reference findings need no source, so continue
  producing them regardless of source availability.
- Only the cross-component adjudication depends on a source. If a source needed to
  settle a specific disagreement is REQUIRED and unavailable, report the
  disagreement as unresolved and mark that adjudication **blocked** — do not pick a
  side, and do not invent a source finding.

## Output

Contribute your findings to the single check run produced by the workflow.

Classify each in-scope area into exactly one coverage state (see
[RESULTS-SCHEMA.md](../../RESULTS-SCHEMA.md)); for this test:

- **reviewed-and-supported** — internally consistent, references resolve, no
  contradictions found. (An area can reach this state even with its source
  unavailable, because internal consistency needs no source — note when that is so.)
- **reviewed-with-conflicting-evidence** — a contradiction was found (a finding),
  whether internal or cross-component.
- **skipped-by-policy** — excluded by `exclude` or by the `generated` policy.
- **unsupported-by-configured-sources** — not applicable to purely internal checks;
  use only for a cross-component adjudication with no configured source.
- **blocked-required-source-unavailable** — a required source needed to adjudicate a
  specific cross-component disagreement was unavailable.

Then report:

- `failure` if you found at least one contradiction and `reporting.fail_on_findings`
  is true; otherwise `neutral`.
- `success` only if every in-scope area is reviewed-and-supported or
  skipped-by-policy. A run with no configured source can still legitimately reach
  `success` on internal consistency, or `failure` on internal contradictions.
- For each finding include: the set of conflicting statements with each location
  (`doc_file` + line), and — if a source adjudicates — which statement is correct and
  the source evidence (`sources/<name>/<path>`, symbol). Mark unresolved conflicts
  clearly.
- Set severity by impact: `error` when following one page would break what another
  page documents; `warning` for terminology or wording inconsistencies that do not
  change behavior.
- Group findings by the conflict; list any blocked adjudications separately.

### Handling private sources safely

When a private source is used to adjudicate a conflict:

- Prefer source paths, symbols, and short paraphrases over copying substantial
  private code into the report.
- Identify the private repository and location only to the extent appropriate for
  the repository where the check runs (a public check run must not leak private
  source contents).
- If you could not access a source needed to resolve a conflict, report the conflict
  as unresolved rather than guessing.
