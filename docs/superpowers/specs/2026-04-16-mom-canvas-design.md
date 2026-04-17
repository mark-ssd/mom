# mom-canvas — Design Spec

**Date:** 2026-04-16
**Status:** Draft (awaiting review)
**Owner:** mark-ssd (aveyurov@gmail.com)
**Repo:** `github.com/mark-ssd/mom`

## 1. Goal

Let a user write text on their GitHub contribution graph by invoking a CLI — or, equivalently, by asking Claude via a Skill — with a single input string. The tool validates whether the text fits the chosen year and, on confirmation, materialises the drawing as backdated commits in a dedicated GitHub repository.

## 2. Deliverables

Two things ship from one repo:

1. **`mom` CLI** — a Python 3.10+ package (PyPI name: `mom-canvas`, binary: `mom`) installable via `pipx install mom-canvas` or `pipx install git+https://github.com/mark-ssd/mom`.
2. **`mom-canvas` Claude Skill** — a thin orchestration layer that wraps the CLI so users can invoke `/mom-canvas TEXT` in Claude and have Claude handle install, auth, preview, and confirmation conversationally.

## 3. User Flows

### 3.1 CLI (standalone)

```
$ mom draw "HELLO WORLD" --year 2024
Target:  github.com/mark-ssd/mom-canvas (year 2024, 52 weeks available)
Text:    "HELLO WORLD" (11 chars × 3 cols + 10 spacings = 43 cols; fits)
Commits: 2240 commits across 112 dates at max intensity (20 commits/cell)

Preview (rows = Sun..Sat, · = empty, █ = on):
        Jan  Feb  Mar  ...
Sun  ·························
Mon  ···█·█·█·█·█·█···█···█···
...
Proceed? [y/N]: y
Done. View at https://github.com/mark-ssd/mom-canvas/graphs/contribution-activity
```

### 3.2 Claude Skill

1. User (one-time): *"install the mom-canvas skill from https://github.com/mark-ssd/mom"* → Claude reads `README.md`, clones the repo, copies `skill/SKILL.md` to `~/.claude/skills/mom-canvas/`, runs `pipx install` on the package.
2. User: `/mom-canvas HELLO WORLD` → Claude follows `SKILL.md`, bootstraps CLI if missing, prompts for PAT if missing, runs `mom draw --dry-run`, shows preview, asks confirm, runs `mom draw --yes`, reports result.

## 4. Architecture

### 4.1 Repository layout

```
mom/                            # github.com/mark-ssd/mom
├── pyproject.toml              # project metadata (PyPI name: mom-canvas)
├── README.md                   # install docs (human + Claude-readable)
├── src/mom/
│   ├── __init__.py
│   ├── cli.py                  # Typer entrypoint; installed as binary `mom`
│   ├── font.py                 # Tom Thumb 3×5 bitmap, full printable ASCII
│   ├── layout.py               # pure: text + year + today → Canvas
│   ├── preview.py              # Canvas → ASCII string
│   ├── config.py               # ~/.config/mom/config.json + auth resolution
│   ├── gh.py                   # GitHub REST: ensure_repo, verify_token, verify_email
│   └── git_ops.py              # clone, orphan-reset, backdated commits, force-push
├── skill/
│   └── SKILL.md                # runtime instructions for Claude
├── tests/                      # pytest
└── docs/superpowers/specs/     # this file
```

### 4.2 Module responsibilities

| Module | Responsibility | Purity |
|---|---|---|
| `cli` | Parse argv, orchestrate, print, prompt. Owns nothing else. | Impure (I/O) |
| `font` | Static glyph table. Raises `UnsupportedCharError` on missing char. | Pure |
| `layout` | `plan(text, year, today, intensity) -> Canvas \| Fit(ok=False)`. | Pure |
| `preview` | `render(canvas) -> str`. | Pure |
| `config` | Load/save `~/.config/mom/config.json`. Resolve auth precedence. | Impure (fs) |
| `gh` | GitHub REST calls via `requests`. | Impure (net) |
| `git_ops` | Local git tree management. | Impure (fs + net) |

