# Landscape example

A worked, multi-repository configuration for reviewing the **Landscape reference
documentation** with this tool. It exists to demonstrate the tool's
source-ownership, required/optional, and partial-coverage features against a real
product whose sources span several repositories — some of them **private**. It is
**not** used by this repository's own CI.

## Layout (and the convention for new examples)

```
examples/
  landscape/
    docs-testing.config.yml   # the example config          (committed)
    README.md                 # this file                    (committed)
    fetch-fixtures.sh         # pulls docs + sources locally (committed)
    docs/      (gitignored)   # reference docs under review  (fetched)
    sources/   (gitignored)   # source-of-truth checkouts    (fetched)
    results/   (gitignored)   # deterministic output         (generated)
```

To add another example, create `examples/<your-example>/` with the same shape:
commit the config (and any helper), and keep fetched docs/sources gitignored.

## Try it locally

The agentic test in [`tests/agentic/reference-review.md`](../../tests/agentic/reference-review.md)
is an instruction file for an AI engine (run via gh-aw in CI). To preview it
without CI, fetch the fixtures and have an engine execute those instructions
against this folder's `docs/` and `sources/`.

```bash
./fetch-fixtures.sh          # populates docs/ and sources/landscape-client
# optionally clone the private sources it prints, if you have access
```

- **Public only:** with just `landscape-client`, most of the Landscape reference
  set (which is server-owned) is reported as `blocked-required-source-unavailable`
  — a faithful demonstration that the review does not pass or fabricate findings
  for material it cannot verify.
- **With private access:** clone `landscape-server` (and optionally
  `landscape-server-operator`, `landscape-ui`) into `sources/` to unlock
  server-side coverage and real drift detection.

The deterministic broken-link check can be run directly:

```bash
python ../../tests/deterministic/broken_links.py \
  --targets 'docs/reference/**/*.md' --output results/reference-links.json
```

See the comments in [`docs-testing.config.yml`](docs-testing.config.yml) for the
full repository inventory, source-ownership map, and coverage expectations.
