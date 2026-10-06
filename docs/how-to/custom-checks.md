# How to add your own deterministic check

A deterministic check is a command that you supply. There are two ways for it to report results, and the simpler one needs no code.

This guide covers deterministic checks only. Agentic reviews cannot be added from your configuration. To propose a new one, see [CONTRIBUTING](https://github.com/canonical/user-docs-testing/blob/main/CONTRIBUTING.md#adding-an-agentic-review).

## Report through the exit status

With no `results:` field, the command's exit status is the result. Zero passes. Non-zero becomes a single finding carrying the command's output.

```yaml
tests:
  - name: vale
    run: "vale --minAlertLevel=error docs/reference"
```

Use this form to adopt a linter you already run.

## Report structured findings

With a `results:` field, the command writes that file and the runner merges its contents into the same report as everything else. This form gives you per-file and per-line findings, severities, and coverage.

```yaml
tests:
  - name: style
    run: "python3 scripts/check_style.py --output results/style.json"
    results: "results/style.json"
```

The file's schema is in [the results reference](../reference/results.md#reporting-findings-from-your-own-check). Any language can write it.

## Constraints on commands

**Commands run without a shell.** A command containing `|`, `&&`, `;`, `>` or similar characters is rejected, so configuration cannot inject a shell. Put the pipeline in a script and call the script.

**Install dependencies with `setup:`.** The action provides Python. Anything else needs a setup command.

```yaml
    setup:
      - "pip install -r scripts/requirements.txt"
```

**Your command scopes itself.** `targets` and `exclude` narrow the agentic reviews. A command is your own program, so it takes its own arguments.

**Findings can suppress duplicate review findings.** Give a finding a `covered_topic` and the reviews skip that topic, so a deterministic result is not reported twice.

## Worked examples

The [`tests/deterministic/`](https://github.com/canonical/user-docs-testing/tree/main/tests/deterministic) directory holds two scripts written to be read. `undocumented_surface.py` diffs a machine-readable interface manifest against the documentation. `source_manifest.py` emits coverage and source evidence, so unverifiable material is reported as blocked instead of passing. Both are demonstrations rather than checks that this project runs for you.