### 4.3 Data flow (draw command)

```
argv → cli.parse
     → config.resolve_auth             (token from --token > env > file > gh-cli)
     → gh.verify_token                 (GET /user; check scopes)
     → gh.verify_email                 (GET /user/emails; match git config)
     → layout.plan                     (pure, returns Canvas or Fit-fail)
     → preview.render                  (ASCII string)
     → if not --yes: prompt user y/N
     → gh.ensure_repo                  (create if 404)
     → git_ops.rebuild                 (clone, orphan, commit all state, force-push)
     → cli.print_success
```

Layout is pure — it can be tested exhaustively without network or git. Side-effect modules run only after the user confirms (or `--yes`).

## 5. Fit Algorithm & Font

### 5.1 Font

- **Source:** Tom Thumb by Robey Pointer (CC0). 3 cols wide × 5 rows tall. Covers printable ASCII U+0020–U+007E (95 glyphs).
- **Encoding:** shipped as a Python literal `GLYPHS: dict[str, tuple[tuple[bool, ...], ...]]` (5 rows, 3 cols each). Generated offline from the BDF source; build step not required at runtime.
- **Unsupported chars:** raise `UnsupportedCharError(char)` and surface *"Character 'x' not supported. Allowed: printable ASCII (0x20–0x7E)."* from the CLI.

### 5.2 Grid coordinate system

- Rows 0–6 map to Sun, Mon, Tue, Wed, Thu, Fri, Sat.
- Font occupies rows **1–5** (Mon–Fri). Rows 0 (Sun) and 6 (Sat) stay empty for vertical margin.
- Columns = calendar weeks, Sunday-anchored.

### 5.3 Drawable columns (capacity)

For year `Y` and current date `today`:

```python
grid_start = sunday_on_or_before(date(Y, 1, 1))
usable_weeks = []
for week_idx in range(54):
    sun = grid_start + timedelta(weeks=week_idx)
    mon, fri, sat = sun + td(1), sun + td(5), sun + td(6)
    if mon.year != Y or fri.year != Y:
        continue                      # skip partial weeks on year boundaries
    if Y == today.year and sat > today:
        break                         # current-year cutoff (week must have ended)
    usable_weeks.append(week_idx)
```

Results:
- **Past years:** ~52 usable cols (precisely, weeks whose Mon–Fri all fall in year Y).
- **Current year:** only weeks whose Saturday ≤ today.
- **Future years:** `usable_weeks == []` → fit fails.

### 5.4 Width and fit check

```
required_cols = 4 * len(text) - 1       # 3-col glyph + 1-col spacing between
fit.ok        = required_cols <= len(usable_weeks)
```

On fail, output includes both numbers and a suggestion (different year, shorter text).

### 5.5 Centering

```
pad       = (len(usable_weeks) - required_cols) // 2
start_col = usable_weeks[pad]
```

Text sits centered in the usable window.

### 5.6 Pixel → date → commit count

For each glyph pixel `(r, c)` that is True:

```python
date  = grid_start + timedelta(weeks=c, days=r)
count = intensity_to_commits[intensity]   # {1:5, 2:10, 3:15, 4:20}
```

The `Canvas` dataclass is the handoff:

```python
@dataclass
class Canvas:
    year: int
    cells: list[tuple[date, int]]      # (date, commit_count)
    width_cols: int                     # for preview rendering
    grid_start: date                    # Sunday anchor
    usable_week_indices: list[int]      # for preview window markers
    intensity: int                      # 1..4
    text: str                           # echoed back for preview header
```

## 6. CLI Surface

### 6.1 Commands

