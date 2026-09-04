# How it works

You do not need this page to use Docs Testing. It is here for when something
looks surprising and you want to know what is actually running.

## The pieces

Docs Testing is a thin layer over
[GitHub Agentic Workflows](https://github.github.io/gh-aw/) (gh-aw), which is
what lets a Markdown file describe an AI-driven GitHub Actions workflow.

| Piece | Lives in | What it is |
| ----- | -------- | ---------- |
| `docs-testing.config.yml` | your repository | What to test, and against what. The only file you normally edit. |
| `.github/workflows/docs-testing.md` | your repository | The workflow, installed by `gh aw add`. Mostly ours. |
| `.github/workflows/docs-testing.lock.yml` | your repository | Generated. The YAML that Actions actually runs. |
| `.github/aw/` | your repository | Generated. gh-aw's cache of imported files and pinned action versions. |
| the checks and review instructions | this repository | Fetched at install and compile time. |

## Why there is a lock file

GitHub Actions cannot run Markdown. `gh aw compile` reads
`docs-testing.md` — frontmatter plus prompt — and generates
`docs-testing.lock.yml`, a complete standard Actions workflow. **Actions runs the
lock file, not the Markdown.** A workflow without a lock file does not appear in
the Actions tab at all.

Compiling also resolves everything to an immutable version:

- each imported instruction file is fetched and pinned to a commit SHA, and a
  copy is written under `.github/aw/imports/`;
- every action, including ours, is rewritten to a SHA;
- container images are pinned by digest.

That is why your runs are reproducible even though the workflow tracks `main`
upstream: nothing changes under you until you deliberately update.

Both the lock file and `.github/aw/` must be committed. They are marked as
generated in `.gitattributes`, so they collapse in pull request diffs.

## When you have to compile

Usually never — the commands do it for you:

| You run | Compiles? |
| ------- | --------- |
| `gh aw add ...` | Yes, on install |
| `gh aw update docs-testing` | Yes, after merging upstream changes |
| Editing `docs-testing.config.yml` | **No compile needed** — the config is read at run time |
| Editing `docs-testing.md` by hand | Yes: run `gh aw compile` |

The important row is the third one. Day-to-day work — changing what is tested,
adding a check, adjusting scope — touches only `docs-testing.config.yml`, which
is read when the workflow runs. No compile, no lock file churn.

You edit the workflow itself mainly to add `checkout:` blocks for your sources.
If a lock file ever drifts out of sync with its Markdown, the run detects it and
reports a stale lock file rather than silently running old instructions.

## What happens during a run

1. **Checkout.** Your repository, plus one directory per source under
   `sources/<name>`.
2. **`actions/docs-tests`** (ours) validates `docs-testing.config.yml` and stops
   the run immediately if it is wrong. Then it records which sources really
   arrived — directory present, commit SHA, file count — and runs the
   deterministic checks. Everything lands in `results/all.json`.
3. **The agent** reads `results/all.json`: the resolved plan, the source
   evidence, and the findings so far. It performs the reviews, skipping anything
   the deterministic checks already reported.
4. **Safe outputs.** The agent cannot write to your repository. It emits a
   request, and a separate gated job creates the Check Run. Secrets never enter
   the agent's runtime. See
   [safe outputs](https://github.github.io/gh-aw/reference/safe-outputs/).

Step 2 running before step 3 is deliberate: it means a review cannot claim to
have checked documentation against a source that was never there.

## Upstream reference

Ours is the configuration and the checks; everything about workflow mechanics is
gh-aw's:

- [Architecture](https://github.github.io/gh-aw/introduction/architecture/) —
  compilation, the agent firewall, and the security model.
- [CLI commands](https://github.github.io/gh-aw/setup/cli/) — `add`, `update`,
  `compile`, `run`, `logs`.
- [Frontmatter](https://github.github.io/gh-aw/reference/frontmatter/) — every
  field in the workflow's header.
- [Imports](https://github.github.io/gh-aw/reference/imports/) — how shared
  instruction files are fetched and pinned.
- [Triggers](https://github.github.io/gh-aw/reference/triggers/) — schedules and
  events; see also [scheduling](scheduling.md).
- [Engines](https://github.github.io/gh-aw/reference/engines/) — providers and
  their credentials.
- [Network](https://github.github.io/gh-aw/reference/network/) — what the agent
  is allowed to reach.
- [Cost management](https://github.github.io/gh-aw/reference/cost-management/) —
  what a scheduled AI run costs and how to bound it.
