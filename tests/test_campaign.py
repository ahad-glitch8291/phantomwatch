"""
Full campaign integration test — apt-macos profile.
"""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from rich.console import Console
from core.campaign import Campaign, CAMPAIGN_PROFILES

console = Console()

# ── List available profiles ────────────────────────────────────────
console.print("\n[bold cyan]Available campaign profiles:[/bold cyan]")
for key, p in CAMPAIGN_PROFILES.items():
    console.print(f"  [yellow]{key}[/yellow] — {p['name']}")

# ── Run apt-macos campaign ─────────────────────────────────────────
console.print("\n[bold cyan]══ Running: apt-macos ══[/bold cyan]\n")
campaign = Campaign("apt-macos")
campaign.run()

# ── Generate report ────────────────────────────────────────────────
path    = campaign.report(open_browser=True)
summary = campaign.save_summary()

console.print(f"\n[bold green]✓ Campaign complete[/bold green]")
console.print(f"  Report:  {path}")
console.print(f"  Summary: {summary}")
