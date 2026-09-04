"""Load, validate, and normalize `docs-testing.config.yml`.

Configuration is validated here, once, before anything else runs. That is
deliberate: a typo must produce a precise message with a location and a
suggestion, not an agent halfway through a review guessing what `targests` meant.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from docs_testing.results import SEVERITIES

CONFIG_VERSION = 1
DEFAULT_CONFIG_NAME = "docs-testing.config.yml"

# --- Built-in checks --------------------------------------------------------

AGENTIC = "agentic"
DETERMINISTIC = "deterministic"


@dataclass(frozen=True)
class BuiltIn:
    id: str
    kind: str
    summary: str
    #: Required keys under `with:` for deterministic built-ins.
    required_with: tuple[str, ...] = ()
    optional_with: tuple[str, ...] = ()


BUILTINS: dict[str, BuiltIn] = {
    "reference-review": BuiltIn(
        id="reference-review",
        kind=AGENTIC,
        summary="Does the documentation contradict the product that owns the behavior?",
    ),
    "reference-completeness": BuiltIn(
        id="reference-completeness",
        kind=AGENTIC,
        summary="Does user-facing product surface exist that the documentation never mentions?",
    ),
    "undocumented-surface": BuiltIn(
        id="undocumented-surface",
        kind=DETERMINISTIC,
        summary="Diff a machine-readable interface manifest against the documentation.",
        required_with=("manifest",),
        optional_with=("ignore", "severity", "source_name"),
    ),
}

# --- Accepted keys ----------------------------------------------------------

TOP_LEVEL_KEYS = {
    "version",
    "docs",
    "exclude",
    "sources",
    "source_map",
    "reporting",
    "tests",
}

SOURCE_KEYS = {"name", "repo", "ref", "paths", "auth", "required"}
SOURCE_MAP_KEYS = {"area", "paths", "sources"}
REPORTING_KEYS = {
    "mode",
    "fail_on_findings",
    "on_incomplete_coverage",
    "title",
    "labels",
}
TEST_KEYS = {
    "name",
    "uses",
    "run",
    "results",
    "setup",
    "docs",
    "exclude",
    "sources",
    "source_map",
    "generated",
    "with",
    "enabled",
    "skip_deterministically_covered",
}
GENERATED_KEYS = {"paths", "mode"}
GENERATED_MODES = {"skip", "annotate", "deterministic-only"}
REPORTING_MODES = {"check-run", "issue", "both"}
INCOMPLETE_CONCLUSIONS = {"neutral", "action_required"}

SOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
AUTH_RE = re.compile(r"^secret:[A-Za-z_][A-Za-z0-9_]*$")

# Keys that used to exist, mapped to what replaced them. Kept so an older config
# gets a migration instruction instead of "unknown key".
RENAMED_KEYS = {
    "targets": "docs",
    "results_file": "results",
    "command": "run",
    "type": "uses/run (the kind of test is now inferred)",
}


class ConfigError(Exception):
    """A configuration problem, reported with a location and a suggested fix."""

    def __init__(self, where: str, problem: str, hint: str | None = None):
        self.where = where
        self.problem = problem
        self.hint = hint
        super().__init__(f"{where}: {problem}")

    def render(self, config_path: Path | str) -> str:
        lines = [f"{config_path}: error at {self.where}", f"  problem: {self.problem}"]
        if self.hint:
            lines.append(f"  fix:     {self.hint}")
        return "\n".join(lines)


@dataclass
class Source:
    name: str
    repo: str | None = None
    ref: str = "main"
    paths: list[str] = field(default_factory=lambda: ["**"])
    auth: str | None = None
    required: bool = True

    @property
    def is_private(self) -> bool:
        return self.auth is not None

    @property
    def secret_name(self) -> str | None:
        return self.auth.split(":", 1)[1] if self.auth else None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repo": self.repo,
            "ref": self.ref,
            "required": self.required,
            "private": self.is_private,
        }


@dataclass
class Test:
    name: str
    kind: str
    uses: str | None = None
    run: str | None = None
    results: str | None = None
    setup: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    source_map: list[dict] = field(default_factory=list)
    generated: dict | None = None
    options: dict = field(default_factory=dict)
    skip_deterministically_covered: bool = True

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "kind": self.kind,
            "uses": self.uses,
            "docs": self.docs,
            "exclude": self.exclude,
            "sources": self.sources,
            "generated": self.generated,
            "skip_deterministically_covered": self.skip_deterministically_covered,
        }
        if self.source_map:
            data["source_map"] = self.source_map
        return data


@dataclass
class Reporting:
    mode: str = "check-run"
    fail_on_findings: bool = True
    on_incomplete_coverage: str = "neutral"
    title: str = "Documentation testing"
    labels: list[str] = field(default_factory=lambda: ["docs-testing"])

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "fail_on_findings": self.fail_on_findings,
            "on_incomplete_coverage": self.on_incomplete_coverage,
            "title": self.title,
            "labels": self.labels,
        }


@dataclass
class Config:
    path: Path
    docs: list[str]
    exclude: list[str]
    sources: list[Source]
    source_map: list[dict]
    reporting: Reporting
    tests: list[Test]

    @property
    def agentic_tests(self) -> list[Test]:
        return [t for t in self.tests if t.kind == AGENTIC]

    @property
    def deterministic_tests(self) -> list[Test]:
        return [t for t in self.tests if t.kind == DETERMINISTIC]

    def source(self, name: str) -> Source | None:
        return next((s for s in self.sources if s.name == name), None)

    def plan(self) -> dict:
        """The normalized run plan handed to the agent.

        The agent consumes this instead of re-parsing YAML, so config semantics
        are resolved in exactly one place.
        """
        return {
            "reporting": self.reporting.to_dict(),
            "sources": [s.to_dict() for s in self.sources],
            "source_map": self.source_map,
            "agentic_tests": [t.to_dict() for t in self.agentic_tests],
            "deterministic_tests": [t.name for t in self.deterministic_tests],
        }


# --- Helpers ----------------------------------------------------------------


def _unknown_key(key: str, allowed: set[str], where: str) -> ConfigError:
    if key in RENAMED_KEYS:
        return ConfigError(
            where,
            f"`{key}` is no longer supported",
            f"rename it to `{RENAMED_KEYS[key]}`",
        )
    close = difflib.get_close_matches(key, sorted(allowed), n=1, cutoff=0.6)
    hint = f"did you mean `{close[0]}`?" if close else f"accepted keys: {', '.join(sorted(allowed))}"
    return ConfigError(where, f"unknown key `{key}`", hint)


def _check_keys(mapping: dict, allowed: set[str], where: str) -> None:
    for key in mapping:
        if key not in allowed:
            raise _unknown_key(str(key), allowed, where)


def _as_list(value, where: str, *, what: str = "a string or list of strings") -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                raise ConfigError(where, f"expected {what}, found a {type(item).__name__} item")
        return list(value)
    raise ConfigError(where, f"expected {what}, found {type(value).__name__}")


def _as_bool(value, where: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ConfigError(where, f"expected true or false, found {value!r}")


def _require_mapping(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(where, f"expected a mapping, found {type(value).__name__}")
    return value


# --- Parsing ----------------------------------------------------------------


def _parse_source(raw, index: int) -> Source:
    where = f"sources[{index}]"
    raw = _require_mapping(raw, where)
    _check_keys(raw, SOURCE_KEYS, where)

    name = raw.get("name")
    if not isinstance(name, str) or not SOURCE_NAME_RE.match(name):
        raise ConfigError(
            where,
            f"`name` is missing or invalid ({name!r})",
            "use a short identifier such as `product` — it names the directory the "
            "source is checked out into (sources/<name>)",
        )

    repo = raw.get("repo")
    if repo is not None and (not isinstance(repo, str) or not REPO_RE.match(repo)):
        raise ConfigError(
            f"{where}.repo", f"expected `owner/name`, found {repo!r}", "for example `canonical/landscape-client`"
        )

    auth = raw.get("auth")
    if auth is not None and (not isinstance(auth, str) or not AUTH_RE.match(auth)):
        raise ConfigError(
            f"{where}.auth",
            f"expected `secret:NAME`, found {auth!r}",
            "name the GitHub secret holding a read token, e.g. `secret:SOURCE_REPO_TOKEN`; "
            "never put a token in this file",
        )

    return Source(
        name=name,
        repo=repo,
        ref=raw.get("ref") or "main",
        paths=_as_list(raw.get("paths"), f"{where}.paths") or ["**"],
        auth=auth,
        required=_as_bool(raw.get("required"), f"{where}.required", True),
    )


def _parse_source_map(raw_list, where_prefix: str, known_sources: set[str]) -> list[dict]:
    entries = []
    for index, raw in enumerate(raw_list or []):
        where = f"{where_prefix}[{index}]"
        raw = _require_mapping(raw, where)
        _check_keys(raw, SOURCE_MAP_KEYS, where)

        paths = _as_list(raw.get("paths"), f"{where}.paths")
        if not paths:
            raise ConfigError(
                f"{where}.paths",
                "at least one documentation path is required",
                "for example `paths: [\"docs/reference/cli/**\"]`",
            )

        owners = _as_list(raw.get("sources"), f"{where}.sources")
        for owner in owners:
            if owner not in known_sources:
                close = difflib.get_close_matches(owner, sorted(known_sources), n=1, cutoff=0.6)
                raise ConfigError(
                    f"{where}.sources",
                    f"`{owner}` is not declared under top-level `sources`",
                    f"did you mean `{close[0]}`?" if close else "add it to `sources:` first",
                )

        entries.append(
            {
                "area": raw.get("area") or ", ".join(paths),
                "paths": paths,
                # `sources: []` is meaningful: nothing owns this area, so it can
                # never be reported as verified.
                "sources": owners,
            }
        )
    return entries


def _parse_generated(raw, where: str) -> dict | None:
    if raw is None:
        return None
    raw = _require_mapping(raw, where)
    _check_keys(raw, GENERATED_KEYS, where)
    mode = raw.get("mode", "skip")
    if mode not in GENERATED_MODES:
        raise ConfigError(
            f"{where}.mode",
            f"unknown mode {mode!r}",
            f"use one of: {', '.join(sorted(GENERATED_MODES))}",
        )
    return {"paths": _as_list(raw.get("paths"), f"{where}.paths"), "mode": mode}


def _parse_test(raw, index: int, config_docs: list[str], config_exclude: list[str],
                known_sources: set[str]) -> Test | None:
    where = f"tests[{index}]"

    # Shorthand: `- reference-review` runs a built-in with all defaults.
    if isinstance(raw, str):
        raw = {"name": raw, "uses": raw}

    raw = _require_mapping(raw, where)
    _check_keys(raw, TEST_KEYS, where)

    if not _as_bool(raw.get("enabled"), f"{where}.enabled", True):
        return None

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(
            where,
            "`name` is required",
            "give the test a short name; it labels its findings in the report",
        )
    where = f"tests[{name}]"

    uses = raw.get("uses")
    run = raw.get("run")

    if uses and run:
        raise ConfigError(
            where,
            "a test declares either `uses` (a built-in) or `run` (your own command), not both",
            "delete whichever one you did not mean",
        )
    if not uses and not run:
        raise ConfigError(
            where,
            "the test does nothing: it has neither `uses` nor `run`",
            f"set `uses:` to a built-in ({', '.join(sorted(BUILTINS))}) or `run:` to your own command",
        )

    if uses:
        if uses not in BUILTINS:
            close = difflib.get_close_matches(uses, sorted(BUILTINS), n=1, cutoff=0.5)
            raise ConfigError(
                f"{where}.uses",
                f"unknown built-in check `{uses}`",
                f"did you mean `{close[0]}`?" if close else
                f"available built-ins: {', '.join(sorted(BUILTINS))} "
                "(run `docs-testing list` to see them)",
            )
        builtin = BUILTINS[uses]
        kind = builtin.kind
        options = _require_mapping(raw.get("with") or {}, f"{where}.with")
        allowed_with = set(builtin.required_with) | set(builtin.optional_with)
        if kind == DETERMINISTIC:
            _check_keys(options, allowed_with, f"{where}.with")
            for required in builtin.required_with:
                if not options.get(required):
                    raise ConfigError(
                        f"{where}.with",
                        f"`{required}` is required by the `{uses}` check",
                        f"add `with: {{{required}: ...}}` — see docs/reference/configuration.md",
                    )
        elif options:
            raise ConfigError(
                f"{where}.with",
                f"the `{uses}` check takes no `with:` options",
                "remove the `with:` block",
            )
    else:
        if not isinstance(run, str) or not run.strip():
            raise ConfigError(f"{where}.run", f"expected a command string, found {run!r}")
        kind = DETERMINISTIC
        options = {}

    results = raw.get("results")
    if results is not None and not isinstance(results, str):
        raise ConfigError(f"{where}.results", f"expected a file path, found {type(results).__name__}")

    sources = _as_list(raw.get("sources"), f"{where}.sources")
    for source_name in sources:
        if source_name not in known_sources:
            close = difflib.get_close_matches(source_name, sorted(known_sources), n=1, cutoff=0.6)
            raise ConfigError(
                f"{where}.sources",
                f"`{source_name}` is not declared under top-level `sources`",
                f"did you mean `{close[0]}`?" if close else "add it to `sources:` first",
            )

    docs = _as_list(raw.get("docs"), f"{where}.docs") or list(config_docs)
    if kind == AGENTIC and not docs:
        raise ConfigError(
            where,
            "no documentation is in scope for this test",
            "set a top-level `docs:` glob, or `docs:` on this test",
        )

    return Test(
        name=name,
        kind=kind,
        uses=uses,
        run=run,
        results=results,
        setup=_as_list(raw.get("setup"), f"{where}.setup"),
        docs=docs,
        exclude=_as_list(raw.get("exclude"), f"{where}.exclude") or list(config_exclude),
        # An agentic test with no explicit list may use every configured source.
        sources=sources or ([s for s in known_sources] if kind == AGENTIC else []),
        source_map=_parse_source_map(raw.get("source_map"), f"{where}.source_map", known_sources),
        generated=_parse_generated(raw.get("generated"), f"{where}.generated"),
        options=dict(options),
        skip_deterministically_covered=_as_bool(
            raw.get("skip_deterministically_covered"),
            f"{where}.skip_deterministically_covered",
            True,
        ),
    )


def _parse_reporting(raw) -> Reporting:
    if raw is None:
        return Reporting()
    raw = _require_mapping(raw, "reporting")
    _check_keys(raw, REPORTING_KEYS, "reporting")

    mode = raw.get("mode", "check-run")
    if mode not in REPORTING_MODES:
        raise ConfigError(
            "reporting.mode",
            f"unknown mode {mode!r}",
            f"use one of: {', '.join(sorted(REPORTING_MODES))}",
        )

    on_incomplete = raw.get("on_incomplete_coverage", "neutral")
    if on_incomplete not in INCOMPLETE_CONCLUSIONS:
        extra = ""
        if on_incomplete == "success":
            extra = " — unverified documentation must never conclude `success`"
        raise ConfigError(
            "reporting.on_incomplete_coverage",
            f"invalid conclusion {on_incomplete!r}{extra}",
            f"use one of: {', '.join(sorted(INCOMPLETE_CONCLUSIONS))}",
        )

    return Reporting(
        mode=mode,
        fail_on_findings=_as_bool(raw.get("fail_on_findings"), "reporting.fail_on_findings", True),
        on_incomplete_coverage=on_incomplete,
        title=raw.get("title") or "Documentation testing",
        labels=_as_list(raw.get("labels"), "reporting.labels") or ["docs-testing"],
    )


def parse(data: dict, path: Path) -> Config:
    data = _require_mapping(data, "the config file")
    _check_keys(data, TOP_LEVEL_KEYS, "top level")

    version = data.get("version")
    if version is None:
        raise ConfigError("top level", "`version` is missing", f"add `version: {CONFIG_VERSION}`")
    if version != CONFIG_VERSION:
        raise ConfigError(
            "version",
            f"unsupported config version {version!r}",
            f"this release understands version {CONFIG_VERSION}",
        )

    raw_sources = data.get("sources") or []
    if not isinstance(raw_sources, list):
        raise ConfigError("sources", f"expected a list, found {type(raw_sources).__name__}")
    sources = [_parse_source(raw, i) for i, raw in enumerate(raw_sources)]

    seen: set[str] = set()
    for source in sources:
        if source.name in seen:
            raise ConfigError(
                "sources",
                f"duplicate source name `{source.name}`",
                "each source needs a unique name; it is also its checkout directory",
            )
        seen.add(source.name)

    docs = _as_list(data.get("docs"), "docs")
    exclude = _as_list(data.get("exclude"), "exclude")
    source_map = _parse_source_map(data.get("source_map"), "source_map", seen)

    raw_tests = data.get("tests")
    if raw_tests is None:
        raise ConfigError(
            "top level",
            "`tests` is missing, so nothing would run",
            "add `tests:` with at least one entry, e.g. `tests: [reference-review]`",
        )
    if not isinstance(raw_tests, list):
        raise ConfigError("tests", f"expected a list, found {type(raw_tests).__name__}")

    tests: list[Test] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_tests):
        test = _parse_test(raw, index, docs, exclude, seen)
        if test is None:
            continue
        if test.name in names:
            raise ConfigError("tests", f"duplicate test name `{test.name}`", "give each test a unique name")
        names.add(test.name)
        tests.append(test)

    if not tests:
        raise ConfigError(
            "tests",
            "every test is disabled, so the run would verify nothing",
            "enable at least one test, or remove the workflow",
        )

    return Config(
        path=path,
        docs=docs,
        exclude=exclude,
        sources=sources,
        source_map=source_map,
        reporting=_parse_reporting(data.get("reporting")),
        tests=tests,
    )


def load(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(
            str(path),
            "configuration file not found",
            f"create `{DEFAULT_CONFIG_NAME}` with `docs-testing init`",
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}, column {mark.column + 1}" if mark else str(path)
        raise ConfigError(where, f"the file is not valid YAML: {getattr(exc, 'problem', exc)}",
                          "check indentation and quoting") from exc
    if raw is None:
        raise ConfigError(str(path), "the file is empty", f"start from `docs-testing init`")
    return parse(raw, path)


def warnings(config: Config) -> list[str]:
    """Non-fatal issues worth telling the user about."""
    notes: list[str] = []

    referenced = {name for test in config.tests for name in test.sources}
    referenced |= {name for entry in config.source_map for name in entry["sources"]}
    for source in config.sources:
        if source.name not in referenced:
            notes.append(
                f"source `{source.name}` is declared but no test or source_map entry uses it"
            )

    for test in config.deterministic_tests:
        if test.run and not test.results:
            notes.append(
                f"test `{test.name}` has no `results:` file, so only its exit status is used "
                "(that is fine for a pass/fail command, but it cannot report per-file findings)"
            )

    # Ownership only needs stating when there is more than one candidate owner.
    if len(config.sources) > 1 and not config.source_map:
        notes.append(
            "no `source_map:` is set, so every test must infer which of the "
            f"{len(config.sources)} sources owns which documentation; add one to say it "
            "explicitly"
        )

    return notes
