---
description: >
  Repository-agnostic tutorial reviewer. Discovers the tutorial file,
  analyses it for security risks, prerequisite completeness, and
  structural quality issues, then opens a GitHub issue with findings.
on:
  workflow_dispatch:
#  schedule:
    # Weekly, Monday 06:00 UTC
#    - cron: "0 6 * * 1"

permissions:
  contents: read

model: gpt-5
engine: 
  id: copilot

runs-on: [ubuntu-latest]
timeout-minutes: 15

env:
  TUTORIAL_PATH: "docs/tutorial/tutorial.md" 

strict: false

max-ai-credits: 20

# Optional hints — the agent falls back to runtime discovery when omitted.
# config:
#   tutorial-path: docs/tutorial.md  # or docs/tutorial.rst
#   prerequisites:
#     - juju
#     - microk8s

tools:
  bash: [":*"]
  edit:

safe-outputs:
  create-issue:
    title-prefix: "[tutorial-review] "
    labels: [tutorial, review, automation]
    max: 1
    deduplicate-by-title: 1
---

# Review the repository tutorial

You are a tutorial-review agent. Your job is to find the tutorial in this
repository, analyse it for security risks, prerequisite gaps, and structural
quality issues, then report your findings. You do **not** execute any
tutorial commands — this is a static analysis only.

Work through the phases below **in order**.

---

## Phase 1 — Discover the tutorial

Locate the tutorial file to review. The tutorial may be written in Markdown
(`.md`) or reStructuredText (`.rst`). Treat both formats equally.

**Step 1 — Read the environment variable**: Run `echo "$TUTORIAL_PATH"` to
get the configured tutorial path. This is the **primary** source of truth.
If the output is a non-empty file path, use it directly. Do not fall back
to auto-discovery unless the file genuinely does not exist at that path.

**Step 2 — Check the config override**: If a `tutorial-path` value is
provided in the `config` block above, it takes precedence over
`TUTORIAL_PATH`. Use that path instead.

**Step 3 — Verify the file exists**: Run `ls -la` on the resolved path to
confirm the file is present. If it exists, proceed to read it.

**Step 4 — Auto-discovery (last resort)**: Only if the resolved path does
not exist, search the repository in the following order and use the
**first match**:
- `docs/tutorial.md` or `docs/tutorial.rst`
- `TUTORIAL.md` or `TUTORIAL.rst`
- `docs/tutorials/` (if the directory exists, pick the primary file — an
  `index.md`, `index.rst`, or the only `.md`/`.rst` file present)
- `README.md` or `README.rst` — only if it contains a heading whose text
  includes the word "Tutorial" (e.g., `## Tutorial`, `# Quick-start tutorial`).
  Extract only that section and its subsections.

**Step 5 — Give up if nothing found**: If no tutorial is found after all
of the above, call the `noop` tool with the message
`"No tutorial found in repository — nothing to review."` and stop.

Read the discovered file in full before proceeding.

---

## Phase 2 — Analyse the tutorial

Extract the information needed to perform a thorough review.

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

### 2b. Identify stated prerequisites

Look for prerequisite information in the tutorial:

- Sections titled "Prerequisites", "Requirements", "What you'll need",
  "Before you begin", or similar.
- Explicit installation commands (e.g., `sudo snap install`, `apt install`,
  `pip install`).
- Tool names mentioned as requirements (e.g., Juju, MicroK8s, Docker,
  Node.js).

Merge any prerequisites listed in the `config.prerequisites` block above
with those discovered from the tutorial. Deduplicate.

**Check for empty or missing prerequisite sections**: If the tutorial has a
prerequisites heading but no substantive content beneath it (e.g., the next
heading follows immediately), flag this as a structural issue. If the
tutorial has no prerequisites section at all, flag this as a missing
expected section (see 2e).

**Filter infrastructure tools**: The following are workflow infrastructure,
not tutorial dependencies, and should be noted as such:

- `multipass`, `multipassd`, or any Multipass-related package
- `virtualbox`, `qemu`, `libvirt`, `lxd` (hypervisors / VM managers)

### 2c. Security analysis of executable commands

For **every** executable command collected in 2a (including prerequisite
installation commands), perform a security-focused review. For each command,
determine:

- **Risk**: Does the command carry a security-related risk? Consider things
  like: elevated-privilege flags (`--trust`, `--classic`, `sudo`), broad
  network exposure (binding to `0.0.0.0`, opening ports, disabling TLS
  verification), secrets or credentials appearing in plaintext (in the
  command itself, in a heredoc, or written to a file), piping remote content
  directly into a shell (`curl | sh`), overly permissive file or process
  permissions (`chmod 777`, running services as root unnecessarily), and use
  of deprecated or known-insecure flags/APIs.
