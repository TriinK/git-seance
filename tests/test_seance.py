import os
import subprocess
import sys
import types

import pytest

from seance import cli, git_tools
from seance.ghost import build_why_messages, unknown_citations


def git(repo, *args, date=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.com",
           "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.com"}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q")
    (tmp_path / "app.js").write_text("var a = 1;\nvar timeout = 300; // TODO tune this\n")
    (tmp_path / "old.js").write_text("// legacy helper\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Initial AngularJS app", date="2015-03-01T10:00:00")
    (tmp_path / "app.js").write_text("var a = 1;\nvar timeout = 3000; // TODO tune this\n")
    git(tmp_path, "commit", "-qam", "Raise timeout: IE8 too slow", date="2016-06-01T10:00:00")
    (tmp_path / "new.js").write_text("// fresh\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Add new file")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_parse_target():
    assert git_tools.parse_target("src/app.js:42") == ("src/app.js", 42)
    assert git_tools.parse_target(r"C:\code\app.js:7") == (r"C:\code\app.js", 7)
    for bad in ["app.js", "app.js:", "app.js:0", ":5", "app.js:x"]:
        with pytest.raises(ValueError):
            git_tools.parse_target(bad)


def test_line_history(repo):
    ev = git_tools.line_history("app.js", 2)
    assert len(ev.commit_hashes) == 2
    assert "IE8 too slow" in ev.history
    assert ">> 2 | var timeout = 3000;" in ev.code_context
    msgs = build_why_messages(ev)
    assert ev.commit_hashes[0] in msgs[1]["content"]


def test_truncation_keeps_whole_commits(repo):
    ev = git_tools.line_history("app.js", 2, max_chars=120)
    assert ev.truncated
    assert len(ev.commit_hashes) == 1
    assert "omitted" in ev.history


def test_unknown_citations():
    known = ["a1b2c3d", "0f9e8d7"]
    text = "I was born in [a1b2c3d], changed in [0f9e8d7c55], then [deadbee1] lied. Defaced cafebabe."
    assert unknown_citations(text, known) == ["deadbee1"]


def test_haunt_finds_old_files_and_todos(repo):
    files = git_tools.forgotten_files(years=3, limit=5)
    assert [g.location for g in files] == ["old.js", "app.js"]
    todos = git_tools.ancient_todos(limit=5)
    assert todos[0].location == "app.js:2" and todos[0].age_years > 9


def test_cli_why_with_fake_model(repo, monkeypatch, capsys):
    real = git_tools.line_history("app.js", 2).commit_hashes
    fake = types.SimpleNamespace(
        ResponseError=type("ResponseError", (Exception,), {}),
        chat=lambda **kw: iter([{"message": {"content": f"I was changed in [{real[0]}] "}},
                                {"message": {"content": "and in [1234abcd]."}}]),
    )
    monkeypatch.setitem(sys.modules, "ollama", fake)
    assert cli.main(["why", "app.js:2"]) == 0
    out = capsys.readouterr().out
    assert "1234abcd" in out and "don't exist" in out


def test_cli_errors_are_friendly(repo, capsys):
    assert cli.main(["why", "missing.js:1", "--no-ai"]) == 1
    assert "seance:" in capsys.readouterr().err
