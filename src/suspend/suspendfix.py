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
import sys
import time
from typing import Optional

sys.dont_write_bytecode = True


try:
    import t2  # type: ignore
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2  # type: ignore

version = "0.6.0"
logger = t2.setup_logging("SuspendFix", level=logging.DEBUG)


def _log(char, msg) -> None:
    t2.log_event(logger, char, msg)


def rescan_pci() -> bool:
    _log("*", "Rescanning PCI bus...")
    try:
        with open("/sys/bus/pci/rescan", "w") as f:
            f.write("1")
            return True
    except Exception as e:
        _log("-", f"Failed to rescan PCI: {e}")
        return False


def remove_device(device_id: str, name: Optional[str] = None) -> bool:
    path = f"/sys/bus/pci/devices/{device_id}/remove"
    if os.path.exists(path):
        _log("*", f"Removing {name or device_id}...")
        try:
            with open(path, "w") as f:
                f.write("1")
            return True
        except Exception as e:
            _log("-", f"Failed to remove {name or device_id}: {e}")
    return False


def load_sequence() -> None:
    _log("*", "Executing LOAD sequence...")
    t2.load_module("apple-bce", logger, delay=4)
    t2.load_module("hid_appletb_bl", logger)
    t2.load_module("hid_appletb_kbd", logger)
    t2.load_module("appletbdrm", logger)
    t2.load_module("brcmfmac_wcc", logger, delay=1)
    t2.load_module("hci_bcm4377", logger, delay=3)
    rescan_pci()
    t2.load_module("thunderbolt", logger)
    t2.start_service("pipewire.socket", logger, block=False, as_user=True)
    t2.start_service("pipewire.service", logger, block=False, as_user=True)
    t2.start_service("wireplumber.service", logger, block=False, as_user=True)
    t2.start_service("NetworkManager.service", logger, block=True, as_user=False)
    t2.start_service("bluetooth.service", logger, block=True, as_user=False)
    t2.start_service("tiny-dfr.service", logger, block=False, as_user=False)
    t2.start_service("wluma.service", logger, block=False, as_user=True)
    _log("*", "LOAD sequence complete.")


def unload_sequence() -> None:
    _log("*", "Executing UNLOAD sequence...")
    t2.stop_service("wluma.service", logger, block=False, as_user=True)
    t2.stop_service("pipewire.socket", logger, block=True, as_user=True)
    t2.stop_service("wireplumber.service", logger, block=True, as_user=True)
    t2.stop_service("pipewire.service", logger, block=True, as_user=True)
    t2.stop_service("bluetooth.service", logger, block=True, as_user=False)
    t2.stop_service("NetworkManager.service", logger, block=True, as_user=False)
    t2.stop_service("tiny-dfr.service", logger, block=True, as_user=False)
    remove_device("0000:06:00.0", "Thunderbolt Controller")
    t2.unload_module("thunderbolt", logger)
    t2.unload_module("appletbdrm", logger)
    t2.unload_module("hid_appletb_bl", logger)
    t2.unload_module("hid_appletb_kbd", logger)
    t2.unload_module("hci_bcm4377", logger, delay=2)
    t2.unload_module("brcmfmac_wcc", logger, delay=2)
    t2.unload_module("apple-bce", logger, delay=4)
    _log("*", "UNLOAD sequence complete.")


def main() -> None:
    t2.check_root()
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
