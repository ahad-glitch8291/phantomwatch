"""
T1543.001 — Create or Modify System Process: Launch Agent
Simulates adversarial Launch Agent persistence on macOS.
Creates a .plist in ~/Library/LaunchAgents/, loads it via launchctl,
then cleans up completely.
"""

import plistlib
from pathlib import Path
from techniques.base import AtomicBase, Telemetry


AGENT_LABEL = "com.phantomwatch.test.agent"
AGENT_PATH  = Path.home() / "Library/LaunchAgents/com.phantomwatch.test.agent.plist"


class T1543_001_LaunchAgent(AtomicBase):
    TECHNIQUE_ID = "T1543.001"
    TACTIC       = "persistence"
    NAME         = "Create or Modify System Process: Launch Agent"
    PLATFORMS    = ["macOS"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # ── 1. Write a Launch Agent plist ─────────────────────────
        plist_data = {
            "Label":             AGENT_LABEL,
            "ProgramArguments":  ["/bin/bash", "-c", "echo phantomwatch-persistence >> /tmp/pw_agent.log"],
            "RunAtLoad":         True,
            "KeepAlive":         False,
            "StandardOutPath":   "/tmp/pw_agent_stdout.log",
            "StandardErrorPath": "/tmp/pw_agent_stderr.log",
        }

        AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_PATH, "wb") as f:
            plistlib.dump(plist_data, f)

        t = self._run_command(["ls", "-la", str(AGENT_PATH)])
        t.artifacts.append(str(AGENT_PATH))

        self._add_ioc(t, "path",    str(AGENT_PATH))
        self._add_ioc(t, "pattern", "LaunchAgents")
        self._add_ioc(t, "pattern", "RunAtLoad")
        self._add_ioc(t, "pattern", AGENT_LABEL)

        # ── 2. Load the agent via launchctl ───────────────────────
        load = self._run_command([
            "launchctl", "load", str(AGENT_PATH)
        ])
        t.stdout += f"\n--- launchctl load ---\n{load.stdout or '(no output — loaded)'}"
        t.stderr += load.stderr

        self._add_ioc(t, "process", "launchctl")
        self._add_ioc(t, "pattern", "launchctl load")

        # ── 3. Verify it is registered ────────────────────────────
        verify = self._run_command([
            "launchctl", "list", AGENT_LABEL
        ])
        if verify.exit_code == 0:
            t.stdout += f"\n--- launchctl list ---\n{verify.stdout}"
        else:
            t.stdout += f"\n--- launchctl list --- (agent queued for load at login)"

        # ── 4. Check persistence log artifact ─────────────────────
        log_check = self._run_command(["cat", "/tmp/pw_agent.log"])
        if log_check.exit_code == 0:
            t.stdout   += f"\n--- agent log output ---\n{log_check.stdout}"
            t.artifacts.append("/tmp/pw_agent.log")

        t.exit_code = 0
        return t

    def cleanup(self):
        # Unload from launchctl
        self._run_command(["launchctl", "unload", str(AGENT_PATH)])

        # Remove plist
        if AGENT_PATH.exists():
            AGENT_PATH.unlink()

        # Remove log artifacts
        for f in ["/tmp/pw_agent.log", "/tmp/pw_agent_stdout.log", "/tmp/pw_agent_stderr.log"]:
            p = Path(f)
            if p.exists():
                p.unlink()

        self._wipe_sandbox()
