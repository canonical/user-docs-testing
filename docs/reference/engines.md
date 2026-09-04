# Engines, tokens, and private sources

Two independent kinds of credential can be involved in a run. They solve
different problems and are configured separately.

- **Engine authentication** — how the AI engine that performs the reviews
  authenticates.
- **Source tokens** — how `actions/checkout` reads a *private* product
  repository declared in `sources:`. Public sources need none.

Mixing them up is the most common setup failure. A token that can talk to an AI
engine generally cannot read your private repository, and vice versa.

## Choosing an engine

Pick the engine when you install, and gh-aw writes and compiles the workflow for
you:

```bash
gh aw add canonical/user-docs-testing/docs-testing --engine claude
```

The default is `copilot` with `copilot-requests: write` permission, which
authenticates using the workflow's own token. That needs no secret at all, but
does require your organization to have centralized Copilot billing.

If it does not, remove the `copilot-requests: write` line and add a secret
instead:

| Engine | `engine:` | Secret |
| ------ | --------- | ------ |
| GitHub Copilot | `copilot` | `COPILOT_GITHUB_TOKEN` — a **fine-grained** PAT with **Copilot Requests: Read-only**. Classic `ghp_...` tokens are rejected. |
| Claude | `claude` | `ANTHROPIC_API_KEY` |
| OpenAI Codex | `codex` | `OPENAI_API_KEY` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` |

OpenAI-compatible providers such as OpenRouter also work, either via
`engine: codex` with `OPENAI_BASE_URL`, or via Copilot BYOK with
`COPILOT_PROVIDER_BASE_URL`. The provider hostname must be added to
`network.allowed`. See the
[gh-aw engines reference](https://github.github.io/gh-aw/reference/engines/).

To switch engines after installing: change `engine:` in
`.github/workflows/docs-testing.md`, run `gh aw compile`, commit the regenerated
`.lock.yml`, and add the matching secret.

## Private sources

A private source needs its own read token, separate from the engine.

1. Create a fine-grained PAT with **Contents: Read** on the private repositories.
   If your organization enforces SAML, authorize it for the organization.
2. Store it as a repository or organization secret.
3. Reference the secret in the config, and use it in the matching checkout:

```yaml
# docs-testing.config.yml
sources:
  - name: product-server
    repo: my-org/product-server
    auth: secret:SOURCE_REPO_TOKEN
    required: true
```

```yaml
# .github/workflows/docs-testing.md
checkout:
  - current: true
  - repository: my-org/product-server
    ref: main
    path: sources/product-server
    token: ${{ secrets.SOURCE_REPO_TOKEN }}
```

`docs-testing validate` checks that the two agree, and fails if a required source
has no checkout — a review that quietly loses its source verifies nothing.

A fine-grained PAT has a single resource owner, so one token cannot both act as a
personal `COPILOT_GITHUB_TOKEN` and read a private repository in another
organization. A private organization source needs its own organization-owned
secret.

## Keeping private sources safe

Two rules matter, and neither is optional.

**Never expose a source token to an untrusted fork.** A pull request from a fork
can modify the workflow and `docs-testing.config.yml`. If a privileged token were
available to that run, the fork could use it to read your private repositories.
The shipped workflow therefore triggers only on `workflow_dispatch` and
`schedule`. If you add a `pull_request` trigger, restrict it to
same-repository pull requests.

**Reports may be public.** The reviews are instructed to cite paths, symbols, and
short paraphrases rather than copying private source code into a Check Run. Keep
that in mind if you widen their scope.

The agent itself runs read-only, with `contents: read`. All writes happen in the
gated safe-outputs job, so secrets never enter the agent runtime.
