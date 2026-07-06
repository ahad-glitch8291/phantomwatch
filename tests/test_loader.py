"""Quick smoke test for TechniqueLoader."""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from core.technique_loader import TechniqueLoader

loader = TechniqueLoader()
loader.fetch()
loader.summary_table()

# Spot checks
print("\n--- Lookup T1059 ---")
t = loader.get_by_id("T1059")
if t:
    print(f"  {t['id']} | {t['name']} | Tactics: {t['tactics']}")

print("\n--- Search 'phishing' ---")
for t in loader.search("phishing")[:3]:
    print(f"  {t['id']} | {t['name']}")

print("\n--- Discovery techniques (first 5) ---")
for t in loader.get_by_tactic("discovery")[:5]:
    print(f"  {t['id']} | {t['name']}")
