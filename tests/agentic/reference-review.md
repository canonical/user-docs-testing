# Reference documentation review

A shipped agentic test. It reviews reference documentation against a source of
truth (code, configuration, or generated artifacts) and reports where the
documentation no longer matches it.

Enable it from your `docs-testing.config.yml` and point its `targets` at your
reference docs and its `sources` at what they describe.

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
- The `sources:` list at the top of the config marks each source `required` (the
  default) or optional (`required: false`). A required source is one without
  which its dependent review scope cannot be evaluated meaningfully.
- Any deterministic findings are in `results/all.json`.

## Establish source ownership first

Before evaluating findings, build an ownership map for the in-scope material:

- If the config provides a `source_map`, use it as the starting point.
- Otherwise, infer for each in-scope file (or claim category) which configured
  source most likely OWNS the behavior it documents — the component that
  *produces* the interface, not one that merely consumes or displays it.

Do not assume the first or most convenient source is authoritative. A claim that
cannot be found in one source may simply belong to a different component.

## What to do

1. Resolve the in-scope files from this test's `targets` and `exclude`.
2. Respect this test's `generated.mode`:
   - `skip` — do not review generated files at all.
   - `deterministic-only` — do not review generated files; a deterministic test
     covers them.
   - `annotate` — you may review them, but label findings as generated.
3. If this test's `skip_deterministically_covered` is true, read `results/all.json`
   first and do not re-report anything already listed there (match against each
   finding's `covered_topic`, `doc_file`, and `message`).
4. For each in-scope file, compare its claims against the relevant source of truth.
   Look for things like:
   - Settings, flags, defaults, commands, endpoints, or paths that no longer exist
     or now behave differently in the source.
   - Documented behavior that contradicts the source's actual behavior.
   - Values (defaults, limits, versions) that disagree with the source.
   - Described steps or parameters that are missing or renamed in the source.
5. Search the configured sources intelligently. For each claim:
   - Determine which component most likely owns the behavior, then search that
     source (and any narrowed paths) first.
   - Follow references into another configured source when the interface crosses
     component boundaries.
   - Prefer the PRODUCER of an interface over a CONSUMER of it. Use consumers only
     as corroborating evidence.
   - When two configured sources define incompatible expectations for the same
     claim, report the cross-source disagreement rather than silently picking one.
   Weak evidence that does NOT settle a claim on its own:
   - a UI or form displaying a field does not prove the backend default;
   - a consumer passing an option does not prove the producer accepts it;
   - a client constant does not prove the server supports the behavior;
   - a documentation example does not prove an executable is installed;
   - a test fixture does not outweigh the production parser or schema.
6. Only flag issues you can justify by pointing to specific source evidence. When
   unsure, prefer not to flag.

## Missing or unavailable sources

A source directory under `sources/<name>/` may be missing or empty because the
source could not be cloned, authenticated, or read.

- If a claim's only authoritative source is a REQUIRED source that is
  unavailable, mark that file / claim category as **blocked** — do NOT report it
  as passing, and do NOT invent a finding to explain the gap.
- If the unavailable source is OPTIONAL (`required: false`) and no in-scope claim
  depends on it, proceed normally.
- Continue reviewing every file that IS supported by an available source. Never
  reduce the whole run to a single pass/fail because one source was missing.
- A documented item is not invalid merely because it is absent from the first
  source you searched; confirm which component should own it before concluding.

## Output

Contribute your findings to the single check run produced by the workflow.

Classify each in-scope file (or claim category) into exactly one coverage state,
and keep these distinct — do not collapse them into one repository-wide result:

- **reviewed-and-supported** — checked against an available authoritative source,
  no discrepancy.
- **reviewed-with-conflicting-evidence** — checked, and the source contradicts
  the docs (a finding), or two sources disagree.
- **skipped-by-policy** — excluded by `exclude` or by the `generated` policy.
- **unsupported-by-configured-sources** — no configured source is authoritative
  for it (and none is required for it).
- **blocked-required-source-unavailable** — a required source it depends on could
  not be accessed, so its review is incomplete.

Then report:

- `failure` if you found at least one finding and `reporting.fail_on_findings`
  is true; otherwise `neutral`.
- `success` only if every in-scope file is reviewed-and-supported or
  skipped-by-policy with no findings. If any file is blocked or unsupported,
  do NOT report `success` for it — list it explicitly.
- For each finding include: the doc file (and line if known), the owning source
  and evidence location (`sources/<name>/<path>`, symbol, or a concise
  paraphrase), and a one-line description.
- Group findings by file, and list the blocked / unsupported files separately so
  a reader can see exactly which areas were not verified.

### Handling private sources safely

A source may be a private repository. When reporting against one:

- Prefer source paths, symbols, and short paraphrases over copying substantial
  private code into the report.
- Identify the private repository and location only to the extent appropriate for
  the repository where the check runs (a public check run must not leak private
  source contents).
- If you could not access a required source, report that the review is
  incomplete and honest rather than guessing at its contents.
