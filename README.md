# user-docs-testing

> This project is a work-in-progress.

A tool for testing documentation. It reports its findings as a GitHub Check Run.

## Tests

Tests are declared in a `docs-testing.config.yml` in your repo. Two kinds:

- Agentic tests — a review by an AI engine, run through
  [GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw). Each points
  at an instruction file describing what to check. The tool ships a set of these
  under [tests/agentic/](tests/agentic/).
- Deterministic tests — a command that emits findings in a standard JSON schema
  (see [RESULTS-SCHEMA.md](RESULTS-SCHEMA.md)). A few generic ones ship under
  [tests/deterministic/](tests/deterministic/); most are specific to a project, so
  you'll usually add your own.

Choose which tests to run, and point them at your docs, in your config.

## Usage

1. Copy [workflows/docs-testing.md](workflows/docs-testing.md) into your repo under
   `.github/workflows/`.
2. In its `imports:` block, list the shipped agentic tests you want. They're
   fetched from this (public) repo when you compile, so your runs don't need
   access to it.
3. Add a `docs-testing.config.yml` (see
   [docs-testing.config.example.yml](docs-testing.config.example.yml)) with each
   test's targets, sources, and reporting.
4. Compile with `gh aw compile` and commit the generated `.lock.yml`.

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