# How to test tutorials

This project ships two tutorial checks. They are complementary, and they run in
different places:

| Test | What it does | Where it runs |
| ---- | ------------ | ------------- |
| `tutorial-review` | Reads a tutorial and reports security risks, prerequisite gaps, and structural issues. Runs **nothing**. | Inside the unified `docs-testing.md` run, reporting into the one check run. |
| `tutorial-validation` | Installs prerequisites and **executes** every step on a runner, then reports whether it ran clean. | Its own installable workflow, `validate-tutorial.md`. |

Enable `tutorial-review` everywhere; add `tutorial-validation` where a runner can
actually execute the steps.

## Configure the tests

Both are built-ins, selected with `uses:` like any shipped review. Point `targets` at
your tutorial file(s):

```yaml
version: 1

tests:
  # Static review — folds into the unified documentation run.
  - name: tutorial-review
    uses: tutorial-review
    targets:
      - "docs/tutorial/**/*.md"

  # Execution — runs in its own privileged workflow. The first matched file is
  # the one executed end to end.
  - name: tutorial-validation
    uses: tutorial-validation
    targets:
      - "docs/tutorial/getting-started.md"
    # Tools the tutorial assumes you already have; merged with the ones the test
    # discovers in the tutorial itself.
    prerequisites:
      - juju
      - microk8s
```

A tutorial may be Markdown (`.md`) or reStructuredText (`.rst`); both are treated
equally. Run `docs-testing validate` after editing the configuration.

## Install the workflows

`tutorial-review` needs nothing beyond the main documentation workflow — it is imported
by `docs-testing.md`:

```
gh aw add canonical/user-docs-testing/workflows/docs-testing.md
```

`tutorial-validation` executes the tutorial with `sudo`, `snap`, and `apt` on an
ephemeral runner with the agent sandbox disabled, so it ships as a separate workflow:

```
gh aw add canonical/user-docs-testing/workflows/validate-tutorial.md
```

That workflow carries a destructive-command pre-flight (it refuses tutorials containing
patterns like `rm -rf /` or `mkfs`), a network allowlist, and a 60-minute timeout. It
mirrors the agent's check-run conclusion onto the run's exit status, so a failing
tutorial gates CI.

## How results are reported

- `tutorial-review` contributes findings and coverage to the single "Docs Testing" check
  run, in its own clearly-labelled section. It classifies each tutorial file into the
  usual [coverage states](../reference/results.md#coverage): a clean tutorial is
  `reviewed-and-supported`, one with issues is `reviewed-with-conflicting-evidence`, and
  a listed file that is missing is `blocked-required-source-unavailable`.
- `tutorial-validation` publishes its own "Tutorial validation" check run with a
  per-step report. It does not use `results/all.json`.

## Severity and gating

`tutorial-review` marks a command a reader could copy to real harm (unjustified
`sudo`/`--trust`/`--classic`, a plaintext secret, `curl | sh`, world-writable
permissions, or a service bound to `0.0.0.0`) as `error`; everything else — prerequisite
gaps, structural issues, commands with no risk — is a `warning`. Whether an `error`
blocks the run follows `reporting.fail_on_findings`, like any other finding.

`tutorial-validation` concludes `failure` if any step (or prerequisite install) fails,
`success` if every step runs clean, and `neutral` if no tutorial was in scope.

## Notes

- Infrastructure tools — `multipass`, `virtualbox`, `qemu`, `libvirt`, `lxd` — are the
  workflow author's concern, not tutorial dependencies. Neither test treats them as
  gaps, and `tutorial-validation` will not install them.
- Cleanup sections ("Clean up", "Teardown", "Remove", "Destroy") are skipped during
  execution: the runner is ephemeral and is torn down separately.
