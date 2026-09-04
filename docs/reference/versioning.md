# Versioning and stability

## Current status: pre-release

**No release has been tagged.** There are no `v1`, `v1.0.0`, or any other tags in
this repository. The installation instructions and the shipped workflow track
`main`, because that is the only thing that actually exists.

If you see documentation anywhere referring to `@v1`, it is wrong. Pinning to a
tag that does not exist fails at compile time with "failed to download import
file".

## What that means for you

Installing with `gh aw add canonical/user-docs-testing/docs-testing` records the
exact commit it installed in the `source:` field of your workflow, and pins every
import and action to a SHA in the generated `.lock.yml`. Your runs are therefore
reproducible even though the upstream reference is a branch: nothing changes
under you until you run `gh aw update`.

So the practical contract today is:

- Your installed workflow is pinned and stable.
- Upstream `main` may change, including in breaking ways.
- You pick up changes only when you choose to, by running `gh aw update`.
- Read the change summary that update produces before committing it.

## Stability of each interface

| Interface | Stability | Notes |
| --------- | --------- | ----- |
| `docs-testing.config.yml` | Settling | Fields may still be added or renamed before the first tag. |
| The five outcomes and their Check Run conclusions | Stable in intent | The vocabulary may gain a state; the guarantee that a broken tool never reports as a pass will not change. |
| The coverage states | Stable | |
| Finding and coverage fields in a custom check's results file | Stable | New optional fields may be added. |
| `results/all.json` layout, including `plan` | Unstable | It is the interface between this tool and the agent. Do not build on it. |
| The `docs-testing` command surface | Settling | |
| The built-in check identifiers | Stable | |

## Recommendation

Cut a `v1.0.0` tag, and a `v1` major-version tag that moves with it, before this
is offered to teams outside the group building it. At that point the workflow's
`imports:` and the composite action reference should change from `@main` to
`@v1`, and this page should describe a real support commitment rather than the
absence of one.

That work is deliberately not part of this change: manufacturing tags and a
stability promise that nobody has validated yet would be less honest than saying
there are none.
