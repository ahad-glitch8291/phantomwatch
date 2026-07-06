"""
T1059.006 — Command and Scripting Interpreter: Python
Simulates adversarial Python execution patterns:
- inline -c execution
- base64-encoded payload (common obfuscation)
- environment reconnaissance via Python
"""

import base64
from techniques.base import AtomicBase, Telemetry


class T1059_006_PythonExecution(AtomicBase):
    TECHNIQUE_ID = "T1059.006"
    TACTIC       = "execution"
    NAME         = "Command and Scripting Interpreter: Python"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # ── 1. Inline -c execution ─────────────────────────────────
        t = self._run_command([
            "python3", "-c",
            "import sys; print('interpreter:', sys.executable); print('version:', sys.version)"
        ])

        self._add_ioc(t, "process",  "python3")
        self._add_ioc(t, "pattern",  "python3 -c")

        # ── 2. Base64-encoded payload (common evasion pattern) ─────
        payload     = "import os; print(os.uname())"
        encoded     = base64.b64encode(payload.encode()).decode()
        decode_cmd  = f"import base64; exec(base64.b64decode('{encoded}').decode())"

        b64 = self._run_command(["python3", "-c", decode_cmd])
        if b64.exit_code == 0:
            t.stdout += f"\n--- base64 payload execution ---\n{b64.stdout}"

        self._add_ioc(t, "pattern", "base64.b64decode")
        self._add_ioc(t, "pattern", "exec(base64")

        # ── 3. Environment recon via Python ───────────────────────
        recon_script = (
            "import os, sys, socket; "
            "print('host:', socket.gethostname()); "
            "print('user:', os.getenv('USER')); "
            "print('path:', os.getenv('PATH', '')[:80])"
        )
        recon = self._run_command(["python3", "-c", recon_script])
        if recon.exit_code == 0:
            t.stdout += f"\n--- env recon ---\n{recon.stdout}"

        self._add_ioc(t, "pattern", "socket.gethostname")
        self._add_ioc(t, "pattern", "os.getenv")

        # ── 4. Write + execute a temp script (file-based execution) ─
        script_path = self.sandbox / "recon.py"
        script_path.write_text(
            "import platform, os\n"
            "print('platform:', platform.platform())\n"
            "print('cwd:', os.getcwd())\n"
        )
        file_exec = self._run_command(["python3", str(script_path)])
        if file_exec.exit_code == 0:
            t.stdout   += f"\n--- file-based execution ---\n{file_exec.stdout}"
            t.artifacts.append(str(script_path))

        self._add_ioc(t, "artifact", str(script_path))
        self._add_ioc(t, "pattern",  "platform.platform()")

        return t

    def cleanup(self):
        script = self.sandbox / "recon.py"
        if script.exists():
            script.unlink()
        self._wipe_sandbox()
