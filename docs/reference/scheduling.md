# Scheduling

The installed workflow runs on a schedule and on demand:

```yaml
on:
  workflow_dispatch:            # "Run workflow" button, any time
  schedule:
    - cron: "weekly on monday"
```

Manual runs need nothing extra — Actions → Documentation testing → Run workflow.

## Schedule syntax

gh-aw accepts friendly expressions and raw cron:

| Expression | Meaning |
| ---------- | ------- |
| `daily` | Once a day |
| `weekly on monday` | Once a week |
| `weekly on friday at 09:00` | With a time |
| `0 6 1 * *` | Raw cron — required for monthly |

Friendly expressions are *scattered*: gh-aw converts them to a fixed minute
derived from your repository name, so a hundred repositories running "weekly on
monday" do not all start at 06:00. Raw cron is used exactly as written.

Several entries are allowed:

```yaml
schedule:
  - cron: "weekly on monday"
  - cron: "0 6 1 * *"
```

Both run the same tests over the same scope, just more often.

## Different scopes on different cadences

A cheap check often and an expensive one occasionally is a common want — for
example a fast deterministic pass every week and a full review monthly.

A single workflow cannot do this, because it has one configuration. Install it
twice instead, each with its own name, schedule, and config:

```bash
gh aw add canonical/user-docs-testing/docs-testing -n docs-testing-weekly
gh aw add canonical/user-docs-testing/docs-testing -n docs-testing-monthly
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

Each produces its own Check Run, named from its own `reporting.title`, so the
two results stay distinguishable in the Checks UI.

## Running on pull requests

The shipped workflow does not trigger on pull requests, deliberately: a reference
review costs AI credits on every push, and a fork pull request must never be able
to reach a private source token.

If you have no private sources and want PR-time coverage, add:

```yaml
on:
  pull_request:
    paths:
      - "docs/**"
```

Restrict it to same-repository pull requests if any source is private. See
[engines and tokens](engines.md) for why.
