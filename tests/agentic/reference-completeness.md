# Reference documentation completeness

A shipped agentic test. It checks whether the reference documentation *covers* the
interface its sources expose — it looks for user-facing elements that exist in the
source but are **missing** from the docs.

Where the general `reference-review` test catches "documented but wrong", this test
catches "exists but undocumented". Enable it from your `docs-testing.config.yml`,
point its `targets` at your reference docs, and its `sources` at what they describe.

## Inputs available to you

- The documentation repository is checked out at the workspace root.
- Each configured source of truth is checked out under `sources/<name>/`. A
  source directory may be missing or empty if that source could not be cloned,
  authenticated, or read.
- The project configuration is in `docs-testing.config.yml`. This test's entry in
  the `tests` list tells you:
  - `targets` / `exclude` — which files are in scope.
  - `generated` — auto-generated material and how to treat it.
  - `sources` — which sources of truth (by name) to compare against.
  - `source_map` (optional) — an explicit ownership map associating in-scope
    files / claim categories with the source(s) most likely to be AUTHORITATIVE
    for them. When present, prefer it when deciding which source owns an area.
- The `sources:` list marks each source `required` (default) or optional
  (`required: false`).
- Any deterministic findings are in `results/all.json`.

## Establish source ownership first

For each in-scope area, decide which configured source *produces* the interface it
documents (use `source_map` when present, otherwise infer). You can only judge
completeness of an area against the source that owns its surface. A missing
element in one source may simply belong to a different component.

## What to do

1. Resolve the in-scope files from this test's `targets` and `exclude`.
2. For each area, enumerate the **user-facing documentable surface** from its owning
   source — only things that belong in reference docs. Depending on the area, that
   may include:
   - CLI commands and subcommands, and their flags / options / arguments;
   - configuration keys, sections, and environment variables;
   - public API endpoints, methods, and parameters;
   - user-visible settings, roles, permissions, states, or enums;
   - installed executables, services, or scheduled jobs.
   Exclude internal, private, test-only, experimental, or clearly hidden/deprecated
   elements — they do not belong in user reference.
3. For each surface element, check whether the in-scope reference docs document it.
4. Flag every user-facing element the source exposes but the docs do **not** cover.
   Do NOT flag documented items that no longer exist in the source — that is the
   general `reference-review` test's job; keep this test to the "missing" direction.
5. Respect `generated.mode`: if generated reference covers part of the surface
   (e.g. an auto-generated API reference), treat that surface as covered/skipped
   per the policy rather than reporting it as missing.
6. Only flag elements you are confident are user-facing and in scope for reference.
   The public/internal judgment is where this test is most likely to produce false
   positives, so apply explicit heuristics and err strongly toward NOT flagging:
   - Positive signals (may be user-facing): appears in a machine-readable public
     interface (`--help`, OpenAPI/Swagger, an exported JSON Schema); is exported from
     a public module or `__all__`; ships in the packaged default/sample config; has a
     stable name referenced in user-facing help text.
   - Negative signals (treat as internal — do NOT flag): a leading underscore or an
     `internal`/`private`/`debug`/`experimental`/`dev`/`test` name; gated behind a
     debug/experimental/feature flag; only referenced from tests; marked deprecated
     or hidden; not reachable through any user-facing entry point.
   When the signals conflict or you cannot tell, do not flag.

### Prefer a deterministic check for machine-enumerable surface

Where the surface is machine-enumerable — a CLI's `--help`, an OpenAPI/Swagger
spec, or an exported JSON Schema — a deterministic diff is more precise and
repeatable than this review. Prefer the shipped
[`undocumented_surface.py`](../deterministic/undocumented_surface.py) check for
those surfaces, and let this agentic test concentrate on surface that is NOT
machine-enumerable (for example prose-documented concepts, roles, or states). If
`skip_deterministically_covered` is true, read `results/all.json` first and do not
re-report any element already listed there (match `covered_topic`).

### Respect version and source ref

The source is checked out at a single `ref`. Do not report an element as
"undocumented" when the docs intentionally omit it because it belongs to a different
product version than the source `ref`, and do not report as "missing" something the
docs cover under a version-specific heading.

## Missing or unavailable sources

A source directory under `sources/<name>/` may be missing or empty.

- If an area's owning source is REQUIRED and unavailable, you cannot enumerate its
  surface — mark that area **blocked**; do NOT report it as complete, and do NOT
  invent missing-item findings.
- If the unavailable source is OPTIONAL and no in-scope area depends on it, proceed.
- Continue assessing every area whose owning source IS available. Never reduce the
  run to a single pass/fail because one source was missing.

## Output

Contribute your findings to the single check run produced by the workflow.

Classify each in-scope area into exactly one coverage state (see
[RESULTS-SCHEMA.md](../../RESULTS-SCHEMA.md)); for this test they mean:

- **reviewed-and-supported** — the enumerated surface for the area is fully documented.
- **reviewed-with-conflicting-evidence** — the source exposes user-facing elements
  the docs do not cover (one finding per undocumented element or group).
- **skipped-by-policy** — excluded by `exclude` or covered by the `generated` policy.
- **unsupported-by-configured-sources** — no configured source can enumerate it.
- **blocked-required-source-unavailable** — a required owning source was unavailable.

Then report:

- `failure` if you found at least one undocumented element and
  `reporting.fail_on_findings` is true; otherwise `neutral`.
- `success` only if every in-scope area is reviewed-and-supported or
  skipped-by-policy. Never report `success` for a blocked or unsupported area.
- For each finding include: the undocumented source element (name plus
  `sources/<name>/<path>` or symbol), the area it belongs to, and a one-line note.
- Use `severity: warning` for undocumented surface — it is a coverage gap, not a
  broken claim — reserving `severity: error` for a user-facing element whose absence
  blocks a documented workflow.
- Group findings by area, and briefly note the surface you enumerated so a reader
  can gauge how much was checked. List blocked / unsupported areas separately.

### Handling private sources safely

A source may be a private repository. When reporting against one:

- Prefer source paths, symbols, and short paraphrases over copying substantial
  private code into the report.
- Name the undocumented element and its location only to the extent appropriate for
  the repository where the check runs (a public check run must not leak private
  source contents).
- If you could not access a required source, report that the assessment is
  incomplete rather than guessing at its surface.
