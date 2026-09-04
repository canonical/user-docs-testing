"""Record which sources of truth were actually checked out, and block what wasn't.

This is not a user-configured test; it runs automatically on every run. An
agent's own report is not evidence: without this, a run where a private source
silently failed to check out and a run where it was read thoroughly both end in
the same "success". Recording the machine truth — directory present, commit SHA,
file count — is what lets a reviewer tell those two runs apart.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from docs_testing.config import Config
from docs_testing.results import BLOCKED, UNSUPPORTED

#: Enough files to prove a checkout is not empty; we do not need an exact count.
_FILE_SCAN_LIMIT = 1000


def _commit(path: Path) -> str | None:
    """The commit checked out at `path`, or None if it is not its own checkout.

    `git -C` searches upwards, so a plain directory sitting inside another
    repository would otherwise report that repository's HEAD — attesting a commit
    for a source that was never cloned. The toplevel check rejects that.
    """
    try:
        toplevel = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if toplevel.returncode != 0:
            return None
        if Path(toplevel.stdout.strip()).resolve() != path.resolve():
            return None

        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def inspect_source(name: str, root: Path) -> dict:
    path = root / name
    files = 0
    if path.is_dir():
        for entry in path.rglob("*"):
            if entry.is_file() and ".git/" not in entry.as_posix():
                files += 1
                if files >= _FILE_SCAN_LIMIT:
                    break
    return {
        "name": name,
        "path": path.as_posix(),
        "available": files > 0,
        "commit": _commit(path),
        "files_seen": files,
    }


def collect(config: Config, sources_root: Path) -> tuple[list[dict], list[dict]]:
    """Return `(source_evidence, coverage)` for the configured sources."""
    evidence = [inspect_source(source.name, sources_root) for source in config.sources]
    available = {e["name"] for e in evidence if e["available"]}

    coverage: list[dict] = []
    mapped: set[str] = set()

    for entry in config.source_map:
        owners = entry["sources"]
        area = entry["area"]
        mapped.update(owners)

        if not owners:
            coverage.append(
                {
                    "area": area,
                    "state": UNSUPPORTED,
                    "sources": [],
                    "detail": "No configured source owns this area, so it was NOT verified.",
                }
            )
            continue

        if any(owner in available for owner in owners):
            continue

        blocked = any((config.source(o).required if config.source(o) else True) for o in owners)
        coverage.append(
            {
                "area": area,
                "state": BLOCKED if blocked else UNSUPPORTED,
                "sources": owners,
                "detail": (
                    f"Owning source(s) not checked out: {', '.join(owners)}. "
                    "This area was NOT verified."
                ),
            }
        )

    # A source that owns no mapped area still backs every claim a review might
    # make against it. Without this, a project with no `source_map` could lose
    # its only required source and still report "verified" — the exact failure
    # the coverage model exists to prevent.
    for source in config.sources:
        if source.name in available or source.name in mapped:
            continue
        coverage.append(
            {
                "area": f"documentation depending on source `{source.name}`",
                "state": BLOCKED if source.required else UNSUPPORTED,
                "sources": [source.name],
                "detail": (
                    f"Source `{source.name}` was not checked out, so nothing could be "
                    "verified against it."
                ),
            }
        )

    return evidence, coverage


def missing_required(config: Config, evidence: list[dict]) -> list[str]:
    available = {e["name"] for e in evidence if e["available"]}
    return [s.name for s in config.sources if s.required and s.name not in available]
