"""
base.py
Abstract base class for all PhantomWatch atomic techniques.
Every technique module inherits from AtomicBase.
"""

import os
import subprocess
import shutil
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SANDBOX_DIR = Path("/tmp/phantomwatch-sandbox")


@dataclass
class Telemetry:
    """Raw execution telemetry captured during an atomic run."""
    technique_id:  str
    command:       str
    stdout:        str        = ""
    stderr:        str        = ""
    exit_code:     int        = -1
    pid:           int        = -1
    started_at:    str        = ""
    finished_at:   str        = ""
    duration_ms:   float      = 0.0
    iocs:          list       = field(default_factory=list)
    artifacts:     list       = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "technique_id": self.technique_id,
            "command":      self.command,
            "stdout":       self.stdout[:2000],
            "stderr":       self.stderr[:500],
            "exit_code":    self.exit_code,
            "pid":          self.pid,
            "started_at":   self.started_at,
            "finished_at":  self.finished_at,
            "duration_ms":  self.duration_ms,
            "iocs":         self.iocs,
            "artifacts":    self.artifacts,
        }


class AtomicBase(ABC):
    """
    Abstract base for all atomic technique implementations.

    Subclasses must define:
        TECHNIQUE_ID  — e.g. "T1082"
        TACTIC        — e.g. "discovery"
        PLATFORMS     — e.g. ["macOS", "Linux"]
        NAME          — human-readable name

    And implement:
        execute()     — run the technique, return Telemetry
        cleanup()     — undo any artifacts created
    """

    TECHNIQUE_ID: str       = ""
    TACTIC:       str       = ""
    PLATFORMS:    list[str] = []
    NAME:         str       = ""
    SAFE:         bool      = True   # False = requires --force flag

    def __init__(self, platform: str = "macOS", allow_network: bool = False):
        self.platform       = platform
        self.allow_network  = allow_network
        self.sandbox        = SANDBOX_DIR / self.TECHNIQUE_ID
        self._telemetry:    list[Telemetry] = []

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def setup(self):
        """Create sandbox dir before execution."""
        self.sandbox.mkdir(parents=True, exist_ok=True)
        logger.info(f"[{self.TECHNIQUE_ID}] sandbox ready: {self.sandbox}")

    @abstractmethod
    def execute(self) -> Telemetry:
        """Run the atomic. Must return a populated Telemetry object."""
        ...

    @abstractmethod
    def cleanup(self):
        """Remove any artifacts, processes, or files created."""
        ...

    def run(self) -> Telemetry:
        """
        Full lifecycle: setup → execute → cleanup.
        Called by the engine — do not override.
        """
        if self.platform not in self.PLATFORMS:
            return self._skip(f"Platform '{self.platform}' not supported")

        self.setup()
        try:
            telemetry = self.execute()
            self._telemetry.append(telemetry)
            logger.info(
                f"[{self.TECHNIQUE_ID}] executed | "
                f"exit={telemetry.exit_code} | "
                f"duration={telemetry.duration_ms:.0f}ms"
            )
            return telemetry
        except Exception as e:
            logger.error(f"[{self.TECHNIQUE_ID}] execution error: {e}")
            return self._error(str(e))
        finally:
            try:
                self.cleanup()
            except Exception as e:
                logger.warning(f"[{self.TECHNIQUE_ID}] cleanup error: {e}")

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _run_command(self, cmd: list[str] | str, shell: bool = False, timeout: int = 15) -> Telemetry:
        """
        Execute a shell command and capture full telemetry.
        Use this inside execute() for every command you run.
        """
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        t = Telemetry(
            technique_id = self.TECHNIQUE_ID,
            command      = cmd_str,
            started_at   = datetime.now(timezone.utc).isoformat(),
        )

        try:
            start = datetime.now(timezone.utc)
            proc  = subprocess.run(
                cmd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.sandbox),
            )
            end = datetime.now(timezone.utc)

            t.stdout      = proc.stdout.strip()
            t.stderr      = proc.stderr.strip()
            t.exit_code   = proc.returncode
            t.pid         = proc.pid if hasattr(proc, "pid") else -1
            t.finished_at = end.isoformat()
            t.duration_ms = (end - start).total_seconds() * 1000

        except subprocess.TimeoutExpired:
            t.stderr    = f"Timed out after {timeout}s"
            t.exit_code = -1
        except FileNotFoundError as e:
            t.stderr    = f"Command not found: {e}"
            t.exit_code = 127

        return t

    def _skip(self, reason: str) -> Telemetry:
        return Telemetry(
            technique_id = self.TECHNIQUE_ID,
            command      = "N/A",
            stdout       = "",
            stderr       = reason,
            exit_code    = -99,
            started_at   = datetime.now(timezone.utc).isoformat(),
            finished_at  = datetime.now(timezone.utc).isoformat(),
        )

    def _error(self, reason: str) -> Telemetry:
        return Telemetry(
            technique_id = self.TECHNIQUE_ID,
            command      = "N/A",
            stderr       = reason,
            exit_code    = -1,
            started_at   = datetime.now(timezone.utc).isoformat(),
            finished_at  = datetime.now(timezone.utc).isoformat(),
        )

    def _add_ioc(self, telemetry: Telemetry, ioc_type: str, value: str):
        """Attach an indicator of compromise to telemetry."""
        telemetry.iocs.append({"type": ioc_type, "value": value})

    def _wipe_sandbox(self):
        """Nuclear cleanup — removes entire sandbox for this technique."""
        if self.sandbox.exists():
            shutil.rmtree(self.sandbox)
