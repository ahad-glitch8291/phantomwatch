"""
T1082 — System Information Discovery
Collects OS version, hardware, and kernel info via native macOS commands.
"""

from techniques.base import AtomicBase, Telemetry


class T1082_SystemInfoDiscovery(AtomicBase):
    TECHNIQUE_ID = "T1082"
    TACTIC       = "discovery"
    NAME         = "System Information Discovery"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # Primary: sw_vers gives OS name + version + build
        t = self._run_command(["sw_vers"])

        # Chain additional commands — append stdout
        for cmd in [
            ["uname", "-a"],
            ["sysctl", "-n", "hw.model"],
            ["sysctl", "-n", "hw.ncpu"],
            ["sysctl", "-n", "hw.memsize"],
        ]:
            extra = self._run_command(cmd)
            if extra.exit_code == 0:
                t.stdout += f"\n--- {' '.join(cmd)} ---\n{extra.stdout}"

        # IOCs — what a detection rule should look for
        self._add_ioc(t, "process", "sw_vers")
        self._add_ioc(t, "process", "uname")
        self._add_ioc(t, "process", "sysctl")
        self._add_ioc(t, "pattern", "hw.model")

        return t

    def cleanup(self):
        pass  # read-only — nothing to undo