| Command | Purpose |
|---|---|
| `mom draw TEXT [opts]` | Main verb. Plan + preview + confirm + commit + push. |
| `mom preview TEXT [opts]` | Alias for `draw --dry-run`. |
| `mom clean --year YYYY` | Remove year's drawing from state, rebuild. |
| `mom config check` | Exit 0 if auth resolvable + repo reachable. |
| `mom config set-token TOKEN` | Persist PAT to config file. |
| `mom config show` | Print config (token redacted). |
| `mom --version` | Print version. |

### 6.2 `draw` flags

| Flag | Default | Purpose |
|---|---|---|
| `--year YYYY` | current year | Target calendar year. |
| `--repo NAME` | `mom-canvas` (or config) | Dedicated repo name. |
| `--yes / -y` | false | Skip y/N confirm. |
| `--dry-run` | false | Preview + fit check only. No git, no API. |
| `--format text\|json` | `text` | Human vs. machine output. |
| `--intensity 1-4` | 4 | Commit count per on-cell (see §5.6). |
| `--token TOKEN` | — | Inline PAT override. |

### 6.3 `--format json` output

```json
{
  "status": "preview" | "success" | "error",
  "fit": {"ok": true, "required_cols": 43, "available_cols": 52, "year": 2024},
  "commits": {"total": 2240, "date_range": ["2024-01-08", "2024-12-27"]},
  "preview_ascii": "…",
  "repo_url": "https://github.com/mark-ssd/mom-canvas",
  "error": null | {"code": 3, "kind": "fit_fail", "message": "…"}
}
```

### 6.4 Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic/unexpected |
| 2 | Usage error (bad flags, unsupported char, future year) |
| 3 | Fit failure |
| 4 | Auth failure (missing/invalid PAT, email mismatch) |
| 5 | Network / GitHub API / push failure |

### 6.5 Config file

Path: `~/.config/mom/config.json` (respects `$XDG_CONFIG_HOME`). Chmod `0600` on write.

```json
{
  "repo": "mom-canvas",
  "github_user": "mark-ssd",
  "token": "ghp_…"                    // only if set via `config set-token`
}
```

Auth precedence (highest wins): `--token` flag → `GITHUB_TOKEN` env → config file → `gh auth token`. First hit that produces a working `GET /user` response is used.

## 7. Commit & Reset Mechanics

### 7.1 Dedicated-repo model

The repo owned by the tool contains:

```
main branch:
├── README.md              # static: explains this repo
└── .mom-state.json        # source of truth
```

All drawings are encoded in `.mom-state.json`; each rebuild regenerates the commit history deterministically from it.

**State file:**

```json
{
  "managed_by": "mom",
  "version": 1,
  "drawings": {
    "2024": {"text": "HELLO WORLD", "intensity": 4, "updated_at": "2024-05-12T11:02:00Z"},
    "2025": {"text": "HI",          "intensity": 4, "updated_at": "2025-01-03T09:40:00Z"}
  }
}
```

### 7.2 Empty-commit strategy

Each "on" pixel produces N `git commit --allow-empty` commits with backdated `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` set to `<date>T12:00:00Z`. Empty commits count on the contribution graph and avoid file churn. `N = intensity_to_commits[intensity]` (default 20 at level 4).

### 7.3 `rebuild` algorithm

```
1.  ensure_local_clone(repo_dir, remote_url)
2.  state = read_state(repo_dir) or empty_state()
3.  refuse_if_not_ours(repo_dir)           # .mom-state.json must have managed_by == "mom"
4.  state["drawings"][str(year)] = {text, intensity, updated_at: now}   # or delete for `clean`
5.  canvases = [layout.plan(d["text"], int(y), today, d["intensity"]) for y, d in state.drawings.items()]
6.  git checkout --orphan _build
7.  git rm -rf .
8.  write README.md; write .mom-state.json
9.  git add .; git commit -m "rebuild" --date=<min_date - 1 day>
10. for (date, count) in flatten_chronologically(canvases):
        for i in range(count):
            GIT_AUTHOR_DATE=<date>T12:00:00Z GIT_COMMITTER_DATE=<date>T12:00:00Z \
                git commit --allow-empty -m "canvas <date> #<i+1>"
11. git branch -D main; git branch -M _build main
12. git push --force origin main
```

