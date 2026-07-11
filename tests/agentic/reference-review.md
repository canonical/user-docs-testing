# Reference documentation review

A shipped agentic test. It reviews reference documentation against a source of
truth (code, configuration, or generated artifacts) and reports where the
documentation no longer matches it.

Enable it from your `docs-testing.config.yml` and point its `targets` at your
reference docs and its `sources` at what they describe.

## Inputs available to you

- The documentation repository is checked out at the workspace root.
- Each configured source of truth is checked out under `sources/<name>/`.
- The project configuration is in `docs-testing.config.yml`. This test's entry in
  the `tests` list tells you:
  - `targets` / `exclude` — which files are in scope.
  - `generated` — auto-generated material and how to treat it.
  - `sources` — which sources of truth (by name) to compare against.
- Any deterministic findings are in `results/all.json`.

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
5. Only flag issues you can justify by pointing to specific source evidence. When
   unsure, prefer not to flag.

## Output

Contribute your findings to the single check run produced by the workflow:

- Report `failure` if you found at least one finding and `reporting.fail_on_findings`
  is true; otherwise `neutral`.
- Report `success` if you reviewed the in-scope files and found nothing.
- For each finding include: the doc file (and line if known), the source evidence
  (`sources/<name>/<path>`), and a one-line description.
- Group findings by file. Keep it concise and factual.

If you could not access a required source, report that honestly rather than
guessing.
