# docs-testing-tool

> This project is a work-in-progress.

A tool for testing documentation. It reports its findings as a GitHub Check Run.

## Tests

Tests are declared in a `docs-testing.config.yml` in your repo. Two kinds:

- Agentic tests — a review by an AI engine, run through
  [GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw). Each points
  at an instruction file describing what to check. The tool ships a set of these
  under [tests/agentic/](tests/agentic/).
- Deterministic tests — a command that emits findings in a standard JSON schema
  (see [RESULTS-SCHEMA.md](RESULTS-SCHEMA.md)). A few generic ones ship under
  [tests/deterministic/](tests/deterministic/); most are specific to a project, so
  you'll usually add your own.

Choose which tests to run, and point them at your docs, in your config.

## Usage

1. Copy [workflows/docs-testing.md](workflows/docs-testing.md) into your repo under
   `.github/workflows/`.
2. Add a `docs-testing.config.yml` (see
   [docs-testing.config.example.yml](docs-testing.config.example.yml)) selecting
   the tests you want and pointing them at your docs.
3. Compile with `gh aw compile` and commit the generated `.lock.yml`.