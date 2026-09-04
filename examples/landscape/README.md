# Landscape example

A worked configuration for a product implemented across six repositories, four of
them private. It exists to show source ownership, required versus optional
sources, and honest partial coverage against something real. It is **not** used
by this repository's own CI.

If you are starting out, read [examples/minimal](../minimal/) first — this one is
deliberately the complicated end of the spectrum.

## What makes it a useful example

The authoritative source for a Landscape claim depends on which component
implements it. The `config/` pages document the *server's* `service.conf`, not
the client's, so they are checked against the private server repository. Charm
options belong to the operator repository. Nothing owns the packaging and PPA
page at all.

The configuration states that ownership once, and every review uses it.

## Layout

```
docs-testing.config.yml   the example config          (committed)
fetch-fixtures.sh         pulls docs + sources        (committed)
docs/      (gitignored)   reference docs under review (fetched)
sources/   (gitignored)   source-of-truth checkouts   (fetched)
results/   (gitignored)   check output                (generated)
```

## Try it locally

```bash
./fetch-fixtures.sh          # populates docs/ and sources/landscape-client
docs-testing validate
docs-testing run
```

With only the public `landscape-client` source, most of the reference set is
reported as `blocked-required-source-unavailable` and the run is **incomplete**.
That is the example working correctly: it refuses to pass documentation it could
not verify, and it does not invent findings to explain the gap.

Clone `landscape-server` (and optionally `landscape-server-operator`,
`landscape-ui`) into `sources/` if you have access, and the blocked areas become
reviewable.

`reference-review` itself is performed by an AI engine and needs the installed
workflow; see the [README](../../README.md).
