from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .pipeline import PipelineRunner

app = typer.Typer(help="OpenBlock – CLI-first AI agent pipeline")
console = Console()


@app.command()
def run(
    plan: Path = typer.Argument(Path("openblock.yaml"), help="Path to plan file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Execute without running commands"),
    log_dir: Optional[Path] = typer.Option(None, "--log-dir", help="Directory for run artifacts"),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", help="Directory where files/commands operate (default: plan dir)"
    ),
):
    """Execute the OpenBlock agent pipeline for the given plan."""
    runner = PipelineRunner.from_file(plan_path=plan, dry_run=dry_run, log_dir=log_dir, workspace=workspace)
    console.rule(f"[bold cyan]Project: {runner.config.name}")
    console.print(f"Goal: {runner.config.goal}")
    runs = runner.execute()
    table = Table(title="Task Summary")
    table.add_column("Task")
    table.add_column("Planner Output")
    table.add_column("Code")
    table.add_column("Verdict")
    for run in runs:
        planner_preview = "\n".join(run.plan_steps)
        code_status = "-"
        if run.coding:
            successes = sum(1 for a in run.coding.artifacts if a.error is None)
            code_status = f"{successes}/{len(run.coding.artifacts)} files"
        table.add_row(run.task.name, planner_preview, code_status, run.review.verdict)
    console.print(table)
    console.print(f"Logs written to: {runner.log_dir.resolve()}")


def main():
    app()


if __name__ == "__main__":
    main()
