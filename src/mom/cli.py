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
