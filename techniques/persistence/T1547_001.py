"""
T1547.001 — Boot or Logon Autostart Execution: Login Item
Simulates persistence via macOS Login Items using osascript
and direct plist manipulation of
~/Library/Preferences/com.apple.loginitems.plist
"""

import plistlib
from pathlib import Path
from datetime import datetime, timezone
from techniques.base import AtomicBase, Telemetry


LOGIN_ITEMS_PLIST = (
    Path.home()
    / "Library/Preferences/com.apple.loginitems.plist"
)
PHANTOM_SCRIPT = Path("/tmp/phantomwatch_login_item.sh")


class T1547_001_LoginItem(AtomicBase):
    TECHNIQUE_ID = "T1547.001"
    TACTIC       = "persistence"
    NAME         = "Boot or Logon Autostart: Login Item"
    PLATFORMS    = ["macOS"]
    SAFE         = True

    def execute(self) -> Telemetry:
        # ── 1. Drop a script that would run at login ───────────────
        PHANTOM_SCRIPT.write_text(
            "#!/bin/bash\n"
            f"# PhantomWatch login item simulation — {datetime.now(timezone.utc).isoformat()}\n"
            "echo phantomwatch-login-item >> /tmp/pw_loginitem.log\n"
            "echo 'user:' $(whoami) >> /tmp/pw_loginitem.log\n"
        )
        PHANTOM_SCRIPT.chmod(0o755)

        t = self._run_command(["ls", "-la", str(PHANTOM_SCRIPT)])
        t.artifacts.append(str(PHANTOM_SCRIPT))

        self._add_ioc(t, "path",    str(PHANTOM_SCRIPT))
        self._add_ioc(t, "pattern", "loginitems")
        self._add_ioc(t, "pattern", "com.apple.loginitems")

        # ── 2. Add via osascript (AppleScript method) ──────────────
        osa = self._run_command([
            "osascript", "-e",
            f'tell application "System Events" to make login item '
            f'at end with properties {{path:"{PHANTOM_SCRIPT}", hidden:false, name:"PhantomWatchTest"}}'
        ])
        t.stdout += f"\n--- osascript add login item ---\n"
        t.stdout += osa.stdout if osa.exit_code == 0 else f"(requires Full Disk Access: {osa.stderr[:200]})"

        self._add_ioc(t, "process", "osascript")
        self._add_ioc(t, "pattern", "make login item")
        self._add_ioc(t, "pattern", "System Events")

        # ── 3. Enumerate current login items ──────────────────────
        enum = self._run_command([
            "osascript", "-e",
            'tell application "System Events" to get the name of every login item'
        ])
        t.stdout += f"\n--- current login items ---\n"
        t.stdout += enum.stdout if enum.exit_code == 0 else "(enumeration requires permissions)"

        self._add_ioc(t, "pattern", "get the name of every login item")

        # ── 4. Direct plist inspection ────────────────────────────
        if LOGIN_ITEMS_PLIST.exists():
            plist_read = self._run_command([
                "plutil", "-p", str(LOGIN_ITEMS_PLIST)
            ])
            if plist_read.exit_code == 0:
                t.stdout += f"\n--- loginitems plist ---\n{plist_read.stdout[:400]}"
                t.artifacts.append(str(LOGIN_ITEMS_PLIST))
        else:
            t.stdout += "\n--- loginitems plist not found (normal on fresh systems) ---"

        self._add_ioc(t, "path", str(LOGIN_ITEMS_PLIST))

        t.exit_code = 0
        return t

    def cleanup(self):
        # Remove via osascript
        self._run_command([
            "osascript", "-e",
            'tell application "System Events" to delete login item "PhantomWatchTest"'
        ])

        # Remove dropped script
        if PHANTOM_SCRIPT.exists():
            PHANTOM_SCRIPT.unlink()

        # Remove log
        log = Path("/tmp/pw_loginitem.log")
        if log.exists():
            log.unlink()

        self._wipe_sandbox()
