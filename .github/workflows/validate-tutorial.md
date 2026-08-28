---
description: >
  Repository-agnostic tutorial validator. Discovers the tutorial file,
  analyses prerequisites, executes every step on the runner, and opens
  a GitHub issue if any step fails.
on:
  workflow_dispatch:
#  schedule:
    # Weekly, Monday 06:00 UTC
#    - cron: "0 6 * * 1"

permissions:
  contents: read
  copilot-requests: write

engine: copilot

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

# Optional hints — the agent falls back to runtime discovery when omitted.
# config:
#   tutorial-path: docs/tutorial.md
#   prerequisites:
#     - juju
#     - microk8s

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
---

# Validate the repository tutorial

You are a tutorial-validation agent. Your job is to find the tutorial in this
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

## Phase 1 — Discover the tutorial

Locate the tutorial file to execute.

1. If a `tutorial-path` value is provided in the `config` block above, use
   that path directly.
2. Otherwise, search the repository in the following order and use the **first
   match**:
   - `docs/tutorial.md`
   - `TUTORIAL.md`
   - `docs/tutorials/` (if the directory exists, pick the primary file — an
     `index.md` or the only `.md` file present)
   - `README.md` — only if it contains a Markdown heading whose text includes
     the word "Tutorial" (e.g., `## Tutorial`, `# Quick-start tutorial`).
     Extract only that section and its subsections.
3. If no tutorial is found, call the `noop` tool with the message
   `"No tutorial found in repository — nothing to validate."` and stop.

Read the discovered file in full before proceeding.

---

## Phase 2 — Analyse the tutorial

Extract the information needed to set up the environment and run the tutorial.

### 2a. Identify executable commands

Scan every fenced code block in the tutorial. A block is **executable** when
any of the following are true:

- Its language hint is `bash`, `sh`, `shell`, or `console`.
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

Merge any prerequisites listed in the `config.prerequisites` block above
with those discovered from the tutorial. Deduplicate.

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

---

## Phase 5 — Report the outcome

You **MUST** call exactly one safe output.

### All steps succeeded

Call the `noop` tool with a message such as:
`"Tutorial completed successfully — no action needed."`

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

Only one safe output call is expected per run.

---

## Phase 6 — Teardown

No teardown is needed — this runner is ephemeral and will be destroyed by
the CI platform after the workflow completes. You may skip this phase.
