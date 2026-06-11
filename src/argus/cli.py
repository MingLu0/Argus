from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from argus import __version__
from argus.backends.discovery import discover_backends
from argus.config import load_config
from argus.decisions import DecisionAction, apply_decision, render_run_show
from argus.executor.run import run_discussion
from argus.modes import supported_modes

app = typer.Typer(help="Argus: many eyes on hard technical decisions.")


@app.command()
def version() -> None:
    """Print the Argus version."""
    typer.echo(__version__)


@app.command()
def agents(project_root: Path = typer.Option(Path.cwd(), "--project-root")) -> None:
    """List locally available agent backends."""
    config = load_config(project_root)
    for backend in discover_backends(config.backends):
        if backend.available:
            typer.echo(f"✓ {backend.id}: {backend.path}")
        else:
            typer.echo(f"- {backend.id}: {backend.reason}")


@app.command()
def doctor(project_root: Path = typer.Option(Path.cwd(), "--project-root")) -> None:
    """Check Argus configuration and backend availability."""
    typer.echo("Argus")
    typer.echo(f"version: {__version__}")
    typer.echo(f"project_root: {project_root}")
    typer.echo("modes: " + ", ".join(supported_modes()))
    typer.echo("backends:")
    config = load_config(project_root)
    for backend in discover_backends(config.backends):
        status = "available" if backend.available else "missing"
        detail = backend.path or backend.reason or ""
        typer.echo(f"  {backend.id}: {status} {detail}".rstrip())


@app.command()
def run(
    topic: Path,
    mode: str = typer.Option("tech-stack", "--mode"),
    backends: str = typer.Option("auto", "--backends"),
    timeout: float = typer.Option(30.0, "--timeout"),
    project_root: Path = typer.Option(Path.cwd(), "--project-root"),
) -> None:
    """Run a discussion against a topic file."""
    if mode not in supported_modes():
        supported = ", ".join(supported_modes())
        raise typer.BadParameter(f"unsupported mode {mode}; choose one of {supported}")
    try:
        manifest = asyncio.run(
            run_discussion(
                topic_path=topic,
                mode=mode,
                project_root=project_root,
                backend_selection=backends,
                timeout_seconds=timeout,
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--backends") from exc
    typer.echo(f"run: {manifest.id}")
    typer.echo(f"status: {manifest.status}")
    typer.echo(f"artifacts: {project_root / '.argus' / 'runs' / manifest.id}")


@app.command()
def status(project_root: Path = typer.Option(Path.cwd(), "--project-root")) -> None:
    """Show the latest run status."""
    runs_dir = project_root / ".argus" / "runs"
    if not runs_dir.exists():
        typer.echo("no runs")
        return
    runs = sorted([path for path in runs_dir.iterdir() if path.is_dir()])
    if not runs:
        typer.echo("no runs")
        return
    latest = runs[-1]
    typer.echo(f"latest: {latest.name}")
    typer.echo(latest / "run.yaml")


@app.command()
def show(
    run_id: str,
    project_root: Path = typer.Option(Path.cwd(), "--project-root"),
) -> None:
    """Show a run summary and decision gate context."""
    try:
        typer.echo(render_run_show(project_root, run_id))
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="run_id") from exc


@app.command()
def respond(
    run_id: str,
    action: DecisionAction = typer.Option(..., "--action"),
    note: str = typer.Option("", "--note"),
    choice: str = typer.Option("", "--choice"),
    project_root: Path = typer.Option(Path.cwd(), "--project-root"),
) -> None:
    """Resolve or update a run decision gate."""
    try:
        manifest = apply_decision(
            project_root=project_root,
            run_id=run_id,
            action=action,
            note=note,
            choice=choice,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="run_id") from exc
    typer.echo(f"run: {manifest.id}")
    typer.echo(f"decision: {manifest.decision_action}")
    typer.echo(f"status: {manifest.status}")


if __name__ == "__main__":
    app()
