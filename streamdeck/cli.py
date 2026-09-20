# cli.py — Typer command line interface.
#
# One command to rule the stack:
#   streamdeck serve   — API + device runner
#   streamdeck demo    — frontend with no server URL needed (in-browser demo)
#   streamdeck list    — list attached decks
#   streamdeck run     — device runner only
#   streamdeck agent   — nominate-a-computer agent loop
#   streamdeck ui      — serve the built frontend as static files

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from . import __version__

app = typer.Typer(
    name="streamdeck",
    help="Standalone Stream Deck control stack (API, device runner, web UI).",
    no_args_is_help=True,
    # Shell completion (--install-completion / --show-completion) is typer's
    # built-in; leaving it enabled is the whole of P17's CLI half. Do not
    # disable it again — tests/test_cli.py pins its presence.
)
console = Console()

ASSETS_DIR = Path(__file__).parent / "assets"
# Frontend lives at the repository/package-project root (sibling of the
# python package folder), and may also be shipped inside the package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_CANDIDATES = [
    _REPO_ROOT / "frontend",
    Path(__file__).parent / "frontend",
]


def _frontend_dir() -> Path:
    for candidate in _FRONTEND_CANDIDATES:
        if (candidate / "dist" / "index.html").is_file() or (
            candidate / "dist-demo" / "index.html"
        ).is_file():
            return candidate
    return _FRONTEND_CANDIDATES[0]


def _transport() -> str:
    return os.getenv("STREAMDECK_TRANSPORT", "libusb").lower()


def _api_base() -> str:
    return os.getenv("STREAMDECK_API", "http://localhost:8000").rstrip("/")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address for the API"),
    port: int = typer.Option(8000, help="Port for the API"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
):
    """Run the configuration API (FastAPI + uvicorn)."""
    from .db import init_db

    init_db()
    uvicorn.run("streamdeck.app:app", host=host, port=port, reload=reload)


@app.command(name="list-devices")
def list_devices():
    """List attached Stream Deck devices."""
    from .app import list_device_metadata

    decks = list_device_metadata()
    console.print(f"Found {len(decks)} Stream Deck(s)")
    for deck in decks:
        console.print(
            f"- [bold]{deck['type']}[/bold] "
            f"(Serial: [cyan]{deck['serial'] or 'unknown'}[/cyan], "
            f"{deck['key_count']} keys)"
        )


@app.command()
def run(
    config: str = typer.Option(None, help="Path to a config JSON file"),
    device_id: str = typer.Option(None, help="Device serial number to drive"),
    brightness: int = typer.Option(30, help="Key brightness 0-100"),
    ignore_device_type_check: bool = typer.Option(
        False, "--ignore-device-type-check", help="Skip device_type matching"
    ),
):
    """Run the device runner against attached decks."""
    import argparse

    from .runner import main as runner_main

    args = argparse.Namespace(
        config=config,
        brightness=brightness,
        list_devices=False,
        device_type=None,
        ignore_device_type_check=ignore_device_type_check,
        api=_api_base(),
        device_id=device_id,
    )
    runner_main(args)


@app.command()
def agent(
    server: str = typer.Option(None, help="Base URL of the Stream Deck server"),
    interval: float = typer.Option(5.0, help="Poll interval in seconds"),
):
    """Run the nominate-a-computer agent loop on this machine."""
    from .agent import agent_loop

    agent_loop(server or _api_base(), interval)


@app.command()
def demo(
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(8080, help="Port"),
):
    """Serve the web UI in offline demo mode (no API server required)."""
    index = _find_demo_index()
    if index is None:
        console.print(
            "[red]No built frontend found.[/red] Build it first with:\n"
            "  [cyan]bun install && bun run build[/cyan] in [bold]frontend/[/bold]\n"
            "or run [cyan]scripts/build-frontend.sh[/cyan]"
        )
        raise typer.Exit(1)
    _serve_static(index.parent, host, port)


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(8080, help="Port"),
):
    """Serve the built frontend pointing at the API (full-stack mode)."""
    index = _find_built_index()
    if index is None:
        console.print(
            "[red]No built frontend found.[/red] Build it first with "
            "[cyan]scripts/build-frontend.sh[/cyan]"
        )
        raise typer.Exit(1)
    _serve_static(index.parent, host, port)


def _find_built_index() -> Path | None:
    env_dir = os.getenv("STREAMDECK_UI_DIR")
    candidates = [_frontend_dir() / "dist" / "index.html"]
    if env_dir:
        candidates.insert(0, Path(env_dir) / "index.html")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _find_demo_index() -> Path | None:
    """Prefer a demo build (DEMO_MODE inlined) over the normal build."""
    env_dir = os.getenv("STREAMDECK_UI_DIR")
    candidates = [
        _frontend_dir() / "dist-demo" / "index.html",
        _frontend_dir() / "dist" / "index.html",
    ]
    if env_dir:
        candidates.insert(0, Path(env_dir) / "index.html")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _serve_static(root: Path, host: str, port: int) -> None:
    """Serve a static SPA root with correct mime types and SPA fallback."""
    from functools import partial

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    spa = FastAPI()
    spa.mount(
        "/assets",
        StaticFiles(directory=str(root / "assets"), check_dir=False),
        name="assets",
    )

    @spa.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = root / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(root / "index.html")

    uvicorn.run(spa, host=host, port=port, log_level="info")


@app.command()
def version():
    """Print version information."""
    console.print(f"streamdeck {__version__}")


@app.command()
def export_config(
    config_id: str = typer.Argument(..., help="Config UUID to export"),
    output: str = typer.Option(None, help="Output file (default: stdout)"),
):
    """Export a stored config as JSON (backup / sharing)."""
    import requests

    response = requests.get(f"{_api_base()}/config/{config_id}", timeout=10)
    response.raise_for_status()
    payload = json.dumps(response.json(), indent=2)
    if output:
        Path(output).write_text(payload + "\n", encoding="utf-8")
        console.print(f"[green]Wrote {output}[/green]")
    else:
        console.print(payload)


if __name__ == "__main__":
    app()