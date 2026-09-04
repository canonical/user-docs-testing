# Documentation review: rules common to every reference test

These rules apply to every shipped reference test. Each individual test file
states only the question it uniquely answers; everything about evidence,
ownership, coverage, and reporting is here so the tests cannot drift apart.

## What you are given

- The documentation repository is checked out at the workspace root.
- Each configured source of truth is checked out under `sources/<name>/`. A
  source directory may be **missing or empty** if it could not be cloned,
  authenticated, or read.
- `results/all.json` is the run plan and the deterministic results, produced
  before you started. It is the authoritative description of this run:
  - `plan.agentic_tests` — the tests you must run, each already resolved to its
    `docs` globs, `exclude`, `sources`, `generated` policy, and `source_map`.
    Run exactly these. Do not run a test that is not listed, and do not skip one
    that is.
  - `plan.source_map` — which source **owns** which documentation paths.
  - `plan.reporting` — how to conclude.
  - `source_evidence` — what was really on disk.
  - `findings` / `coverage` / `errors` — what the deterministic checks found.

The configuration has already been parsed and validated. Read `results/all.json`
rather than re-interpreting `docs-testing.config.yml`.

## Evidence beats impression

`source_evidence` records which sources were really checked out, with the commit
SHA of each. **It overrides your own impression.**

- Treat a source whose evidence says `"available": false` as unavailable, even if
  a directory for it exists. Never report anything as reviewed against it.
- Coverage entries already in `results/all.json` are established facts. Do not
  upgrade a `blocked-required-source-unavailable` area to reviewed.
- If `errors` is non-empty, the run is already compromised. Report it (see
  "Concluding") and do not paper over it.

## Establish ownership before judging anything

A product is often implemented across several repositories, so the authoritative
source for a claim is whichever component **produces** the interface.

1. Look the file's path up in `plan.source_map`, and in the test's own
   `source_map` if it has one (a test-level entry wins for the paths it matches).
2. If no entry matches, infer which configured source produces the interface.
3. The owner is the producer, never a consumer.

These do **not** settle a claim on their own:

- absence of an item from a repository that does not own it;
- a UI, client, or other consumer, when the producing source is available — a
  form field does not prove a backend default, a client constant does not prove
  server behavior;
- a test fixture, when the production schema or parser says otherwise;
- a documentation example, which is not an implementation.

When the owning source is available it outranks all of these. When two *owning*
sources disagree, report the disagreement rather than picking a side.

## Require evidence, and prefer silence

Report something only when you can cite a specific location in the owning source.
No citation, no finding. The path you cite must actually exist in the checkout; a
citation nobody can open is not evidence.

If after all of the above you are not confident, do not flag it. A false positive
costs a writer more than a missed one.

## Respect the source ref

Each source is checked out at a single `ref`, while documentation often covers
several versions ("since 25.10", "deprecated in 26.10"). A claim scoped to a
different version than the source `ref` is not a defect — note the version skew
instead.

## When a source is unavailable

- Required owning source missing → mark that file or claim category **blocked**.
  Do not report it as reviewed, and do not invent a finding to explain the gap.
- Optional owning source missing → mark it **unsupported**.
- Keep going for every area whose owner *is* available. One missing source must
  never collapse the run into a single verdict.
- A documented item is not wrong merely because you did not find it in the first
  place you looked.

## Do not repeat the deterministic checks

If the test's `skip_deterministically_covered` is true, read the `findings`
already in `results/all.json` and do not re-report anything they cover. Match on
`covered_topic` first, then on `doc_file` plus `message`.

## Classify coverage

Classify every in-scope file or claim category into exactly one state:

| State | Meaning |
| ----- | ------- |
| `reviewed-and-supported` | Checked against an available owning source; nothing to report. |
| `reviewed-with-conflicting-evidence` | Checked, and the source contradicts the docs. |
| `skipped-by-policy` | Excluded by `exclude` or the `generated` policy. |
| `unsupported-by-configured-sources` | No configured source is authoritative for it. |
| `blocked-required-source-unavailable` | A required owning source could not be read. |

For every area you mark `reviewed-and-supported`, name at least one source file
you actually consulted. "Reviewed" with nothing cited is indistinguishable from
not having looked — report such an area as blocked instead.

## Concluding

Emit exactly one `create_check_run` for the whole workflow, covering every test.
Choose the conclusion in this order, and stop at the first that applies:

1. `action_required` — `results/all.json` has a non-empty `errors` list. A check
   failed to run, so the results are not trustworthy. Say so plainly; do not
   describe the documentation as passing or failing.
2. `failure` — at least one finding of severity `error`, and
   `plan.reporting.fail_on_findings` is true.
3. `plan.reporting.on_incomplete_coverage` (default `neutral`) — no blocking
   finding, but at least one area is `blocked-required-source-unavailable` or
   `unsupported-by-configured-sources`. **Never `success` here**: nothing was
   proven wrong, but the review is not complete.
4. `neutral` — only `warning`-severity findings, or findings with
   `fail_on_findings` false.
5. `success` — every in-scope area is `reviewed-and-supported` or
   `skipped-by-policy`, with no findings at all.

## Writing the report

Optimize for someone scanning it in a pull request. Use this order, and omit any
section that is empty:

1. **Outcome** — one line: what happened, and whether action is needed.
2. **Tool errors** — only if `errors` is non-empty. What broke and what to fix.
3. **Problems** — findings that need action, grouped by documentation file.
4. **Warnings** — findings worth knowing about that do not block.
5. **Not verified** — blocked and unsupported areas, listed **explicitly**, so a
   reader can see exactly which material was not checked.
6. **Verified** — a short summary of what was checked and against which sources.

Keep a successful run short. Do not pad it with the reasoning behind a clean
result. Spend the detail on failures.

Each finding must give a technical writer everything needed to act:

- **Where** — documentation file and line.
- **What it says** — the documented claim, quoted or tightly paraphrased.
- **What the source says** — the conflicting authoritative behavior or value.
- **Proof** — `sources/<name>/<path>`, plus a symbol or line where useful.
- **Why it matters** — one line.

Report output is sanitized before publication, and any URL that is not HTTPS is
removed. A finding about a non-HTTPS URL would therefore lose the evidence it
depends on: describe such a value in words — scheme, host, and path — instead of
pasting it.

## Private sources

- Cite paths, symbols, and short paraphrases. Do not copy substantial private
  source code into a report that may be publicly visible.
- If a required private source was inaccessible, say the review is incomplete
  rather than guessing at its contents.
