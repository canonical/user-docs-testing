---
description: >
  Repository-agnostic tutorial tester. Selects the tutorial file from
  docs-testing.config.yml, analyses prerequisites, executes every step on
  the runner, and opens a GitHub issue if any step fails.
on:
  workflow_dispatch:
#  schedule:
    # Weekly, Monday 06:00 UTC
#    - cron: "0 6 * * 1"

permissions:
  contents: read
  copilot-requests: write

#model: gpt-5
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
  threat-detection: false
  create-issue:
    title-prefix: "[tutorial-failure] "
    labels: [tutorial, automation, bug]
    max: 1
    deduplicate-by-title: 1
  # The gate below fails the run deliberately; don't also open a failure issue.
  report-failure-as-issue: false

# Fail the run when the agent reports a tutorial failure (a create_issue item),
# so CI is gated. Runs at the end of the agent job, after safe outputs are written.
post-steps:
  - name: Gate run on tutorial validation outcome
    shell: bash
    run: |
      set -euo pipefail
      OUT="${RUNNER_TEMP}/gh-aw/safeoutputs/outputs.jsonl"
      if [ ! -s "$OUT" ]; then
        echo "No safe-outputs file at $OUT; nothing to gate."
        exit 0
      fi
      ITEM=$(jq -c 'select(.type=="create_issue")' "$OUT" | head -n1)
      if [ -z "$ITEM" ]; then
        echo "Tutorial validation reported no failure; run passes."
        exit 0
      fi
      TITLE=$(printf '%s' "$ITEM" | jq -r '.title // "Tutorial failure"')
      BODY=$(printf '%s' "$ITEM" | jq -r '.body // ""')
      {
        echo "## ❌ ${TITLE}"
        echo
        echo "$BODY"
      } >> "$GITHUB_STEP_SUMMARY"
      # Keep the plain-text job log readable: short annotation plus a pointer to
      # the rendered report; fold the Markdown body into a collapsible group.
      echo "::error::${TITLE} — tutorial validation failed. See the run Summary for the full report."
      echo "::group::Full tutorial validation report (Markdown)"
      printf '%s\n' "$BODY"
      echo "::endgroup::"
      exit 1
---

# Test the repository tutorial

You are a tutorial-testing agent. Your job is to find the tutorial in this
repository, understand what it requires, execute every step on the runner,
and report the outcome.

Work through the phases below **in order**.

**IMPORTANT — Runner environment**: You are executing directly on an ephemeral
`ubuntu-latest` GitHub Actions runner with the AWF sandbox disabled. The
following are true about your environment:

- You have a normal user shell with full `sudo` access.
- `snap` and `apt` are available and fully functional. Use them to install
  any prerequisites the tutorial requires.
- You do not need nested virtualisation. Run tutorial commands directly on
  this runner — it is already an isolated, disposable environment.
- If a tutorial lists Multipass as a prerequisite, ignore it. Multipass is
  infrastructure for the workflow author, not a tutorial dependency for you.

---

## Phase 1 — Select the tutorial

Determine which tutorial file to execute from the config. The tutorial may be
written in Markdown (`.md`) or reStructuredText (`.rst`). Treat both formats
equally.

**Step 1 — Read the config**: Read `docs-testing.config.yml`. Find the
`tutorial-validation` test entry in the `tests:` list. Its `targets` field is a
list of glob patterns naming the tutorial file(s); its optional `exclude` field
lists globs to remove from that set. Expand the `targets` globs, subtract any
`exclude` globs, and take the **first** matching file in document order —
validation executes one tutorial end to end, so only the first in-scope file is
used. The config is the single source of truth: do not guess a path when it
names none.

**Step 2 — Verify the file exists**: Run `ls -la` on the resolved path to
confirm the file is present.

**Step 3 — Give up if nothing is in scope**: If the config file is missing, the
`tutorial-validation` entry is absent, its `targets` list is empty, or no file
matches after applying `exclude`, call the `noop` tool with the message
`"No tutorial configured in docs-testing.config.yml — nothing to validate."`
and stop. Do not fall back to auto-discovery.

Read the tutorial file in full before proceeding.

---

## Phase 2 — Analyse the tutorial

Extract the information needed to set up the environment and run the tutorial.

### 2a. Identify executable commands

Scan every code block in the tutorial. The tutorial may use Markdown fenced
blocks or reStructuredText `.. code-block::` directives. A block is
**executable** when any of the following are true:

- Its language hint is `bash`, `sh`, `shell`, or `console`.
  - Markdown: ` ```bash ` or ` ```console `
  - reStructuredText: `.. code-block:: bash` or `.. code:: shell`
- It has no language hint **and** its lines begin with a `$` or `#` prompt
  character (strip the prompt before execution).
