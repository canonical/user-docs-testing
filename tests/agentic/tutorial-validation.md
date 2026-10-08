# Tutorial validation

A shipped agentic test. It selects the tutorial from `docs-testing.config.yml`,
installs its prerequisites, executes every step on the runner, and reports the
outcome. Because it runs tutorial commands with full privileges, it ships as its own
dedicated workflow rather than inside the shared read-only documentation run — the
workflow that imports these instructions provides the privileged runner, the network
allowlist, and the safety pre-flight.

Work through the phases below **in order**.

**IMPORTANT — Runner environment**: You are executing directly on an ephemeral
`ubuntu-latest` GitHub Actions runner with the AWF sandbox disabled:

- You have a normal user shell with full `sudo` access, and `snap` and `apt` work.
  Use them to install any prerequisites the tutorial requires.
- You do not need nested virtualisation. Run tutorial commands directly on this
  runner — it is already isolated and disposable.
- If a tutorial lists Multipass as a prerequisite, ignore it. Multipass is
  infrastructure for the workflow author, not a tutorial dependency for you.

---

## Phase 1 — Select the tutorial

**Step 1 — Read the config**: Read `docs-testing.config.yml`. Find the
`tutorial-validation` test entry in the `tests:` list. Its `targets` field is a list of
glob patterns naming the tutorial file(s); its optional `exclude` field lists globs to
remove. Expand the `targets` globs, subtract any `exclude` globs, and take the **first**
matching file in document order — validation executes one tutorial end to end, so only
the first in-scope file is used. The config is the single source of truth: do not guess
a path when it names none. A tutorial may be Markdown (`.md`) or reStructuredText
(`.rst`); treat both equally.

**Step 2 — Verify the file exists**: Run `ls -la` on the resolved path.

**Step 3 — Give up if nothing is in scope**: If the config file is missing, the
`tutorial-validation` entry is absent, its `targets` list is empty, or no file matches
after applying `exclude`, emit a single `create_check_run` with conclusion `neutral`
(per `reporting.on_incomplete_coverage`, default `neutral`) whose body states
`"No tutorial configured in docs-testing.config.yml — nothing to validate."` and stop.
Do not fall back to auto-discovery.

Read the tutorial file in full before proceeding.

---

## Phase 2 — Analyse the tutorial

### 2a. Identify executable commands

Scan every code block. A block is **executable** when any of the following are true:

- Its language hint is `bash`, `sh`, `shell`, or `console` (Markdown ` ```bash `, or
  reStructuredText `.. code-block:: bash`).
- It has no language hint **and** its lines begin with a `$` or `#` prompt (strip the
  prompt before execution).
- It has no language hint and the surrounding prose introduces it as a command to run
  ("Run the following:", "Execute:").

A block is **output-only** (skip it) when its language hint is a non-shell language
(`yaml`, `json`, `python`, `text`), or every line lacks a prompt and the prose presents
it as expected output ("You should see:").

Collect the executable blocks in document order.

### 2b. Identify prerequisites

Look for a "Prerequisites", "Requirements", "What you'll need", or "Before you begin"
section, explicit installation commands (`sudo snap install`, `apt install`,
`pip install`), and tool names mentioned as requirements. Merge these with the
`prerequisites` field from the `tutorial-validation` test entry, and deduplicate.

**Filter infrastructure tools**: Remove the following from the merged list. They are
workflow infrastructure, not tutorial dependencies, and MUST NOT be installed by you:
`multipass`, `virtualbox`, `qemu`, `libvirt`, `lxd`.

### 2c. Identify cleanup sections

Locate any final section whose heading contains words like "Clean up", "Teardown",
"Remove", or "Destroy". Mark those sections to be **skipped** during execution — the
runner is ephemeral and is torn down separately.

---

## Phase 3 — Set up the environment

Run all commands directly on the runner; no nested virtualisation is needed. Install
every prerequisite identified in Phase 2b. If a prerequisite's installation commands
were already extracted as tutorial steps, you may run them here, but still record them
as executed steps. If any prerequisite fails to install, **record it as a failure** (do
not silently skip it) and continue with the rest.

---

## Phase 4 — Execute the tutorial

Run each executable command from Phase 2a **in document order** directly on the runner.

- For each command: capture the exact command string, exit status, and a trimmed
  excerpt of stdout/stderr (last ~40 lines).
- On a step failure, do **not** abort — record the failure and continue so the report
  captures every problem in one run.
- Skip the cleanup sections identified in Phase 2c.
- There is no per-command timeout; the overall workflow timeout is the safety net. Note
  any command that appears stuck.
- Do not modify any repository file.
- **Record pivots**: whenever you correct, adapt, or deviate from a command as written
  (fix a typo, change a flag, substitute a package) to keep making progress, log a pivot
  entry with the original command, the command you executed, and a short reason — even
  when the step ultimately succeeds, since a pivot likely signals a bug or ambiguity in
  the tutorial.

---

## Phase 5 — Report the outcome

You **MUST** emit exactly one `create_check_run`. Never call `noop` and never create an
issue — even a clean run must produce a check run so CI has a record. The check-run
conclusion is mirrored onto the workflow run's exit status: a `failure` conclusion fails
the run.

### Choosing the conclusion

Choose the conclusion in this order — the outcomes must stay distinct:

1. **`failure`** — one or more tutorial steps failed (or a prerequisite failed to
   install). This gates CI.
2. **`neutral`** — no tutorial was in scope or the tutorial could not be run at all
   (see Phase 1 Step 3). Never report `success` in this case.
3. **`success`** — every executable step ran to completion with a successful exit
   status.

### All steps succeeded

Emit a `create_check_run` with conclusion `success`. Its body must contain a one-line
summary ("Tutorial completed successfully — no action needed.") and an **Execution
pivots** section listing every pivot from Phase 4, or `"None"`.

### One or more steps failed

Emit a `create_check_run` with conclusion `failure`, `title` set to
`Tutorial failure on run ${{ github.run_id }}`, and a Markdown report in `text`:

1. **Run metadata**: date, workflow run URL, discovered tutorial path, resolved
   prerequisites.
2. **Overall status**: `failure` with a one-line summary.
3. **Per-step results**: one section per step with the command, exit status, and
   trimmed evidence.
4. **Root cause hypothesis**: for each failed step, a short analysis.
5. **Follow-ups**: anything that blocked the tutorial or would improve it.
6. **Execution pivots**: every pivot from Phase 4, or `"None"`. Call out any pivot that
   may indicate a bug in the tutorial.

Only one `create_check_run` call is expected per run.

---

## Phase 6 — Teardown

No teardown is needed — this runner is ephemeral and is destroyed after the workflow
completes. Skip this phase.
