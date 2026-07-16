---
# Documentation testing workflow (GitHub Agentic Workflow source).
#
# Generic template. Consumers install it into their repository, then drive it
# from their own `docs-testing.config.yml`. It contains no project-specific logic.
#
# Setup for a consuming repository:
#   1. Copy this file to `.github/workflows/docs-testing.md` in your repo.
#   2. Under `imports:`, list the shipped agentic tests you want to run.
#   3. Add a `docs-testing.config.yml` (see docs-testing.config.example.yml) with
#      each test's targets, sources, and reporting.
#   4. Fill in the source-of-truth checkouts and any secrets your tests need.
#   5. Compile:  gh aw compile
#      Commit the generated docs-testing.lock.yml next to this file.
description: "Run documentation tests declared in docs-testing.config.yml."
emoji: "🔎"
labels: ["docs-testing", "automation"]

# Shipped agentic tests. Each is a markdown instruction file fetched from the
# (public) tool repo at COMPILE time, pinned to a ref, and baked into the
# generated lock file — so the workflow needs no runtime access to the tool repo.
# Add one line per agentic test you want; remove the ones you don't.
imports:
  - canonical/user-docs-testing/tests/agentic/reference-review.md@v1

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

engine: copilot

# Check out the repositories the run needs.
checkout:
  # Your repository: documentation and docs-testing.config.yml.
  - repo: ${{ github.repository }}

  # Your source-of-truth repo(s). One block per source in your config. Use a
  # secret for private repos; omit `token` for public ones. Example:
  #
  # - repo: my-org/my-product
  #   ref: main
  #   path: sources/product
  #   token: ${{ secrets.PRODUCT_REPO_TOKEN }}

  # Only if you run a *shipped* deterministic test: check out the (public) tool
  # repo to get run_tests.py and the shipped check scripts. Not needed for
  # agentic-only setups, or when your deterministic scripts live in your repo.
  #
  # - repo: canonical/user-docs-testing
  #   ref: v1
  #   path: .user-docs-testing

# Deterministic layer (OPTIONAL). Uncomment if your config declares deterministic
# tests. It runs the orchestrator before the agent, writing combined findings to
# results/all.json so the agent can de-duplicate against them.
# steps:
#   - name: Set up Python
#     uses: actions/setup-python@v5
#     with:
#       python-version: "3.12"
#   - name: Install orchestrator deps
#     run: pip install pyyaml
#   - name: Run deterministic tests
#     run: python .user-docs-testing/run_tests.py --config docs-testing.config.yml --output results/all.json
#   - name: Upload deterministic results
#     uses: actions/upload-artifact@v4
#     with:
#       name: deterministic-results
#       path: results/all.json
#       if-no-files-found: warn

# Report findings as a CI-gating Check Run (the default reporting mode).
safe-outputs:
  create-check-run:
    name: "Documentation testing"
    max: 1
---

# Documentation testing

Run the documentation tests configured for this repository. The instructions for
each shipped agentic test are included above (via imports) — follow those
criteria, and do not impose criteria of your own.

Follow these steps:

1. **Read the config.** Load `docs-testing.config.yml`. For each test with
   `type: agentic`, note its `name`, `targets`/`exclude`, `sources`, `generated`
   policy, and the `reporting` settings. Sources of truth are checked out under
   `sources/`.

2. **Read the deterministic results, if any.** If `results/all.json` exists, it
   holds findings from deterministic tests that ran before you. Use it both to
   report and to avoid duplicating work.

3. **Run each agentic test.** For every configured agentic test, apply the
   matching instructions from above to the files in its `targets` (minus
   `exclude`), using its `sources` where relevant.
   - Honour the test's `generated` policy (`skip`, `annotate`, or
     `deterministic-only`) if present.
   - If `skip_deterministically_covered` is true, do not re-report anything whose
     topic already appears as a `covered_topic` in `results/all.json`.

4. **Report once.** Emit a single `create_check_run` that combines the
   deterministic findings and your agentic findings:
   - `conclusion: failure` if there are findings and `reporting.fail_on_findings`
     is true.
   - `conclusion: neutral` if there are findings but failing is disabled.
   - `conclusion: success` if no findings.
   - The summary must group findings by test and by documentation file, each with
     a one-line description and any supporting evidence.

If nothing needs action, you MUST still emit a `create_check_run` with
`conclusion: success`.
