#!/usr/bin/env python3
#
#  WiFi-Monitor
#  T2_Linux
#
#  Created by turannul on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import logging
import os
import re
import subprocess
import sys
import time
from typing import Pattern

# Prevent __pycache__ creation
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

cd_sec: int = 20
lrt: float = 0.0

try:
    import t2  # type: ignore
except ImportError:
    # Add parent directory to sys.path to find t2 when running from repo
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2  # type: ignore

logger = t2.setup_logging("WiFi-Guardian", level=logging.DEBUG)


def _log(log_level: str, event_msg: str) -> None:
    """Log a message with a specific log level format using shared logger."""
    t2.log_event(logger, log_level, event_msg)


s_list: list[str] = ["NetworkManager", "bluetooth"]
m_list: list[str] = ["brcmfmac_wcc", "hci_bcm4377"]

# regex pattern to match fatal errors (from my own experience):
p_list: list[str] = [
    r"CMD_TRIGGER_SCAN.*error.*\(5\)",  # - CMD_TRIGGER_SCAN error (5): I/O Error during scan start
    r"brcmf_msgbuf_query_dcmd",  # - query_dcmd: Firmware timeout (Hang)
    r"set wpa_auth failed",  # - set wpa_auth failed: Crypto offload failure
    r"error \(-12\)"  # - error (-12): ENOMEM (Memory allocation failure)
]


def _service_handler(s: str, a: str) -> bool:
    """Executes a systemctl act on a specified service."""
    try:
        if a == "is-active":
            _, _, rc = t2.execute_command(f"systemctl is-active --quiet {s}")
            return rc == 0

        _log("+", f"{a.capitalize()}ing Service: {s}")  # Start'ing, Stop'ing...
        _, _, rc = t2.execute_command(f"systemctl {a} {s}")
        return rc == 0
    except Exception as err:
        _log("-", f"Service handler error ({a} {s}): {err}")
        return False


def _module_handler(m: str, a: str) -> bool:
    """Handles kernel module loading and unloading."""
    try:
        if a == "load":
            _log("+", f"Loading module: {m}")
            cmd = f"modprobe --verbose {m}"
        elif a == "unload":
            _log("+", f"Unloading module: {m}")
            cmd = f"modprobe --verbose --remove --remove-holders {m}"
        else:
            return False

        _, _, rc = t2.execute_command(cmd)
        return rc == 0
    except Exception as err:
        _log("-", f"Module handler error ({a} {m}): {err}")
        return False


def _unload() -> bool:
    """Performs hardware reset STAGE 1: Stops s_list and unloads kernel m_list."""
    try:
        _log("+", "STAGE 1: Unloading...")
        # stop service first then, unload driver.
        s_bool = True
        for s in reversed(s_list):
            if not _service_handler(s, "stop"):
                s_bool = False

        for m in reversed(m_list):
            if not _module_handler(m, "unload"):
                s_bool = False

        return s_bool
    except Exception as err:
        _log("-", f"Unload unsuccessful: {err}")
        return False


def _load() -> bool:
    """Performs hardware reset STAGE 2: Loads kernel m_list and restarts s_list."""
    try:
        _log("+", "STAGE 2: Loading...")
        # load driver first then, [re]start service
        s_bool = True
        for m in m_list:
            if not _module_handler(m, "load"):
                s_bool = False

        for s in s_list:
            # Check if service is already running, if so do restart.
            act = "restart" if _service_handler(s, "is-active") else "start"
            if not _service_handler(s, act):
                s_bool = False

        return s_bool
    except Exception as err:
        _log("-", f"Load unsuccessful: {err}")
        return False


def _reset_sequence() -> bool:
    global lrt
    n = time.time()

    if n - lrt < cd_sec:
        r = int(cd_sec - (n - lrt))
        _log("#", f"Cooldown active ({r}s remaining), skipping reset.")
        return False

    if _unload():
        time.sleep(3)
        if _load():
            lrt = time.time()
            return True

    return False


def al_is_watching() -> None:
    """Monitors journalctl for hardware hang signatures and triggers reset."""
    _log("+", "Starting WiFi Guardian Monitor...")
    _log("#", f"Watching for p_list: {p_list}")

    compiled_p_list: list[Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in p_list]

    try:
        p = subprocess.Popen(['journalctl', '-k', '-f', '-n', '0', '--no-pager'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        if p.stdout is None:
            _log("-", f"Failed to open journalctl stdout. Error: {p.stderr}")
            return

        for line in p.stdout:
            if not line:
                continue

            for pattern in compiled_p_list:
                if pattern.search(line):
                    _log("#", f"PATTERN MATCHED: {pattern}")
                    _log("-", f"TRIGGER MATCHED: {line.strip()}")
                    _reset_sequence()
                    _log("+", "Reset sequence completed, monitoring for stability...")
                    break

    except PermissionError:
        _log("-", "Error: Permission denied. Run as root?")
    except Exception as err:
        _log("!", f"Unexpected monitor error: {err}")


if __name__ == "__main__":
    t2.check_root()
    al_is_watching()
