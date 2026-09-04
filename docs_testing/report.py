"""Human-readable rendering of a run.

Two audiences, one hierarchy: the terminal during local iteration, and the GitHub
step summary in CI. Both answer the same questions in the same order — did it
run, what must I fix, what was not verified, what was checked.
"""

from __future__ import annotations

from docs_testing.results import (
    ERROR,
    FAIL,
    INCOMPLETE,
    PASS,
    STATUS_MEANING,
    WARN,
)

_HEADLINE = {
    PASS: "PASS      documentation verified, nothing to fix",
    WARN: "WARNINGS  documentation verified, non-blocking findings reported",
    INCOMPLETE: "INCOMPLETE  part of the documentation could not be verified",
    FAIL: "FAIL      documentation problems found",
    ERROR: "TOOL ERROR  the run did not complete correctly; results are not trustworthy",
}


def _location(finding: dict) -> str:
    doc_file = finding.get("doc_file")
    if not doc_file:
        return finding.get("source_ref") or "(no file)"
    line = finding.get("doc_line")
    return f"{doc_file}:{line}" if line else str(doc_file)


def _detail_lines(finding: dict, indent: str, limit: int = 10) -> list[str]:
    """Output captured from a command. For an exit-status check this is the only
    thing the check had to say, so dropping it would leave the user nothing."""
    detail = finding.get("detail")
    if not detail:
        return []
    return [f"{indent}| {line}" for line in str(detail).splitlines()[:limit]]


def render_text(payload: dict) -> str:
    summary = payload["summary"]
    status = summary["status"]
    out: list[str] = ["", _HEADLINE[status], ""]

    errors = payload.get("errors") or []
    if errors:
        out.append(f"Tool errors ({len(errors)}) — fix these first:")
        for error in errors:
            scope = f"{error['test']}: " if error.get("test") else ""
            out.append(f"  [{error['stage']}] {scope}{error['message']}")
            if error.get("remedy"):
                out.append(f"      fix: {error['remedy']}")
            if error.get("detail"):
                for line in str(error["detail"]).splitlines()[-5:]:
                    out.append(f"      | {line}")
        out.append("")

    blocking = [f for f in payload["findings"] if f.get("severity") == "error"]
    warnings = [f for f in payload["findings"] if f.get("severity") != "error"]

    if blocking:
        out.append(f"Problems ({len(blocking)}):")
        for finding in blocking:
            out.append(f"  {_location(finding)}  {finding['message']}  [{finding['test']}]")
            out.extend(_detail_lines(finding, "      "))
        out.append("")

    if warnings:
        out.append(f"Warnings ({len(warnings)}) — reported, not blocking:")
        for finding in warnings[:20]:
            out.append(f"  {_location(finding)}  {finding['message']}  [{finding['test']}]")
            out.extend(_detail_lines(finding, "      "))
        if len(warnings) > 20:
            out.append(f"  ... and {len(warnings) - 20} more")
        out.append("")

    unverified = [c for c in payload["coverage"] if c["state"] in
                  ("blocked-required-source-unavailable", "unsupported-by-configured-sources")]
    if unverified:
        out.append(f"Not verified ({len(unverified)}):")
        for entry in unverified:
            out.append(f"  {entry['area']}  ({entry['state']})")
            if entry.get("detail"):
                out.append(f"      {entry['detail']}")
        out.append("")

    evidence = payload.get("source_evidence") or []
    if evidence:
        out.append("Sources:")
        for item in evidence:
            mark = "ok     " if item.get("available") else "MISSING"
            commit = (item.get("commit") or "-")[:12]
            out.append(f"  {mark} {item['name']:<28} commit={commit} files={item.get('files_seen', 0)}")
        out.append("")

    out.append(
        f"{summary['tests_run']}/{summary['tests_declared']} check(s) ran, "
        f"{summary['blocking_findings']} problem(s), {summary['warnings']} warning(s), "
        f"{summary['unverified_areas']} unverified area(s), {summary['tool_errors']} tool error(s)"
    )
    reviews = summary.get("reviews_declared", 0)
    if reviews:
        out.append(
            f"{reviews} review(s) are run by the AI engine in CI and are not included above."
        )
    out.append(STATUS_MEANING[status])
    out.append("")
    return "\n".join(out)


def render_markdown(payload: dict) -> str:
    """A compact GitHub step summary. Successful runs stay short on purpose."""
    summary = payload["summary"]
    status = summary["status"]
    out = [f"## Documentation testing — {status.upper()}", "", STATUS_MEANING[status], ""]

    errors = payload.get("errors") or []
    if errors:
        out.append("### Tool errors")
        out.append("")
        for error in errors:
            scope = f"`{error['test']}` " if error.get("test") else ""
            out.append(f"- **{error['stage']}** {scope}— {error['message']}")
            if error.get("remedy"):
                out.append(f"  - fix: {error['remedy']}")
        out.append("")

    blocking = [f for f in payload["findings"] if f.get("severity") == "error"]
    if blocking:
        out.append(f"### Problems ({len(blocking)})")
        out.append("")
        for finding in blocking:
            out.append(f"- `{_location(finding)}` — {finding['message']}")
            if finding.get("detail"):
                out.append("")
                out.append("  ```")
                out.extend(f"  {line}" for line in str(finding["detail"]).splitlines()[:10])
                out.append("  ```")
        out.append("")

    warnings = [f for f in payload["findings"] if f.get("severity") != "error"]
    if warnings:
        out.append(f"### Warnings ({len(warnings)})")
        out.append("")
        for finding in warnings[:20]:
            out.append(f"- `{_location(finding)}` — {finding['message']}")
        if len(warnings) > 20:
            out.append(f"- _... and {len(warnings) - 20} more_")
        out.append("")

    unverified = [c for c in payload["coverage"] if c["state"] in
                  ("blocked-required-source-unavailable", "unsupported-by-configured-sources")]
    if unverified:
        out.append(f"### Not verified ({len(unverified)})")
        out.append("")
        for entry in unverified:
            out.append(f"- **{entry['area']}** — {entry.get('detail') or entry['state']}")
        out.append("")

    return "\n".join(out)
