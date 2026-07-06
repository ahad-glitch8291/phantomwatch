"""
Integration test — credential access atomics.
"""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from rich.console import Console
from rich.panel   import Panel
from techniques.registry        import AtomicRegistry
from core.detection_validator   import DetectionValidator
from core.engine                import SimulationResult
from core.technique_loader      import TechniqueLoader

console  = Console()
registry = AtomicRegistry()
registry.discover()

console.print("\n[bold cyan]══ Credential Access Atomics Test ══[/bold cyan]\n")
registry.summary_table()

TARGET_TECHNIQUES = ["T1555.001", "T1552.001"]
sim_results       = []

loader = TechniqueLoader()
loader.fetch()

for tid in TARGET_TECHNIQUES:
    cls = registry.get(tid)
    if not cls:
        console.print(f"[red]✗ {tid} not in registry[/red]")
        continue

    console.print(f"\n[bold cyan]▶ {tid} — {cls.NAME}[/bold cyan]")
    atomic    = cls(platform="macOS")
    telemetry = atomic.run()

    console.print(Panel(
        f"[yellow]Exit code:[/yellow]  {telemetry.exit_code}\n"
        f"[yellow]Duration:[/yellow]   {telemetry.duration_ms:.0f}ms\n"
        f"[yellow]IOCs:[/yellow]       {len(telemetry.iocs)}\n"
        f"[yellow]Artifacts:[/yellow]  {len(telemetry.artifacts)} files\n\n"
        f"[yellow]stdout:[/yellow]\n{telemetry.stdout[:700]}",
        title=f"[green]{tid} Telemetry[/green]",
        border_style="cyan"
    ))

    tech_data       = loader.get_by_id(tid) or {
        "id": tid, "name": cls.NAME,
        "tactics": [cls.TACTIC], "platforms": cls.PLATFORMS
    }
    tech_data["id"] = tid

    r           = SimulationResult(tech_data, status="simulated",
                      notes=f"atomic | exit={telemetry.exit_code}")
    r.telemetry = telemetry.to_dict()
    sim_results.append(r)

# ── Validate ───────────────────────────────────────────────────────
console.print("\n[bold cyan]══ Validation Pass ══[/bold cyan]")
validator = DetectionValidator()
validator.load_rules()
validated = validator.validate(sim_results)
validator.print_gap_report(validated)

gaps = validator.get_gaps(validated)
if gaps:
    console.print(f"\n[bold yellow]⚡ {len(gaps)} gaps need Sigma rules[/bold yellow]")
    for g in gaps:
        console.print(f"  [red]✗[/red] [{g.technique_id}] {g.name}")
else:
    console.print("\n[bold green]✓ All credential access techniques detected[/bold green]")

# ── IOC summary ────────────────────────────────────────────────────
console.print("\n[bold cyan]══ IOC Summary ══[/bold cyan]")
for r in sim_results:
    tel  = getattr(r, "telemetry", {}) or {}
    iocs = tel.get("iocs", [])
    console.print(f"\n[yellow]{r.technique_id}[/yellow] — {len(iocs)} IOCs:")
    for ioc in iocs:
        console.print(f"  [{ioc['type']}] {ioc['value']}")
