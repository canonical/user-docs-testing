---
# Documentation testing.
#
# Install:   gh aw add canonical/user-docs-testing/docs-testing
# Update:    gh aw update docs-testing
#
# Everything about *what* gets tested lives in `docs-testing.config.yml`, not
# here. The only part of this file most repositories need to touch is the
# `checkout:` block, which must list one entry per source of truth in that
# config. `docs-testing validate` cross-checks the two for you.
description: "Test documentation against the product it describes."
emoji: "🔎"
labels: ["docs-testing", "automation"]

# The shipped reference tests. `reference-common.md` holds the rules they share;
# the other two hold the question each one answers. All are imported, but only
# the tests listed in your `docs-testing.config.yml` actually run — so there is
# normally no reason to edit this block.
#
# No release has been tagged yet, so these track `main`. Pin them to a tag once
# one exists; see docs/reference/versioning.md.
imports:
  - canonical/user-docs-testing/tests/agentic/reference-common.md@main
  - canonical/user-docs-testing/tests/agentic/reference-review.md@main
  - canonical/user-docs-testing/tests/agentic/reference-completeness.md@main

on:
  workflow_dispatch:
  # Scattered by gh-aw to a stable per-repository time, so many repositories
  # running this do not all start at once. `weekly on monday`, `daily`, and
  # `weekly on friday at 09:00` all work; monthly needs raw cron (`0 6 1 * *`).
  # Several entries are allowed. To run different scopes on different cadences,
  # install this workflow twice with separate configs — see docs/reference/scheduling.md.
  schedule:
    - cron: "weekly on monday"
  # SECURITY — private sources and untrusted pull requests:
  # Do NOT add a `pull_request` trigger from FORKS while any private source is
  # configured. A fork PR can alter this workflow or docs-testing.config.yml and,
  # if a privileged source token were exposed to it, use that token to read
  # private repositories. Keep private-source runs on trusted events only
  # (workflow_dispatch, schedule, or pushes to protected branches). If you need
  # PR-time coverage, restrict it to same-repository pull requests.

# The agent runs READ-ONLY. All writes happen in the gated safe-outputs job, so
# secrets never enter the agent runtime.
permissions:
  contents: read
  # Lets the Copilot engine authenticate with the workflow's own token, so no
  # personal access token is needed. This requires centralized Copilot billing;
  # if your organization does not have it, remove this line and set a
  # COPILOT_GITHUB_TOKEN secret instead. See docs/reference/engines.md.
  copilot-requests: write

# The AI engine that performs the reviews. Pick it at install time instead of
# editing here:  gh aw add canonical/user-docs-testing/docs-testing --engine claude
# Supported: copilot | claude | codex | gemini. Each needs its own secret, except
# copilot with the permission above. If you change this line by hand, run
# `gh aw compile` afterwards. See docs/reference/engines.md.
engine: copilot

checkout:
  # Your documentation and docs-testing.config.yml.
  - current: true

  # One block per `sources:` entry in docs-testing.config.yml. The `path` must be
  # `sources/<name>`, matching that source's `name`. A PRIVATE source needs its
  # own read token (Contents: Read), separate from the engine's authentication
  # above; omit `token` for public repositories.
  #
  # - repository: my-org/my-product
  #   ref: main
  #   path: sources/product
  #
  # - repository: my-org/my-private-product
  #   ref: main
  #   path: sources/private-product
  #   token: ${{ secrets.SOURCE_REPO_TOKEN }}
  #
  # A REQUIRED source that is missing here makes the reviews depending on it
  # incomplete — they are never reported as passing. Never expose a private
  # source token to an untrusted fork (see the SECURITY note under `on:`).

# Validates the configuration, records which sources were really checked out, and
# runs the deterministic checks, writing results/all.json for the agent to read.
# A configuration error fails here, in seconds, instead of confusing the agent.
steps:
  - name: Run documentation checks
    uses: canonical/user-docs-testing/actions/docs-tests@main
    # Defaults shown; set `config` to run a different scope on this schedule.
    # with:
    #   config: docs-testing.config.yml
    #   sources-root: sources

safe-outputs:
  create-check-run:
    name: "Documentation testing"
    max: 1
---

# Documentation testing

Run the documentation tests configured for this repository and report them as a
single check run.

1. **Read `results/all.json`.** It is the plan and the deterministic results:
   which tests to run (`plan.agentic_tests`), which source owns which
   documentation (`plan.source_map`), how to conclude (`plan.reporting`), what
   was really checked out (`source_evidence`), what the deterministic checks
   already found (`findings`, `coverage`), and whether anything went wrong
   (`errors`).

   If the file is missing or unreadable, the deterministic stage did not
   complete. Report `action_required` saying so, and review nothing — without it
   you cannot tell which sources were actually available.

2. **Run each test in `plan.agentic_tests`.** For each, apply the imported
   instructions whose title names that test, over its `docs` minus `exclude`,
   following the shared rules in "Documentation review: rules common to every
   reference test" above. Run every listed test, and only those.

3. **Report once.** Emit exactly one `create_check_run` covering the
   deterministic and agentic results together, using the conclusion order and
   report structure from the shared rules.

You must emit a `create_check_run` even when there is nothing to fix.

