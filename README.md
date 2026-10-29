# 🕯 git-seance

**Ask the ghosts in your git history.** Point git-seance at any line of legacy code and a local [Gemma](https://ai.google.dev/gemma) model tells you its story, in the first person, citing the real commits that shaped it.

<!-- TODO before publishing: replace this illustrative sample with output from a real run. -->
```text
$ seance why src/app.js:214

   210 |   $scope.refresh = function () {
>> 214 |     $timeout(poll, 3000); // do not lower!
   218 |   };

3 commit(s) have touched this line.

🕯  Lighting the candles... summoning gemma4:e4b

I was born a modest 300 milliseconds in [3f1c2a9]... 

Advice from beyond: write a test before you dare to lower me.

✓ Every commit the ghost cited is real.
```

Everything runs on your machine. Your code never leaves it, and it works with the Wi-Fi off.

## Why

Every legacy codebase has lines nobody dares to touch, written by people who left years ago. The reason is usually still there, buried in commit messages nobody reads. git-seance digs it up with plain `git` and lets an open-weight model narrate it.

## Quick start (about 5 minutes)

**Requirements:** Python 3.9+, git, and [Ollama](https://ollama.com/download) v0.20 or later.

```bash
# 1. Get the model (~10 GB; use gemma4:e2b on machines with less than 16 GB RAM)
ollama pull gemma4:e4b

# 2. Install git-seance
git clone https://github.com/<your-username>/git-seance
cd git-seance
pip install -e .

# 3. Go to any git repo and summon a ghost
cd ~/some/old/project
seance why path/to/file.js:42
```

## Usage

| Command | What it does |
|---|---|
| `seance why FILE:LINE` | The ghost of one line tells its story, citing commits. |
| `seance haunt` | Lists files untouched for years and the oldest TODO/FIXME/HACK comments, each with an epitaph. |

| Option | Applies to | Default | Meaning |
|---|---|---|---|
| `--model NAME` | both | `$SEANCE_MODEL` or `gemma4:e4b` | Any Ollama model tag. |
| `--no-ai` | both | off | Show only the git evidence, no model call. |
| `--temperature N` | both | `0.7` | Lower is calmer, higher is spookier. |
| `--max-chars N` | `why` | `12000` | Maximum history sent to the model. Older commits are dropped first. |
| `--years N` | `haunt` | `3` | Minimum years untouched for a file to count as a ghost. |
| `--limit N` | `haunt` | `5` | Maximum ghosts of each kind. |

Ollama on another machine? Set `OLLAMA_HOST`, e.g. `OLLAMA_HOST=http://192.168.1.20:11434`.

## How it works

1. **Evidence, not imagination.** `git log -L<line>,<line>:<file>` returns every commit that changed that exact line, with full messages. `haunt` uses `git log --name-only`, `git grep` and `git blame`. No AI is involved in this step; run with `--no-ai` to see exactly what the model receives.
2. **The medium.** The evidence and the surrounding code go to Gemma through Ollama, with a system prompt that forbids inventing commits and requires a cited hash for every event.
3. **The skeptic.** After the story streams in, git-seance checks every hash-like token against the real commit list and warns you if the ghost made something up.

## Good repos to try

Any abandoned project with a long history works. For a properly spooky demo, try an AngularJS-era app (AngularJS reached end-of-life at the end of 2021), or any project of yours with commits older than five years.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests build a throwaway git repo with backdated commits and use a fake Ollama client, so they run without a model.

Ideas for contributions: a `seance blame-war` mode for lines rewritten back and forth, multilingual ghosts, or an editor plugin.

## License

MIT, see [LICENSE](LICENSE).

Built for [Hacktoberfest 2026](https://hacktoberfest.com/): AI belongs to everyone.
