"""
main.py
PhantomWatch CLI — purple team automation platform.

Commands:
    run         Simulate a tactic or single technique
    validate    Validate a saved results file
    list        List tactics or techniques
    info        Lookup a technique by ID
"""

import json
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from core.engine import PhantomEngine
from core.detection_validator import DetectionValidator
from core.technique_loader import TechniqueLoader

console = Console()

BANNER = """
[bold cyan]
██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
[/bold cyan]
[dim]Purple Team Automation Platform — by Ahad[/dim]
[dim]MITRE ATT&CK Simulation · Detection Validation · Sigma Generation[/dim]
"""


@click.group()
def cli():
    """PhantomWatch — Purple Team Automation Platform."""
    console.print(BANNER)


# ------------------------------------------------------------------ #
#  run                                                                 #
# ------------------------------------------------------------------ #

@cli.command()
@click.option("--tactic",    "-t", default=None,   help="Tactic to simulate (e.g. discovery)")
@click.option("--technique", "-T", default=None,   help="Single technique ID (e.g. T1082)")
@click.option("--platform",  "-p", default="macOS",help="Target platform (macOS/Windows/Linux)")
@click.option("--validate",  "-v", is_flag=True,   help="Run detection validation after simulation")
@click.option("--save",      "-s", is_flag=True,   help="Save results to reports/")
@click.option("--all",       "-a", "run_all", is_flag=True, help="Simulate ALL techniques (slow)")
def run(tactic, technique, platform, validate, save, run_all):
    """Simulate ATT&CK techniques and optionally validate detections."""

    engine = PhantomEngine(config={"platform": platform})
    engine.load()

    # ── Determine what to run ──────────────────────────────────────
    if run_all:
        results = engine.run_all(platform=platform)

    elif tactic:
        results = engine.run_tactic(tactic, platform=platform)

    elif technique:
        result = engine.run_technique(technique, platform=platform)
        results = [result] if result else []

    else:
        console.print("[yellow]⚠ Specify --tactic, --technique, or --all[/yellow]")
        console.print("  Example: [bold]phantomwatch run --tactic discovery --validate[/bold]")
        return

    if not results:
        console.print("[red]✗ No results generated.[/red]")
        return

    engine.print_summary(results)

    # ── Optional validation ────────────────────────────────────────
    if validate:
        console.print("\n[bold cyan]→ Running detection validation...[/bold cyan]")
        validator = DetectionValidator()
        validator.load_rules()
        validated = validator.validate(results)
        validator.print_gap_report(validated)

        gaps = validator.get_gaps(validated)
        if gaps:
            console.print(f"\n[bold yellow]⚡ {len(gaps)} gaps found — run sigma-gen to create rules[/bold yellow]")

        if save:
            validator.save_validation(validated)
    elif save:
        engine.save_results(results)


# ------------------------------------------------------------------ #
#  validate                                                            #
# ------------------------------------------------------------------ #

@cli.command()
@click.argument("results_file")
@click.option("--save", "-s", is_flag=True, help="Save validation output to reports/")
def validate(results_file, save):
    """Validate a saved simulation results JSON file."""

    path = Path(results_file)
    if not path.exists():
        console.print(f"[red]✗ File not found: {results_file}[/red]")
        return

    with open(path) as f:
        data = json.load(f)

    raw_results = data.get("results", [])
    console.print(f"[cyan]→ Loaded {len(raw_results)} results from {path.name}[/cyan]")

    # Reconstruct lightweight result objects for validator
    class _R:
        def __init__(self, d):
            self.technique_id = d["technique_id"]
            self.name         = d["name"]
            self.tactics      = d["tactics"]
            self.platforms    = d["platforms"]
            self.status       = d["status"]
            self.detected     = d.get("detected")
            self.notes        = d.get("notes", "")
            self.timestamp    = d.get("timestamp", "")

        def to_dict(self):
            return self.__dict__

    results = [_R(r) for r in raw_results]

    validator = DetectionValidator()
    validator.load_rules()
    validated = validator.validate(results)
    validator.print_gap_report(validated)

    if save:
        validator.save_validation(validated)


# ------------------------------------------------------------------ #
#  list                                                                #
# ------------------------------------------------------------------ #

@cli.command(name="list")
@click.option("--tactic",   "-t", default=None, help="Filter by tactic")
@click.option("--platform", "-p", default=None, help="Filter by platform")
@click.option("--tactics",  is_flag=True,       help="List all available tactics")
def list_techniques(tactic, platform, tactics):
    """List available ATT&CK tactics or techniques."""

    loader = TechniqueLoader()
    loader.fetch()

    if tactics:
        loader.summary_table()
        return

    techniques = loader.get_by_tactic(tactic) if tactic else loader.techniques

    if platform:
        techniques = [t for t in techniques if platform in t.get("platforms", [])]

    table = Table(title=f"Techniques — {tactic or 'All'}", style="cyan")
    table.add_column("ID",       style="bold yellow", no_wrap=True)
    table.add_column("Name",     style="white")
    table.add_column("Tactics",  style="dim")
    table.add_column("Platforms",style="dim")

    for t in techniques[:60]:
        table.add_row(
            t["id"],
            t["name"][:55],
            ", ".join(t["tactics"])[:40],
            ", ".join(t["platforms"])[:30],
        )

    console.print(table)
    console.print(f"[dim]Showing {min(60, len(techniques))} of {len(techniques)} techniques[/dim]")


