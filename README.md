# Docs Testing

Test documentation against the product it describes, and report the result as a
GitHub Check Run.

Documentation goes stale silently. Nothing fails when a default changes, a flag
is renamed, or an option ships undocumented — until a user follows the
instructions and they do not work. This runs those checks in CI, the way you
already run tests.

> **Status: pre-release.** No version has been tagged yet; installations track
> `main` but are pinned to a commit. See [versioning](docs/reference/versioning.md).

## What it checks

| Check | Question it answers |
| ----- | ------------------- |
| `reference-review` | Does the documentation state something the product contradicts? |
| `reference-completeness` | Does product surface exist that the documentation never mentions? |
| `undocumented-surface` | The same question, done precisely, wherever the interface is machine-readable (`--help`, OpenAPI, JSON Schema). |

The first two are reviews performed by an AI engine. The third is a deterministic
diff that also runs locally. You can add your own checks in any language.

Every finding must cite the product source that proves it. A review that cannot
reach its source reports the affected documentation as **unverified** — never as
passing.

## Install

You need the [gh CLI](https://cli.github.com/) and the
[gh-aw extension](https://github.com/githubnext/gh-aw):

```bash
gh extension install githubnext/gh-aw
```

Then, in your documentation repository:

```bash
gh aw add canonical/user-docs-testing/docs-testing
```

That adds `.github/workflows/docs-testing.md`, compiles it, and records where it
came from so `gh aw update docs-testing` can pick up improvements later.

## Configure

Create `docs-testing.config.yml` in the root of the repository:

```yaml
version: 1

docs: "docs/reference/**/*.md"

sources:
  - name: product
    repo: my-org/my-product

tests:
  - reference-review
```

Then tell the workflow to check that product out. In
`.github/workflows/docs-testing.md`, under `checkout:`:

```yaml
  - repository: my-org/my-product
    ref: main
    path: sources/product
```

The `path` must be `sources/<name>`, matching the source's `name`. Recompile and
commit:

```bash
gh aw compile
git add .github/workflows/ docs-testing.config.yml && git commit
```

GitHub Actions cannot run Markdown, so `gh aw compile` generates the `.lock.yml`
that Actions actually executes. It has to be committed next to its `.md`.

## Check it before you push

The checks that do not need an AI engine also run locally:

```bash
pipx install git+https://github.com/canonical/user-docs-testing
```

```bash
docs-testing validate   # is the configuration correct?
docs-testing run        # run the deterministic checks
docs-testing list       # what checks are available?
```

`validate` reports configuration mistakes with a location and a fix, tells you if
the config and the workflow disagree about which sources get checked out, and
lists any secrets you still need to add. CI runs it too, before anything else, so
a typo costs you a fifteen-second step rather than a confusing review.

## Reading the result

Five outcomes, and they never collapse into each other:

| Result | Meaning | Check Run |
| ------ | ------- | --------- |
| **Pass** | Verified; nothing to fix. | `success` |
| **Warnings** | Verified; non-blocking findings reported. | `neutral` |
| **Incomplete** | Part of the scope could not be verified. | `neutral`, or `action_required` |
| **Fail** | An actionable documentation problem was found. | `failure` |
| **Tool error** | The tool itself failed; the results mean nothing. | `action_required` |

The last two rows are the point of the design. A crashed check, an unreadable
results file, or a private source that failed to clone must never come back as
"your documentation passed". Full detail in
[the results reference](docs/reference/results.md).

## Examples

- [examples/minimal](examples/minimal/) — the common case, runnable offline in
  one command. Start here.
- [examples/landscape](examples/landscape/) — a real product implemented across
  six repositories, some private, with source ownership and partial coverage.

## Going further

- [Configuration reference](docs/reference/configuration.md) — every field,
  including source ownership, generated documentation, and custom checks.
- [Results reference](docs/reference/results.md) — outcomes, coverage, and the
  schema for writing your own check.
- [Engines, tokens, and private sources](docs/reference/engines.md) — which
  credential does what, and how to keep a private source safe.
- [Versioning](docs/reference/versioning.md) — what is stable and what is not.
