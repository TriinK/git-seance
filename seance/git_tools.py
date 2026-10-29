"""Everything git-seance knows comes from here: plain git commands, no AI.

The AI only narrates evidence gathered by these functions, so every story
can be checked against real commits.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

COMMIT_MARKER = "=== commit "
_MARKER_RE = re.compile(r"^=== commit ([0-9a-f]{7,40}) \|", re.MULTILINE)
SECONDS_PER_YEAR = 365.25 * 24 * 3600


class GitError(RuntimeError):
    """Raised when a git command fails."""


def run_git(args: list[str], cwd: str | Path = ".") -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def ensure_repo(cwd: str | Path = ".") -> Path:
    try:
        return Path(run_git(["rev-parse", "--show-toplevel"], cwd).strip())
    except GitError as exc:
        raise GitError("Not inside a git repository. cd into one first.") from exc


# --------------------------------------------------------------------------
# `seance why`: the history of a single line
# --------------------------------------------------------------------------

@dataclass
class LineEvidence:
    path: str
    line: int
    code_context: str
    history: str
    commit_hashes: list[str]
    truncated: bool


def parse_target(target: str) -> tuple[str, int]:
    """'src/app.js:42' -> ('src/app.js', 42). Uses the last colon (Windows-safe)."""
    path, sep, line = target.rpartition(":")
    if not sep or not path or not line.isdigit() or int(line) < 1:
        raise ValueError(f"Expected FILE:LINE (e.g. src/app.js:42), got {target!r}")
    return path, int(line)


def code_context(path: str, line: int, radius: int = 4, cwd: str | Path = ".") -> str:
    file_path = Path(cwd) / path
    if not file_path.is_file():
        raise GitError(f"File not found: {path}")
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line > len(lines):
        raise GitError(f"{path} has only {len(lines)} lines")
    start, end = max(1, line - radius), min(len(lines), line + radius)
    width = len(str(end))
    out = []
    for n in range(start, end + 1):
        mark = ">>" if n == line else "  "
        out.append(f"{mark} {n:>{width}} | {lines[n - 1]}")
    return "\n".join(out)


def extract_hashes(history: str) -> list[str]:
    return _MARKER_RE.findall(history)


def line_history(path: str, line: int, cwd: str | Path = ".", max_chars: int = 12000) -> LineEvidence:
    fmt = f"%n{COMMIT_MARKER}%h | %an | %ad ===%n%s%n%b"
    history = run_git(
        ["log", f"-L{line},{line}:{path}", "--date=short", f"--format={fmt}"], cwd
    ).strip()
    if not history:
        raise GitError(f"No git history found for {path}:{line} (is the file committed?)")

    hashes = extract_hashes(history)  # from the full history, before truncation
    truncated = len(history) > max_chars
    if truncated:
        # Newest commits come first; cut at a commit boundary so no story is half-told.
        cut = history.rfind(COMMIT_MARKER, 0, max_chars)
        history = history[: cut if cut > 0 else max_chars].rstrip()
        history += "\n\n[... older commits omitted for length ...]"
        hashes = extract_hashes(history)

    return LineEvidence(
        path=path,
        line=line,
        code_context=code_context(path, line, cwd=cwd),
        history=history,
        commit_hashes=hashes,
        truncated=truncated,
    )


# --------------------------------------------------------------------------
# `seance haunt`: forgotten files and ancient TODOs
# --------------------------------------------------------------------------

@dataclass
class Ghost:
    kind: str          # "file" or "todo"
    location: str      # path, or path:line
    age_years: float
    detail: str        # last commit subject, or the TODO text


def file_last_touched(cwd: str | Path = ".") -> dict[str, tuple[int, str]]:
    """One pass over the log: path -> (unix time, subject) of its latest commit."""
    tracked = set(run_git(["ls-files"], cwd).splitlines())
    out = run_git(["log", "--format=@@%at\t%s", "--name-only"], cwd)
    last: dict[str, tuple[int, str]] = {}
    ts, subject = 0, ""
    for row in out.splitlines():
        if row.startswith("@@"):
            stamp, _, subject = row[2:].partition("\t")
            ts = int(stamp)
        elif row and row in tracked and row not in last:
            last[row] = (ts, subject)
    return last


def forgotten_files(years: float, limit: int, cwd: str | Path = ".", now: float | None = None) -> list[Ghost]:
    now = now or time.time()
    ghosts = []
    for path, (ts, subject) in file_last_touched(cwd).items():
        age = (now - ts) / SECONDS_PER_YEAR
        if age >= years:
            ghosts.append(Ghost("file", path, age, subject))
    ghosts.sort(key=lambda g: g.age_years, reverse=True)
    return ghosts[:limit]


def _blame_time(path: str, line: int, cwd: str | Path) -> int | None:
    try:
        out = run_git(["blame", "--porcelain", f"-L{line},{line}", "--", path], cwd)
    except GitError:
        return None
    for row in out.splitlines():
        if row.startswith("author-time "):
            return int(row.split()[1])
    return None


def ancient_todos(limit: int, cwd: str | Path = ".", max_scan: int = 150, now: float | None = None) -> list[Ghost]:
    now = now or time.time()
    try:
        out = run_git(["grep", "-n", "-I", "-w", "-E", "TODO|FIXME|HACK|XXX"], cwd)
    except GitError:
        return []  # git grep exits 1 when nothing matches
    ghosts = []
    for row in out.splitlines()[:max_scan]:
        path, _, rest = row.partition(":")
        line, _, text = rest.partition(":")
        if not line.isdigit():
            continue
        ts = _blame_time(path, int(line), cwd)
        if ts is None:
            continue
        ghosts.append(Ghost("todo", f"{path}:{line}", (now - ts) / SECONDS_PER_YEAR, text.strip()[:160]))
    ghosts.sort(key=lambda g: g.age_years, reverse=True)
    return ghosts[:limit]
