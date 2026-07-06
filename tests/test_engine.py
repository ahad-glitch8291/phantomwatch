"""Smoke test for PhantomEngine."""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from core.engine import PhantomEngine

engine = PhantomEngine(config={"platform": "macOS"})
engine.load()

# Run a single technique
print("\n=== Single technique: T1082 ===")
result = engine.run_technique("T1082")
if result:
    print(result.to_dict())

# Run a full tactic
print("\n=== Tactic: discovery ===")
results = engine.run_tactic("discovery")
engine.print_summary(results)
engine.save_results(results)
