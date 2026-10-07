# How to schedule runs

The installed workflow runs on a schedule and on demand:

```yaml
on:
  workflow_dispatch:            # "Run workflow" button, any time
  schedule:
    - cron: "weekly on monday"
```

Manual runs need nothing extra — Actions → Docs Testing → Run workflow.

## Schedule syntax

Schedules are gh-aw's, and it accepts both friendly expressions and raw cron. The [gh-aw triggers reference](https://github.github.io/gh-aw/reference/triggers/) documents the full syntax. Two behaviors matter here:

- Friendly expressions such as `daily` or `weekly on monday` are *scattered*: gh-aw derives a fixed minute from your repository name, so many repositories sharing a schedule do not all start at once. Raw cron is used exactly as written.
- Monthly schedules require raw cron, for example `0 6 1 * *`.

Several entries are allowed:

```yaml
schedule:
  - cron: "weekly on monday"
  - cron: "0 6 1 * *"
```

Both run the same tests over the same scope, just more often.

## Different scopes on different cadences

Running checks at different cadences requires multiple installations, because a workflow has one configuration. For example, to run a small check weekly and a larger one monthly, install the project twice, each with its own name, schedule, and config:

```bash
gh aw add canonical/user-docs-testing/workflows/docs-testing.md -n docs-testing-weekly
gh aw add canonical/user-docs-testing/workflows/docs-testing.md -n docs-testing-monthly
```

Point each at its own configuration file:

```yaml
# .github/workflows/docs-testing-weekly.md
on:
  workflow_dispatch:
  schedule:
    - cron: "weekly on monday"

steps:
  - uses: canonical/user-docs-testing/actions/docs-tests@main
    with:
      config: docs-testing.weekly.yml
```

```yaml
# docs-testing.weekly.yml — deterministic only, cheap and fast
version: 1
targets: "docs/reference/**/*.md"
sources:
  - name: product
    repo: my-org/my-product
tests:
  - name: cli-surface
    run: "python3 scripts/check_cli_surface.py --output results/cli-surface.json"
    results: "results/cli-surface.json"
```

```yaml
# docs-testing.monthly.yml — the full review
version: 1
targets: "docs/reference/**/*.md"
sources:
  - name: product
    repo: my-org/my-product
tests:
  - reference-review
  - reference-completeness
```

Each produces its own Check Run, named from its own `reporting.title`, so the two results stay distinguishable in the Checks UI.

## Running on pull requests

The shipped workflow does not trigger on pull requests, deliberately: a reference review costs AI credits on every push, and a fork pull request must never be able to reach a private source token.

If you have no private sources and want PR-time coverage, add:

```yaml
on:
  pull_request:
    paths:
      - "docs/**"
```

Restrict it to same-repository pull requests if any source is private. See [engines and tokens](engines.md) for why.
