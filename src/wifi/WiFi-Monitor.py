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
from typing import List, Pattern

sys.dont_write_bytecode = True

cd_sec: int = 20
lrt: float = 0.0

sys.path.append("/usr/local/sbin/common")
import t2

version = "0.2.5"
logger = t2.setup_logging("WiFi-Guardian", level=logging.DEBUG)


def _log(log_level: str, event_msg: str) -> None:
    """Logs an event using the shared logger."""
    t2.log_event(logger, log_level, event_msg)


p_list: list[str] = [r"CMD_TRIGGER_SCAN.*error.*\(5\)", r"brcmf_msgbuf_query_dcmd", r"set wpa_auth failed", r"error \(-12\)", r"failed with error -110"]


def _unload_wifi() -> None:
    """Unloads the Wi-Fi driver."""
    t2.unload_module("brcmfmac_wcc", logger, delay=3)


def _load_wifi() -> None:
    """Loads the Wi-Fi driver."""
    t2.load_module("brcmfmac_wcc", logger, delay=3)


def _unload_bt() -> None:
    """Unloads the Bluetooth driver."""
    t2.unload_module("hci_bcm4377", logger, delay=3)


def _load_bt() -> None:
    """Loads the Bluetooth driver."""
    t2.load_module("hci_bcm4377", logger, delay=3)


def _unload_all() -> bool:
    """Unloads both Wi-Fi and Bluetooth drivers."""
    try:
        _log("+", "STAGE 1: Unloading drivers...")
        _unload_wifi()
        _unload_bt()
        return True
    except Exception as err:
        _log("-", f"Unable to unload due: {err}")
        return False


def _load_all() -> bool:
    """Loads both Bluetooth and Wi-Fi drivers."""
    try:
        _log("+", "STAGE 2: Loading drivers...")
        _load_bt()
        _load_wifi()
        return True
    except Exception as err:
        _log("-", f"Unable to load due: {err}")
        return False


def _verify_connectivity(retries: int = 3) -> bool:
    """Verifies hardware recovery via sysfs with retries."""
    _log("*", f"Verifying hardware recovery (Attempt {4 - retries}/4)...")
    wifi_ok = any(os.path.exists(f"/sys/class/net/{iface}/wireless") for iface in os.listdir("/sys/class/net"))
    bt_ok = os.path.exists("/sys/class/bluetooth/hci0")
    if wifi_ok and bt_ok:
        t2.execute_command("notify-send 'Wi-Fi Monitor' 'Connectivity restored' --urgency=low --icon=network-wireless", as_user=True)
        _log("+", "Connectivity verified: Wi-Fi and Bluetooth are active.")
        return True
    if retries > 0:
        if not wifi_ok:
            _log("!", "Wi-Fi missing. Retrying Wi-Fi reload...")
            _unload_wifi()
            _load_wifi()
        if not bt_ok:
            _log("!", "Bluetooth missing. Retrying BT reload...")
            _unload_bt()
            _load_bt()
        time.sleep(2)
        return _verify_connectivity(retries - 1)
    t2.execute_command("notify-send 'Wi-Fi Monitor' 'Recovery failed after multiple attempts' --urgency=critical --icon=dialog-error", as_user=True)
    if not wifi_ok:
        _log("-", "Verification failed: No Wi-Fi interface found in sysfs.")
    if not bt_ok:
        _log("-", "Verification failed: Bluetooth controller hci0 missing in sysfs.")
    return False


def _reset_sequence() -> bool:
    """Executes the full hardware reset sequence."""
    global lrt
    n = time.time()
    if n - lrt < cd_sec:
        _log("#", f"Cooldown active ({int(cd_sec - (n - lrt))}s remaining), skipping reset.")
        return False
    t2.execute_command("notify-send 'Wi-Fi Monitor' 'Reset sequence started' --urgency=normal --icon=view-refresh", as_user=True)
    if _unload_all():
        _log("*", "Hardware settling (5s)...")
        time.sleep(5)
        if _load_all():
            _log("*", "Waiting for hardware initialization (5s)...")
            time.sleep(5)
            if _verify_connectivity(retries=3):
                lrt = time.time()
                return True
            else:
                _log("!", "Post-reset verification failed after retries. Recovery may be incomplete.")
    return False


def al_is_watching() -> None:
    """ Monitors journalctl for hardware hang signatures. """
    _log("+", "Starting WiFi Guardian Monitor...")
    compiled_p_list: list[Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in p_list]
    try:
        p = subprocess.Popen(["journalctl", "-k", "-f", "-n", "0", "--no-pager"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        if p.stdout is None:
            _log("-", f"Failed to open journalctl stdout. Error: {p.stderr}")
            return
        for line in p.stdout:
            if not line:
                continue
            for pattern in compiled_p_list:
                if pattern.search(line):
                    _log("-", f"Reset trigger: {line.strip()} (Pattern: {pattern.pattern})")
                    t2.execute_command("notify-send 'Wi-Fi Monitor' 'Hardware hang detected' --urgency=critical --icon=dialog-error", as_user=True)
                    _reset_sequence()
                    _log("+", "Reset sequence completed, monitoring for stability...")
                    break
    except PermissionError:
        _log("-", "Error: Permission denied. Run as root?")
    except Exception as err:
        _log("!", f"Unexpected monitor error: {err}")


def main() -> None:
    """ Main entry point for the WiFi monitor. """
    t2.check_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "daemon", "version", "v"])
    args = parser.parse_args()
    if args.action in ["version", "v"]:
        print(version)
    if args.action == "exec":
        t2.execute_command("notify-send 'Wi-Fi Monitor' 'Manual reset triggered' --urgency=normal --icon=view-refresh", as_user=True)
        _reset_sequence()
    if args.action == "daemon":
        al_is_watching()


if __name__ == "__main__":
    main()
