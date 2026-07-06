import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from core.engine import PhantomEngineV2

engine = PhantomEngineV2(config={"platform": "macOS"})
engine.load()

results = engine.run_tactic("discovery", platform="macOS")
engine.print_summary(results)
engine.save_results(results)
