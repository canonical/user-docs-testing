---
# Documentation testing workflow (GitHub Agentic Workflow source).
#
# This is a generic template. Consumers install it into their repository, then
# drive it entirely from their own `docs-testing.config.yml`. It contains no
# project-specific logic.
#
# Setup for a consuming repository:
#   1. Copy this file to `.github/workflows/docs-testing.md` in your repo.
#   2. Add a `docs-testing.config.yml` (see docs-testing.config.example.yml).
#   3. Fill in the checkout entries for your source-of-truth repos and any
#      secrets they need (see the commented block below).
#   4. Compile:  gh aw compile
#      Commit the generated docs-testing.lock.yml next to this file.
description: "Run documentation tests declared in docs-testing.config.yml."
emoji: "🔎"
labels: ["docs-testing", "automation"]

on:
  # Manual trigger.
  workflow_dispatch:
  # Scheduled run — adjust or remove as needed.
  schedule:
    - cron: "0 6 * * 1"

# The agent runs READ-ONLY. All writes happen in the gated safe-outputs job, so
# secrets never enter the agent runtime.
permissions:
  contents: read

# Default engine. Individual agentic tests may request a different engine in the
# config; this is the fallback for the workflow itself.
engine: copilot

# Check out the repositories the run needs.
checkout:
  # The consuming repo: documentation, config, and test files.
  - repo: ${{ github.repository }}

  # This tool repo, pinned to a ref. Provides the orchestrator (run_tests.py) and
  # the shipped tests. Replace OWNER/REPO and the ref with the tool's location and
  # a tag/commit you trust.
  - repo: OWNER/docs-testing-tool
    ref: main
    path: .docs-testing-tool

  # Your source-of-truth repo(s). One block per source in your config. Use a
  # secret for private repos; omit `token` for public ones. Example:
  #
  # - repo: my-org/my-product
  #   ref: main
  #   path: sources/product
  #   token: ${{ secrets.PRODUCT_REPO_TOKEN }}

# Static steps run before the agent. They run the OPTIONAL deterministic layer so
# the agent can de-duplicate against objective findings. If your config has no
# deterministic tests, this simply produces an empty results file.
steps:
  - name: Set up Python
    uses: actions/setup-python@v5
    with:
      python-version: "3.12"
  - name: Install orchestrator deps
    run: pip install pyyaml
  - name: Run deterministic tests
    run: python .docs-testing-tool/run_tests.py --config docs-testing.config.yml --output results/all.json
  - name: Upload deterministic results
    uses: actions/upload-artifact@v4
    with:
      name: deterministic-results
      path: results/all.json
      if-no-files-found: warn

# Report findings as a CI-gating Check Run (the default reporting mode).
safe-outputs:
  create-check-run:
    name: "Documentation testing"
    max: 1
---

# Documentation testing

You are running the documentation tests declared in this repository's
`docs-testing.config.yml`. Each test defines its own criteria in its instruction
file — follow those, and do not impose criteria of your own.

Follow these steps:

1. **Read the config.** Load `docs-testing.config.yml`. Note the `sources` (their
   checkout paths under `sources/`), the `reporting` settings, and the `tests`
   list.

2. **Read the deterministic results.** The step before you wrote combined
   deterministic findings to `results/all.json` (may be empty). You will use
   these both to report and to avoid duplicating work.

3. **Run each agentic test.** For every test with `type: agentic`:
   - Read its `instructions` file (shipped tests are under `.docs-testing-tool/`).
     That file defines exactly what to check and how to judge it.
   - Apply it to the files matched by the test's `targets` (minus `exclude`),
     using the named `sources` where relevant.
   - Honour the test's `generated` policy (`skip`, `annotate`, or
     `deterministic-only`) if present.
   - If `skip_deterministically_covered` is true, do not re-report anything whose
     topic already appears as a `covered_topic` in `results/all.json`.

4. **Report once.** Emit a single `create_check_run` that combines the
   deterministic findings and your agentic findings:
   - `conclusion: failure` if there are error-severity findings and
     `reporting.fail_on_findings` is true.
   - `conclusion: neutral` if there are findings but failing is disabled.
   - `conclusion: success` if no findings.
   - The summary must group findings by test and by documentation file, each with
     a one-line description and any supporting evidence.

If nothing needs action, you MUST still emit a `create_check_run` with
`conclusion: success`.
