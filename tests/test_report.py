"""
Full end-to-end pipeline:
simulate → validate → sigma → HTML report
"""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from rich.console import Console
from core.engine              import PhantomEngineV2
from core.detection_validator import DetectionValidator
from core.sigma_generator     import SigmaGenerator
from core.reporter            import Reporter

console = Console()
console.print("\n[bold cyan]██ PhantomWatch — Full Pipeline ██[/bold cyan]\n")

# 1 — simulate
engine = PhantomEngineV2(config={"platform": "macOS"})
engine.load()
results  = engine.run_tactic("discovery", platform="macOS")
results += engine.run_tactic("execution", platform="macOS")

# 2 — validate
validator = DetectionValidator()
validator.load_rules()
validated = validator.validate(results)
validator.print_gap_report(validated)

# 3 — sigma
gaps      = validator.get_gaps(validated)
generator = SigmaGenerator()
rules     = generator.generate(gaps)
generator.save(rules)
generator.save_bundle(rules)

# 4 — report
reporter = Reporter()
path     = reporter.generate(
    results     = validated,
    sigma_rules = rules,
    meta        = {
        **engine.run_meta,
        "attack_version": "v14",
    },
)

console.print(f"\n[bold green]✓ Pipeline complete[/bold green]")
console.print(f"[bold cyan]→ Open your report:[/bold cyan]")
console.print(f"  open {path}\n")