- **Best-practice alternative**: If a risk is present, identify a safer or
  more idiomatic alternative the tutorial could use instead. If the command
  is a reasonable and necessary use of an elevated capability (e.g., a charm
  genuinely requires `--trust` to function), say so explicitly rather than
  recommending removal — the goal is a realistic, actionable suggestion, not
  a blanket objection.
- If a command carries no meaningful security risk, record that explicitly
  (e.g., "no risk identified") rather than omitting it — the report
  should account for every command reviewed, not just the risky ones.

Keep a structured record of each command alongside its risk assessment and
recommendation (if any).

### 2d. Prerequisite completeness check

Cross-reference the executable commands from 2a against the stated
prerequisites from 2b. Flag the following gaps:

- **Unlisted tool dependency**: A command uses a tool, package, or service
  that is not mentioned in the prerequisites (e.g., `juju deploy` appears
  but Juju is not listed as a prerequisite).
- **Unlisted service dependency**: A command requires a running service that
  is not set up in the prerequisites (e.g., `microk8s enable dns` but
  MicroK8s installation is not listed).
- **Missing file/resource prerequisite**: A command references a file or
  resource that is not created by any prior step or prerequisite (e.g.,
  `cat config.yaml` but no step creates `config.yaml`).
- **Dead prerequisite**: A prerequisite is stated but never used by any
  command in the tutorial. Flag these as potentially unnecessary cruft.

For each gap, record the command that triggered it, the missing or dead
prerequisite, and a suggested fix.

### 2e. Structural quality checks

Inspect the tutorial for the following structural issues:

- **Broken or suspicious links**: Check any URLs in the tutorial. For each
  URL, note if it uses `http://` (instead of `https://`), points to a
  known-deprecated domain, or appears malformed.
- **Missing cleanup section**: If the tutorial instructs the reader to
  create resources (deploys services, creates files, starts processes) but
  has no section whose heading contains words like "Clean up", "Teardown",
  "Remove", or "Destroy", flag this. Readers need to know how to undo what
  they did.
- **Inconsistent terminology**: Flag cases where the same concept is
  referred to by different names (e.g., "MicroK8s" vs "microk8s" vs
  "Microk8s", or "Juju" vs "juju" used interchangeably in prose). Note the
  location and the variants found.
- **Ambiguous or imprecise instructions**: Flag vague instructions that
  leave the reader guessing. Examples: "wait a few minutes" without a
  concrete check command, "configure as needed" without specifics, "you may
  need to..." without a way to determine whether the step applies.
- **Missing expected sections**: Flag if the tutorial lacks any of these
  common structural elements:
  - An introduction or overview paragraph (the reader should know what
    they'll accomplish)
  - A prerequisites section (the reader should know what they need before
    starting)
  - A "Next steps" or "Where to go from here" section (the reader should
    know what to do after completing the tutorial)

Record each finding with its location in the tutorial and a suggested fix.

---

## Phase 3 — Report the outcome

You **MUST** call exactly one safe output.

### No issues found

Call the `noop` tool with a message containing:

1. A one-line summary:
   `"Tutorial review complete — no issues found."`
2. Summary counts: number of commands reviewed for security, number of
   prerequisites checked, number of structural checks performed.

Do not create an issue.

### Issues found

Call the `create_issue` tool **once** with:

- `title`: `Tutorial review findings on run ${{ github.run_id }}`
- `body`: a Markdown report containing:

  1. **Run metadata**: date, workflow run URL
     (`${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`),
     discovered tutorial path.

  2. **Overall status**: `review-complete` with a summary of issue counts
     by category (e.g., "3 security findings, 2 prerequisite gaps, 1
     structural issue").

  3. **Security analysis** (from 2c): for every executable command
     reviewed, include the command, its risk assessment, and any
     best-practice alternative. Group by severity: commands with risks
     first, then commands with no risk identified.

  4. **Prerequisite gaps** (from 2d): each gap with the command that
     triggered it, the missing or dead prerequisite, and a suggested fix.

  5. **Structural issues** (from 2e): each issue with its location in the
     tutorial and a suggested fix. Group by subcategory (broken links,
     missing cleanup, inconsistent terminology, ambiguous instructions,
     missing sections).

  6. **Summary table**: a table of all findings with columns for category,
     severity (use `warning` for all findings — this is a review, not a
     test failure), location, and a one-line description.

Only one safe output call is expected per run.