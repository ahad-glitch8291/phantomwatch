"""
registry.py
Auto-discovers and indexes all AtomicBase subclasses in /techniques.
Drop a new technique .py file in the right tactic folder — it's live.
"""

import importlib
import pkgutil
import logging
from pathlib import Path
from rich.console import Console
from rich.table import Table

from techniques.base import AtomicBase

console = Console()
logger  = logging.getLogger(__name__)


class AtomicRegistry:
    """
    Scans techniques/ subdirectories and builds an index of
    all AtomicBase subclasses keyed by TECHNIQUE_ID.

    Usage:
        registry = AtomicRegistry()
        registry.discover()
        atomic_cls = registry.get("T1082")
        telemetry  = atomic_cls().run()
    """

    def __init__(self):
        self._registry: dict[str, type[AtomicBase]] = {}

    def discover(self, base_package: str = "techniques"):
        """Walk techniques/ subpackages and register all AtomicBase subclasses."""
        self._registry.clear()
        base_path = Path(__file__).parent

        for finder, pkg_name, is_pkg in pkgutil.walk_packages(
            path=[str(base_path)],
            prefix=f"{base_package}.",
            onerror=lambda x: logger.warning(f"Import error in {x}"),
        ):
            # skip __init__ and base/registry modules
            if any(x in pkg_name for x in ["__init__", "base", "registry"]):
                continue
            try:
                module = importlib.import_module(pkg_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, AtomicBase)
                        and attr is not AtomicBase
                        and attr.TECHNIQUE_ID
                    ):
                        self._registry[attr.TECHNIQUE_ID.upper()] = attr
                        logger.debug(f"Registered: {attr.TECHNIQUE_ID} ← {pkg_name}")
            except Exception as e:
                logger.warning(f"Failed to import {pkg_name}: {e}")

        console.print(f"[bold green]✓ Registry: {len(self._registry)} atomics loaded[/bold green]")

    def get(self, technique_id: str) -> type[AtomicBase] | None:
        """Return the atomic class for a technique ID, or None."""
        return self._registry.get(technique_id.upper())

    def all(self) -> dict[str, type[AtomicBase]]:
        return dict(self._registry)

    def by_tactic(self, tactic: str) -> dict[str, type[AtomicBase]]:
        """Return all atomics for a given tactic."""
        return {
            tid: cls for tid, cls in self._registry.items()
            if cls.TACTIC.lower() == tactic.lower()
        }

    def summary_table(self):
        """Rich table of all registered atomics."""
        table = Table(title="Atomic Registry", style="cyan")
        table.add_column("ID",       style="bold yellow", no_wrap=True)
        table.add_column("Name",     style="white")
        table.add_column("Tactic",   style="dim")
        table.add_column("Platforms",style="dim")
        table.add_column("Safe",     style="green")

        for tid, cls in sorted(self._registry.items()):
            table.add_row(
                tid,
                cls.NAME[:50],
                cls.TACTIC,
                ", ".join(cls.PLATFORMS),
                "✓" if cls.SAFE else "[red]✗[/red]",
            )

        console.print(table)
