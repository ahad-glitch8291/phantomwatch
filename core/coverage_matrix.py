"""
coverage_matrix.py
Scores detection coverage per tactic and technique.
Exports ATT&CK Navigator layer JSON for visual coverage mapping.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib  import Path
from rich.console import Console
from rich.table   import Table

console = Console()
logger  = logging.getLogger(__name__)

COLOR_DETECTED = "#00ff9f"
COLOR_PARTIAL  = "#ffd700"
COLOR_GAP      = "#ff4d4d"
COLOR_SKIPPED  = "#334155"

TACTIC_KEY_MAP = {
    "credential_access":    "credential-access",
    "lateral_movement":     "lateral-movement",
    "defense_evasion":      "defense-evasion",
    "privilege_escalation": "privilege-escalation",
    "command_and_control":  "command-and-control",
    "initial_access":       "initial-access",
    "resource_development": "resource-development",
}

def _normalise_tactic(tactic: str) -> str:
    return TACTIC_KEY_MAP.get(tactic, tactic.replace("_", "-"))


class CoverageMatrix:
    def __init__(self):
        self.tactic_scores:    dict = {}
        self.technique_scores: dict = {}
        self.results:          list = []

    def build(self, results: list):
        self.results = results
        for r in results:
            if r.status != "simulated":
                continue
            tid    = r.technique_id
            tactic = r.tactics[0] if r.tactics else "unknown"
            detail = getattr(r, "detection_detail", {})
            status = detail.get("status", "unknown")
            conf   = detail.get("confidence") or "none"
            score  = self._score(status, conf)
            self.technique_scores[tid] = {
                "name":       r.name,
                "tactic":     tactic,
                "status":     status,
                "confidence": conf,
                "score":      score,
                "color":      self._color(status, conf),
                "rules":      detail.get("rules", []),
            }
            self.tactic_scores.setdefault(tactic, {
                "detected": 0, "partial": 0, "undetected": 0, "total": 0,
            })
            self.tactic_scores[tactic]["total"] += 1
            if status == "detected":
                self.tactic_scores[tactic]["detected"]   += 1
            elif status == "partial":
                self.tactic_scores[tactic]["partial"]    += 1
            else:
                self.tactic_scores[tactic]["undetected"] += 1

        console.print(
            f"[bold green]✓ Coverage matrix built — "
            f"{len(self.technique_scores)} techniques scored[/bold green]"
        )

    def _score(self, status, confidence):
        if status == "detected":
            return {"high": 100, "medium": 75, "low": 50}.get(confidence, 75)
        elif status == "partial":
            return 25
        return 0

    def _color(self, status, confidence):
        if status == "detected":
            return COLOR_DETECTED
        elif status == "partial":
            return COLOR_PARTIAL
        return COLOR_GAP

    def print_matrix(self):
        table = Table(title="PhantomWatch — Coverage Matrix", style="cyan")
        table.add_column("Tactic",      style="bold yellow")
        table.add_column("Detected",    style="green",   justify="right")
        table.add_column("Partial",     style="yellow",  justify="right")
        table.add_column("Undetected",  style="red",     justify="right")
        table.add_column("Total",       style="white",   justify="right")
        table.add_column("Coverage %",  style="magenta", justify="right")
        table.add_column("Grade",       style="bold",    justify="center")

        overall_det = overall_total = 0
        for tactic, s in sorted(self.tactic_scores.items()):
            pct   = round(s["detected"] / s["total"] * 100) if s["total"] else 0
            grade = (
                "[green]A[/green]"   if pct >= 80 else
                "[cyan]B[/cyan]"     if pct >= 60 else
                "[yellow]C[/yellow]" if pct >= 40 else
                "[red]D[/red]"       if pct >= 20 else
                "[red]F[/red]"
            )
            table.add_row(
                tactic.replace("_", " ").title(),
                str(s["detected"]), str(s["partial"]),
                str(s["undetected"]), str(s["total"]),
                f"{pct}%", grade,
            )
            overall_det   += s["detected"]
            overall_total += s["total"]

        console.print(table)
        overall_pct = round(overall_det / overall_total * 100) if overall_total else 0
        color = "green" if overall_pct >= 70 else "yellow" if overall_pct >= 40 else "red"
        console.print(
            f"\n[bold]Overall coverage: [{color}]{overall_pct}%[/{color}][/bold] — "
            f"{overall_det} detected / {overall_total} simulated"
        )

    def export_navigator(self, profile="phantomwatch", outfile=None) -> str:
        techniques_layer = []
        for tid, data in self.technique_scores.items():
            tactic = _normalise_tactic(data["tactic"])
            techniques_layer.append({
                "techniqueID": tid,
                "tactic":      tactic,
                "color":       data["color"],
                "comment":     (
                    f"Status: {data['status']} | "
                    f"Confidence: {data['confidence']} | "
                    f"Score: {data['score']} | "
                    f"Rules: {', '.join(data['rules']) or 'none'}"
                ),
                "enabled": True,
                "score":   data["score"],
                "metadata": [
                    {"name": "phantomwatch_status",     "value": data["status"]},
                    {"name": "phantomwatch_confidence", "value": data["confidence"]},
                    {"name": "rules_hit", "value": ", ".join(data["rules"]) or "none"},
                ],
            })

        simulated_ids = set(self.technique_scores.keys())
        for r in self.results:
            if r.status == "skipped" and r.technique_id not in simulated_ids:
                tactic = _normalise_tactic(r.tactics[0] if r.tactics else "unknown")
                techniques_layer.append({
                    "techniqueID": r.technique_id,
                    "tactic":      tactic,
                    "color":       COLOR_SKIPPED,
                    "comment":     "Skipped — platform not applicable",
                    "enabled":     True,
                    "score":       0,
                })

        layer = {
            "name":    f"PhantomWatch — {profile}",
            "versions": {"attack": "14", "navigator": "4.9", "layer": "4.5"},
            "domain":  "enterprise-attack",
            "description": (
                f"Auto-generated by PhantomWatch. Profile: {profile}. "
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            ),
            "filters":  {"platforms": ["macOS", "Linux"]},
            "sorting":  3,
            "layout": {
                "layout": "side", "aggregateFunction": "average",
                "showID": True, "showName": True,
                "showAggregateScores": True, "countUnscored": False,
            },
            "hideDisabled": False,
            "techniques":   techniques_layer,
            "gradient": {
                "colors":   [COLOR_GAP, COLOR_PARTIAL, COLOR_DETECTED],
                "minValue": 0, "maxValue": 100,
            },
            "legendItems": [
                {"label": "Detected",          "color": COLOR_DETECTED},
                {"label": "Partial",           "color": COLOR_PARTIAL},
                {"label": "Gap",               "color": COLOR_GAP},
                {"label": "Skipped",           "color": COLOR_SKIPPED},
            ],
            "metadata": [
                {"name": "generated_by", "value": "PhantomWatch"},
                {"name": "profile",      "value": profile},
                {"name": "generated_at", "value": datetime.now(timezone.utc).isoformat()},
            ],
        }

        Path("reports").mkdir(exist_ok=True)
        filename = outfile or f"reports/navigator_{profile}.json"
        with open(filename, "w") as f:
            json.dump(layer, f, indent=2)

        console.print(f"[bold green]✓ Navigator layer → {filename}[/bold green]")
        console.print(
            f"[dim]  Open https://mitre-attack.github.io/attack-navigator/ "
            f"→ Open Existing Layer → Upload File[/dim]"
        )
        return filename

    def save_matrix(self, outfile=None) -> str:
        Path("reports").mkdir(exist_ok=True)
        ts       = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = outfile or f"reports/coverage_matrix_{ts}.json"
        with open(filename, "w") as f:
            json.dump({
                "generated_at":     datetime.now(timezone.utc).isoformat(),
                "tactic_scores":    self.tactic_scores,
                "technique_scores": self.technique_scores,
            }, f, indent=2)
        console.print(f"[bold green]✓ Matrix saved → {filename}[/bold green]")
        return filename
