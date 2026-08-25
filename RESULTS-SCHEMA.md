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
  ],
  "coverage": [
    {
      "area": "reference/cli.md",
      "state": "reviewed-and-supported",
      "sources": ["product"],
      "detail": null
    }
  ]
}
```

Only `findings` is strictly required by the orchestrator; the rest is
recommended for standalone runs and debugging. `coverage` is optional but is what
keeps an unverifiable area from being reported as a clean pass — see
"Coverage" below.

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
    "coverage_incomplete": 0,
    "status": "fail"
  },
  "findings": [ /* every test's findings, each tagged with "test" */ ],
  "coverage": [ /* every test's coverage entries, each tagged with "test" */ ]
}
```

## Coverage

A pass/fail status answers "did anything fail?" but not "what was actually
reviewed?". Reviews are not always whole-repository: some files can be verified
against an available source while others cannot, because a source is optional,
unavailable, or not authoritative for that material.

Any test — deterministic or agentic — may therefore report a `coverage` list
alongside its findings. Each entry classifies one file, glob, or claim category:

| Field     | Required | Description                                                          |
| --------- | -------- | -------------------------------------------------------------------- |
| `area`    | yes      | What was (or was not) reviewed: a doc path, glob, or claim category. |
| `state`   | yes      | One of the states below.                                             |
| `sources` | no       | Names of the sources this area depends on.                           |
| `detail`  | no       | One line explaining the state (especially why it is blocked).        |

| Coverage state                        | Meaning                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------ |
| `reviewed-and-supported`              | Checked against an available authoritative source; no discrepancy.             |
| `reviewed-with-conflicting-evidence`  | Checked, and the source contradicts the docs (or two sources disagree).        |
| `skipped-by-policy`                   | Excluded by config (`exclude`) or the `generated` policy.                      |
| `unsupported-by-configured-sources`   | No configured source is authoritative for it, and none is required for it.     |
| `blocked-required-source-unavailable` | A required source it depends on could not be accessed; its review is incomplete. |

The orchestrator adds a `test` field to each coverage entry, as it does for
findings.

## Source evidence

Coverage says what a test *claims* it reviewed. `source_evidence` records what was
actually on disk, so those claims can be audited rather than trusted:

```json
"source_evidence": [
  {
    "name": "landscape-client",
    "path": "sources/landscape-client",
    "available": true,
    "commit": "682158e801b5b8aaffbd5ff80f63bd52a72fb430",
    "files_seen": 393
  }
]
```

The shipped [source_manifest.py](tests/deterministic/source_manifest.py) check
produces this before any agent runs, and the orchestrator merges it into the
combined results. `commit` is the useful field: it is the only hard proof that a
private source was really accessed, and at which revision.

An agentic test must not report an area as reviewed against a source whose
evidence says `"available": false`.

## Status and the Check Run conclusion

`summary.status` has three values, and they must not collapse into each other:

| `status`     | Meaning                                                          | Check Run `conclusion` |
| ------------ | ---------------------------------------------------------------- | ---------------------- |
| `pass`       | Everything in scope was verified; nothing actionable found.      | `success`              |
| `fail`       | An actionable discrepancy was found (a finding with `severity: error`). | `failure`         |
| `incomplete` | No discrepancy proven, but required review coverage is missing.  | `neutral`              |

Precedence: `fail` beats `incomplete`, which beats `pass`. A run is `incomplete`
when any coverage entry is `blocked-required-source-unavailable` or
`unsupported-by-configured-sources`.

`neutral` is a real GitHub Check Run conclusion (the API accepts `success`,
`failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`),
and it renders distinctly from success in the Checks UI. It does **not** block a
required status check. If your team wants incomplete coverage to gate merges,
set `reporting.on_incomplete_coverage: action_required` in your config — that is
the conclusion GitHub does treat as blocking. Do not use `success` for it.

A file listed as `blocked-required-source-unavailable` or
`unsupported-by-configured-sources` must never be described as passing review.
See [tests/agentic/reference-review.md](tests/agentic/reference-review.md) for how
the shipped agentic test applies this vocabulary.

