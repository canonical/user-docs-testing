# Tutorial review

A shipped agentic test. It reviews a tutorial statically — it does **not** execute
any command — and reports security risks, prerequisite gaps, and structural quality
issues. It runs inside the unified documentation-testing run, so it contributes its
findings to the single check run the workflow produces rather than concluding on its
own.

Where `tutorial-validation` proves a tutorial *runs*, this test reads a tutorial and
judges whether it is *safe and complete* without running anything. The two are
companions: enable this one everywhere, and add validation where a runner can execute
the steps.

## Inputs

- The documentation repository is checked out at the workspace root. A tutorial may
  be written in Markdown (`.md`) or reStructuredText (`.rst`); treat both equally.
- `docs-testing.config.yml` provides this test's entry: `targets` / `exclude` scope
  the tutorial file(s), and an optional `prerequisites` list names tools the author
  considers assumed knowledge.
- Deterministic findings, if any, are in `results/all.json`.

## Scope

Your scope is this test's entry in `plan.agentic_tests[].files` in `results/all.json`:
the in-scope tutorial files, already expanded from `targets` minus `exclude`. Use that
list rather than expanding the globs yourself, and give **every** file on it a coverage
state. A listed file that does not exist is a coverage gap for that path, not a silent
omission.

Read each in-scope tutorial in full before reviewing it.

## Procedure

Work through each in-scope tutorial.

### 1. Identify executable commands

Scan every code block. A block is **executable** when any of the following are true:

- Its language hint is `bash`, `sh`, `shell`, or `console` (Markdown ` ```bash `, or
  reStructuredText `.. code-block:: bash`).
- It has no language hint **and** its lines begin with a `$` or `#` prompt.
- It has no language hint and the surrounding prose introduces it as a command to run
  ("Run the following:", "Execute:").

A block is **output-only** (skip it) when its language hint is a non-shell language
(`yaml`, `json`, `python`, `text`), or every line lacks a prompt and the prose presents
it as expected output ("You should see:").

Collect the executable blocks in document order.

### 2. Identify stated prerequisites

Look for a "Prerequisites", "Requirements", "What you'll need", or "Before you begin"
section, explicit installation commands (`sudo snap install`, `apt install`,
`pip install`), and tool names mentioned as requirements. Merge these with the
`prerequisites` field from this test's config entry, and deduplicate.

Treat these as workflow infrastructure, not tutorial dependencies, and do not count
them as gaps: `multipass`, `virtualbox`, `qemu`, `libvirt`, `lxd`.

### 3. Security analysis

For every executable command, judge whether it carries a security-related risk:
elevated-privilege flags (`--trust`, `--classic`, `sudo`), broad network exposure
(binding to `0.0.0.0`, disabling TLS verification), plaintext secrets, piping remote
content into a shell (`curl | sh`), overly permissive permissions (`chmod 777`), or
deprecated/insecure flags. When a risk is present, name a safer alternative — or, if an
elevated capability is genuinely required (a charm that needs `--trust`), say so rather
than objecting. Account for every command, including those with no risk.

### 4. Prerequisite completeness

Cross-reference the executable commands against the stated prerequisites and flag:
an **unlisted tool** a command uses, an **unlisted service** a command requires, a
**missing file/resource** no prior step creates, or a **dead prerequisite** stated but
never used.

### 5. Structural quality

Flag: `http://` or malformed links; a **missing cleanup section** when the tutorial
creates resources; **inconsistent terminology** for the same concept; **ambiguous
instructions** ("wait a few minutes" with no check); and **missing expected sections**
(introduction, prerequisites, next steps).

## Output

Contribute your findings to the single check run produced by the workflow. Do **not**
emit a check run of your own, and do not choose the run's conclusion — the workflow does
that from the findings you report.

Classify every in-scope tutorial file into exactly one coverage state (see
[the results schema](../../docs/reference/results.md)); for this test they mean:

- **reviewed-and-supported** — reviewed in full; no issues of any severity.
- **reviewed-with-conflicting-evidence** — reviewed, and at least one issue was found
  (one finding per issue).
- **skipped-by-policy** — excluded by `exclude` or the `generated` policy.
- **blocked-required-source-unavailable** — a listed target file does not exist, so it
  could not be read.

`unsupported-by-configured-sources` does not apply: a tutorial is judged against itself,
not against a source of truth.

Give every finding a `severity`:

- `error` — a command a reader could copy to real harm: unjustified elevated privilege,
  a plaintext secret, `curl | sh`, world-writable permissions, or a service bound to
  `0.0.0.0` with no warning.
- `warning` — everything else: prerequisite gaps, structural issues, and commands with
  no security risk identified. A command that genuinely needs an elevated capability is
  still a `warning`, with the justification noted.

Report the findings grouped by tutorial file, as a table with short cells (severity,
location, one-line summary), and put the evidence under it as a list. Keep URLs, pipes,
and line breaks out of cells. Never paste a URL as evidence — describe its scheme, host,
and path in words, outside backticks. Note the surface you reviewed (how many commands,
which sections) so a reader can gauge how much was checked, and list any blocked file
separately.
