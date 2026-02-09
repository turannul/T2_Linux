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

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from typing import Pattern

sys.dont_write_bytecode = True

cd_sec: int = 20
lrt: float = 0.0

try:
    import t2  # type: ignore
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2  # type: ignore

version = "0.2.5"
logger = t2.setup_logging("WiFi-Guardian", level=logging.DEBUG)


def _log(log_level: str, event_msg: str) -> None:
    """Log a message with a specific log level format using shared logger."""
    t2.log_event(logger, log_level, event_msg)


# regex pattern to match fatal errors (from my own experience):
p_list: list[str] = [
    r"CMD_TRIGGER_SCAN.*error.*\(5\)",  # - CMD_TRIGGER_SCAN error (5): I/O Error during scan start
    r"brcmf_msgbuf_query_dcmd",  # - query_dcmd: Firmware timeout (Hang)
    r"set wpa_auth failed",  # - set wpa_auth failed: Crypto offload failure
    r"error \(-12\)"  # - error (-12): ENOMEM (Memory allocation failure)
]


def _unload() -> bool:
    try:
        _log("+", "STAGE 1: Unloading...")
        # stop service first then, unload driver.
        t2.stop_service("systemd-networkd", logger, block=True)
        t2.unload_module("brcmfmac_wcc", logger)
        t2.stop_service("bluetooth", logger, block=True)
        t2.unload_module("hci_bcm4377", logger)
        return True
    except Exception as err:
        _log("-", f"Unload unsuccessful: {err}")
        return False


def _load() -> bool:
    try:
        _log("+", "STAGE 2: Loading...")
        # load driver then, start service
        t2.load_module("hci_bcm4377", logger, delay=3)
        t2.start_service("bluetooth", logger, block=True)
        t2.load_module("brcmfmac_wcc", logger)
        t2.start_service("systemd-networkd", logger, block=True)
        return True
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


def main() -> None:
    t2.check_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "daemon", "version", "v"])
    args = parser.parse_args()
    if args.action in ["version", "v"]:
        print(version)
    if args.action == "exec":
        _unload()
        time.sleep(3)
        _load()
    if args.action == "daemon":
        al_is_watching()


if __name__ == "__main__":
    main()
