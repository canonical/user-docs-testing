# How to add your own deterministic check

A deterministic check is a command you supply. There are two ways to report from one, and the simple one needs no code.

## Report through the exit status

With no `results:` field, the command's exit status is the answer. Zero passes; non-zero becomes a single finding carrying the command's output.

```yaml
tests:
  - name: vale
    run: "vale --minAlertLevel=error docs/reference"
```

That is enough to adopt a linter you already run.

## Report structured findings

With a `results:` field, the command writes that file and the runner merges its contents into the same report as everything else. This is what buys you per-file and per-line findings, severities, and coverage.

```yaml
tests:
  - name: style
    run: "python3 scripts/check_style.py --output results/style.json"
    results: "results/style.json"
```

The file's shape is in [the results reference](../reference/results.md#reporting-findings-from-your-own-check). Any language can write it.

## Things worth knowing

**Commands run without a shell.** A command containing `|`, `&&`, `;`, `>` or similar is rejected, so configuration cannot inject a shell. Put the pipeline in a script and call the script.

**Install what you need with `setup:`.** The action guarantees Python. Anything else needs a setup command.

```yaml
    setup:
      - "pip install -r scripts/requirements.txt"
```

**Your command scopes itself.** `targets` and `exclude` narrow the agentic reviews. A command is your own program, so it takes its own arguments.

**Findings can suppress duplicate review findings.** Give a finding a `covered_topic` and the reviews will skip that topic, so a deterministic result is not reported twice.

## Worked examples

The [`tests/deterministic/`](https://github.com/canonical/user-docs-testing/tree/main/tests/deterministic) directory holds two scripts written to be read: `undocumented_surface.py` diffs a machine-readable interface manifest against the documentation, and `source_manifest.py` emits coverage and source evidence so unverifiable material is reported as blocked rather than passing. They are demonstrations, not checks this project runs for you.
