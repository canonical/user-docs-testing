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
# Add one line per agentic test you want; remove the ones you don't. Available:
#   reference-review        general accuracy/drift review (default; start here)
#   reference-completeness  interface in source but undocumented
#   reference-defaults      documented defaults, types, and constraints
#   reference-consistency   pages agree with each other and across components
#   reference-permissions   authentication / privilege / permission claims
imports:
  - canonical/user-docs-testing/tests/agentic/reference-review.md@v1
  # - canonical/user-docs-testing/tests/agentic/reference-completeness.md@v1
  # - canonical/user-docs-testing/tests/agentic/reference-defaults.md@v1
  # - canonical/user-docs-testing/tests/agentic/reference-consistency.md@v1
  # - canonical/user-docs-testing/tests/agentic/reference-permissions.md@v1

on:
  # Manual trigger.
  workflow_dispatch:
  # Scheduled run — adjust or remove as needed.
  schedule:
    - cron: "0 6 * * 1"
  # SECURITY — private sources and untrusted pull requests:
  # Do NOT add a `pull_request` trigger from FORKS while any private source is
  # configured. A fork PR can alter this workflow or docs-testing.config.yml and,
  # if a privileged source token were exposed to it, use that token to read
  # private repositories. Keep private-source runs on trusted events only
  # (workflow_dispatch, schedule, or pushes to protected branches). If you need
  # PR-time coverage, restrict it to same-repository PRs and gate any
  # private-source checkout behind an appropriate trusted event.

# The agent runs READ-ONLY. All writes happen in the gated safe-outputs job, so
# secrets never enter the agent runtime.
permissions:
  contents: read

# AI engine that runs the agentic tests. Not fixed to Copilot — set this to any
# provider gh-aw supports and store the matching secret in your repo/org:
#   copilot -> COPILOT_GITHUB_TOKEN (fine-grained PAT, Copilot Requests: Read-only)
#   claude  -> ANTHROPIC_API_KEY
#   codex   -> OPENAI_API_KEY
#   gemini  -> GEMINI_API_KEY
# OpenAI-compatible providers (e.g. OpenRouter) work via codex + OPENAI_BASE_URL
# or Copilot BYOK + COPILOT_PROVIDER_BASE_URL; add the provider host to
# network.allowed. After changing this, run `gh aw compile` and commit the
# regenerated .lock.yml. This engine token is SEPARATE from any source token
# below. See https://github.github.com/gh-aw/reference/engines/ and README.md.
engine: copilot

# Check out the repositories the run needs.
checkout:
  # Your repository: documentation and docs-testing.config.yml (primary target).
  - current: true

  # Your source-of-truth repo(s). One block per source in your config. A private
  # source needs its OWN read token (Contents: Read) — this is separate from the
  # engine token above, and a personal fine-grained PAT cannot span orgs. Use a
  # secret for private repos; omit `token` for public ones. Example:
  #
  # - repository: my-org/my-product
  #   ref: main
  #   path: sources/product
  #   token: ${{ secrets.SOURCE_REPO_TOKEN }}
  #
  # Match each block to a `sources:` entry in docs-testing.config.yml. If a
  # source is REQUIRED there and its checkout fails, the runs that depend on it
  # are incomplete — the agent reports those files as blocked, never as passing,
  # and the check run concludes with `reporting.on_incomplete_coverage` rather
  # than `success`. Never expose a private source token to an untrusted fork
  # (see the SECURITY note under `on:`).

  # Only if you run a *shipped* deterministic test: check out the (public) tool
  # repo to get run_tests.py and the shipped check scripts. Not needed for
  # agentic-only setups, or when your deterministic scripts live in your repo.
  #
  # - repository: canonical/user-docs-testing
  #   ref: main
  #   path: .docs-testing-tool

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

1. **Read the config.** Load `docs-testing.config.yml`. Note the top-level
   `sources` (with each one's `required` flag), the shared `source_map` that says
   which source owns which documentation, and the `reporting` settings. For each
   test with `type: agentic`, note its `name`, `targets`/`exclude`, `sources`,
   `generated` policy, and any test-level `source_map`. Sources of truth are
   checked out under `sources/`.

2. **Read the deterministic results, if any.** If `results/all.json` exists, it
   holds findings from deterministic tests that ran before you, plus their
   `coverage` entries. Use it both to report and to avoid duplicating work.

3. **Run each agentic test.** For every configured agentic test, apply the
   matching instructions from above to the files in its `targets` (minus
   `exclude`), using its `sources` where relevant.
   - Honour the test's `generated` policy (`skip`, `annotate`, or
     `deterministic-only`) if present.
   - If `skip_deterministically_covered` is true, do not re-report anything whose
     topic already appears as a `covered_topic` in `results/all.json`.

4. **Report once.** Emit a single `create_check_run` combining the deterministic
   and agentic results. Pick the conclusion in this order — the three outcomes
   must stay distinct:
   - `failure` — there are findings and `reporting.fail_on_findings` is true.
     ("We found a problem.")
   - `reporting.on_incomplete_coverage` (default `neutral`) — no findings, but at
     least one area is `blocked-required-source-unavailable` or
     `unsupported-by-configured-sources`, in either `results/all.json` coverage
     or an agentic test's classification. ("We could not establish whether it is
     correct.") Never report `success` in this case.
   - `neutral` — there are findings but `fail_on_findings` is false.
   - `success` — every in-scope area was reviewed and nothing was found.
     ("We checked it and it appears correct.")
   - The summary must group findings by test and by documentation file, each with
     a one-line description and any supporting evidence, and must list blocked or
     unsupported areas separately so a reader can see what was NOT verified.

If nothing needs action, you MUST still emit a `create_check_run`, using the
conclusion chosen by the rules above.

