"""
Integration test — runs all four discovery atomics and prints telemetry.
"""
import sys, json
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from rich.console import Console
from rich.panel   import Panel
from techniques.registry import AtomicRegistry

console  = Console()
registry = AtomicRegistry()
registry.discover()
registry.summary_table()

TARGET_TECHNIQUES = ["T1082", "T1083", "T1057", "T1016"]

for tid in TARGET_TECHNIQUES:
    cls = registry.get(tid)
    if not cls:
        console.print(f"[red]✗ {tid} not found in registry[/red]")
        continue

    console.print(f"\n[bold cyan]▶ Running {tid} — {cls.NAME}[/bold cyan]")
    atomic    = cls(platform="macOS")
    telemetry = atomic.run()

    console.print(Panel(
        f"[yellow]Command:[/yellow]    {telemetry.command}\n"
        f"[yellow]Exit code:[/yellow]  {telemetry.exit_code}\n"
        f"[yellow]Duration:[/yellow]   {telemetry.duration_ms:.0f}ms\n"
        f"[yellow]IOCs:[/yellow]       {len(telemetry.iocs)}\n"
        f"[yellow]Artifacts:[/yellow]  {telemetry.artifacts[:3]}\n"
        f"[yellow]stdout:[/yellow]\n{telemetry.stdout[:400]}",
        title=f"[green]{tid} Telemetry[/green]",
        border_style="cyan",
    ))

    console.print(f"[dim]IOC list: {json.dumps(telemetry.iocs, indent=2)[:300]}[/dim]")

console.print("\n[bold green]✓ All discovery atomics executed[/bold green]")
