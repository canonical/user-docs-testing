# Landscape example: several sources, one private

Landscape is implemented across four repositories, one of them private. This is its configuration, and it is here to be read rather than copied.

The documentation it tests is not in this repository — `fetch-fixtures.sh` pulls it into a gitignored `docs/`. So that the config makes sense without it, this is the reference set it refers to and who owns each part:

| Documentation | Owner | Why |
| ------------- | ----- | --- |
| `config/**` | `landscape-server` | These pages document the *server's* `service.conf` and `LANDSCAPE_*` variables, not the client's. |
| `lsctl.md`, `database.md`, `logs.md`, `networking/**` | `landscape-server` | Server CLIs, schema, and runtime behavior. |
| `charm/**` | `landscape-server-operator` | Charm options and relations belong to the operator. |
| `terms/**` | `landscape-server` and `landscape-ui` | The server defines what a term means; the UI defines the label a reader sees. |
| `supported-versions-and-ppas.md` | nothing | No packaging source is configured. |
| `release-notes/**`, `known-issues.md`, `_includes/**` | excluded | Narrative or fragments, not source-backed reference. |

That table is what `source_map` encodes. Stating it once means every review checks an area against the component that produces it, instead of guessing from the repository name.

Two rows are worth dwelling on. `terms/**` has **two owners**, because one component defines the behavior and another the surface. `supported-versions-and-ppas.md` has **none**: `sources: []` is deliberate, and makes the area report as unsupported rather than passing. An area nobody owns cannot be verified, and saying so is more useful than a green check.

The config also shows required versus optional sources, and one private source naming a secret with `auth:`. Only `landscape-server` is private; the other three need no token.

Every field is explained in [the configuration reference](../../docs/reference/configuration.md). For the simplest possible setup, see [examples/minimal](../minimal/).
