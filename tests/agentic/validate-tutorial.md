---
description: >
  Repository-agnostic tutorial validator. Discovers the tutorial file,
  analyses prerequisites, executes every step in a fresh Multipass VM,
  and opens a GitHub issue if any step fails.
on:
  workflow_dispatch:
  schedule:
    # Weekly, Monday 06:00 UTC
    - cron: "0 6 * * 1"

permissions:
  contents: read

engine: claude

runs-on: [self-hosted, linux, edge]
timeout-minutes: 60

# Optional hints — the agent falls back to runtime discovery when omitted.
# config:
#   tutorial-path: docs/tutorial.md
#   vm-cpus: 4
#   vm-memory: 8G
#   vm-disk: 50G
#   vm-image: "24.04"
#   prerequisites:
#     - juju
#     - microk8s

tools:
  bash:
    - "multipass:*"
    - "cat"
    - "find"
    - "ls"
    - "sed"
    - "awk"
    - "grep"
    - "head"
    - "tail"
    - "wc"
    - "date"
  edit:

safe-outputs:
  create-issue:
    title-prefix: "[tutorial-failure] "
    labels: [tutorial, automation, bug]
    max: 1
    deduplicate-by-title: 1
---

# Validate the repository tutorial

You are a tutorial-validation agent. Your job is to find the tutorial in this
repository, understand what it requires, execute every step inside an isolated
Multipass VM, and report the outcome.

Work through the phases below **in order**.

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

### 2c. Identify resource requirements

Check whether the tutorial states minimum hardware requirements (CPU, RAM,
disk). If the tutorial specifies values **higher** than the defaults
(4 CPUs / 8 GB RAM / 50 GB disk), use the tutorial's values. Otherwise keep
the defaults. Override with any explicit `config.vm-*` values.

### 2d. Identify cleanup sections

Locate any final section whose heading contains words like "Clean up",
"Teardown", "Remove", or "Destroy". Mark those sections to be **skipped**
during execution — the VM is torn down separately.

---

## Phase 3 — Set up the environment

Create an ephemeral Multipass VM so the self-hosted runner stays clean.
Use the resource values determined in Phase 2c and the VM image from
`config.vm-image` (default `24.04`).

```
multipass launch <vm-image> --name tutorial-vm-${{ github.run_id }} \
  --cpus <cpus> --memory <memory> --disk <disk>
```

Run **every** subsequent command inside the VM using:

```
multipass exec tutorial-vm-${{ github.run_id }} -- bash -lc "<command>"
```

Do **not** run tutorial commands directly on the runner host.

### Install prerequisites

Install every prerequisite identified in Phase 2b inside the VM. If a
prerequisite requires installation commands that were already extracted as
tutorial steps, you may execute them here as part of setup — but still
record them as executed steps.

If any prerequisite fails to install, **record it as a failure** (do not
silently skip it) and continue with the remaining prerequisites.

---

## Phase 4 — Execute the tutorial

Run each executable command from Phase 2a **in document order** inside the
VM.

### Execution rules

- For each command: capture the exact command string, exit status, and a
  trimmed excerpt of stdout/stderr (last ~40 lines is enough).
- On a step failure, do **not** abort — record the failure and continue with
  the remaining steps so the report captures every problem in one run.
- Skip the cleanup sections identified in Phase 2d.
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
     VM name, VM image, Multipass version, discovered tutorial path,
     resolved prerequisites.
  2. **Overall status**: `failure` with a one-line summary.
  3. **Per-step results**: one section per tutorial step containing the
     command, exit status, and trimmed evidence.
  4. **Root cause hypothesis**: for each failed step, a short analysis.
  5. **Follow-ups**: anything that blocked the tutorial or would improve it.

Only one safe output call is expected per run.

---

## Phase 6 — Teardown

After you have called either `noop` or `create_issue`, delete the VM:

```
multipass delete --purge tutorial-vm-${{ github.run_id }}
```

Failure to reach the teardown step is acceptable — a follow-up cleanup step
outside the agent handles orphaned VMs.