# ------------------------------------------------------------------ #
#  info                                                                #
# ------------------------------------------------------------------ #

@cli.command()
@click.argument("technique_id")
def info(technique_id):
    """Show full details for a technique by ID (e.g. T1082)."""

    loader = TechniqueLoader()
    loader.fetch()

    t = loader.get_by_id(technique_id)
    if not t:
        console.print(f"[red]✗ Technique not found: {technique_id}[/red]")
        return

    console.print(f"\n[bold cyan]{t['id']} — {t['name']}[/bold cyan]")
    console.print(f"[yellow]Tactics:[/yellow]   {', '.join(t['tactics'])}")
    console.print(f"[yellow]Platforms:[/yellow] {', '.join(t['platforms'])}")
    console.print(f"[yellow]Subtech:[/yellow]   {'Yes' if t['is_subtechnique'] else 'No'}")
    console.print(f"\n[yellow]Description:[/yellow]\n{t['description']}\n")


# ------------------------------------------------------------------ #
#  reports                                                             #
# ------------------------------------------------------------------ #

@cli.command()
def reports():
    """List all saved reports."""

    reports_dir = Path("reports")
    if not reports_dir.exists() or not list(reports_dir.glob("*.json")):
        console.print("[yellow]No reports found in reports/[/yellow]")
        return

    table = Table(title="Saved Reports", style="cyan")
    table.add_column("File",    style="bold white")
    table.add_column("Size",    style="dim")
    table.add_column("Modified",style="dim")

    for f in sorted(reports_dir.glob("*.json"), reverse=True):
        stat = f.stat()
        size = f"{stat.st_size / 1024:.1f} KB"
        from datetime import datetime
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(f.name, size, mtime)

    console.print(table)



# ── report command ────────────────────────────────────────────────────

@cli.command(name="report")
@click.option("--tactic",   "-t", default="discovery", help="Tactic to run")
@click.option("--platform", "-p", default="macOS",     help="Target platform")
@click.option("--open",     "-o", "open_browser", is_flag=True, help="Open report in browser")
def report(tactic, platform, open_browser):
    """Full pipeline: simulate → validate → sigma → HTML report."""
    import subprocess
    from core.engine              import PhantomEngineV2
    from core.detection_validator import DetectionValidator
    from core.sigma_generator     import SigmaGenerator
    from core.reporter            import Reporter

    engine = PhantomEngineV2(config={"platform": platform})
    engine.load()
    results   = engine.run_tactic(tactic, platform=platform)

    validator = DetectionValidator()
    validator.load_rules()
    validated = validator.validate(results)

    gaps      = validator.get_gaps(validated)
    generator = SigmaGenerator()
    rules     = generator.generate(gaps)
    generator.save(rules)
    generator.save_bundle(rules)

    reporter  = Reporter()
    path      = reporter.generate(
        results     = validated,
        sigma_rules = rules,
        meta        = {**engine.run_meta, "attack_version": "v14"},
    )

    if open_browser:
        subprocess.run(["open", path])



# ── campaign command ──────────────────────────────────────────────────

@cli.command()
@click.option("--profile", "-p", default="apt-macos",
              help="Campaign profile: apt-macos | discovery-only | exec-persist | cred-harvest")
@click.option("--open",    "-o", "open_browser", is_flag=True,
              help="Open HTML report in browser when done")
@click.option("--tactics", "-t", default=None,
              help="Custom tactic chain e.g. 'discovery,execution'")
def campaign(profile, open_browser, tactics):
    """Run a multi-tactic APT campaign chain."""
    from core.campaign import Campaign

    custom = [t.strip() for t in tactics.split(",")] if tactics else None
    c      = Campaign(profile=profile, custom_tactics=custom)
    c.run()
    c.report(open_browser=open_browser)
    c.save_summary()


@cli.command(name="profiles")
def list_profiles():
    """List available campaign profiles."""
    from core.campaign import CAMPAIGN_PROFILES

    table = Table(title="Campaign Profiles", style="cyan")
    table.add_column("Profile",     style="bold yellow")
    table.add_column("Name",        style="white")
    table.add_column("Tactics",     style="dim")
    table.add_column("Description", style="dim")

    for key, p in CAMPAIGN_PROFILES.items():
        table.add_row(
            key,
            p["name"],
            " → ".join(p["tactics"]),
            p["description"][:55],
        )

    console.print(table)


if __name__ == "__main__":
    cli()
