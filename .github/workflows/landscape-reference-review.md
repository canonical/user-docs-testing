---
# Run the shipped reference-review test against the REAL Landscape reference
# documentation, using examples/landscape/docs-testing.config.yml.
#
# This is the proving-ground run. It uses Landscape as the test project, exactly
# as intended — the tool itself stays product-agnostic.
#
# SECRET REQUIRED for full coverage: SOURCE_REPO_TOKEN, a canonical-owned
# fine-grained PAT with Contents: Read on canonical/landscape-server,
# SSO-authorized for the canonical org. This is the same secret name already used
# by YanisaHS/user-docs-testing-example-project. Without it the server checkout
# fails and every server-owned page is reported as blocked — a valid and useful
# first run, but not a complete review.
#
# SECURITY: workflow_dispatch only. Do NOT add a fork-PR trigger while a private
# source token is configured.
description: >
  Run the reference-review agentic test against the Landscape reference
  documentation and report the result as a Check Run.
on:
  workflow_dispatch:

permissions:
  contents: read

engine: copilot

runs-on: [ubuntu-latest]
timeout-minutes: 45

checkout:
  # This repository: the test instructions and examples/landscape config.
  - current: true

  # The documentation under review (public).
  - repository: canonical/landscape-documentation
    ref: main
    path: landscape-docs

  # Authoritative source, PRIVATE and REQUIRED. If this checkout fails, every
  # server-owned page must be reported as blocked, never as passing.
  - repository: canonical/landscape-server
    ref: main
    path: landscape-sources/landscape-server
    token: ${{ secrets.SOURCE_REPO_TOKEN }}

  # Corroborating source, public and optional.
  - repository: canonical/landscape-client
    ref: main
    path: landscape-sources/landscape-client

# Proof of access, before the agent runs. These steps record which sources were
# really checked out and at which commit, independently of anything the agent
# later claims. The commit SHA in the job log is the audit trail: if the private
# checkout silently failed, it shows up here rather than in a plausible-looking
# report.
steps:
  - name: Set up Python
    uses: actions/setup-python@v5
    with:
      python-version: "3.12"
  - name: Install orchestrator deps
    run: pip install pyyaml
  - name: Record which sources were actually checked out
    run: |
      python3 tests/deterministic/source_manifest.py \
        --config examples/landscape/docs-testing.config.yml \
        --sources-root landscape-sources \
        --output results/source-availability.json
      echo "### Source availability" >> "$GITHUB_STEP_SUMMARY"
      python3 - <<'PY' >> "$GITHUB_STEP_SUMMARY"
      import json
      d = json.load(open("results/source-availability.json"))
      print("| source | available | commit | files |")
      print("| --- | --- | --- | --- |")
      for e in d["source_evidence"]:
          print(f"| `{e['name']}` | {'yes' if e['available'] else '**NO**'} "
                f"| `{(e['commit'] or '-')[:12]}` | {e['files_seen']} |")
      PY
  - name: Upload source evidence
    uses: actions/upload-artifact@v4
    with:
      name: source-availability
      path: results/source-availability.json
      if-no-files-found: warn

tools:
  bash:
    - "cat"
    - "find"
    - "ls"
    - "grep"
    - "sed"
    - "awk"
    - "head"
    - "tail"
    - "wc"

safe-outputs:
  create-check-run:
    name: "Landscape reference review"
    max: 1
---

# Landscape reference review

Run the shipped reference review against the Landscape reference documentation.

## Where everything is

- **Instructions:** `tests/agentic/reference-review.md` in this repository. Read
  it and follow it exactly. Do not add criteria of your own.
- **Config:** `examples/landscape/docs-testing.config.yml`. Read its `sources`
  (and each one's `required` flag), the shared `source_map`, `reporting`, and the
  `reference-review` test entry.
- **Proof of access:** `results/source-availability.json`, already generated. Its
  `source_evidence` list is authoritative about which sources were checked out
  and at which commit. Read it first; it overrides your own impression. Its
  `coverage` entries are established facts — you may not upgrade an area it marks
  blocked.
- **Documentation under review:** `landscape-docs/`. Paths in the config such as
  `docs/reference/config/**` are relative to that directory, so
  `docs/reference/lsctl.md` means `landscape-docs/docs/reference/lsctl.md`.
- **Sources of truth:** `landscape-sources/<name>/`, so where the instructions
  say `sources/landscape-server/` read `landscape-sources/landscape-server/`.

Sources listed in the config with no checkout above (`landscape-server-operator`,
`landscape-ui`) are unavailable. They are `required: false`, so areas that depend
on them are **unsupported**, not blocked.

If `source_evidence` shows `landscape-server` as unavailable, the private
checkout failed. That is an expected outcome when the secret is absent: report
every server-owned area as `blocked-required-source-unavailable`, do not
speculate about server behavior, and do not invent findings to fill the gap.

## Scope for this first run

Reviewing all 40+ reference pages in one pass produces a report nobody can
verify. Restrict this run to the areas below, which are small and have a clearly
identified owner in `source_map`:

- `docs/reference/lsctl.md`
- `docs/reference/config/**`

Report every other in-scope path as `skipped-by-policy` with the note "out of
scope for this run", so the coverage list stays honest about what was checked.

## Output

Emit exactly one `create_check_run`, choosing the conclusion by the rules in the
instruction file. For each finding give the doc file and line, the documented
claim, the conflicting authoritative behavior, and the source location under
`landscape-sources/`. Keep private source content to paths, symbols, and short
paraphrases.

End the summary with an **Evidence** section listing, for each area you reviewed,
the specific source files you opened under `landscape-sources/` — repo-relative
paths only, no contents. If that list is empty for an area, you did not review it
and must report it as blocked instead. This section is what makes the run
auditable: the paths can be checked against the commit recorded in
`source_evidence`.
