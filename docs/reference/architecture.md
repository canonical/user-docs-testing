# Architecture

What each directory in this repository contains, and which parts end up in a repository that installs the workflow.

## Directories

| Path | Contents |
| ---- | -------- |
| `docs_testing/` | The Python package. Parses and validates `docs-testing.config.yml`, expands globs, records source evidence, runs deterministic checks, and writes `results/all.json`. Provides the `docs-testing` command. |
| `actions/docs-tests/` | The composite GitHub Action that runs the package in CI. Installs the package, validates the configuration, then runs the deterministic stage. |
| `workflows/docs-testing.md` | The installable workflow: gh-aw frontmatter plus the prompt that instructs the agent. This is what `gh aw add` copies into a user's repository. |
| `tests/agentic/` | One instruction file per shipped review. Imported by the workflow at compile time and pinned to a commit. |
| `tests/deterministic/` | Example deterministic checks. These are illustrations to copy and adapt, not checks the workflow runs for you. |
| `selftests/` | Contract tests for this repository, run by `.github/workflows/selftest.yml`. |
| `examples/` | Two worked configurations. See [examples/minimal](../../examples/minimal/) and [examples/full-product](../../examples/full-product/). |
| `docs/` | This documentation. |

## Inside the package

| Module | Responsibility |
| ------ | -------------- |
| `config.py` | The schema. Parses YAML, validates it, and produces the run plan. |
| `runner.py` | Executes the deterministic stage and assembles results. |
| `results.py` | Outcome and coverage vocabulary, and their precedence. |
| `report.py` | Human-readable output for local runs. |
| `cli.py` | The `validate`, `run`, and `list` subcommands. |
| `checks/globs.py` | Glob expansion for `targets` and `exclude`. |
| `checks/source_evidence.py` | Records what was actually checked out under `sources/`. |

## What a user's repository ends up with

Installing adds `.github/workflows/docs-testing.md`, its generated `.lock.yml`, and `.github/aw/` holding gh-aw's pinned imports and action versions. The user writes `docs-testing.config.yml` themselves.

Nothing else from this repository is copied. The package and the composite action are fetched at run time, pinned to the commit recorded at install.

## What belongs to gh-aw

Workflow compilation, the lock file, imports and pinning, engine selection, network restrictions, and safe outputs are all [gh-aw](https://github.github.io/gh-aw/) behavior. This project supplies the configuration format, the deterministic stage, the shipped review instructions, and the reporting contract. See [how it works](../explanation/how-it-works.md) for where the boundary falls during a run.
