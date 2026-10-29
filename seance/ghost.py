"""The medium: turns git evidence into ghost stories with a local Gemma model."""

from __future__ import annotations

import re
import sys
from typing import Iterable

from .git_tools import Ghost, LineEvidence

DEFAULT_MODEL = "gemma4:e4b"

SYSTEM_PROMPT = """You are the ghost that haunts a piece of old source code.
You speak in the first person, eerie but warm, like a spirit at a seance who
remembers everything that happened to this code.

Hard rules:
- Use ONLY the git history and code you are given. Never invent commits,
  authors, dates or reasons.
- When you mention an event, cite its short commit hash in brackets, e.g. [a1b2c3d].
- If the history does not explain WHY something was done, say the reason was
  lost to time. Do not guess and present it as fact.
- End with one line starting with "Advice from beyond:" giving a concrete,
  practical tip for the living developer (keep it, test it, rename it, delete it...).
- Keep the whole story under 250 words."""

HAUNT_PROMPT = """You are the caretaker of a codebase graveyard.
For each ghost below, write ONE short epitaph line (max 25 words) in the format:
[n] Here lies <what it is> ... <why it was forgotten or what it still whispers>.
Base every epitaph only on the details given. Do not invent history.
After the list, add one line starting with "Advice from beyond:" suggesting
which ghost the living should deal with first, and why."""

_HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def build_why_messages(ev: LineEvidence) -> list[dict]:
    note = " (older commits were omitted for length)" if ev.truncated else ""
    user = (
        f"File: {ev.path}, line {ev.line}.\n\n"
        f"The code around it (the haunted line is marked >>):\n{ev.code_context}\n\n"
        f"Its complete git history, newest first{note}:\n{ev.history}\n\n"
        "Tell the story of this line."
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def build_haunt_messages(ghosts: list[Ghost]) -> list[dict]:
    rows = []
    for n, g in enumerate(ghosts, 1):
        if g.kind == "file":
            rows.append(f"[{n}] FILE {g.location}, untouched for {g.age_years:.1f} years. Last commit: {g.detail!r}")
        else:
            rows.append(f"[{n}] TODO at {g.location}, written {g.age_years:.1f} years ago: {g.detail!r}")
    return [
        {"role": "system", "content": HAUNT_PROMPT},
        {"role": "user", "content": "The ghosts:\n" + "\n".join(rows)},
    ]


def unknown_citations(text: str, known_hashes: Iterable[str]) -> list[str]:
    """Hash-like tokens in the story that don't match any real commit.

    A token counts as a citation only if it contains a digit (so words like
    'defaced' are ignored) and matches a known hash by prefix in either direction.
    """
    known = list(known_hashes)
    bad = []
    for token in _HASH_RE.findall(text.lower()):
        if not any(c.isdigit() for c in token):
            continue
        if not any(k.startswith(token) or token.startswith(k) for k in known):
            if token not in bad:
                bad.append(token)
    return bad


def _connect_errors() -> type[Exception]:
    """httpx (used by ollama) raises its own ConnectError in streaming mode."""
    try:
        import httpx
        return httpx.ConnectError
    except ImportError:  # pragma: no cover
        return ConnectionError


def summon(messages: list[dict], model: str, temperature: float = 0.7, out=sys.stdout) -> str:
    """Stream Gemma's answer to the terminal and return the full text."""
    try:
        import ollama
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The 'ollama' Python package is missing: pip install ollama") from exc

    parts: list[str] = []
    try:
        stream = ollama.chat(model=model, messages=messages, stream=True,
                             options={"temperature": temperature})
        for chunk in stream:
            piece = chunk["message"]["content"]
            parts.append(piece)
            out.write(piece)
            out.flush()
    except ollama.ResponseError as exc:
        if getattr(exc, "status_code", None) == 404:
            raise RuntimeError(f"Model '{model}' is not downloaded. Run: ollama pull {model}") from exc
        raise RuntimeError(f"Ollama error: {exc}") from exc
    except (ConnectionError, OSError, _connect_errors()) as exc:
        raise RuntimeError("Can't reach Ollama. Is it running? Start it with: ollama serve") from exc
    out.write("\n")
    return "".join(parts)
