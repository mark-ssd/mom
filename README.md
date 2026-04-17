# mom-canvas

Draw text on your GitHub contribution graph. A CLI plus a Claude Skill.

## What it does

Give it a string like `HELLO WORLD`. It renders the text as pixel art in a
7-row × N-column grid (GitHub's contribution calendar), then materialises
the drawing as backdated empty commits in a dedicated GitHub repo. Once pushed,
the text appears on your profile graph.

**Default target:** the trailing 12-month view — what visitors see by default
on your profile. Always 52 columns of capacity. Use `--year YYYY` to target
a specific calendar-year tab instead.

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

# Recommended: authenticate via GitHub CLI
gh auth login -s repo -s delete_repo

# Then draw
mom draw "HELLO WORLD" --year 2024
```

## Requirements

- Python 3.10+
- git
- **GitHub authentication** — either:
  - **GitHub CLI (recommended):** `gh auth login -s repo -s delete_repo`. mom
    reads your session via `gh auth token` with no config of its own.
  - **Personal Access Token (fallback):** create at
    https://github.com/settings/tokens/new?scopes=repo,delete_repo then
    `mom config set-token <PAT>` (or export `GITHUB_TOKEN=<PAT>`).
- Commits use `<user-id>+<login>@users.noreply.github.com` automatically, so
  they always count toward your contribution graph regardless of your local
  `git config user.email`.

## Auth precedence

mom resolves a token in this order (first hit wins):

1. `--token` flag
2. `gh auth token` (GitHub CLI session)
3. `GITHUB_TOKEN` env var
4. `~/.config/mom/config.json` (set via `mom config set-token`)

## Commands

| Command | Purpose |
|---|---|
| `mom draw TEXT` | Trailing 12-month view (default); plan + preview + confirm + commit + push |
| `mom draw TEXT --year YYYY` | Target a specific calendar year instead |
| `mom preview TEXT [--year YYYY]` | Alias for `draw --dry-run` |
| `mom clean <state-key>` | Remove a drawing, e.g. `trailing-2026-04-16` or `calendar-2024` |
| `mom config check` | Verify auth is working |
| `mom config set-token TOKEN` | Save a PAT to config |
| `mom config show` | Print config (token redacted) |

## Character set

Printable ASCII U+0020 through U+007E (95 chars): `A-Z a-z 0-9` plus
punctuation and symbols. Lowercase renders identically to uppercase — 3×5
bitmaps are too small for meaningful case distinction.

## How capacity works

Each letter is 3 cols wide with 1-col spacing, so `required_cols = 4N - 1`
for N characters.

- **Trailing 12-month view** (default): always 52 complete weeks ending with
  the most recent completed Saturday. Fits ~13 characters.
- **Calendar year** (`--year YYYY`): 52 weeks for a past year; only the
  elapsed weeks for the current year (so less capacity early in the year).

The CLI prints the exact available capacity on a fit failure.

## Safety

- Refuses to touch any repo that doesn't have `.mom-state.json` with
  `managed_by: "mom"` — so pointing `--repo` at a real repo is a no-op.
- Force-push is used on the dedicated repo only.
- Tokens are never written to `.git/config`; they live in memory during
  pushes and in `~/.config/mom/config.json` (chmod 600) at rest.

## License

MIT.
