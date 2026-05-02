"""CLI entry point."""

import click
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
from agent_eval_lab.eval_harness import run_eval
from agent_eval_lab.golden_set import GOLDEN_SET
from agent_eval_lab.agents import run_agent_loop

load_dotenv()
console = Console()


@click.group()
def cli():
    """Agent Eval Lab - Multi-agent test generation + eval harness."""
    pass


@cli.command()
@click.option("--output", "-o", default="runs/eval_results.json", help="Where to save results")
def eval(output):
    """Run the full eval suite over the golden set."""
    console.print("[bold cyan]Running Agent Eval Lab on golden set...[/]")
    summary = run_eval(output)

    table = Table(title="Eval Results")
    table.add_column("Function", style="cyan")
    table.add_column("Score", style="green")
    table.add_column("Tests", style="yellow")
    table.add_column("Failures", style="red")

    for r in summary["results"]:
        failures = ", ".join(r["failure_modes"]) or "-"
        table.add_row(
            r["name"],
            f"{r['overall_score']}/100",
            str(r["scores"]["test_count"]),
            failures,
        )

    console.print(table)
    console.print(f"\n[bold]Average score:[/] {summary['average_score']}/100")
    console.print(f"[bold]Pass rate:[/] {summary['pass_rate_percent']}%")
    console.print(f"\n[dim]Full results: {output}[/]")


@cli.command()
@click.argument("function_code")
def generate(function_code):
    """Generate tests for a single function (pass code as string)."""
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


if __name__ == "__main__":
    cli()
