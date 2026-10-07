# Tutorial example: reviewing and validating tutorials

A worked configuration for the two shipped tutorial tests. The folder holds a single
tutorial (`tutorial.md`) used as the test target.

- `tutorial-review` statically checks every tutorial here for security risks,
  prerequisite gaps, and structural issues. It runs inside the unified
  `docs-testing.md` workflow and reports into its check run.
- `tutorial-validation` executes one tutorial (`tutorial.md`) end to end on a
  runner. Because it runs commands with elevated privileges, it installs and runs as its
  own workflow, `validate-tutorial.md`.

Neither test needs a product source: a tutorial is judged against itself (review) or by
running it (validation).

See [how to test tutorials](../../docs/how-to/tutorial-testing.md) for the full
walkthrough, and [the configuration reference](../../docs/reference/configuration.md)
for every field.
