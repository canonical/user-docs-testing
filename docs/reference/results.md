# Results reference

## The five outcomes

A documentation test can end in five ways, and they must never collapse into each
other. In particular, a tool that failed and documentation that is correct have to
look completely different.

| Outcome | Meaning | Exit status | Check Run |
| ------- | ------- | ----------- | --------- |
| `pass` | Everything in scope was verified; nothing to fix. | `0` | `success` |
| `warn` | Verified; only non-blocking findings. | `0` | `neutral` |
| `incomplete` | Part of the scope could not be verified. | `3` | `neutral`, or `action_required` |
| `fail` | An actionable documentation problem was found. | `1` | `failure` |
| `error` | The tool failed; the results are not trustworthy. | `2` | `action_required` |

Precedence is `error` > `fail` > `incomplete` > `warn` > `pass`. `error` outranks
everything because a run that did not execute correctly tells you nothing about
the documentation, including the parts that appeared to pass.

### What produces each outcome

**`fail`** — a finding with `severity: error`: a documented claim the owning
source contradicts, or a non-zero exit from one of your own commands.

**`warn`** — only `severity: warning` findings: undocumented surface, drifting
terminology, a stale but still-working example. Worth seeing, not worth blocking
a merge. Set `severity: error` on a check, or `fail_on_findings: false`
globally, to move the line.

**`incomplete`** — nothing was proven wrong, but something in scope was never
checked: a required source could not be read, no configured source owns an area,
or a surface manifest was absent. This is not a pass. `neutral` renders
differently from success but does not block a required check; set
`reporting.on_incomplete_coverage: action_required` if incomplete verification
should gate merges. `success` is rejected by the configuration validator.

**`error`** — the run itself broke: a command crashed or was not found, a
declared results file was never written, results JSON was unreadable, or the
configuration was malformed. These are reported as `errors`, never as findings,
and never as zero findings.

## Coverage

Pass/fail answers "did anything fail?" but not "what was actually checked?".
Reviews are rarely whole-repository: some files can be verified against an
available source while others cannot.

Every test classifies each file, glob, or claim category into one state:

| State | Meaning |
| ----- | ------- |
| `reviewed-and-supported` | Checked against an available owning source; no discrepancy. |
| `reviewed-with-conflicting-evidence` | Checked, and the source contradicts the documentation. |
| `skipped-by-policy` | Excluded by `exclude` or the `generated` policy. |
| `unsupported-by-configured-sources` | No configured source is authoritative for it. |
| `blocked-required-source-unavailable` | A required owning source could not be read. |

The last two mean "not verified", and either one makes the run `incomplete`.

## Source evidence

Coverage says what a test *claims* it reviewed. `source_evidence` records what was
actually on disk, so those claims can be audited rather than trusted:

```json
"source_evidence": [
  {
    "name": "product",
    "path": "sources/product",
    "available": true,
    "commit": "682158e801b5b8aaffbd5ff80f63bd52a72fb430",
    "files_seen": 393
  }
]
```

This is collected automatically on every run, before anything else. `commit` is
the useful field: it is the only hard proof that a private source was really
accessed, and at which revision. Without it, a run where a private source
silently failed to check out and a run where it was read thoroughly would end the
same way.

A review must not report an area as verified against a source whose evidence says
`"available": false`.

## The combined results file

`docs-testing run` writes `results/all.json`. The agent reads it, and so can you.

```json
{
  "tool": "user-docs-testing",
  "schema_version": 2,
  "summary": {
    "status": "warn",
    "meaning": "Documentation was verified; only non-blocking findings were reported.",
    "tests_declared": 1,
    "tests_run": 1,
    "reviews_declared": 1,
    "findings": 1,
    "blocking_findings": 0,
    "warnings": 1,
    "unverified_areas": 0,
    "tool_errors": 0
  },
  "errors": [],
  "findings": [ ... ],
  "coverage": [ ... ],
  "source_evidence": [ ... ],
  "plan": { ... }
}
```

`plan` is the validated, normalized configuration: which reviews to run, with
what scope, which source owns what, and how to conclude. The agent uses it
instead of re-reading the YAML, so configuration is interpreted in exactly one
place.

## Extending with your own check

A test declaring `results:` writes a JSON object with a `findings` list. Any
language works.

```json
{
  "findings": [
    {
      "check": "heading-case",
      "severity": "warning",
      "doc_file": "docs/reference/cli.md",
      "doc_line": 12,
      "message": "Heading uses title case; the style guide requires sentence case.",
      "covered_topic": "heading-case:docs/reference/cli.md:12"
    }
  ],
  "coverage": [
    { "area": "docs/reference/cli.md", "state": "reviewed-and-supported" }
  ]
}
```

### Finding fields

| Field | Required | Description |
| ----- | -------- | ----------- |
| `message` | yes | Human-readable description of the problem. |
| `severity` | no | `error` (fails CI) or `warning` (default). |
| `check` | no | Identifier of the specific check. Defaults to the test name. |
| `doc_file` | no | Documentation file, repository-relative. |
| `doc_line` | no | 1-based line number. |
| `source` | no | Name of the source of truth involved. |
| `source_ref` | no | Location within that source. |
| `covered_topic` | no | Stable identifier of what this covers. Reviews skip topics already listed here, which is how duplicates between a deterministic check and a review are avoided. |

`test` is added automatically.

### Coverage fields

| Field | Required | Description |
| ----- | -------- | ----------- |
| `area` | yes | What was, or was not, reviewed. |
| `state` | yes | One of the five states above. |
| `sources` | no | Sources this area depends on. |
| `detail` | no | One line explaining the state, especially why it is blocked. |

A malformed finding or coverage entry is reported as a tool error, not silently
dropped — dropping it could shrink the finding count and turn a real failure into
a pass.
