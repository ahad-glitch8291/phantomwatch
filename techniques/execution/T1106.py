"""
T1106 — Native API
Simulates execution via OS-level subprocess and native API calls —
a common pattern in malware that avoids obvious shell interpreters.
"""

import os
from techniques.base import AtomicBase, Telemetry


class T1106_NativeAPI(AtomicBase):
    TECHNIQUE_ID = "T1106"
    TACTIC       = "execution"
    NAME         = "Native API"
    PLATFORMS    = ["macOS", "Linux"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # ── 1. os.system() — lowest-level shell execution ─────────
        t = self._run_command(["python3", "-c",
            "import os; ret = os.system('id'); print('os.system ret:', ret)"
        ])

        self._add_ioc(t, "process", "python3")
        self._add_ioc(t, "pattern", "os.system")

        # ── 2. subprocess.Popen — direct process spawning ─────────
        popen_cmd = (
            "import subprocess; "
            "p = subprocess.Popen(['whoami'], stdout=subprocess.PIPE); "
            "out, _ = p.communicate(); "
            "print('popen whoami:', out.decode().strip())"
        )
        popen = self._run_command(["python3", "-c", popen_cmd])
        if popen.exit_code == 0:
            t.stdout += f"\n--- subprocess.Popen ---\n{popen.stdout}"

        self._add_ioc(t, "pattern", "subprocess.Popen")
        self._add_ioc(t, "pattern", "stdout=subprocess.PIPE")

        # ── 3. os.execve() simulation — process replacement ────────
        execve_cmd = (
            "import os, sys; "
            "print('execve target: /usr/bin/id'); "
            "print('would replace pid:', os.getpid())"
        )
        execve = self._run_command(["python3", "-c", execve_cmd])
        if execve.exit_code == 0:
            t.stdout += f"\n--- os.execve simulation ---\n{execve.stdout}"

        self._add_ioc(t, "pattern", "os.execve")
        self._add_ioc(t, "pattern", "os.getpid")

        # ── 4. ctypes — direct libc call simulation ────────────────
        ctypes_cmd = (
            "import ctypes, ctypes.util; "
            "lib = ctypes.util.find_library('c'); "
            "print('libc path:', lib)"
        )
        ct = self._run_command(["python3", "-c", ctypes_cmd])
        if ct.exit_code == 0:
            t.stdout += f"\n--- ctypes libc resolution ---\n{ct.stdout}"

        self._add_ioc(t, "pattern", "ctypes.util.find_library")
        self._add_ioc(t, "pattern", "import ctypes")

        return t

    def cleanup(self):
        self._wipe_sandbox()
