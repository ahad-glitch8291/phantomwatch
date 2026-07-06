"""
Full pipeline test:
simulate → validate → extract gaps → generate Sigma → save
"""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from rich.console import Console
from core.engine              import PhantomEngineV2
from core.detection_validator import DetectionValidator
from core.sigma_generator     import SigmaGenerator

console = Console()

# ── 1. Simulate discovery + execution tactics ──────────────────────
console.print("\n[bold cyan]══ Step 1: Simulate ══[/bold cyan]")
engine = PhantomEngineV2(config={"platform": "macOS"})
engine.load()

discovery_results = engine.run_tactic("discovery", platform="macOS")
execution_results = engine.run_tactic("execution", platform="macOS")
all_results       = discovery_results + execution_results

# ── 2. Validate ────────────────────────────────────────────────────
console.print("\n[bold cyan]══ Step 2: Validate ══[/bold cyan]")
validator = DetectionValidator()
validator.load_rules()
validated = validator.validate(all_results)
validator.print_gap_report(validated)

# ── 3. Extract gaps ────────────────────────────────────────────────
gaps = validator.get_gaps(validated)
console.print(f"\n[bold yellow]⚡ {len(gaps)} gaps found[/bold yellow]")

# ── 4. Generate Sigma rules ────────────────────────────────────────
console.print("\n[bold cyan]══ Step 3: Generate Sigma ══[/bold cyan]")
generator = SigmaGenerator()
rules     = generator.generate(gaps)
generator.print_summary(rules)

# ── 5. Save individual rules + bundle ─────────────────────────────
console.print("\n[bold cyan]══ Step 4: Save ══[/bold cyan]")
generator.save(rules)
bundle = generator.save_bundle(rules)

# ── 6. Preview one rule ────────────────────────────────────────────
if rules:
    console.print(f"\n[bold cyan]══ Preview: {rules[0].technique_id} ══[/bold cyan]")
    console.print(rules[0].to_yaml())

console.print(f"\n[bold green]✓ Pipeline complete — {len(rules)} Sigma rules ready[/bold green]")
console.print(f"[dim]Bundle: {bundle}[/dim]")
