---
name: mom-canvas
description: Draw text on the user's GitHub contribution graph. Use when user
  invokes /mom-canvas <text>, or asks to "write/draw text on my GitHub graph".
  Creates/updates a dedicated GitHub repo with backdated empty commits forming
  pixel-art letters in the 7-row contribution grid. Full ASCII supported,
  auto-centered, validates fit against the window's capacity.
---

# mom-canvas

User invokes as `/mom-canvas TEXT [--year YYYY]`. Execute steps IN ORDER.
Any non-zero exit halts the flow — surface the error, do NOT proceed.

## Step 1 — Parse input
Extract TEXT (required, everything up to `--year`). Extract `--year YYYY`
(optional).

**Default window:** If no `--year` is given, the CLI targets the **trailing
12-month view** — this is what visitors see on the user's profile by default
(the "N contributions in the last year" panel). It always has 52 usable columns.

With `--year YYYY`, the CLI targets that specific calendar year tab on the
profile instead. Current year has reduced capacity (only elapsed weeks).

## Step 2 — Ensure CLI is installed
Run: `command -v mom >/dev/null 2>&1 && mom --version`

If the command fails:
1. Tell user: "Installing the mom CLI (one-time setup)…"
2. Run: `pipx install git+https://github.com/mark-ssd/mom`
3. Retry `mom --version`. If still failing, surface the install error and STOP.

## Step 3 — Ensure auth is configured
Run: `mom config check --format json`

Parse the JSON:
- `status == "ok"` → proceed to Step 4.
- `error.kind == "auth_missing"`:
    1. Ask user: "I need a GitHub Personal Access Token with `repo` scope.
       Create one at
       https://github.com/settings/tokens/new?scopes=repo&description=mom-canvas
       and paste it here. It'll be saved to ~/.config/mom/config.json
       (chmod 600; never sent anywhere else)."
    2. Once user pastes, run: `mom config set-token <TOKEN>` (pass token as argv, not interpolated into a shell string).
    3. Re-run `mom config check --format json`. Proceed if ok; otherwise surface error.
- `error.kind == "auth_invalid"` or `"auth_scope"`: surface the error
    message verbatim, tell the user to regenerate the PAT with `repo`
    scope, and STOP.
- `error.kind == "email_mismatch"`: surface the error verbatim and STOP.
    The user must fix `git config user.email` themselves — do NOT auto-edit git config.

## Step 4 — Preview + fit check
Run: `mom draw "$TEXT" --year $YEAR --dry-run --format json`

Parse JSON:
- `fit.ok == false`:
    1. Show the user the `preview_ascii` block in a ```` ``` ```` code fence.
    2. Show the `error.message` (which includes required/available cols and max-char suggestion).
    3. STOP.
- `fit.ok == true`:
    1. Show `preview_ascii` verbatim in a ```` ``` ```` code fence.
    2. Summarize: "N commits across M dates on year Y. Proceed?"
    3. Wait for explicit yes. Do NOT proceed without it.

## Step 5 — Execute
On confirmation, run: `mom draw "$TEXT" --year $YEAR --yes --format json`

Parse JSON:
- `status == "success"`: tell user: "Done. View your canvas at `<repo_url>`.
    The contribution graph updates within a few minutes."
- `status == "error"`: surface `error.message` + `error.code`. STOP.

## Removal
If the user asks to remove a drawing, suggest: `mom clean <state-key>` where
`<state-key>` is the identifier shown in previous runs (e.g., `trailing-2026-04-16`
or `calendar-2024`). Run it only after explicit confirmation.
Mirror the same auth/error handling as above.

## Safety
- Always pass TEXT as a single argv element. Never interpolate user input into
  a shell command string.
- Always use `--format json` from this skill. Text mode is for human CLI use.
- Never modify `git config` on the user's behalf.
- Never write the user's PAT to disk outside of `mom config set-token`.
