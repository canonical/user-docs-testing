# Results schema

Deterministic tests communicate their findings to the tool through a JSON file.
The [orchestrator](run_tests.py) reads each test's `results_file`, tags every
finding with the test's name, and merges them into one combined report that the
workflow uses for CI status and de-duplication against agentic findings.

Any deterministic test — in any language — is compatible as long as it writes a
file in this shape.

## Per-test results file

A test writes an object like this to the path named by its `results_file`:

```json
{
  "tool": "my-check",
  "schema_version": 1,
  "summary": {
    "checks_run": 1,
    "files_checked": 42,
    "findings": 1,
    "status": "fail"
  },
  "findings": [
    {
      "check": "broken-relative-link",
      "severity": "error",
      "doc_file": "reference/cli.md",
      "doc_line": 87,
      "source": null,
      "source_ref": null,
      "message": "Link target 'options.md' does not exist.",
      "covered_topic": "reference/cli.md#options"
    }
  ]
}
```

Only `findings` is strictly required by the orchestrator; the rest is
recommended for standalone runs and debugging.

## Finding fields

| Field           | Required | Description                                                                                 |
| --------------- | -------- | ------------------------------------------------------------------------------------------- |
| `check`         | yes      | Identifier of the specific check that produced the finding.                                 |
| `severity`      | yes      | `error` (fails CI) or `warning` (reported, does not fail).                                   |
| `doc_file`      | yes      | Documentation file the finding is about (repo-relative).                                     |
| `doc_line`      | no       | 1-based line number, if applicable.                                                         |
| `source`        | no       | Name of the source of truth involved, if any.                                               |
| `source_ref`    | no       | Location within the source (path, symbol, line), if any.                                     |
| `message`       | yes      | Human-readable description of the problem.                                                   |
| `covered_topic` | no       | Stable identifier of what this finding covers. Agentic tests skip topics already listed here to avoid duplicate reports. |

The orchestrator adds a `test` field to each finding automatically (the name of
the test that produced it); tests do not need to set it.

## Combined results file

The orchestrator writes a merged file (default `results/all.json`):

```json
{
  "tool": "user-docs-testing",
  "schema_version": 1,
  "summary": {
    "tests_run": 2,
    "findings": 1,
    "status": "fail"
  },
  "findings": [ /* every test's findings, each tagged with "test" */ ]
}
```

`summary.status` is `fail` if any finding has `severity: error`, otherwise
`pass`.

## Coverage status vocabulary

A pass/fail status answers "did anything fail?" but not "what was actually
reviewed?". Reviews are not always whole-repository: some files can be verified
against an available source while others cannot, because a source is optional,
unavailable, or not authoritative for that material.

Tests (deterministic or agentic) that want to express *coverage* should classify
each reviewed file or claim category as one of:

| Coverage state                        | Meaning                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------ |
| `reviewed-and-supported`              | Checked against an available authoritative source; no discrepancy.             |
| `reviewed-with-conflicting-evidence`  | Checked, and the source contradicts the docs (or two sources disagree).        |
| `skipped-by-policy`                   | Excluded by config (`exclude`) or the `generated` policy.                      |
| `unsupported-by-configured-sources`   | No configured source is authoritative for it, and none is required for it.     |
| `blocked-required-source-unavailable` | A required source it depends on could not be accessed; its review is incomplete. |

These states are additive to `status`: a run can be `pass` while still listing
files as `blocked-required-source-unavailable` or `unsupported-by-configured-sources`.
Such files must NOT be reported as passing review. See
[tests/agentic/reference-review.md](tests/agentic/reference-review.md) for how the
shipped agentic test applies this vocabulary.
