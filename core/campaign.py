"""
campaign.py
Multi-tactic campaign orchestrator for PhantomWatch.
Chains tactics into APT-style kill chains, tracks timeline,
and produces unified results for validation and reporting.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib  import Path
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from core.engine              import PhantomEngineV2, SimulationResult
from core.detection_validator import DetectionValidator
from core.sigma_generator     import SigmaGenerator
from core.reporter            import Reporter

console = Console()
logger  = logging.getLogger(__name__)


# ── Built-in campaign profiles ─────────────────────────────────────────
CAMPAIGN_PROFILES = {
    "apt-macos": {
        "name":        "APT macOS Full Chain",
        "description": "Full kill chain simulating a macOS-targeting APT actor",
        "author":      "PhantomWatch",
        "tactics": [
            "discovery",
            "execution",
            "persistence",
            "credential_access",
        ],
        "platform": "macOS",
    },
    "discovery-only": {
        "name":        "Discovery Sweep",
        "description": "Reconnaissance-focused run across all discovery techniques",
        "author":      "PhantomWatch",
        "tactics":     ["discovery"],
        "platform":    "macOS",
    },
    "exec-persist": {
        "name":        "Execution + Persistence Chain",
        "description": "Simulates initial execution followed by persistence establishment",
        "author":      "PhantomWatch",
        "tactics":     ["execution", "persistence"],
        "platform":    "macOS",
    },
    "cred-harvest": {
        "name":        "Credential Harvesting",
        "description": "Focuses on credential access techniques across file and keychain stores",
        "author":      "PhantomWatch",
        "tactics":     ["discovery", "credential_access"],
        "platform":    "macOS",
    },
}


class CampaignStep:
    """Represents one tactic step within a campaign run."""

    def __init__(self, tactic: str, results: list, duration_ms: float):
        self.tactic      = tactic
        self.results     = results
        self.duration_ms = duration_ms
        self.started_at  = datetime.now(timezone.utc).isoformat()

        simulated    = [r for r in results if r.status == "simulated"]
        self.total      = len(results)
        self.simulated  = len(simulated)
        self.skipped    = len([r for r in results if r.status == "skipped"])
        self.errors     = len([r for r in results if r.status == "error"])

    def to_dict(self) -> dict:
        return {
            "tactic":      self.tactic,
            "total":       self.total,
            "simulated":   self.simulated,
            "skipped":     self.skipped,
            "errors":      self.errors,
            "duration_ms": self.duration_ms,
            "started_at":  self.started_at,
        }


class Campaign:
    """
    Orchestrates a multi-tactic PhantomWatch campaign.

    Usage:
        campaign = Campaign("apt-macos")
        campaign.run()
        campaign.report()
    """

    def __init__(self, profile: str = "apt-macos", custom_tactics: list = None):
        if profile not in CAMPAIGN_PROFILES and not custom_tactics:
            raise ValueError(
                f"Unknown profile '{profile}'. "
                f"Available: {list(CAMPAIGN_PROFILES.keys())}"
            )

        self.profile_key  = profile
        self.profile      = CAMPAIGN_PROFILES.get(profile, {
            "name":        f"Custom — {profile}",
            "description": "Custom tactic chain",
            "author":      "PhantomWatch",
            "tactics":     custom_tactics or [],
            "platform":    "macOS",
        })

        self.campaign_id  = str(uuid.uuid4())[:8]
        self.started_at   = None
        self.finished_at  = None
        self.steps:  list[CampaignStep]    = []
        self.all_results: list             = []
        self.validated:   list             = []
        self.sigma_rules: list             = []
        self.report_path: str              = ""

        self.engine    = PhantomEngineV2(config={
            "platform": self.profile.get("platform", "macOS")
        })
        self.validator = DetectionValidator()
        self.generator = SigmaGenerator()
        self.reporter  = Reporter()

    # ------------------------------------------------------------------ #
    #  Run                                                                 #
    # ------------------------------------------------------------------ #

    def run(self) -> list:
        """Execute the full campaign — all tactics in sequence."""
        self.started_at = datetime.now(timezone.utc).isoformat()
        platform        = self.profile.get("platform", "macOS")
        tactics         = self.profile["tactics"]

        self._print_campaign_banner()

        # ── Load ATT&CK data + registry once ──────────────────────
        self.engine.load()
        self.validator.load_rules()

        # ── Execute each tactic step ───────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=35),
            TextColumn("[dim]{task.completed}/{task.total}"),
            console=console,
        ) as progress:

            for i, tactic in enumerate(tactics, 1):
                task = progress.add_task(
                    f"[{i}/{len(tactics)}] {tactic.upper().replace('_', ' ')}",
                    total=100,
                )
                t_start  = datetime.now(timezone.utc)
                results  = self.engine.run_tactic(tactic, platform=platform)
                t_end    = datetime.now(timezone.utc)
                duration = (t_end - t_start).total_seconds() * 1000

                progress.update(task, completed=100)

                step = CampaignStep(tactic, results, duration)
                self.steps.append(step)
                self.all_results.extend(results)

                logger.info(
                    f"Campaign {self.campaign_id} | "
                    f"tactic={tactic} | "
                    f"simulated={step.simulated} | "
                    f"duration={duration:.0f}ms"
                )

        self.finished_at = datetime.now(timezone.utc).isoformat()

        # ── Validate all results ───────────────────────────────────
        console.print("\n[bold cyan]→ Validating detections...[/bold cyan]")
        self.validated = self.validator.validate(self.all_results)
        self.validator.print_gap_report(self.validated)

        # ── Generate Sigma for gaps ────────────────────────────────
        gaps = self.validator.get_gaps(self.validated)
        if gaps:
            console.print(
                f"\n[bold cyan]→ Generating Sigma rules "
                f"for {len(gaps)} gaps...[/bold cyan]"
            )
            self.sigma_rules = self.generator.generate(gaps)
            self.generator.save(self.sigma_rules)
            self.generator.save_bundle(self.sigma_rules)

        self._print_campaign_summary()
        return self.validated

    # ------------------------------------------------------------------ #
    #  Report                                                              #
    # ------------------------------------------------------------------ #

    def report(self, open_browser: bool = False) -> str:
        """Generate HTML report from campaign results."""
        if not self.validated:
            console.print("[yellow]⚠ Run campaign first — no results to report[/yellow]")
            return ""

        import subprocess
        self.report_path = self.reporter.generate(
            results     = self.validated,
            sigma_rules = self.sigma_rules,
            meta        = {
                "session_id":     self.campaign_id,
                "campaign":       self.profile.get("name"),
                "profile":        self.profile_key,
                "attack_version": "v14",
                "started_at":     self.started_at,
                "finished_at":    self.finished_at,
                "tactics":        self.profile["tactics"],
            },
            outfile = f"reports/campaign_{self.profile_key}_{self.campaign_id}.html",
        )

        if open_browser:
            subprocess.run(["open", self.report_path])

        return self.report_path

    def save_summary(self) -> str:
        """Save campaign summary JSON to reports/."""
        Path("reports").mkdir(exist_ok=True)
        filename = f"reports/campaign_{self.profile_key}_{self.campaign_id}_summary.json"

        simulated = [r for r in self.validated if r.status == "simulated"]
        detected  = [r for r in simulated if getattr(r, "detected", False)]
        gaps      = [r for r in simulated if not getattr(r, "detected", True)]

        payload = {
            "campaign_id":   self.campaign_id,
            "profile":       self.profile_key,
            "name":          self.profile.get("name"),
            "started_at":    self.started_at,
            "finished_at":   self.finished_at,
            "steps":         [s.to_dict() for s in self.steps],
            "coverage": {
                "total":     len(simulated),
                "detected":  len(detected),
                "gaps":      len(gaps),
                "pct":       round(len(detected) / len(simulated) * 100, 1)
                             if simulated else 0,
            },
            "sigma_rules_generated": len(self.sigma_rules),
            "report_path":           self.report_path,
        }

        with open(filename, "w") as f:
            json.dump(payload, f, indent=2)

        console.print(f"[bold green]✓ Summary saved → {filename}[/bold green]")
        return filename

    # ------------------------------------------------------------------ #
    #  Display                                                             #
    # ------------------------------------------------------------------ #

    def _print_campaign_banner(self):
        console.print(Panel(
            f"[bold cyan]{self.profile['name']}[/bold cyan]\n"
            f"[dim]{self.profile['description']}[/dim]\n\n"
            f"[yellow]Profile:[/yellow]  {self.profile_key}\n"
            f"[yellow]Tactics:[/yellow]  {' → '.join(self.profile['tactics'])}\n"
            f"[yellow]Platform:[/yellow] {self.profile.get('platform', 'macOS')}\n"
            f"[yellow]ID:[/yellow]       {self.campaign_id}",
            title="[bold]PhantomWatch Campaign[/bold]",
            border_style="cyan",
        ))

    def _print_campaign_summary(self):
        # ── Step timeline table ────────────────────────────────────
        table = Table(title="Campaign Timeline", style="cyan")
        table.add_column("Step",      style="dim",        no_wrap=True)
        table.add_column("Tactic",    style="bold yellow")
        table.add_column("Total",     style="white",  justify="right")
        table.add_column("Simulated", style="green",  justify="right")
        table.add_column("Skipped",   style="dim",    justify="right")
        table.add_column("Errors",    style="red",    justify="right")
        table.add_column("Duration",  style="magenta",justify="right")

        for i, step in enumerate(self.steps, 1):
            table.add_row(
                str(i),
                step.tactic.replace("_", " ").upper(),
                str(step.total),
                str(step.simulated),
                str(step.skipped),
                str(step.errors),
                f"{step.duration_ms / 1000:.1f}s",
            )

        console.print(table)

        # ── Overall stats ──────────────────────────────────────────
        simulated = [r for r in self.validated if r.status == "simulated"]
        detected  = [r for r in simulated if getattr(r, "detected", False)]
        gaps      = [r for r in simulated if not getattr(r, "detected", True)]
        coverage  = round(len(detected) / len(simulated) * 100, 1) if simulated else 0
        cov_color = "green" if coverage >= 70 else "yellow" if coverage >= 40 else "red"

        console.print(
            f"\n[bold]Campaign {self.campaign_id} complete[/bold] | "
            f"Tactics: {len(self.steps)} | "
            f"Techniques: {len(simulated)} simulated | "
            f"Coverage: [{cov_color}]{coverage}%[/{cov_color}] | "
            f"Gaps: [red]{len(gaps)}[/red] | "
            f"Sigma: [yellow]{len(self.sigma_rules)}[/yellow] rules generated"
        )
