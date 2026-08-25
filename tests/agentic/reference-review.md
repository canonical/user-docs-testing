# Reference documentation review

A shipped agentic test. It reviews reference documentation against the source of
truth that *owns* each documented behavior, and reports where the documentation
contradicts it.

This is the **general, default** reference test. If you run only one reference
test, run this one. It catches documented claims that the source contradicts.
The companion test, `reference-completeness`, catches the opposite direction:
interface that exists in the source but is missing from the docs.

## Inputs

- The documentation repository is checked out at the workspace root.
- Each configured source is checked out under `sources/<name>/`. A source
  directory may be **missing or empty** if it could not be cloned, authenticated,
  or read.
- `docs-testing.config.yml` provides:
  - `sources:` — each marked `required: true` (default) or `required: false`.
  - `source_map:` (top level) — which source(s) OWN which documentation paths.
    This is shared by all reference tests; use it as the ownership map.
  - this test's entry: `targets` / `exclude`, `generated`, `sources` (which
    sources this test may use), `skip_deterministically_covered`, and an optional
    test-level `source_map` that overrides the shared one for matching paths.
- Deterministic findings, if any, are in `results/all.json`.

## Check what was actually checked out, first

`results/all.json` may contain a `source_evidence` list recording which sources
were really on disk, with the commit SHA of each. **It overrides your own
impression.** Before reviewing anything:

- Treat a source whose evidence says `"available": false` as unavailable, even if
  a directory for it exists. Do not report any area as reviewed against it.
- Coverage entries already present in `results/all.json` are established facts.
  Do not upgrade a `blocked-required-source-unavailable` area to reviewed.
- If there is no `source_evidence`, check each `sources/<name>/` directory
  yourself and treat an empty or missing one as unavailable.

## Procedure

For each in-scope file (from `targets` minus `exclude`, honouring
`generated.mode`: `skip` and `deterministic-only` mean do not review, `annotate`
means review but label findings as generated), work claim by claim:

1. **State the claim.** Identify a specific, checkable assertion — a default, a
   flag, a path, an endpoint, a name, a limit, a described behavior. Skip prose
   that asserts nothing checkable.
2. **Find the owner.** Look the file's path up in `source_map` to get the
   source(s) that own it. If no entry matches, infer which configured source
   *produces* the interface. The owner is the producer, never a consumer.
3. **Read the owning source.** Search `sources/<owner>/` for the implementation
   or design artifact that defines the claim. Follow cross-component references
   when an interface spans components.
4. **Require evidence.** Report a contradiction only when you can cite a specific
   location in the owning source that says something different. No citation, no
   finding.
5. **Judge the evidence.** These do **not** settle a claim on their own:
   - absence of the item from a repository that does not own it;
   - a UI, client, or other consumer, when the producing source is available — a
     form field does not prove a backend default, a client constant does not
     prove server behavior;
   - a test fixture, when the production schema or parser says otherwise;
   - a documentation example, which is not an implementation.

   When the owning source is available, it outranks all of these. When two
   *owning* sources disagree, report the cross-source disagreement rather than
   picking a side.
6. **Check version scope.** Each source is checked out at one `ref`, while docs
   often cover several versions ("since 25.10", "deprecated in 26.10"). A claim
   scoped to a different version than the source `ref` is not drift — note the
   version skew instead.
7. **Prefer silence.** If after the above you are not confident, do not flag. A
   false positive costs a writer more than a missed one.

If `skip_deterministically_covered` is true, read `results/all.json` first and do
not re-report anything already listed there (match `covered_topic`, `doc_file`,
and `message`).

## When a source is unavailable

- Required owning source missing → mark that file / claim category **blocked**.
  Do not report it as reviewed, and do not invent a finding to explain the gap.
- Optional owning source missing → mark it **unsupported**.
- Keep reviewing every area whose owner *is* available. One missing source must
  never collapse the run into a single verdict.
- A documented item is not wrong merely because you did not find it in the first
  place you looked. Confirm ownership before concluding anything.

## Output

Contribute to the single check run the workflow produces.

Classify every in-scope file (or claim category) into exactly one coverage state
from [RESULTS-SCHEMA.md](../../RESULTS-SCHEMA.md): `reviewed-and-supported`,
`reviewed-with-conflicting-evidence`, `skipped-by-policy`,
`unsupported-by-configured-sources`, `blocked-required-source-unavailable`.

Choose the conclusion in this order:

1. `failure` — at least one finding, and `reporting.fail_on_findings` is true.
2. `reporting.on_incomplete_coverage` (default `neutral`) — no findings, but at
   least one area is blocked or unsupported. Never `success` here: nothing was
   proven wrong, but the review is not complete.
3. `success` — every in-scope area is `reviewed-and-supported` or
   `skipped-by-policy`, with no findings.

Each finding must give a technical writer everything needed to act:

- **Where** — doc file and line.
- **What it says** — the documented claim, quoted or tightly paraphrased.
- **What the source says** — the conflicting authoritative behavior or value.
- **Proof** — the owning source and location: `sources/<name>/<path>`, plus a
  symbol or line where useful. The path must be one that actually exists in the
  checkout; a citation nobody can open is not evidence, and a finding without one
  must not be reported at all.
- **Why it matters** — one line on what likely needs review.

For every area you mark `reviewed-and-supported`, name at least one source file
you actually consulted to reach that conclusion. "Reviewed" with nothing cited is
indistinguishable from not having looked, so report such an area as blocked
instead.

Group findings by file. List blocked and unsupported areas **separately and
explicitly**, so a reader can see exactly which material was not verified.

### Private sources

- Cite paths, symbols, and short paraphrases; do not copy substantial private
  code into a report that may be publicly visible.
- If a required private source was inaccessible, say the review is incomplete
  rather than guessing at its contents.
