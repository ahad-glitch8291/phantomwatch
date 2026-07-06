"""
T1016 — System Network Configuration Discovery
Enumerates network interfaces, routing tables, DNS, and ARP cache.
"""

from techniques.base import AtomicBase, Telemetry


class T1016_NetworkConfigDiscovery(AtomicBase):
    TECHNIQUE_ID = "T1016"
    TACTIC       = "discovery"
    NAME         = "System Network Configuration Discovery"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # Network interfaces
        t = self._run_command(["ifconfig"])

        # Routing table
        for cmd, label in [
            (["netstat", "-rn"],         "routing table"),
            (["arp",     "-a"],          "arp cache"),
            (["cat",     "/etc/hosts"],  "hosts file"),
            (["networksetup", "-listallnetworkservices"], "network services"),
            (["scutil",  "--dns"],       "dns config"),
        ]:
            extra = self._run_command(cmd)
            if extra.exit_code == 0:
                t.stdout += f"\n--- {label} ---\n{extra.stdout[:500]}"

        self._add_ioc(t, "process", "ifconfig")
        self._add_ioc(t, "process", "netstat")
        self._add_ioc(t, "process", "arp")
        self._add_ioc(t, "process", "scutil")
        self._add_ioc(t, "path",    "/etc/hosts")

        return t

    def cleanup(self):
        pass  # read-only
