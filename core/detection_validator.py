"""
detection_validator.py
Validates simulation results against detection rules.
Flags techniques as detected, undetected, or partial.
Gaps feed into sigma_generator.py
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table

console = Console()

# Detection status constants
DETECTED   = "detected"
UNDETECTED = "undetected"
PARTIAL    = "partial"
UNKNOWN    = "unknown"


class DetectionRule:
    """Represents a single detection rule loaded from /detections."""

    def __init__(self, data: dict):
        self.rule_id      = data.get("rule_id", "UNKNOWN")
        self.name         = data.get("name", "")
        self.technique_ids = [t.upper() for t in data.get("technique_ids", [])]
        self.keywords     = [k.lower() for k in data.get("keywords", [])]
        self.log_source   = data.get("log_source", "")
        self.confidence   = data.get("confidence", "medium")  # low / medium / high
        self.enabled      = data.get("enabled", True)

    def matches(self, technique_id: str) -> bool:
        return technique_id.upper() in self.technique_ids


class DetectionValidator:
    """
    Validates simulated techniques against loaded detection rules.

    Usage:
        validator = DetectionValidator()
        validator.load_rules()
        validated = validator.validate(results)
        validator.print_gap_report(validated)
        gaps = validator.get_gaps(validated)
    """

    def __init__(self, rules_dir: str = "detections"):
        self.rules_dir = Path(rules_dir)
        self.rules: list[DetectionRule] = []

    # ------------------------------------------------------------------ #
    #  Rule loading                                                        #
    # ------------------------------------------------------------------ #

    def load_rules(self):
        """Load all .json detection rules from /detections."""
        self.rules = []
        if not self.rules_dir.exists():
            console.print(f"[yellow]⚠ Detections dir not found: {self.rules_dir}[/yellow]")
            return

        for path in self.rules_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                rule = DetectionRule(data)
                if rule.enabled:
                    self.rules.append(rule)
            except Exception as e:
                console.print(f"[red]✗ Failed to load rule {path.name}: {e}[/red]")

        console.print(f"[bold green]✓ Loaded {len(self.rules)} detection rules[/bold green]")

    # ------------------------------------------------------------------ #
    #  Validation                                                          #
    # ------------------------------------------------------------------ #

    def validate(self, results: list) -> list:
        """
        Cross-reference simulation results against detection rules.
        Attaches detection status to each SimulationResult.
        Returns the annotated list.
        """
        rule_index = {}
        for rule in self.rules:
            for tid in rule.technique_ids:
                rule_index.setdefault(tid, []).append(rule)

        for result in results:
            if result.status != "simulated":
                result.detected = None
                result.detection_detail = {"status": UNKNOWN, "rules": []}
                continue

            tid = result.technique_id.upper()
            matching = rule_index.get(tid, [])

            if not matching:
                result.detected = False
                result.detection_detail = {
                    "status":      UNDETECTED,
                    "rules":       [],
                    "gap":         True,
                    "confidence":  None,
                }
            else:
                confidences = [r.confidence for r in matching]
                top = "high" if "high" in confidences else \
                      "medium" if "medium" in confidences else "low"

                # Partial: matched but low confidence only
                if all(c == "low" for c in confidences):
                    status = PARTIAL
                    result.detected = False
                else:
                    status = DETECTED
                    result.detected = True

                result.detection_detail = {
                    "status":     status,
                    "rules":      [r.rule_id for r in matching],
                    "confidence": top,
                    "gap":        status == PARTIAL,
                }

        return results

    # ------------------------------------------------------------------ #
    #  Reporting                                                           #
    # ------------------------------------------------------------------ #

    def print_gap_report(self, results: list):
        """Rich table showing detection coverage and gaps."""
        simulated = [r for r in results if r.status == "simulated"]
        detected  = [r for r in simulated if getattr(r, "detected", False)]
        gaps      = [r for r in simulated if not getattr(r, "detected", True)]

        coverage  = (len(detected) / len(simulated) * 100) if simulated else 0

        table = Table(title="PhantomWatch — Detection Gap Report", style="cyan")
        table.add_column("Technique",  style="bold white", no_wrap=True)
        table.add_column("Name",       style="white")
        table.add_column("Tactic",     style="yellow")
        table.add_column("Status",     style="green")
        table.add_column("Confidence", style="magenta")
        table.add_column("Rules Hit",  style="dim")

        for r in simulated[:50]:
            detail  = getattr(r, "detection_detail", {})
            status  = detail.get("status", UNKNOWN)
            conf    = detail.get("confidence") or "—"
            rules   = ", ".join(detail.get("rules", [])) or "—"
            tactic  = r.tactics[0] if r.tactics else "—"

            color = {
                DETECTED:   "green",
                UNDETECTED: "red",
                PARTIAL:    "yellow",
                UNKNOWN:    "dim",
            }.get(status, "white")

            table.add_row(
                r.technique_id,
                r.name[:50],
                tactic.replace("-", " ").title(),
                f"[{color}]{status}[/{color}]",
                conf,
                rules,
            )

        console.print(table)
        console.print(
            f"\n[bold]Coverage:[/bold] [{'green' if coverage >= 70 else 'yellow' if coverage >= 40 else 'red'}]"
            f"{coverage:.1f}%[/] — "
            f"[green]Detected: {len(detected)}[/green] | "
            f"[red]Gaps: {len(gaps)}[/red] | "
            f"[dim]Total simulated: {len(simulated)}[/dim]"
        )

    def get_gaps(self, results: list) -> list:
        """Return only undetected/partial simulated techniques — fed to Sigma generator."""
        return [
            r for r in results
            if r.status == "simulated" and not getattr(r, "detected", True)
        ]

    def save_validation(self, results: list, outfile: str | None = None):
        """Persist validated results with detection detail to JSON."""
        Path("reports").mkdir(exist_ok=True)
        ts       = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = outfile or f"reports/validation_{ts}.json"

        payload = []
        for r in results:
            d = r.to_dict()
            d["detection_detail"] = getattr(r, "detection_detail", {})
            payload.append(d)

        with open(filename, "w") as f:
            json.dump(payload, f, indent=2)

        console.print(f"[bold green]✓ Validation saved → {filename}[/bold green]")
        return filename
