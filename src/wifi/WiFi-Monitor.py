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
import time
from common.t2 import _check_root, _execute_command, _load_module, _log_event, _setup_logging, _unload_module
from typing import Pattern

cd_sec: int = 20
lrt: float = 0.0
version = "0.3.2"
logger = _setup_logging("WiFi-Guardian", level=logging.DEBUG)


def _log(char: str, msg: str) -> None:
    """Logs an event using the shared logger."""
    _log_event(logger, char, msg)


p_list: list[str] = [r"CMD_TRIGGER_SCAN.*error.*\(5\)", r"brcmf_msgbuf_query_dcmd", r"set wpa_auth failed", r"error \(-12\)"]


def _unload_wifi() -> None:
    """Unloads the Wi-Fi driver."""
    _unload_module("brcmfmac_wcc", logger, delay=1)


def _load_wifi() -> None:
    """Loads the Wi-Fi driver."""
    _load_module("brcmfmac_wcc", logger, delay=1)


def _unload_bt() -> None:
    """Unloads the Bluetooth driver."""
    _unload_module("hci_bcm4377", logger, delay=1)


def _load_bt() -> None:
    """Loads the Bluetooth driver."""
    _load_module("hci_bcm4377", logger, delay=1)


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


def verify_connectivity(max_attempts: int = 3) -> bool:
    """Verifies hardware recovery via sysfs with retries."""
    wifi_ok, bt_ok = False, False
    for attempt in range(1, max_attempts + 1):
        _log("*", f"Verifying hardware recovery (Attempt {attempt}/{max_attempts})...")
        try:
            wifi_ok: bool = any(os.path.exists(f"/sys/class/net/{iface}/wireless") for iface in os.listdir("/sys/class/net"))
        except FileNotFoundError:
            wifi_ok = False
        bt_ok: bool = os.path.exists("/sys/class/bluetooth/hci0")
        if wifi_ok and bt_ok:
            _execute_command("notify-send 'Wi-Fi Monitor' 'No hardware issue(s) found.' --urgency=low --icon=network-wireless", as_user=True)
            _log("+", "Connectivity verified.")
            return True
        if attempt < max_attempts:
            if not wifi_ok:
                _log("!", "Wi-Fi missing, reloading...")
                _unload_wifi()
                _load_wifi()
            if not bt_ok:
                _log("!", "Bluetooth missing, reloading...")
                _unload_bt()
                _load_bt()
            time.sleep(2)
    if not wifi_ok:
        _log("-", "WiFi Controller is missing.")
    if not bt_ok:
        _log("-", "Bluetooth Controller is missing.")
    _execute_command("notify-send 'Wi-Fi Monitor' 'Recovery failed' --urgency=critical --icon=dialog-error", as_user=True)
    return False


def _reset_sequence() -> bool:
    """Executes the full hardware reset sequence."""
    global lrt
    n = time.time()
    if n - lrt < cd_sec:
        _log("#", f"Cooldown active ({int(cd_sec - (n - lrt))}s remaining), skipping reset.")
        return False
    if _unload_all():
        _log("*", "Hardware settling (2s)...")
        time.sleep(2.5)
        if _load_all():
            _log("*", "Waiting for hardware initialization (2s)...")
            time.sleep(2.5)
            if verify_connectivity(5):
                lrt = time.time()
                return True
            else:
                _log("!", "Post-reset verification failed after retries. Recovery likely failed :(")
    return False


def al_is_watching() -> None:
    """Monitors journalctl for hardware hang signatures."""
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
                    _execute_command("notify-send 'Wi-Fi Monitor' 'Hang detected' --urgency=critical --icon=dialog-error", as_user=True)
                    _reset_sequence()
                    break
    except PermissionError:
        _log("-", "Error: Permission denied. Run as root?")
    except Exception as err:
        _log("!", f"Unexpected monitor error: {err}")


def main() -> None:
    """Main entry point for the WiFi monitor."""
    _check_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "check", "daemon", "version", "v"])
    args = parser.parse_args()
    if args.action in ["version", "v"]:
        print(version)
    if args.action == "exec":
        _reset_sequence()
    if args.action == "check":
        verify_connectivity()
    if args.action == "daemon":
        al_is_watching()


if __name__ == "__main__":
    main()
