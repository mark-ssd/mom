"""Typer CLI."""

from __future__ import annotations
import json as _json
import subprocess
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional, NoReturn
import typer
from mom import __version__
from mom.errors import (
    AuthError, FitError, NetworkError,
    NotOurRepoError, UnsupportedCharError,
)
from mom.layout import Canvas, Fit, plan
from mom.preview import render
from mom.config import load, save, resolve_token
from mom.gh import verify_token, verify_email, ensure_repo
from mom.git_ops import rebuild

app = typer.Typer(
    help="Draw text on your GitHub contribution graph.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(help="Config subcommands.")
app.add_typer(config_app, name="config")


class Format(str, Enum):
    text = "text"
    json = "json"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def _main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    pass


def _emit_error(fmt: Format, code: int, kind: str, message: str, extra: dict | None = None) -> NoReturn:
    if fmt is Format.json:
        payload = {
            "status": "error",
            "error": {"code": code, "kind": kind, "message": message, **(extra or {})},
        }
        typer.echo(_json.dumps(payload))
    else:
        typer.echo(f"x {message}", err=True)
    raise typer.Exit(code)


def _git_user_email() -> str:
    r = subprocess.run(
        ["git", "config", "--global", "--get", "user.email"],
        capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


@app.command()
def draw(
    text: Annotated[str, typer.Argument(help="Text to draw.")],
    year: Annotated[int, typer.Option(help="Target calendar year.")] = date.today().year,
    repo: Annotated[Optional[str], typer.Option(help="Dedicated repo name.")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview + fit check only.")] = False,
    fmt: Annotated[Format, typer.Option("--format", help="Output format.")] = Format.text,
    intensity: Annotated[int, typer.Option(help="Intensity 1-4.")] = 4,
    token: Annotated[Optional[str], typer.Option(help="PAT override.")] = None,
) -> None:
    cfg = load()
    if repo:
        cfg.repo = repo

    # Layout first (pure, cheap, catches fit + char errors without any I/O).
    today = date.today()
    try:
        result = plan(text, year, today, intensity)
    except UnsupportedCharError as e:
        _emit_error(fmt, 2, "unsupported_char", str(e))
    if isinstance(result, Fit):
        _emit_error(
            fmt, 3, "fit_fail", str(FitError(result.required, result.available, result.year)),
            extra={"fit": {"ok": False, "required_cols": result.required,
                           "available_cols": result.available, "year": result.year}},
        )
    assert isinstance(result, Canvas)
    canvas: Canvas = result
    preview_ascii = render(canvas)
    total_commits = sum(n for _, n in canvas.cells)
    dates = sorted({d for d, _ in canvas.cells})
    date_range = [dates[0].isoformat(), dates[-1].isoformat()] if dates else []

    payload = {
        "status": "preview" if dry_run else "success",
        "fit": {"ok": True, "required_cols": 4 * len(text) - 1,
                "available_cols": len(canvas.usable_week_indices), "year": year},
        "commits": {"total": total_commits, "date_range": date_range},
        "preview_ascii": preview_ascii,
        "repo_url": None,
        "error": None,
    }

    if dry_run:
        if fmt is Format.json:
            typer.echo(_json.dumps(payload))
        else:
            typer.echo(preview_ascii)
            typer.echo(f"\n{total_commits} commits across {len(dates)} dates (dry-run).")
        raise typer.Exit(0)

    # Auth + GitHub calls.
    try:
        tok = resolve_token(token)
        user = verify_token(tok)
        if not cfg.github_user:
            cfg.github_user = user
            save(cfg)
        git_email = _git_user_email()
        if git_email:
            verify_email(tok, git_email)
        clone_url, html_url = ensure_repo(tok, user, cfg.repo)
        auth_clone = clone_url.replace("https://", f"https://x-access-token:{tok}@")
    except AuthError as e:
        _emit_error(fmt, 4, e.kind, str(e))
    except NetworkError as e:
        _emit_error(fmt, 5, "network", str(e))

    # Confirm (skipped by --yes).
    if not yes and fmt is Format.text:
        typer.echo(preview_ascii)
        typer.echo(f"\n{total_commits} commits across {len(dates)} dates.")
        ok = typer.confirm("Proceed?")
        if not ok:
            raise typer.Exit(0)

    # Execute.
    try:
        work_dir = Path.home() / ".cache" / "mom" / cfg.repo
        rebuild(
            work_dir=work_dir,
            remote_url=auth_clone,
            year=year,
            canvas=canvas,
            action="upsert",
            today=today,
        )
    except NotOurRepoError as e:
        _emit_error(fmt, 1, "not_our_repo", str(e))
    except subprocess.CalledProcessError as e:
        _emit_error(fmt, 5, "push_rejected", f"git failed: {(e.stderr or '')[:500]}")

    payload["repo_url"] = html_url
    payload["status"] = "success"
    if fmt is Format.json:
        typer.echo(_json.dumps(payload))
    else:
        typer.echo(f"Done. View at {html_url}/graphs/contribution-activity")


@app.command()
def preview(
    text: Annotated[str, typer.Argument()],
    year: Annotated[int, typer.Option()] = date.today().year,
    fmt: Annotated[Format, typer.Option("--format")] = Format.text,
    intensity: Annotated[int, typer.Option()] = 4,
) -> None:
    """Alias for `draw --dry-run`."""
    today = date.today()
    try:
        result = plan(text, year, today, intensity)
    except UnsupportedCharError as e:
        _emit_error(fmt, 2, "unsupported_char", str(e))
    if isinstance(result, Fit):
        _emit_error(fmt, 3, "fit_fail",
                    str(FitError(result.required, result.available, result.year)),
                    extra={"fit": {"ok": False, "required_cols": result.required,
                                   "available_cols": result.available, "year": result.year}})
    assert isinstance(result, Canvas)
    preview_ascii = render(result)
    total = sum(n for _, n in result.cells)
    dates = sorted({d for d, _ in result.cells})
    payload = {
        "status": "preview",
        "fit": {"ok": True, "required_cols": 4 * len(text) - 1,
                "available_cols": len(result.usable_week_indices), "year": year},
        "commits": {"total": total,
                    "date_range": [dates[0].isoformat(), dates[-1].isoformat()] if dates else []},
        "preview_ascii": preview_ascii, "repo_url": None, "error": None,
    }
    if fmt is Format.json:
        typer.echo(_json.dumps(payload))
    else:
        typer.echo(preview_ascii)


@app.command()
def clean(
    year: Annotated[int, typer.Option(help="Year to remove.")],
    repo: Annotated[Optional[str], typer.Option()] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    fmt: Annotated[Format, typer.Option("--format")] = Format.text,
    token: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Remove a year's drawing from the dedicated repo."""
    cfg = load()
    if repo:
        cfg.repo = repo
    try:
        tok = resolve_token(token)
        user = verify_token(tok)
        clone_url, html_url = ensure_repo(tok, user, cfg.repo)
        auth_clone = clone_url.replace("https://", f"https://x-access-token:{tok}@")
    except AuthError as e:
        _emit_error(fmt, 4, e.kind, str(e))
    except NetworkError as e:
        _emit_error(fmt, 5, "network", str(e))

    if not yes and fmt is Format.text:
        if not typer.confirm(f"Remove year {year} from {cfg.repo}?"):
            raise typer.Exit(0)

    today = date.today()
    try:
        work_dir = Path.home() / ".cache" / "mom" / cfg.repo
        rebuild(
            work_dir=work_dir, remote_url=auth_clone,
            year=year, canvas=None, action="delete", today=today,
        )
    except NotOurRepoError as e:
        _emit_error(fmt, 1, "not_our_repo", str(e))
    except subprocess.CalledProcessError as e:
        _emit_error(fmt, 5, "push_rejected", f"git failed: {(e.stderr or '')[:500]}")

    if fmt is Format.json:
        typer.echo(_json.dumps({"status": "success", "repo_url": html_url, "year_removed": year}))
    else:
        typer.echo(f"Removed year {year}. View at {html_url}")


@config_app.command("check")
def config_check(
    fmt: Annotated[Format, typer.Option("--format")] = Format.text,
    token: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Exit 0 if auth is resolvable and the configured repo is reachable."""
    try:
        tok = resolve_token(token)
        user = verify_token(tok)
    except AuthError as e:
        _emit_error(fmt, 4, e.kind, str(e))
    except NetworkError as e:
        _emit_error(fmt, 5, "network", str(e))
    if fmt is Format.json:
        typer.echo(_json.dumps({"status": "ok", "github_user": user, "error": None}))
    else:
        typer.echo(f"OK -- authenticated as {user}")


@config_app.command("set-token")
def config_set_token(token: str) -> None:
    """Persist a PAT to the config file."""
    cfg = load()
    cfg.token = token
    save(cfg)
    typer.echo("Token saved to config.")


@config_app.command("show")
def config_show() -> None:
    """Print config (token redacted)."""
    cfg = load()
    display = {
        "repo": cfg.repo,
        "github_user": cfg.github_user,
        "token": "***" if cfg.token else "(not set)",
    }
    typer.echo(_json.dumps(display, indent=2))
