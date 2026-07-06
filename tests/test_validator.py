"""Smoke test for DetectionValidator."""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from core.engine import PhantomEngine
from core.detection_validator import DetectionValidator

# Step 1 — simulate discovery tactic
engine = PhantomEngine(config={"platform": "macOS"})
engine.load()
results = engine.run_tactic("discovery")

# Step 2 — validate against detection rules
validator = DetectionValidator()
validator.load_rules()
validated = validator.validate(results)

# Step 3 — report
validator.print_gap_report(validated)

# Step 4 — inspect gaps
gaps = validator.get_gaps(validated)
print(f"\n→ {len(gaps)} techniques have no detection coverage:")
for g in gaps[:10]:
    print(f"  [{g.technique_id}] {g.name}")

# Step 5 — save
validator.save_validation(validated)
