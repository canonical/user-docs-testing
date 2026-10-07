---
# Tutorial validation — https://github.com/canonical/user-docs-testing
#
# Install:   gh aw add canonical/user-docs-testing/workflows/validate-tutorial.md
# Update:    gh aw update validate-tutorial
#
# Executes the tutorial named by the `tutorial-validation` test in
# docs-testing.config.yml end to end on the runner, and reports the outcome as a
# CI-gating Check Run. Unlike docs-testing.md this workflow is NOT read-only: it
# installs prerequisites and runs tutorial commands with full privileges, so it
# runs on its own instead of inside the shared documentation run.
description: >
  Repository-agnostic tutorial tester. Selects the tutorial file from
  docs-testing.config.yml, analyses prerequisites, executes every step on
  the runner, and reports the outcome as a CI-gating Check Run that fails
  the workflow run if any step fails.

# The instructions live beside the shipped reviews and are pinned at install.
imports:
  - canonical/user-docs-testing/tests/agentic/tutorial-validation.md@main

on:
  workflow_dispatch:
#  schedule:
    # Weekly, Monday 06:00 UTC
#    - cron: "0 6 * * 1"

permissions:
  contents: read
  copilot-requests: write

engine:
  id: copilot
max-ai-credits: 50

runs-on: [ubuntu-latest]
#runs-on: [self-hosted, linux, amd64]
timeout-minutes: 60

# Disable the AWF sandbox so the agent can use sudo, snap, and apt.
# The ubuntu-latest runner is ephemeral, so the isolation loss is acceptable.
features:
  dangerously-disable-sandbox-agent: "tutorial validation requires sudo snap and apt for installing prerequisites like juju and microk8s"

sandbox:
  agent: false

strict: false

network:
  allowed:
    - defaults
    - api.charmhub.io
    - "snapcraft.io"
    - "charmhub.io"

# Pre-flight safety check: reject tutorials containing obviously destructive
# commands before the agent ever sees them.
#
# The iptables step works around Docker setting the default FORWARD chain
# policy to DROP, which blocks Kubernetes pod egress on this runner.
jobs:
  setup:
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      # Resolve the tutorial path from the same config the agent reads, so the
      # safety gate and the agent act on the same file.
      - name: Resolve tutorial path from config
        run: |
          set -euo pipefail
          CONFIG="docs-testing.config.yml"
          PATTERN=$(yq -r '.tests[] | select(.name == "tutorial-validation") | .targets[0] // ""' "$CONFIG")
          if [ -z "$PATTERN" ]; then
            echo "ERROR: no tutorial-validation targets in $CONFIG"
            exit 1
          fi
          RESOLVED=$(ls -1 $PATTERN 2>/dev/null | head -n1 || true)
          if [ -z "$RESOLVED" ] || [ ! -f "$RESOLVED" ]; then
            echo "ERROR: tutorial target '$PATTERN' matched no existing file"
            exit 1
          fi
          echo "TUTORIAL_PATH=$RESOLVED" >> "$GITHUB_ENV"
          echo "Resolved tutorial path: $RESOLVED"
      - name: Validate tutorial safety
        run: |
          echo "Checking tutorial for dangerous patterns..."
          if grep -qE 'rm -rf /|mkfs\.|dd if=/dev/zero|> /dev/sd' "$TUTORIAL_PATH" 2>/dev/null; then
            echo "ERROR: Tutorial contains potentially destructive commands"
            exit 1
          fi
          echo "Tutorial passed safety check."
      - name: Fix iptables FORWARD chain for Kubernetes pod egress
        run: |
          echo "Docker sets the FORWARD chain policy to DROP, which blocks Kubernetes pod egress."
          sudo iptables -P FORWARD ACCEPT
          echo "FORWARD chain policy set to ACCEPT"
          sudo iptables -L FORWARD | head -n 1

tools:
  bash: [":*"]
  edit:

safe-outputs:
  # Required because sandbox.agent is disabled below; threat detection needs the sandbox.
  threat-detection: false
  create-check-run:
    name: "Tutorial validation"
    max: 1
  # The gate below fails the run deliberately; don't also open a failure issue.
  report-failure-as-issue: false
  report-failed-jobs: false

# Mirror the agent's check-run conclusion onto the run's exit status so a
# `failure` conclusion gates CI. Runs at the end of the agent job, after the
# agent has written its safe outputs.
post-steps:
  - name: Gate run on tutorial-validation conclusion
    shell: bash
    run: |
      set -euo pipefail
      OUT="${RUNNER_TEMP}/gh-aw/safeoutputs/outputs.jsonl"
      if [ ! -s "$OUT" ]; then
        echo "No safe-outputs file at $OUT; nothing to gate."
        exit 0
      fi
      ITEM=$(jq -c 'select(.type=="create_check_run" and .conclusion=="failure")' "$OUT" | head -n1)
      if [ -z "$ITEM" ]; then
        echo "Tutorial validation did not conclude 'failure'; run passes."
        exit 0
      fi
      TITLE=$(printf '%s' "$ITEM" | jq -r '.title // "Tutorial validation"')
      SUMMARY=$(printf '%s' "$ITEM" | jq -r '.summary // ""')
      TEXT=$(printf '%s' "$ITEM" | jq -r '.text // ""')
      {
        echo "## ❌ ${TITLE}"
        echo
        echo "$SUMMARY"
        if [ -n "$TEXT" ]; then
          echo
          echo "$TEXT"
        fi
      } >> "$GITHUB_STEP_SUMMARY"
      # Keep the plain-text job log readable: short prose summary plus a pointer
      # to the rendered report; fold the Markdown body into a collapsible group.
      echo "::error::${TITLE} — tutorial validation concluded 'failure'. See the run Summary for the full report."
      printf '%s\n' "$SUMMARY"
      if [ -n "$TEXT" ]; then
        echo "::group::Full tutorial validation report (Markdown)"
        printf '%s\n' "$TEXT"
        echo "::endgroup::"
      fi
      exit 1
---

# Validate the repository tutorial

The step-by-step instructions for this workflow are the shipped
`tutorial-validation` test, imported above from
`tests/agentic/tutorial-validation.md`. Follow those phases in order: select the
tutorial from `docs-testing.config.yml`, install its prerequisites, execute every
step on the runner, and report the outcome as a single check run.
