# How to set up engines and access private sources

Two independent kinds of credential can be involved in a run. They solve different problems and are configured separately.

- **Engine authentication** — how the AI engine that performs the reviews authenticates.
- **Source tokens** — how `actions/checkout` reads a *private* product repository declared in `sources:`. Public sources need none.

Mixing them up is the most common setup failure. A token that can talk to an AI engine generally cannot read your private repository, and vice versa.

## Choosing an engine

Engine selection belongs to gh-aw, not to this project. Anything gh-aw supports should work here; however, `copilot` is the only engine we've tested so far.

Pick the engine when you install, and gh-aw writes and compiles the workflow:

```bash
gh aw add canonical/user-docs-testing/workflows/docs-testing.md --engine claude
```

The default is `copilot` with `copilot-requests: write` permission, which authenticates using the workflow's own token and needs no secret (assuming the organization has centralized Copilot billing).

To use another engine, set `engine:` to `claude`, `codex`, or `gemini`, or to `codex` with a base URL for an OpenAI-compatible provider such as OpenRouter, and add the secret that engine reads. The [gh-aw engines reference](https://github.github.io/gh-aw/reference/engines/) lists the engine names, their secrets, and the base-URL settings. A provider hostname must also be added to `network.allowed`.

To switch engines after installing: change `engine:` in `.github/workflows/docs-testing.md`, run `gh aw compile`, commit the regenerated `.lock.yml`, and add the matching secret.

## Private sources

A private source needs its own read token, separate from the engine.

1. Create a fine-grained PAT with **Contents: Read** on the private repositories. If your organization enforces SAML, authorize it for the organization.
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

`docs-testing validate` checks that the two agree, and fails if a required source has no checkout — a review that quietly loses its source verifies nothing.

A fine-grained PAT has a single resource owner, so a token owned by one organization cannot read a private repository in another. A private organization source needs a secret owned by that organization.

## Keeping private sources safe

Two rules matter, and neither is optional.

**Never expose a source token to an untrusted fork.** A pull request from a fork can modify the workflow and `docs-testing.config.yml`. If a privileged token were available to that run, the fork could use it to read your private repositories. The shipped workflow therefore triggers only on `workflow_dispatch` and `schedule`. If you add a `pull_request` trigger, restrict it to same-repository pull requests.

**Reports may be public.** The reviews are instructed to cite paths, symbols, and short paraphrases rather than copying private source code into a Check Run. Keep that in mind if you widen their scope.

The agent itself runs read-only, with `contents: read`. All writes happen in the gated safe-outputs job, so secrets never enter the agent runtime.
