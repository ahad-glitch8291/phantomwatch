"""
T1083 — File and Directory Discovery
Enumerates home directory structure and sensitive file locations.
"""

import os
from techniques.base import AtomicBase, Telemetry


class T1083_FileDirectoryDiscovery(AtomicBase):
    TECHNIQUE_ID = "T1082"
    TACTIC       = "discovery"
    NAME         = "File and Directory Discovery"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    TECHNIQUE_ID = "T1083"

    def execute(self) -> Telemetry:
        home = os.path.expanduser("~")

        # Top-level home directory listing
        t = self._run_command(["ls", "-la", home])

        # Sensitive paths attackers commonly enumerate
        targets = [
            f"{home}/.ssh",
            f"{home}/.bash_history",
            f"{home}/.zsh_history",
            f"{home}/Library/Application Support",
            "/etc",
            "/tmp",
        ]

        for path in targets:
            extra = self._run_command(["ls", "-la", path])
            if extra.exit_code == 0:
                t.stdout += f"\n--- ls {path} ---\n{extra.stdout[:300]}"

        # find sensitive file types in home
        find = self._run_command([
            "find", home, "-maxdepth", "3",
            "-name", "*.pem", "-o",
            "-name", "*.key", "-o",
            "-name", "*.env",
        ], timeout=10)

        if find.stdout:
            t.stdout    += f"\n--- sensitive files ---\n{find.stdout[:500]}"
            t.artifacts  = find.stdout.splitlines()[:20]

        self._add_ioc(t, "process", "ls")
        self._add_ioc(t, "process", "find")
        self._add_ioc(t, "path",    "~/.ssh")
        self._add_ioc(t, "path",    "~/.bash_history")
        self._add_ioc(t, "pattern", "*.pem")

        return t

    def cleanup(self):
        pass  # read-only
