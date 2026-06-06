"""CLI entry point."""

import click
import json
import csv
import sys
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
from agent_eval_lab.eval_harness import run_eval
from agent_eval_lab.golden_set import GOLDEN_SET
from agent_eval_lab.web_ui import run_app

load_dotenv()
console = Console()


def _validate_env() -> None:
    """Fail fast if required env vars are missing."""
    import os
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    required = {
        "groq": ("GROQ_API_KEY", "https://console.groq.com"),
        "openai": ("OPENAI_API_KEY", "https://platform.openai.com"),
        "anthropic": ("ANTHROPIC_API_KEY", "https://console.anthropic.com"),
    }
    if provider in required:
        key, url = required[provider]
        if not os.getenv(key):
            console.print(f"[bold red]Error:[/] {key} is not set. Get one at {url}")
            raise SystemExit(1)


@click.group()
def cli():
    """Agent Eval Lab - Multi-agent test generation + eval harness."""
    pass


@cli.command()
@click.option("--output", "-o", default=None, help="Where to save results (default: timestamped in runs/)")
@click.option("--coverage", "-c", is_flag=True, help="Collect code coverage metrics")
@click.option("--timeout", default=30, type=int, help="Test execution timeout in seconds")
@click.option("--workers", default=1, type=int, help="Number of parallel workers")
@click.option("--progress", is_flag=True, help="Show progress bar (sequential only)")
@click.option("--snapshots", is_flag=True, help="Enable snapshot testing")
@click.option("--snapshot-dir", default="snapshots", help="Snapshot directory")
@click.option("--update-snapshots", is_flag=True, help="Update snapshots instead of comparing")
def eval(output, coverage, timeout, workers, progress, snapshots, snapshot_dir, update_snapshots):
    """Run the full eval suite over the golden set."""
    _validate_env()
    # Generate timestamped output if not provided
    if output is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"runs/eval_{timestamp}.json"

    console.print("[bold cyan]Running Agent Eval Lab on golden set...[/]")
    summary = run_eval(
        output_path=output,
        test_timeout=timeout,
        collect_coverage=coverage,
        workers=workers,
        show_progress=progress,
        snapshot_dir=snapshot_dir if snapshots else None,
        update_snapshots=update_snapshots,
    )

    table = Table(title="Eval Results")
    table.add_column("Function", style="cyan")
    table.add_column("Score", justify="right", style="green")
    table.add_column("Tests", justify="right", style="yellow")
    table.add_column("Agent", justify="center", style="magenta")
    table.add_column("Exec", justify="center", style="blue")
    if coverage:
        table.add_column("Cov%", justify="right", style="cyan")
    table.add_column("Failures", style="red")

    for r in summary["results"]:
        failures = ", ".join(r["failure_modes"]) or "-"
        agent_ok = "✓" if r["agent_passed"] else "✗"
        exec_data = r.get("execution")
        exec_ok = "✓" if exec_data and exec_data["success"] else ("✗" if exec_data else "-")
        cov_str = ""
        if coverage and exec_data and exec_data.get("coverage") is not None:
            cov_str = f"{exec_data['coverage']:.1f}%"
        elif coverage:
            cov_str = "-"
        row = [
            r["name"],
            f"{r['overall_score']}/100",
            str(r["scores"]["test_count"]),
            agent_ok,
            exec_ok,
        ]
        if coverage:
            row.append(cov_str)
        row.append(failures)
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[bold]Average AST score:[/] {summary['average_score']}/100")
    console.print(f"[bold]Agent pass rate:[/] {summary['agent_pass_rate_percent']}%")
    console.print(f"[bold]Execution pass rate:[/] {summary['execution_pass_rate_percent']}%")
    if summary.get("average_coverage_percent") is not None:
        console.print(f"[bold]Avg coverage:[/] {summary['average_coverage_percent']}%")
    total_usage = summary.get("total_usage", {})
    if total_usage.get("total_tokens", 0) > 0:
        console.print(f"[bold]Total tokens:[/] {total_usage['total_tokens']} "
                      f"({total_usage['prompt_tokens']} in, {total_usage['completion_tokens']} out)")
    console.print(f"\n[dim]Full results: {output}[/]")


@cli.command()
@click.argument("function_code")
def generate(function_code):
    """Generate tests for a single function (pass code as string)."""
    _validate_env()
    console.print("[bold cyan]Running agents...[/]")
    result = run_agent_loop(function_code)
    console.print("\n[bold green]Generated test code:[/]")
    console.print(result.get("final_test_code", "FAILED"))
    console.print(f"\n[bold]Passed:[/] {result['passed']}")


@cli.command(name="list-golden")
def list_golden():
    """List all golden-set items."""
    table = Table(title="Golden Set")
    table.add_column("Name", style="cyan")
    table.add_column("Min Tests", style="yellow")
    table.add_column("Edge Cases", style="green")

    for item in GOLDEN_SET:
        table.add_row(
            item["name"],
            str(item["min_tests"]),
            ", ".join(item["expected_edge_cases"]),
        )
    console.print(table)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=5000, type=int, help="Port for web UI")
def web(host, port):
    """Launch the web UI to browse eval runs."""
    run_app(host=host, port=port)


@cli.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option("--format", "-f", type=click.Choice(["csv", "md", "json"]), default="csv")
def export(json_file, format):
    """Export eval results to CSV, Markdown, or JSON."""
    with open(json_file) as f:
        data = json.load(f)

    if format == "json":
        click.echo(json.dumps(data, indent=2))
    elif format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow([
            "name", "overall_score", "agent_passed", "execution_success",
            "tests_count", "coverage", "judge_score", "failure_modes"
        ])
        for r in data["results"]:
            exec_data = r.get("execution") or {}
            coverage_val = exec_data.get("coverage")
            coverage_str = f"{coverage_val:.2f}" if coverage_val is not None else ""
            judge_fb = r.get("judge_feedback") or {}
            judge_score = judge_fb.get("semantic_score", "")
            failures = ";".join(r.get("failure_modes", []))
            writer.writerow([
                r["name"],
                r["overall_score"],
                r["agent_passed"],
                exec_data.get("success", ""),
                r["scores"]["test_count"],
                coverage_str,
                judge_score,
                failures,
            ])
    elif format == "md":
        click.echo("| Name | Score | Agent | Exec | Coverage | Judge | Failures |")
        click.echo("|------|-------|-------|------|----------|-------|----------|")
        for r in data["results"]:
            exec_data = r.get("execution") or {}
            coverage_val = exec_data.get("coverage")
            coverage = f"{coverage_val:.1f}%" if coverage_val is not None else "-"
            judge_fb = r.get("judge_feedback") or {}
            judge_score = judge_fb.get("semantic_score", "-")
            failures = ", ".join(r.get("failure_modes", [])) or "-"
            agent_ok = "✅" if r["agent_passed"] else "❌"
            exec_ok = "✅" if exec_data.get("success") else ("❌" if exec_data else "-")
            click.echo(f"| {r['name']} | {r['overall_score']}/100 | {agent_ok} | {exec_ok} | {coverage} | {judge_score} | {failures} |")


if __name__ == "__main__":
    cli()
