# Getting started

Run a documentation check locally and see each of the outcomes it can produce. Nothing is installed into GitHub, and no AI engine is involved.

The example you will use also declares an agentic review. That one needs the installed workflow and does not run locally, so it is skipped throughout.

## Before you start

Install the command:

```bash
pipx install git+https://github.com/canonical/user-docs-testing
```

## Run a check

[examples/minimal](../../examples/minimal/) contains one documentation tree, one product source, and a configuration naming both.

```bash
cd examples/minimal
docs-testing run
```

The documentation covers `--verbose` and `--output`. The product also has `--retries`, which the check reports:

```
WARNINGS  documentation verified, non-blocking findings reported

Warnings (1) — reported, not blocking:
  sources/product/cli-surface.txt  Interface element not documented in reference targets: --retries  [cli-surface]
```

Exit status is `0`. An undocumented option is worth reporting, but it is not a false claim, so by default it does not fail CI.

## Make it pass

Document `--retries` in `docs/reference/cli.md` and run again:

```
PASS      documentation verified, nothing to fix
```

`PASS` means the check ran, the product source was present, and every option in it was found in the documentation.

## See an unverified run

Remove the file the check reads its list of options from:

```bash
mv sources/product/cli-surface.txt /tmp/
docs-testing run
```

The result is `INCOMPLETE`, not `PASS`. The product surface could not be read, so the documentation was never verified. A missing source never produces a pass.

Put it back when you are done:

```bash
mv /tmp/cli-surface.txt sources/product/
```

## Next

- [examples/minimal](../../examples/minimal/) also shows how to make the same finding fail the build instead of warning.
- To run this in CI, and to add the two shipped reviews, follow the install steps in the [README](../../README.md).
- [Configuration reference](../reference/configuration.md) covers every field.
