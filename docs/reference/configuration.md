# Configuration reference

Everything Docs Testing does is driven by `docs-testing.config.yml` in the root of
your documentation repository. Run `docs-testing validate` after changing it;
every field below is checked, and mistakes are reported with a location and a
suggested fix.

The smallest valid configuration:

```yaml
version: 1
targets: "docs/reference/**/*.md"
sources:
  - name: product
    repo: my-org/my-product
tests:
  - reference-review
```

## Top level

| Field | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `version` | yes | — | Must be `1`. |
| `targets` | yes | — | Glob, or list of globs, of the documentation to test. Individual tests may narrow it. |
| `exclude` | no | none | Globs to leave out of every test. |
| `sources` | no | none | The product repositories documentation is checked against. |
| `source_map` | no | none | Which source owns which documentation. |
| `reporting` | no | see below | How results become a Check Run. |
| `tests` | yes | — | What to run. |

Globs support `**`. Paths are relative to the repository root.

## `sources`

A source is a repository holding the authoritative definition of some documented
behavior. Findings must cite one, so a review with no sources cannot prove
anything.

```yaml
sources:
  - name: product
    repo: my-org/my-product
    ref: main
    required: true
    auth: secret:SOURCE_REPO_TOKEN
```

| Field | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `name` | yes | — | Short identifier. Also the directory it is checked out into: `sources/<name>`. |
| `repo` | no | — | `owner/name`. Documentation only; the checkout itself is declared in the workflow. |
| `ref` | no | `main` | Branch, tag, or commit. Pin it for reproducible runs. |
| `required` | no | `true` | See below. |
| `paths` | no | `["**"]` | The parts of the source that are relevant. |
| `auth` | no | none | `secret:NAME` — the GitHub secret holding a read token for a **private** source. Never put a token in this file. |

`required` decides what happens when a source cannot be read:

- **Required** and unavailable: every area depending on it is reported as
  `blocked-required-source-unavailable`. The run is *incomplete*, never a pass.
  Areas backed by other available sources are still reviewed.
- **Optional** (`required: false`) and unavailable: the areas depending on it are
  reported as `unsupported-by-configured-sources`. The run continues.

Each source needs a matching `checkout:` block in
`.github/workflows/docs-testing.md`, with `path: sources/<name>`.
`docs-testing validate` fails if a required source has no checkout, because a
review that silently loses its source verifies nothing.

## `source_map`

States once which source owns which documentation, so every test checks an area
against the component that *produces* the interface rather than guessing.

```yaml
source_map:
  - area: "Server configuration"
    paths: ["docs/reference/config/**"]
    sources: [product-server]

  - area: "Supported versions"
    paths: ["docs/reference/versions.md"]
    sources: []      # nothing owns this: reported as unsupported, never as passing
```

| Field | Required | Description |
| ----- | -------- | ----------- |
| `area` | no | Human-readable label. Defaults to the paths. |
| `paths` | yes | Documentation paths this entry covers. |
| `sources` | yes | Names of the owning sources. An empty list means nothing owns it. |

Paths matched by no entry fall back to the test's own `sources` list. A test may
set its own `source_map` to override ownership for the paths it matches; most
should not need to.

## `tests`

Each entry is either a built-in, or your own command. `docs-testing list` prints
what is available.

### Shipped reviews

Performed by an AI engine in CI.

```yaml
tests:
  - reference-review          # shorthand for the entry below with all defaults
  - name: reference-completeness
    uses: reference-completeness
    targets: "docs/reference/cli/**/*.md"
```

| Review | Question it answers |
| ------ | ------------------- |
| `reference-review` | Does the documentation state something the owning product contradicts? |
| `reference-completeness` | Does user-facing product surface exist that the documentation never mentions? |

These are the only checks this tool ships. Every deterministic check is a
command of your own.

### Deterministic checks

A deterministic check is any command, in any language. Nothing about it is
AI-driven, and it runs locally as readily as in CI.

```yaml
tests:
  - name: style
    run: "python3 scripts/check_style.py --output results/style.json"
    results: "results/style.json"
    setup:
      - "pip install -r scripts/requirements.txt"
```

With `results`, the file is the report — see
[the results schema](results.md#extending-with-your-own-check). Without it, the
command's exit status is the result: zero passes, non-zero becomes one finding
carrying the command's output. That is enough for an existing pass/fail linter.

Commands run **without a shell**, so configuration cannot inject one. A command
containing `|`, `&&`, `;`, `>` or similar is rejected with an explanation; put
the pipeline in a script and call the script.

`targets` and `exclude` scope the **reviews**. A command is your own program, so
it scopes itself through its own arguments.

#### Worked examples

The [`tests/deterministic/`](https://github.com/canonical/user-docs-testing/tree/main/tests/deterministic)
directory of the user-docs-testing repository holds two scripts that show how to
write a check of this shape:

| Script | What it demonstrates |
| ------ | -------------------- |
| `undocumented_surface.py` | Diffing a machine-readable interface manifest — OpenAPI, JSON Schema, or a captured `--help` — against the documentation, and emitting findings with a `covered_topic` so a review skips them. |
| `source_manifest.py` | Emitting `coverage` and `source_evidence`, so unverifiable material is reported as blocked rather than passing. |

They are **demonstrations, not checks you are expected to run**. Read them, copy
what is useful, and write the checks your project actually needs.

### Fields common to every test

| Field | Default | Description |
| ----- | ------- | ----------- |
| `name` | — | Required. Labels the test's findings. |
| `uses` | — | A shipped review. Mutually exclusive with `run`. |
| `run` | — | Your own command. Mutually exclusive with `uses`. |
| `results` | none | Where `run` writes its findings. |
| `setup` | none | Commands to prepare this test. |
| `targets` | top-level `targets` | Narrow a review's scope. |
| `exclude` | top-level `exclude` | Narrow a review's scope. |
| `sources` | all sources | Which sources this test may use. |
| `source_map` | top-level | Test-specific ownership. |
| `generated` | none | `paths` plus `mode`: `skip`, `annotate`, or `deterministic-only`. |
| `skip_deterministically_covered` | `true` | Do not re-report what a deterministic check already found. |
| `enabled` | `true` | Set `false` to turn a test off without deleting it. |

## `reporting`

```yaml
reporting:
  fail_on_findings: true
  on_incomplete_coverage: neutral
  title: "Documentation testing"
```

| Field | Default | Description |
| ----- | ------- | ----------- |
| `mode` | `check-run` | `check-run`, `issue`, or `both`. |
| `fail_on_findings` | `true` | When false, `error`-severity findings are reported without failing CI. |
| `on_incomplete_coverage` | `neutral` | Conclusion when verification was incomplete. Only `neutral` or `action_required`; `success` is rejected. |
| `title` | `Documentation testing` | Check Run title. |
| `labels` | `["docs-testing"]` | Labels for issue mode. |
