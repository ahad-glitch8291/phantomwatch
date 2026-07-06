"""Verify registry discovers atomics correctly (0 for now — grows with each step)."""
import sys
sys.path.insert(0, "/Users/ahadshaikh/phantomwatch")

from techniques.registry import AtomicRegistry

registry = AtomicRegistry()
registry.discover()
registry.summary_table()
print(f"\n→ Total atomics registered: {len(registry.all())}")
print("→ Registry wired correctly — ready for atomic modules")
