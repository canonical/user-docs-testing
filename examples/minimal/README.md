# Minimal example

The smallest useful setup: one documentation tree, one product, two tests. It
runs offline, so you can see real output before installing anything.

```
docs/reference/cli.md          the documentation under test
sources/product/               stands in for the product repository
docs-testing.config.yml        the whole configuration
```

## Run it

From this directory:

```bash
docs-testing run
```

(If you have not installed it: `pipx install git+https://github.com/canonical/user-docs-testing`,
or from a clone of this repository, `PYTHONPATH=../.. python3 -m docs_testing run`.)

## What you should see

The documentation covers `--verbose` and `--output`, but the product also has
`--retries`. The deterministic check finds it:

```
WARNINGS  documentation verified, non-blocking findings reported

Warnings (1) — reported, not blocking:
  sources/product/cli-surface.txt  Interface element not documented in reference targets: --retries  [cli-surface]

Sources:
  ok      product                      commit=- files=1

1/1 check(s) ran, 0 problem(s), 1 warning(s), 0 unverified area(s), 0 tool error(s)
1 review(s) are run by the AI engine in CI and are not included above.
```

Exit status is `0`: an undocumented option is worth knowing about, but it is not
a broken claim, so by default it does not fail CI.

## Make it a failure instead

Pass `--severity error` to the check's command:

```yaml
  - name: cli-surface
    run: "python3 ../../tests/deterministic/undocumented_surface.py
           --manifest sources/product/cli-surface.txt
           --targets docs/reference/**/*.md
           --severity error
           --output results/cli-surface.json"
    results: "results/cli-surface.json"
```

Now the same run reports `FAIL` and exits `1`.

## Make it pass

Document `--retries` in `docs/reference/cli.md` and run again:

```
PASS      documentation verified, nothing to fix
```

That is the meaningful part: `PASS` here means the check ran, the product source
was present, and every enumerated option was found. Delete
`sources/product/cli-surface.txt` and you get `INCOMPLETE` instead — the surface
could not be enumerated, so the documentation was never actually verified.

## The second test

`reference-review` is a review by an AI engine and needs the workflow, so it does
not run locally. See the [README](../../README.md) to install it.
