# user-docs-testing

> This project is a work-in-progress.

A tool for testing documentation. It reports its findings as a GitHub Check Run.

## Tests

Tests are declared in a `docs-testing.config.yml` in your repo. Two kinds:

- Agentic tests — a review by an AI engine, run through
  [GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw). Each points
  at an instruction file describing what to check. The tool ships a set of these
  under [tests/agentic/](tests/agentic/). Two ship for reference docs:
  `reference-review`, the general accuracy check, and `reference-completeness`,
  which finds interface that exists in the source but is not documented.
- Deterministic tests — a command that emits findings in a standard JSON schema
  (see [RESULTS-SCHEMA.md](RESULTS-SCHEMA.md)). A few generic ones ship under
  [tests/deterministic/](tests/deterministic/): `broken_links.py` (relative-link
  targets that don't exist) and `undocumented_surface.py` (the precise counterpart
  to `reference-completeness` — diffs a machine-readable interface manifest, e.g.
  OpenAPI/`--help`/JSON Schema, against the docs). Most deterministic checks are
  specific to a project, so you'll usually add your own.

Choose which tests to run, and point them at your docs, in your config.

## Sources and coverage

Products are often implemented across several repositories, so the authoritative
source for a documented claim depends on which component owns the behavior. The
config models this:

- Each entry under `sources:` names a repository a test compares docs against.
  Mark it `required: true` (default) or `required: false`. A required source that
  can't be read makes the reviews depending on it **incomplete** — those files are
  reported as blocked, never as passing. An optional source can be absent, and the
  areas that need it are reported as unsupported.
- A top-level `source_map:` states **once** which source owns which documentation
  paths, so each area is checked against the *producer* of an interface (other
  sources only corroborate). Every reference test reads the same map; a test adds
  its own `source_map` only when it genuinely needs different ownership.
- Reviews are not reduced to one repo-wide pass/fail. Each area is classified with
  the coverage vocabulary in [RESULTS-SCHEMA.md](RESULTS-SCHEMA.md)
  (reviewed-and-supported, reviewed-with-conflicting-evidence, skipped-by-policy,
  unsupported-by-configured-sources, blocked-required-source-unavailable).

## Three outcomes, never two

The report distinguishes three things that must not collapse into one:

| Outcome                                     | `status`     | Check Run  |
| ------------------------------------------- | ------------ | ---------- |
| We checked it and it appears correct        | `pass`       | `success`  |
| We found a problem                          | `fail`       | `failure`  |
| We could not establish whether it is correct | `incomplete` | `neutral`  |

If a required source is unavailable, the material it owns is *not verified*, so
the run is `incomplete` — it must never look like a clean pass. Set
`reporting.on_incomplete_coverage: action_required` if you want that to block
merges. Details in [RESULTS-SCHEMA.md](RESULTS-SCHEMA.md).

Private sources need care: never expose a private source token to an untrusted
fork (see the SECURITY note in [workflows/docs-testing.md](workflows/docs-testing.md)).

## Examples

[examples/landscape/](examples/landscape/) is the proving ground: a worked,
multi-repository configuration (public + private sources, ownership map, partial
coverage) for a real product. Run it from
[.github/workflows/landscape-reference-review.md](.github/workflows/landscape-reference-review.md).



## Usage

1. Copy [workflows/docs-testing.md](workflows/docs-testing.md) into your repo under
   `.github/workflows/`.
2. In its `imports:` block, list the shipped agentic tests you want. They're
   fetched from this (public) repo when you compile, so your runs don't need
   access to it.
3. Add a `docs-testing.config.yml` (see
   [docs-testing.config.example.yml](docs-testing.config.example.yml)) with each
   test's targets, sources, and reporting.
4. Compile it — see below — and commit the generated `.lock.yml`.

## Compiling

GitHub Actions cannot run Markdown. `gh aw compile` turns each
`.github/workflows/*.md` into a `.lock.yml`, and **that** is what Actions
executes. Commit the `.lock.yml` next to its `.md`; a workflow without one does
not appear in the Actions tab at all.

