"""git-seance: ask the ghosts in your git history what happened.

  seance why src/app.js:42     the ghost of one line tells its story
  seance haunt                 a graveyard of forgotten files and ancient TODOs
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .ghost import DEFAULT_MODEL, build_haunt_messages, build_why_messages, summon, unknown_citations
from .git_tools import GitError, ancient_todos, ensure_repo, forgotten_files, line_history, parse_target

DIM, PURPLE, YELLOW, RESET = "\033[2m", "\033[35m", "\033[33m", "\033[0m"


def _c(code: str, text: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


def cmd_why(args: argparse.Namespace) -> int:
    ensure_repo()
    path, line = parse_target(args.target)
    ev = line_history(path, line, max_chars=args.max_chars)

    print(_c(DIM, ev.code_context))
    print(_c(DIM, f"\n{len(ev.commit_hashes)} commit(s) have touched this line."))

    if args.no_ai:
        print("\n" + ev.history)
        return 0

    print(_c(PURPLE, f"\n🕯  Lighting the candles... summoning {args.model}\n"))
    story = summon(build_why_messages(ev), model=args.model, temperature=args.temperature)

    bad = unknown_citations(story, ev.commit_hashes)
    if bad:
        print(_c(YELLOW, f"\n⚠  The ghost mentioned commits that don't exist here: {', '.join(bad)}. "
                         "Don't trust those parts."))
    else:
        print(_c(DIM, "\n✓ Every commit the ghost cited is real."))
    return 0


def cmd_haunt(args: argparse.Namespace) -> int:
    ensure_repo()
    print(_c(DIM, "Walking the graveyard..."))
    ghosts = forgotten_files(args.years, args.limit) + ancient_todos(args.limit)
    if not ghosts:
        print(f"No ghosts older than {args.years} years. This codebase rests in peace.")
        return 0

    for n, g in enumerate(ghosts, 1):
        label = "📄" if g.kind == "file" else "📝"
        print(_c(DIM, f"[{n}] {label} {g.location}  ({g.age_years:.1f} y)  {g.detail}"))

    if args.no_ai:
        return 0

    print(_c(PURPLE, f"\n🪦 Reading the epitaphs... summoning {args.model}\n"))
    summon(build_haunt_messages(ghosts), model=args.model, temperature=args.temperature)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="seance", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"git-seance {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", default=os.environ.get("SEANCE_MODEL", DEFAULT_MODEL),
                        help=f"Ollama model (default: $SEANCE_MODEL or {DEFAULT_MODEL})")
    common.add_argument("--temperature", type=float, default=0.7)
    common.add_argument("--no-ai", action="store_true",
                        help="only show the git evidence, don't summon the model")

    sub = p.add_subparsers(dest="command", required=True)
    why = sub.add_parser("why", parents=[common], help="tell the story of one line")
    why.add_argument("target", help="FILE:LINE, e.g. src/app.js:42")
    why.add_argument("--max-chars", type=int, default=12000,
                     help="max characters of history sent to the model (default 12000)")
    why.set_defaults(func=cmd_why)

    haunt = sub.add_parser("haunt", parents=[common], help="list forgotten files and ancient TODOs")
    haunt.add_argument("--years", type=float, default=3.0,
                       help="minimum years untouched for a file to count (default 3)")
    haunt.add_argument("--limit", type=int, default=5, help="max ghosts per kind (default 5)")
    haunt.set_defaults(func=cmd_haunt)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (GitError, ValueError, RuntimeError) as exc:
        print(f"seance: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nThe spirits withdraw.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