Step 3 is the **safety latch**: if the repo exists but lacks `.mom-state.json` with `managed_by == "mom"`, the tool refuses to touch it. This protects a user who accidentally points `--repo` at a real repo.

### 7.4 Force-push rationale

The dedicated repo's sole purpose is rendering; its history has no external consumers. Force-push is the correct move and is safe because:
- The tool owns the repo.
- State is deterministically regenerable from `.mom-state.json`.
- The `_build` temp branch is renamed to `main` only after all commits succeed, so a crash mid-build never corrupts `main`.

### 7.5 GitHub API calls

| Operation | Endpoint | When |
|---|---|---|
| Verify token | `GET /user` | first thing each run; fail fast on 401 |
| Verify email | `GET /user/emails` — match `git config user.email` | pre-flight; warn if no match |
| Repo lookup | `GET /repos/{user}/{repo}` | decide create vs. reuse |
| Repo create | `POST /user/repos` `{name, private:false, auto_init:false}` | only if 404 |

HTTPS push uses `https://x-access-token:<TOKEN>@github.com/<user>/<repo>.git` — token held in memory only, never written to `.git/config`. Fallback: `gh auth setup-git` delegates to the `gh` CLI's credentials.

### 7.6 Commit author identity

- Uses `git config --global user.name` + `user.email`.
- Pre-flight: `user.email` must match one of the verified emails on the GitHub account (via `GET /user/emails`). If not, abort with *"Commits authored as X won't count for Y. Set `git config user.email` to a GitHub-verified email and retry."*
- The tool does NOT modify git config automatically — that's a user decision.

## 8. Claude Skill (`mom-canvas`)

### 8.1 `skill/SKILL.md`

Frontmatter:

```yaml
---
name: mom-canvas
description: Draw text on the user's GitHub contribution graph. Use when user
  invokes /mom-canvas <text>, or asks to "write/draw text on my GitHub graph".
  Creates/updates a dedicated GitHub repo with backdated empty commits forming
  pixel-art letters in the 7-row contribution grid. Full ASCII supported,
  auto-centered, validates fit against year capacity.
---
```

Body — step-ordered instructions for Claude:

1. **Parse input.** Extract `TEXT` and optional `--year YYYY`.
2. **Ensure CLI installed.** `command -v mom && mom --version`; if missing, `pipx install git+https://github.com/mark-ssd/mom`, retry.
3. **Ensure auth configured.** `mom config check --format json`. If `error.kind == "auth_missing"`, ask user for PAT with `repo` scope (link to `https://github.com/settings/tokens/new?scopes=repo&description=mom-canvas`), then `mom config set-token <token>`. If `error.kind == "email_mismatch"`, surface error and stop — user must fix git config themselves.
4. **Preview + fit.** `mom draw "$TEXT" --year $YEAR --dry-run --format json`. If `fit.ok == false`, surface preview + error and stop. Otherwise show `preview_ascii` in a code fence, summarise commits/dates, ask for explicit yes.
5. **Execute.** On yes: `mom draw "$TEXT" --year $YEAR --yes --format json`. Report `repo_url` on success; surface `error.message` + code on failure.

**Safety notes in SKILL.md:**
- Always pass `TEXT` as a single argv element; never interpolate into a shell.
- Always use `--format json` from this skill.
- For removal, suggest `mom clean --year YYYY`; run only after confirmation.

### 8.2 `README.md` (bootstrap doc for Claude-out-of-context)

Tells Claude how to install on first request:

1. `git clone https://github.com/mark-ssd/mom /tmp/mom-install`
2. `mkdir -p ~/.claude/skills/mom-canvas && cp /tmp/mom-install/skill/SKILL.md ~/.claude/skills/mom-canvas/`
3. `pipx install /tmp/mom-install` (or `pipx install mom-canvas` once PyPI-published)
4. `mom --version` to confirm.