- It has no language hint and the surrounding prose clearly introduces it as
  a command to run (e.g., "Run the following:", "Execute:").

A block is **output-only** (skip it) when:

- Its language hint is a non-shell language (e.g., `yaml`, `json`, `python`,
  `text`).
- Every line lacks a prompt character and the surrounding prose presents it
  as expected output (e.g., "You should see:", "The output will be:").

Collect the executable blocks in document order.

### 2b. Identify prerequisites

Look for prerequisite information in the tutorial:

- Sections titled "Prerequisites", "Requirements", "What you'll need",
  "Before you begin", or similar.
- Explicit installation commands (e.g., `sudo snap install`, `apt install`,
  `pip install`).
- Tool names mentioned as requirements (e.g., Juju, MicroK8s, Docker,
  Node.js).

Merge any prerequisites listed in the `tutorial-validation` test entry's
`prerequisites` field (if present) in `docs-testing.config.yml` with those
discovered from the tutorial. Deduplicate.

**Filter infrastructure tools**: Remove the following from the merged
prerequisite list. These are workflow infrastructure, not tutorial
dependencies, and MUST NOT be installed by you:

- `multipass`, `multipassd`, or any Multipass-related package
- `virtualbox`, `qemu`, `libvirt`, `lxd` (hypervisors / VM managers)

### 2c. Identify cleanup sections

Locate any final section whose heading contains words like "Clean up",
"Teardown", "Remove", or "Destroy". Mark those sections to be **skipped**
during execution — the runner is ephemeral and will be torn down separately.

---

## Phase 3 — Set up the environment

This runner is an ephemeral `ubuntu-latest` GitHub Actions runner with the
AWF sandbox disabled. No nested virtualisation is needed. Run all commands
directly on the runner.

You have full `sudo`, `snap`, and `apt` access. Use them to install
prerequisites.

### Install prerequisites

Install every prerequisite identified in Phase 2b directly on this runner.
If a prerequisite requires installation commands that were already extracted
as tutorial steps, you may execute them here as part of setup — but still
record them as executed steps.

If any prerequisite fails to install, **record it as a failure** (do not
silently skip it) and continue with the remaining prerequisites.

---

## Phase 4 — Execute the tutorial

Run each executable command from Phase 2a **in document order** directly
on the runner.

### Execution rules

- For each command: capture the exact command string, exit status, and a
  trimmed excerpt of stdout/stderr (last ~40 lines is enough).
- On a step failure, do **not** abort — record the failure and continue with
  the remaining steps so the report captures every problem in one run.
- Skip the cleanup sections identified in Phase 2c.
- If a command appears stuck for an unexpectedly long time, note this in
  your report. There is no per-command timeout; the overall workflow timeout
  (60 minutes) is the safety net.
- Do not modify any repository file.
- **Record pivots**: You may correct, adapt, or otherwise deviate from a
  command exactly as written in the tutorial (e.g., fixing a typo, changing
  a flag, substituting a package name, working around a bug) in order to
  keep making progress. Whenever you do this, log a pivot entry containing
  the original command as written in the tutorial, the command you actually
  executed, and a short reason for the change. This applies even when the
  tutorial step ultimately succeeds — a pivot is a deviation worth
  reporting regardless of the outcome, since it likely indicates a bug or
  ambiguity in the tutorial itself.

---

## Phase 5 — Report the outcome

You **MUST** call exactly one safe output.

### All steps succeeded

Call the `noop` tool with a message containing:

1. A one-line summary, e.g.
   `"Tutorial completed successfully — no action needed."`
2. An **Execution pivots** section listing every pivot recorded in Phase 4
   (original command, executed command, reason), or the text `"None"` if no
   pivots were needed.

Do not create an issue.

### One or more steps failed

Call the `create_issue` tool **once** with:

- `title`: `Tutorial failure on run ${{ github.run_id }}`
- `body`: a Markdown report containing:
  1. **Run metadata**: date, workflow run URL
     (`${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`),
     discovered tutorial path, resolved prerequisites.
  2. **Overall status**: `failure` with a one-line summary.
  3. **Per-step results**: one section per tutorial step containing the
     command, exit status, and trimmed evidence.
  4. **Root cause hypothesis**: for each failed step, a short analysis.
  5. **Follow-ups**: anything that blocked the tutorial or would improve it.
  6. **Execution pivots**: every pivot recorded in Phase 4 (original
     command, executed command, reason), or the text `"None"` if no pivots
     were needed. Call out any pivot that may indicate a bug in the
     tutorial itself.

Only one safe output call is expected per run.

---

## Phase 6 — Teardown

No teardown is needed — this runner is ephemeral and will be destroyed by
the CI platform after the workflow completes. You may skip this phase.