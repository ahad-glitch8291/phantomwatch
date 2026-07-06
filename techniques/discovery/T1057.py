"""
T1057 — Process Discovery
Enumerates running processes and identifies security tooling.
"""

from techniques.base import AtomicBase, Telemetry

SECURITY_TOOLS = [
    "CrowdStrike", "falcon", "carbon black", "cbd",
    "SentinelOne", "sentineld", "Cylance", "cylance",
    "Elastic", "elastic-agent", "osquery", "osqueryd",
    "Wireshark", "tcpdump", "Little Snitch", "littlesnitch",
]


class T1057_ProcessDiscovery(AtomicBase):
    TECHNIQUE_ID = "T1057"
    TACTIC       = "discovery"
    NAME         = "Process Discovery"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # Full process list
        t = self._run_command(["ps", "aux"])

        # macOS-specific process tree
        extra = self._run_command(["ps", "-axo", "pid,ppid,user,comm"])
        if extra.exit_code == 0:
            t.stdout += f"\n--- process tree ---\n{extra.stdout[:1000]}"

        # Identify security tools in process list
        found_tools = []
        for line in t.stdout.splitlines():
            for tool in SECURITY_TOOLS:
                if tool.lower() in line.lower():
                    found_tools.append(tool)

        if found_tools:
            t.stdout   += f"\n--- security tools detected ---\n" + "\n".join(set(found_tools))
            t.artifacts = list(set(found_tools))

        self._add_ioc(t, "process", "ps")
        self._add_ioc(t, "pattern", "ps aux")
        self._add_ioc(t, "pattern", "ps -axo pid,ppid")
        for tool in found_tools:
            self._add_ioc(t, "security_tool_found", tool)

        return t

    def cleanup(self):
        pass  # read-only
