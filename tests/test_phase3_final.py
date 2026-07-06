"""
Phase 3 final pipeline:
campaign → matrix → sigma tuner → polished report
"""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from rich.console       import Console
from core.campaign      import Campaign
from core.coverage_matrix import CoverageMatrix
from core.sigma_tuner   import SigmaTuner

console = Console()
console.print("\n[bold cyan]██ PhantomWatch — Phase 3 Final Pipeline ██[/bold cyan]\n")

# 1 — Run campaign
campaign = Campaign("apt-macos")
campaign.run()

# 2 — Coverage matrix + Navigator
console.print("\n[bold cyan]══ Coverage Matrix ══[/bold cyan]")
matrix = CoverageMatrix()
matrix.build(campaign.validated)
matrix.print_matrix()
matrix.export_navigator(profile="apt-macos")
matrix.save_matrix()

# 3 — Tune Sigma rules
console.print("\n[bold cyan]══ Sigma Tuner ══[/bold cyan]")
tuner      = SigmaTuner()
tuned      = tuner.tune(campaign.sigma_rules)
tuner.save(tuned)
tuner.save_tuned_bundle(tuned)
tuner.print_summary(tuned)

# 4 — Generate polished report
console.print("\n[bold cyan]══ Generating Report ══[/bold cyan]")
path = campaign.report(open_browser=True)
campaign.save_summary()

console.print(f"\n[bold green]✓ Phase 3 complete[/bold green]")
console.print(f"  Report:          {path}")
console.print(f"  Navigator:       reports/navigator_apt-macos.json")
console.print(f"  Tuned rules:     sigma_rules/tuned/")
console.print(f"  Tuned bundle:    sigma_rules/tuned/phantomwatch_tuned_bundle.yml")
console.print(
    f"\n[bold cyan]→ ATT&CK Navigator:[/bold cyan]\n"
    f"  https://mitre-attack.github.io/attack-navigator/\n"
    f"  Open Existing Layer → upload reports/navigator_apt-macos.json"
)