## 9. Error Handling

Every error maps to a stable `(exit_code, kind)` pair surfaced both in human text and `--format json`:

| Kind | Exit | Message template |
|---|---|---|
| `unsupported_char` | 2 | `Character '…' not supported. Allowed: printable ASCII (0x20–0x7E).` |
| `fit_fail` | 3 | `Doesn't fit. Required N cols, available M for year Y. Max text: ~K chars. Try different --year or shorter text.` |
| `future_year` | 2 | `Year … hasn't happened yet — no drawable weeks.` |
| `auth_missing` | 4 | `No GitHub token found. Set GITHUB_TOKEN, pass --token, or run 'mom config set-token'.` |
| `auth_invalid` | 4 | `PAT rejected (401). Regenerate at github.com/settings/tokens with 'repo' scope.` |
| `auth_scope` | 4 | `Token lacks 'repo' scope. Re-issue with that scope.` |
| `email_mismatch` | 4 | `git config user.email 'x@y' isn't verified on your GitHub account — commits won't count. Fix then retry.` |
| `not_our_repo` | 1 | `Repo '…' isn't managed by mom (no .mom-state.json). Refusing to touch it. Pick a different --repo.` |
| `network` | 5 | `Network error: …. Local commits kept; rerun to retry.` |
| `push_rejected` | 5 | `Push rejected (branch protection?). Disable protection on the dedicated repo.` |

## 10. Testing Strategy

TDD per superpowers test-driven-development skill. Each layer has a clear test approach:

| Layer | Approach |
|---|---|
| `font` | Sanity: every ASCII printable char has a 5×3 glyph. |
| `layout` | Pure unit tests with pinned `today`. Cases: 1-char fit, exact-fit, off-by-one overflow, year-boundary (2024→2025), leap year (2024 has 53 weeks), current-year partial capacity, future-year rejection, unsupported char. |
| `preview` | Golden-file test: known canvas → known ASCII string. |
| `config` | Temp `$XDG_CONFIG_HOME`; round-trip write/read; auth-precedence order. |
| `gh` | `responses` library mocks; cover 200/404/401/403/422/5xx. |
| `git_ops` | Tmp-dir integration: init bare repo as "origin", run rebuild, assert `git log` dates match expected cells. |
| `cli` | `typer.testing.CliRunner`; `--dry-run --format json` round-trip; `clean` state mutation. |
| End-to-end | `@pytest.mark.live` — pushes to a throwaway repo on a sandbox GitHub account. Opt-in, skipped in CI. |

**Coverage targets:** >90% on pure modules (`font`, `layout`, `preview`, `config`), >70% on impure (`gh`, `git_ops`).

## 11. Distribution

- **Repo:** `github.com/mark-ssd/mom` (public).
- **PyPI:** publish as `mom-canvas`. Version 0.1.0 at first release. Until publish, install via `pipx install git+https://github.com/mark-ssd/mom`.
- **Skill:** copied from `skill/SKILL.md` into `~/.claude/skills/mom-canvas/SKILL.md` during install.

## 12. Out of Scope (for v1)

- Multi-line text (only one horizontal line of text per year).
- Non-ASCII characters (Unicode, emoji).
- Custom glyphs / user-supplied fonts.
- Animation or scheduled redraws over time.
- Undo of individual year drawings without force-push (use `mom clean --year YYYY`).
- Integration with private-only contribution visibility settings (the dedicated repo is public by design).

## 13. Open Questions / TODOs

- None blocking. Owner confirmed (`mark-ssd/mom`), package name (`mom-canvas`), repo name (`mom-canvas`), font (Tom Thumb 3×5), and all UX decisions.
- Publication to PyPI is post-v1; first-release install path is `pipx install git+https://github.com/mark-ssd/mom`.
