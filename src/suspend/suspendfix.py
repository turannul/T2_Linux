#!/usr/bin/env python3
#
#  suspendfix
#  T2_Linux
#
#  Created by turannul on 10/12/2025.
#  Rewritten in Python on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import argparse
import logging
import os
import time
from common.t2 import _check_root, _execute_command, _load_module, _log_event, _setup_logging, _start_service, _stop_service, _unload_module
from typing import Optional

version = "0.6.0"
logger = _setup_logging("SuspendFix", level=logging.DEBUG)


def _log(char: str, msg: str) -> None:
    """Logs an event using the shared logger."""
    _log_event(logger, char, msg)


def _rescan_pci() -> bool:
    """Triggers a PCI bus rescan."""
    _log("*", "Rescanning PCI bus...")
    _, _, code = _execute_command("echo 1 > /sys/bus/pci/rescan")
    return code == 0


def _remove_device(device_id: str, name: Optional[str] = None) -> bool:
    """Removes a PCI device from the system."""
    path = f"/sys/bus/pci/devices/{device_id}/remove"
    if os.path.exists(path):
        _log("*", f"Removing {name or device_id}...")
        _, _, code = _execute_command(f"echo 1 > {path}")
        return code == 0
    return False


def load_sequence() -> None:
    """Executes the driver load sequence after resume."""
    _execute_command("notify-send 'Suspend Fix' 'Executing LOAD sequence' --urgency=normal --icon=view-refresh", as_user=True)
    _log("*", "Executing LOAD sequence...")
    _load_module("apple-bce", logger, delay=4)
    _load_module("hid_appletb_bl", logger)
    _load_module("hid_appletb_kbd", logger)
    _load_module("appletbdrm", logger)
    _load_module("brcmfmac_wcc", logger, delay=1)
    _load_module("hci_bcm4377", logger, delay=1)
    _rescan_pci()
    _load_module("thunderbolt", logger)
    _start_service("pipewire.socket", logger, block=False, as_user=True)
    _start_service("tiny-dfr.service", logger, block=False, as_user=False)
    _start_service("wluma.service", logger, block=False, as_user=True)
    _log("*", "Starting WiFi Monitor...")
    _execute_command("/usr/local/sbin/WiFi-Monitor check")
    _log("*", "LOAD sequence complete.")


def unload_sequence() -> None:
    """Executes the driver unload sequence before suspend."""
    _execute_command("notify-send 'Suspend Fix' 'Executing UNLOAD sequence' --urgency=normal --icon=view-refresh", as_user=True)
    _log("*", "Executing UNLOAD sequence...")
    _stop_service("wluma.service", logger, block=False, as_user=True)
    _stop_service("pipewire.socket", logger, block=True, as_user=True)
    _stop_service("tiny-dfr.service", logger, block=True, as_user=False)
    _remove_device("0000:06:00.0", "Thunderbolt Controller")
    _unload_module("thunderbolt", logger)
    _unload_module("appletbdrm", logger)
    _unload_module("hid_appletb_bl", logger)
    _unload_module("hid_appletb_kbd", logger)
    _unload_module("hci_bcm4377", logger, delay=2)
    _unload_module("brcmfmac_wcc", logger, delay=2)
    _unload_module("apple-bce", logger, delay=4)
    _log("*", "UNLOAD sequence complete.")


def main() -> None:
    """Main entry point for suspend management."""
    _check_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["load", "unload", "reload", "version", "v"])
    args = parser.parse_args()
    if args.action in ["version", "v"]:
        print(version)
    elif args.action == "load":
        load_sequence()
    elif args.action == "unload":
        unload_sequence()
    elif args.action == "reload":
        unload_sequence()
        time.sleep(10)
        load_sequence()


if __name__ == "__main__":
    main()
