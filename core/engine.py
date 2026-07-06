"""
engine.py
Orchestrates PhantomWatch simulation runs.
Loads techniques, runs simulations, tracks results, feeds validator.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import track

from core.technique_loader import TechniqueLoader

console = Console()
logging.basicConfig(
    filename="logs/phantomwatch.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

class SimulationResult:
    """Holds the result of a single technique simulation."""

    STATUSES = ("simulated", "skipped", "error")

    def __init__(self, technique: dict, status: str, notes: str = ""):
        assert status in self.STATUSES, f"Invalid status: {status}"
        self.id           = str(uuid.uuid4())[:8]
        self.technique_id = technique["id"]
        self.name         = technique["name"]
        self.tactics      = technique["tactics"]
        self.platforms    = technique["platforms"]
        self.status       = status
        self.notes        = notes
        self.timestamp    = datetime.now(timezone.utc).isoformat()
        self.detected     = None   # filled by DetectionValidator later

    def to_dict(self) -> dict:
        return {
            "run_id":       self.id,
            "technique_id": self.technique_id,
            "name":         self.name,
            "tactics":      self.tactics,
            "platforms":    self.platforms,
            "status":       self.status,
            "detected":     self.detected,
            "notes":        self.notes,
            "timestamp":    self.timestamp,
        }


class PhantomEngine:
    """
    Core simulation engine.
    
    Usage:
        engine = PhantomEngine()
        engine.load()
        results = engine.run_tactic("discovery")
        engine.print_summary(results)
        engine.save_results(results)
    """

    def __init__(self, config: dict | None = None):
        self.config   = config or {}
        self.loader   = TechniqueLoader()
        self.results  = []
        self.run_meta = {
            "session_id": str(uuid.uuid4()),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "platform_filter": self.config.get("platform", "macOS"),
        }

    def load(self):
        """Fetch and parse ATT&CK data. Must call before any run."""
        self.loader.fetch()

    # ------------------------------------------------------------------ #
    #  Simulation runners                                                  #
    # ------------------------------------------------------------------ #

    def run_tactic(self, tactic: str, platform: str = "macOS") -> list[SimulationResult]:
        """Simulate all techniques under a given tactic."""
        techniques = self.loader.get_by_tactic(tactic.replace("_", "-"))
        if not techniques:
            console.print(f"[yellow]⚠ No techniques found for tactic: {tactic}[/yellow]")
            return []

        console.print(f"\n[bold cyan]▶ Simulating tactic: {tactic.upper()} ({len(techniques)} techniques)[/bold cyan]")
        results = []

        for tech in track(techniques, description=f"[cyan]Running {tactic}..."):
            result = self._simulate_one(tech, platform)
            results.append(result)
            logging.info(f"{result.technique_id} | {result.status} | {result.notes}")

        self.results.extend(results)
        return results

    def run_technique(self, technique_id: str, platform: str = "macOS") -> SimulationResult | None:
        """Simulate a single technique by ID."""
        tech = self.loader.get_by_id(technique_id)
        if not tech:
            console.print(f"[red]✗ Technique not found: {technique_id}[/red]")
            return None

        result = self._simulate_one(tech, platform)
        self.results.append(result)
        logging.info(f"{result.technique_id} | {result.status} | {result.notes}")
        return result

    def run_all(self, platform: str = "macOS") -> list[SimulationResult]:
        """Simulate every loaded technique (use with care — 600+ techniques)."""
        console.print(f"[bold yellow]⚡ Full simulation run — {len(self.loader.techniques)} techniques[/bold yellow]")
        results = []
        for tech in track(self.loader.techniques, description="[yellow]Full run..."):
            result = self._simulate_one(tech, platform)
            results.append(result)
        self.results.extend(results)
        return results

    # ------------------------------------------------------------------ #
    #  Internal simulation logic                                           #
    # ------------------------------------------------------------------ #

    def _simulate_one(self, technique: dict, platform: str) -> SimulationResult:
        """
        Core simulation logic for a single technique.
        Phase 1: marks as 'simulated' if platform matches, else 'skipped'.
        Phase 2 will replace this with real atomic execution.
        """
        if platform and platform not in technique.get("platforms", []):
            return SimulationResult(
                technique,
                status="skipped",
                notes=f"Platform '{platform}' not in {technique['platforms']}"
            )

        return SimulationResult(
            technique,
            status="simulated",
            notes="Phase 1 stub — atomic execution wired in Phase 2"
        )

    # ------------------------------------------------------------------ #
    #  Output                                                              #
    # ------------------------------------------------------------------ #

    def print_summary(self, results: list[SimulationResult]):
        """Rich table summary of a result set."""
        simulated = [r for r in results if r.status == "simulated"]
        skipped   = [r for r in results if r.status == "skipped"]
        errors    = [r for r in results if r.status == "error"]

        table = Table(title="PhantomWatch — Simulation Summary", style="cyan")
        table.add_column("ID",        style="dim")
        table.add_column("Technique", style="bold white")
        table.add_column("Tactic",    style="yellow")
        table.add_column("Status",    style="green")
        table.add_column("Detected",  style="magenta")

        for r in results[:40]:  # cap display at 40 rows
            tactic  = r.tactics[0] if r.tactics else "—"
            status  = r.status
            color   = {"simulated": "green", "skipped": "dim", "error": "red"}.get(status, "white")
            detected = "—" if r.detected is None else ("✓" if r.detected else "✗")
            table.add_row(
                r.technique_id,
                r.name[:55],
                tactic.replace("-", " ").title(),
                f"[{color}]{status}[/{color}]",
                detected,
            )

        console.print(table)
        console.print(
            f"\n[bold]Total:[/bold] {len(results)} | "
            f"[green]Simulated: {len(simulated)}[/green] | "
            f"[dim]Skipped: {len(skipped)}[/dim] | "
            f"[red]Errors: {len(errors)}[/red]"
        )

    def save_results(self, results: list[SimulationResult], outfile: str | None = None):
        """Save results to JSON in the reports directory."""
        Path("reports").mkdir(exist_ok=True)
        filename = outfile or f"reports/run_{self.run_meta['session_id'][:8]}.json"
        payload  = {
            "meta":    self.run_meta,
            "results": [r.to_dict() for r in results],
        }
        with open(filename, "w") as f:
            json.dump(payload, f, indent=2)
        console.print(f"[bold green]✓ Results saved → {filename}[/bold green]")
        return filename


# ------------------------------------------------------------------ #
#  Atomic execution upgrade (Phase 2)                                  #
# ------------------------------------------------------------------ #

from techniques.registry import AtomicRegistry as _Registry

class PhantomEngineV2(PhantomEngine):
    """
    Extends PhantomEngine with real atomic execution via the registry.
    Falls back to stub if no atomic exists for a technique.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.registry = _Registry()

    def load(self):
        super().load()
        self.registry.discover()

    def _simulate_one(self, technique: dict, platform: str):
        from core.engine import SimulationResult
        tid = technique["id"]
        cls = self.registry.get(tid)

        if cls:
            atomic    = cls(platform=platform)
            telemetry = atomic.run()

            status = "simulated" if telemetry.exit_code == 0 else \
                     "skipped"   if telemetry.exit_code == -99 else "error"

            result          = SimulationResult(technique, status=status,
                                notes=f"atomic | exit={telemetry.exit_code}")
            result.telemetry = telemetry.to_dict()
            return result

        # fallback to stub
        return super()._simulate_one(technique, platform)
