"""
technique_loader.py
Loads and parses MITRE ATT&CK techniques using the official STIX data feed.
"""

import json
import requests
from rich.console import Console
from rich.table import Table

console = Console()

ATTACK_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

class TechniqueLoader:
    def __init__(self):
        self.techniques = []
        self.tactics = {}

    def fetch(self):
        """Pull the MITRE ATT&CK STIX bundle from GitHub."""
        console.print("[bold cyan]→ Fetching MITRE ATT&CK data feed...[/bold cyan]")
        try:
            r = requests.get(ATTACK_URL, timeout=30)
            r.raise_for_status()
            bundle = r.json()
            self._parse(bundle)
            console.print(f"[bold green]✓ Loaded {len(self.techniques)} techniques[/bold green]")
        except requests.RequestException as e:
            console.print(f"[bold red]✗ Failed to fetch ATT&CK data: {e}[/bold red]")
            raise

    def _parse(self, bundle):
        """Extract techniques and tactic mappings from STIX bundle."""
        for obj in bundle.get("objects", []):
            if obj.get("type") != "attack-pattern":
                continue
            if obj.get("x_mitre_deprecated", False) or obj.get("revoked", False):
                continue

            technique_id = None
            for ref in obj.get("external_references", []):
                if ref.get("source_name") == "mitre-attack":
                    technique_id = ref.get("external_id")
                    break

            if not technique_id:
                continue

            tactic_list = [
                phase["phase_name"]
                for phase in obj.get("kill_chain_phases", [])
                if phase.get("kill_chain_name") == "mitre-attack"
            ]

            technique = {
                "id":          technique_id,
                "name":        obj.get("name", ""),
                "description": obj.get("description", "")[:300],
                "tactics":     tactic_list,
                "platforms":   obj.get("x_mitre_platforms", []),
                "is_subtechnique": "." in technique_id,
            }

            self.techniques.append(technique)

            for tactic in tactic_list:
                self.tactics.setdefault(tactic, []).append(technique)

    def get_by_tactic(self, tactic: str) -> list:
        """Return all techniques for a given tactic."""
        return self.tactics.get(tactic.replace("_", "-").replace(" ", "-"), [])

    def get_by_id(self, technique_id: str) -> dict | None:
        """Look up a single technique by ID (e.g. T1059)."""
        for t in self.techniques:
            if t["id"].upper() == technique_id.upper():
                return t
        return None

    def search(self, keyword: str) -> list:
        """Search techniques by name keyword."""
        keyword = keyword.lower()
        return [t for t in self.techniques if keyword in t["name"].lower()]

    def summary_table(self):
        """Print a rich table of tactics and technique counts."""
        table = Table(title="MITRE ATT&CK — Loaded Tactics", style="cyan")
        table.add_column("Tactic", style="bold yellow")
        table.add_column("Technique Count", justify="right", style="green")

        for tactic, techs in sorted(self.tactics.items()):
            table.add_row(tactic.replace("-", " ").title(), str(len(techs)))

        console.print(table)
