# User documentation testing

A GitHub Actions workflow that tests documentation against the product it describes and reports the result as a Check Run.

It is a thin wrapper around [gh-aw](https://github.github.io/gh-aw/) that runs documentation checks defined in one configuration file. Two agentic reviews ship with it. You can also run deterministic checks of your own — any command, in any language, as long as it reports its findings in the [results schema](docs/reference/results.md#extending-with-your-own-check) — and both kinds appear in the same report.

> **Status: pre-release.** No version has been tagged. Installation tracks `main`, but `gh aw add` pins the exact commit, so your runs do not change until you update. Upstream may change in breaking ways between updates.

## What it checks

Deterministic checks are commands you supply. They run first, and anything they report is excluded from the reviews that follow.

The two reviews below ship with the workflow and are performed by an AI engine:

| Review | Question it answers |
| ------ | ------------------- |
| `reference-review` | Does the documentation state something the product contradicts? |
| `reference-completeness` | Does product surface exist that the documentation never mentions? |

Every finding must cite the product source that proves it. A review that cannot reach its source reports the affected documentation as **unverified**, not as passing.

## Install

You need the [gh CLI](https://cli.github.com/) and the [gh-aw extension](https://github.com/githubnext/gh-aw):

```bash
gh extension install githubnext/gh-aw
```

Then, in your documentation repository:

```bash
gh aw add canonical/user-docs-testing/workflows/docs-testing.md
```

That adds `.github/workflows/docs-testing.md`, compiles it, and records where it came from so `gh aw update docs-testing` can pick up later changes.

The default engine is `copilot`. To choose another at install time:

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

GitHub Actions cannot run Markdown, so `gh aw compile` generates the `.lock.yml` that Actions actually executes. It has to be committed next to its `.md`.

## Update

```bash
gh aw update docs-testing
```

This re-fetches the workflow and its imports at a newer commit, re-pins actions, and regenerates the `.lock.yml`. Review the diff, then commit it.

Your `checkout:` blocks are in the same file gh-aw rewrites, so an upstream change to the workflow has to be reconciled with your edits. `docs-testing.config.yml` is never affected: it is read at run time, not compiled.

Check the result with `docs-testing validate` and one manual run before relying on it. To undo an update, revert the commit — the workflow, its lock file, and every import are pinned, so nothing else moves.

## Reading the result

Five outcomes:

| Result | Meaning | Check Run |
| ------ | ------- | --------- |
| **Pass** | Verified; nothing to fix. | `success` |
| **Warnings** | Verified; non-blocking findings reported. | `neutral` |
| **Incomplete** | Part of the scope could not be verified. | `neutral`, or `action_required` |
| **Fail** | An actionable documentation problem was found. | `failure` |
| **Tool error** | The tool itself failed; the results mean nothing. | `action_required` |

The last two rows are the reason the outcomes are kept separate. A crashed check, an unreadable results file, or a private source that failed to clone won't report that your documentation passed. Full detail in [the results reference](docs/reference/results.md).

The configuration is checked before any test runs, so a typo fails in seconds with a message naming the field and the fix.

## Examples

- [examples/minimal](examples/minimal/) — one public source, one agentic review and one deterministic check. The deterministic half runs offline. Start here.
- [examples/landscape](examples/landscape/) — a product spread across four repositories, one of them private, with source ownership and partial coverage.
- [docs-testing.config.example.yml](docs-testing.config.example.yml) — every supported field, annotated, with real values.

## Optional: run the checks locally

CI runs all of this. Local runs are for a faster loop while writing your configuration.

```bash
pipx install git+https://github.com/canonical/user-docs-testing

docs-testing validate   # is my configuration correct?
docs-testing run        # run the checks that need no AI engine
docs-testing list       # what checks are available?
```

## Going further

**How-to guides**

- [How to set up engines and access private sources](docs/how-to/engines.md) — which credential does what, and how to keep a private source safe.
- [How to schedule runs](docs/how-to/scheduling.md) — cadence, manual runs, and running different scopes at different frequencies.

**Reference**

- [Configuration](docs/reference/configuration.md) — every field, including source ownership, generated documentation, and custom checks.
- [Results](docs/reference/results.md) — outcomes, coverage, and the schema for writing your own check.
- [Architecture](docs/reference/architecture.md) — what each directory in this repository contains.

**Explanation**

- [How it works](docs/explanation/how-it-works.md) — the lock file, what compiles when, what happens during a run, and how much one review can cover.

To work on this project itself, see [CONTRIBUTING.md](CONTRIBUTING.md).
