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

try:
    import t2
except ImportError:
    # Add parent directory to sys.path to find t2 when running from repo
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2
# initialize logger
t2_logger = t2.setup_logging("WiFi-Guardian", level=logging.DEBUG)


def _log(log_level: str, event_msg: str) -> None:
    """Log a message with a specific log level format using shared logger."""
    t2.log_event(t2_logger, log_level, event_msg)


services: list[str] = ["NetworkManager", "bluetooth"]
modules: list[str] = ["brcmfmac", "brcmfmac_wcc", "hci_bcm4377"]

# regex pattern to match fatal errors (from my own experience):
patterns: list[str] = [
    r"CMD_TRIGGER_SCAN.*error.*\(5\)",  # - CMD_TRIGGER_SCAN error (5): I/O Error during scan start
    r"brcmf_msgbuf_query_dcmd",  # - query_dcmd: Firmware timeout (Hang)
    r"set wpa_auth failed",  # - set wpa_auth failed: Crypto offload failure
    r"error \(-12\)"  # - error (-12): ENOMEM (Memory allocation failure)
]


def _unload() -> bool:
    try:
        _log("+", "STAGE 1: Unloading...")
        # stop service first then, unload driver.
        for s in reversed(services):
            _log("+", f"Stopping Service: {s}")
            t2.execute_command(f"systemctl stop {s}")
        for m in reversed(modules):
            _log("+", f"Unloading module {m}...")
            # using --remove-holders to be safe, similar to modprobe --remove
            t2.execute_command(f"modprobe --verbose --remove --remove-holders {m}")
        # unloaded waiting hw to power off. (5 seconds)
        time.sleep(5)
        return True
    except Exception as err:
        _log("-", f"Unload unsucessful: {err}")
        return False


def _load() -> bool:
    try:
        _log("+", "STAGE 2: Loading...")
        # load driver first then, [re]start service
        for m in modules:
            _log("+", f"Loading module {m}...")
            t2.execute_command(f"modprobe --verbose {m}")
        for s in services:
            _log("+", f"Starting Service: {s}")
            t2.execute_command(f"systemctl start {s}")
        return True
    except Exception as err:
        _log("-", f"Load unsucessful: {err}")
        return False


# if you know you know ;) [tip: deadpool movie reference]
def al_is_watching() -> None:
    """Monitors the kernel ring buffer in real-time via journalctl."""
    _log("+", "Starting WiFi Guardian Monitor...")
    _log("#", f"Watching for patterns: {patterns}")

    compiled_patterns: list[Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in patterns]

    try:
        # popen is different from run_cmd, stick to subprocess for persistent pipe
        p = subprocess.Popen(['journalctl', '-k', '-f', '-n', '0', '--no-pager'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        if p.stdout is None:
            _log("-", f"Failed to open journalctl stdout. Error: {p.stderr}")
            return

        for line in p.stdout:
            if not line:
                continue

            for pattern in compiled_patterns:
                if pattern.search(line):
                    _log("#", f"PATTERN MATCHED: {pattern}")
                    _log("-", f"TRIGGER MATCHED: {line.strip()}")
                    _log("-", "CRITICAL HARDWARE HANG DETECTED. Initiating Nuclear Reset...")
                    _unload()
                    _load()
                    _log("+", "Reset sequence complete. Monitoring for stability...")
                    break

    except PermissionError:
        _log("-", "Error: Permission denied. Run as root?")
    except Exception as err:
        _log("!", f"Unexpected monitor error: {err}")


if __name__ == "__main__":
    t2.check_root()
    al_is_watching()
