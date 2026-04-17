# mom-canvas

Draw text on your GitHub contribution graph. A CLI plus a Claude Skill.

## What it does

Give it a string like `HELLO WORLD`. It renders the text as pixel art in a
7-row × N-column grid (GitHub's contribution calendar), then materialises
the drawing as backdated empty commits in a dedicated GitHub repo. Once pushed,
the text appears on your profile graph.

## Install (with Claude)

Ask Claude:

> install the mom-canvas skill from https://github.com/mark-ssd/mom

Claude will:
1. `git clone https://github.com/mark-ssd/mom /tmp/mom-install`
2. Copy `/tmp/mom-install/skill/SKILL.md` to `~/.claude/skills/mom-canvas/SKILL.md`
3. Install the CLI with `pipx install /tmp/mom-install`
4. Verify with `mom --version`

Then invoke anytime:

    /mom-canvas HELLO WORLD

Claude will handle the first-run PAT prompt, show you the preview, and
ask for confirmation before committing anything.

## Install (CLI-only, no Claude)

```bash
pipx install git+https://github.com/mark-ssd/mom
mom config set-token ghp_your_personal_access_token
mom draw "HELLO WORLD" --year 2024
```

## Requirements

- Python 3.10+
- git
- A GitHub Personal Access Token with `repo` scope
- `git config --global user.email` must be one of your verified GitHub emails
  (otherwise commits don't count toward your contribution graph)

## Commands

| Command | Purpose |
|---|---|
| `mom draw TEXT --year YYYY` | Plan + preview + confirm + commit + push |
| `mom preview TEXT --year YYYY` | Alias for `draw --dry-run` |
| `mom clean --year YYYY` | Remove a year's drawing |
| `mom config check` | Verify auth is working |
| `mom config set-token TOKEN` | Save a PAT to config |
| `mom config show` | Print config (token redacted) |

## Character set

Printable ASCII U+0020 through U+007E (95 chars): `A-Z a-z 0-9` plus
punctuation and symbols. Lowercase renders identically to uppercase — 3×5
bitmaps are too small for meaningful case distinction.

## How capacity works

Each letter is 3 cols wide with 1-col spacing, so `required_cols = 4N - 1`
for N characters. The GitHub year view has ~52 usable columns for past
years and fewer for the current year (only weeks whose Saturday has already
passed count). The CLI prints the exact available capacity on a fit failure.

## Safety

- Refuses to touch any repo that doesn't have `.mom-state.json` with
  `managed_by: "mom"` — so pointing `--repo` at a real repo is a no-op.
- Force-push is used on the dedicated repo only.
- Tokens are never written to `.git/config`; they live in memory during
  pushes and in `~/.config/mom/config.json` (chmod 600) at rest.

## License

MIT.
