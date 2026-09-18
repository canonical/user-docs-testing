# User documentation testing

A GitHub Actions workflow that tests documentation against the product it describes and reports the result as a Check Run.

This project is a wrapper around [gh-aw](https://github.github.io/gh-aw/) that runs documentation checks defined in a project-specific configuration file. It ships with pre-made agentic reviews, and you can also provide your own deterministic checks (any language). Results are all reported together.

## What it checks

There are two kinds of checks this documentation workflow can use:

- **Agentic reviews**: Performed by an AI engine. Agentic reviews are provided in this project, but you choose which to run in your documentation.
- **Deterministic checks**: Project-specific checks you supply. These aren't performed by an AI engine, but See [how to add your own deterministic check](docs/how-to/custom-checks.md).

| Shipped review | Question it answers |
| --------------- | -------------------- |
| `reference-review` | Does the documentation state something the product contradicts? |
| `reference-completeness` | Does product surface exist that the documentation never mentions? |

Any custom deterministic checks you include run first, and anything they report is excluded from the reviews that follow.

All findings cite the product source that proves it. If an agentic review can't reach its source, it reports the affected documentation as **unverified**, not as passing.

## Install

You need the [gh CLI](https://cli.github.com/) and the [gh-aw extension](https://github.com/githubnext/gh-aw):

```bash
gh extension install githubnext/gh-aw
```

Then, in your documentation repository:

```bash
gh aw add canonical/user-docs-testing/workflows/docs-testing.md
```

That adds `.github/workflows/docs-testing.md`, compiles it, and records where it came from. Installation tracks `main` and records the exact commit it resolved to. You can update your project later with:

```bash
gh aw update docs-testing
```

The default engine is `copilot`. To use another, specify that at install time:

```bash
gh aw add canonical/user-docs-testing/workflows/docs-testing.md --engine claude
```

Engine selection comes from upstream gh-aw, see [how to set up engines and access private sources](docs/how-to/engines.md).

## Configure

Create `docs-testing.config.yml` in the root of the repository:

```yaml
version: 1

targets: "docs/reference/**/*.md"

sources:
  - name: product
    repo: my-org/my-product

tests:
  - reference-review
```

Then tell the workflow to check that product out. In `.github/workflows/docs-testing.md`, under `checkout:`:

```yaml
  - repository: my-org/my-product
    ref: main
    path: sources/product
```

The `path` must be `sources/<name>`, matching the source's `name`. Recompile and commit:

```bash
gh aw compile
git add .github/workflows/ docs-testing.config.yml && git commit
```

Because GitHub Actions can't run Markdown, `gh aw compile` generates the `.lock.yml` that Actions actually executes. It has to be committed next to its `.md`, although users won't use or edit this file manually.

## Update

```bash
gh aw update docs-testing
```

This re-fetches the workflow and its imports at a newer commit, re-pins actions, and regenerates the `.lock.yml`. 

gh-aw auto-merges the update with your local edits, including your `checkout:` blocks, rather than overwriting the file. `docs-testing.config.yml` isn't touched in an update.

Validate your update with `docs-testing validate` to catch any `checkout:` blocks the auto-merge may have dropped or moved. It's recommended to also manually review the changes when you update.

## Interpreting the result

Your report can have the following outcomes:

| Result | Meaning | Check Run |
| ------ | ------- | --------- |
| **Pass** | Verified; nothing to fix. | `success` |
| **Warnings** | Verified; non-blocking findings reported. | `neutral` |
| **Incomplete** | Part of the scope could not be verified. | `neutral`, or `action_required` |
| **Fail** | An actionable documentation problem was found. | `failure` |
| **Tool error** | The tool itself failed; the results mean nothing. | `action_required` |

A crashed check, an unreadable results file, or a private source that failed to clone won't report that your documentation passed. Full detail in [the results reference](docs/reference/results.md).

## Examples

- [examples/minimal](examples/minimal/): A minimal example you can get started with. It includes one public source, one agentic review, and one deterministic check.
- [examples/full-product](examples/full-product/): A full example product config spread across four repositories, one of them private, with source ownership and partial coverage. This example is intended to be read and referenced.

See the [full configuration reference](docs/reference/configuration.md).

## Optional: run the checks locally

CI runs all of this. Local runs are for a faster loop while writing your configuration.

```bash
pipx install git+https://github.com/canonical/user-docs-testing

docs-testing validate   # is my configuration correct?
docs-testing run        # run the checks that need no AI engine
docs-testing list       # what checks are available?
```

## Further reading

**How-to guides**

- [How to add your own check](docs/how-to/custom-checks.md) — exit status or structured findings, and what runs where.
- [How to set up engines and access private sources](docs/how-to/engines.md) — which credential does what, and how to keep a private source safe.
- [How to schedule runs](docs/how-to/scheduling.md) — cadence, manual runs, and running different scopes at different frequencies.

**Reference**

- [Configuration](docs/reference/configuration.md) — every field, including source ownership, generated documentation, and custom checks.
- [Results](docs/reference/results.md) — outcomes, coverage, and the schema for writing your own check.
- [Architecture](docs/reference/architecture.md) — what each directory in this repository contains.

**Explanation**

- [How it works](docs/explanation/how-it-works.md) — the lock file, what compiles when, what happens during a run, and how much one review can cover.

To work on this project itself, see [CONTRIBUTING.md](CONTRIBUTING.md).
