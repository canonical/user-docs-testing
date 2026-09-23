# Contributing

## Setup

Python 3.11 or later. No dependencies are required to run the tests.

```bash
git clone https://github.com/canonical/user-docs-testing
cd user-docs-testing
python3 -m unittest discover -s selftests
```

## Tests

`selftests/test_contracts.py` holds the behavioral contracts: what the configuration accepts, what the runner produces, and which guarantees must not regress. Add a test there for any change in behavior. CI runs the same command.

To try a change end to end, use [examples/minimal](examples/minimal/):

```bash
cd examples/minimal
PYTHONPATH=../.. python3 -m docs_testing run
```

## Where things live

See [docs/reference/architecture.md](docs/reference/architecture.md).

## Changing a shipped review

The review instructions in `tests/agentic/` are imported by installed workflows and pinned to a commit, so a change reaches users only when they run `gh aw update`. Their effect cannot be verified by the self-tests; they need a real run against a repository with known documentation defects.

## Adding an agentic review

`docs-testing.config.yml` does not support naming your own project-specific agentic review: `uses:` only accepts the shipped set.

If you want a new agentic review to exist, open an issue or a PR.

## Changing the workflow

`workflows/docs-testing.md` is the installable workflow. If you edit it, run `gh aw compile` in a repository that installs it, not in this one — compiling here leaves stray artifacts.

## Documentation

`docs/` follows [Diátaxis](https://diataxis.fr/): `tutorial/`, `how-to/`, `reference/`, `explanation/`. Keep prose lightweight and declarative. Where behavior belongs to gh-aw, link to its documentation rather than restating it.

Paragraphs are written on one line; wrapping is left to the editor.