Install the [gh CLI](https://cli.github.com/) and the
[gh-aw extension](https://github.com/githubnext/gh-aw):

```bash
gh extension install githubnext/gh-aw   # once
gh aw compile                           # in your repo, after any workflow change
git add .github/workflows/*.lock.yml && git commit -m "chore: compile workflows"
```

Recompile whenever you change the workflow `.md`, your `imports:`, or want to
pick up newer shipped tests. If a lock file drifts out of sync with its source,
the workflow detects it at run time and reports a stale lock file, so you are
told rather than silently running old instructions.

### Staying current

`imports:` are pinned at compile time, which is what lets a run work without
network access to this repo. What gets pinned depends on the ref you name:

| `imports:` ref | On recompile |
| -------------- | ------------------------------------------- |
| `@main`        | picks up the current tip of `main`          |
| `@v1` (tag)    | stays on that tag until you change it       |
| `@<sha>`       | frozen                                       |

Most consumers should track a tag or `@main` and recompile periodically.
`gh aw update` does this for you: it fetches the latest version of each
workflow, merges it with your local edits, and recompiles.

Upstream reference: [gh-aw documentation](https://github.github.io/gh-aw/),
[CLI commands](https://github.github.io/gh-aw/setup/cli/),
[imports](https://github.github.io/gh-aw/reference/imports/).

## Engines and tokens

Two independent tokens can be involved in a run. They solve different problems
and are configured separately:

- **Engine token** — how the AI agent (the engine that runs agentic tests)
  authenticates. Depends on the `engine:` you set in
  [workflows/docs-testing.md](workflows/docs-testing.md).
- **Source token** — how `actions/checkout` reads a *private* source-of-truth
  repo declared in your `docs-testing.config.yml`. Only needed for private
  sources; public sources need none. See "Private sources" below.

### Choosing an engine

The workflow ships with `engine: copilot`, but the engine is not fixed. Set
`engine:` in the workflow frontmatter to any provider gh-aw supports, then store
the matching secret in your repository (or organization):

| Engine                    | `engine:`  | Secret                                                                             |
| ------------------------- | ---------- | ---------------------------------------------------------------------------------- |
| GitHub Copilot (default)  | `copilot`  | `COPILOT_GITHUB_TOKEN` — a **fine-grained** PAT with **Copilot Requests: Read-only** (classic `ghp_...` tokens are rejected) |
| Claude (Anthropic)        | `claude`   | `ANTHROPIC_API_KEY`                                                                |
| OpenAI Codex              | `codex`    | `OPENAI_API_KEY`                                                                   |
| Google Gemini             | `gemini`   | `GEMINI_API_KEY`                                                                   |

OpenAI-compatible providers such as OpenRouter also work — either via
`engine: codex` with `OPENAI_BASE_URL` set to the provider endpoint, or via
Copilot BYOK with `COPILOT_PROVIDER_BASE_URL`. The provider hostname must be
added to `network.allowed`. See the
[gh-aw engines reference](https://github.github.com/gh-aw/reference/engines/) for
details.

### Switching engines

1. Change the `engine:` line in [workflows/docs-testing.md](workflows/docs-testing.md).
2. Run `gh aw compile`.
3. Commit the regenerated `.lock.yml` (it must stay in sync with the source).
4. Add the corresponding secret from the table above.

### Private sources

A source-of-truth repo is checked out separately from the engine, and a private
one needs its own read token — *not* the engine token. In
`docs-testing.config.yml`, a source declares `auth: secret:NAME`, and the
matching `checkout` block in the workflow supplies `token: ${{ secrets.NAME }}`.

Because a fine-grained PAT has a single resource owner, a personal
`COPILOT_GITHUB_TOKEN` cannot also read a private repo in another org. A private
org source therefore needs a *second*, org-owned secret with **Contents: Read**,
separate from the engine token. You must have access to the private repo, and the
org must permit fine-grained PATs (which may require admin approval / SSO
authorization).