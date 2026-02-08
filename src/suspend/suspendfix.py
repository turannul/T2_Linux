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
import subprocess
import sys
import time
from typing import List, Optional, Tuple

# Prevent __pycache__ creation
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

try:
    import t2  # type: ignore
except ImportError:
    # Add parent directory to sys.path to find t2 when running from repo
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2  # type: ignore

# constants
version = "0.5.5-1"
# initialize global logger
logger = t2.setup_logging("SuspendFix", level=logging.DEBUG)


def _log(char, msg) -> None:
    t2.log_event(logger, char, msg)


def get_active_user() -> tuple[None, None] | tuple[str, str]:
    try:
        output: str = subprocess.check_output(["loginctl", "list-users", "--no-legend"], text=True).strip()
        if not output:
            return None, None
        parts: List[str] = output.splitlines()[0].split()
        if len(parts) >= 2:
            user: str = parts[1]
            uid: str = subprocess.check_output(["id", "-u", user], text=True).strip()
            return user, uid
    except Exception as e:
        logger.debug(f"Failed to get active user: {e}")
    return None, None


target_user, target_uid = get_active_user()


def run_cmd_wrapper(cmd: List[str], as_user: bool = False) -> Tuple[str, str, int]:
    """Wrapper to run commands, optionally as the active user (uid: 1000) with preserved environment."""
    cmd_str = " ".join(cmd)
    env = os.environ.copy()

    if as_user:
        if not target_user:
            _log("!", f"No active user found for command: {cmd_str}")
            return "", "No active user found", 1

        env["XDG_RUNTIME_DIR"] = f"/run/user/{target_uid}"
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{target_uid}/bus"
        cmd_str = f"sudo -E -u {target_user} {cmd_str}"

    # Use the shared robust executor from t2
    return t2.execute_command(cmd_str, env=env)


def is_module_loaded(module_name: str) -> bool:
    name = module_name.replace("-", "_")
    try:
        with open("/proc/modules", "r") as f:
            for line in f:
                if line.startswith(f"{name} "):
                    return True
    except Exception:
        stdout, _, _ = t2.execute_command("lsmod")
        return f"\n{name} " in f"\n{stdout}"
    return False


def load_module(module_name: str, delay: float = 0.5) -> bool:
    if is_module_loaded(module_name):
        logger.debug(f"Module {module_name} is already loaded.")
        return True

    _log("*", f"Loading module {module_name}...")
    for attempt in range(1, 4):
        _, _, code = t2.execute_command(f"modprobe --verbose {module_name}")
        if code == 0:
            _log("*", f"Module {module_name} loaded (Attempt {attempt}).")
            time.sleep(delay)
            return True
        _log("!", f"Failed to load {module_name}. Retrying... ({attempt}/3)")
        time.sleep(1)
    _log("-", f"CRITICAL: Failed to load module {module_name}.")
    return False


def unload_module(module_name: str, delay: float = 0.5) -> bool:
    if not is_module_loaded(module_name):
        logger.debug(f"Module {module_name} is not loaded.")
        return True

    _log("*", f"Unloading module {module_name}...")
    for attempt in range(1, 4):
        _, stderr, code = t2.execute_command(f"modprobe --verbose --remove --remove-holders {module_name}")

        if code == 0 and not is_module_loaded(module_name):
            _log("*", f"Module {module_name} unloaded (Attempt {attempt}).")
            time.sleep(delay)
            return True
        else:
            if stderr:
                _log("!", f"Unload attempt {attempt} failed: {stderr}")
        time.sleep(1)
    _log("-", f"CRITICAL: Failed to unload module {module_name}.")
    return False


def stop_service(service_name: str, block: bool = False, as_user: bool = False) -> bool:
    """Stops a systemd service, optionally blocking until it's stopped, with verification and retry logic."""
    try:
        cmd = ["systemctl"]
        if as_user:
            cmd.append("--user")
        stop_args = [] if block else ["--no-block"]

        _log("*", f"Stopping {service_name}...")
        for attempt in range(1, 4):
            run_cmd_wrapper(cmd + ["stop"] + stop_args + [service_name], as_user=as_user)
            if block:
                # systemctl is-active returns 0 if active, non-zero if inactive (e.g. 3)
                _, _, code = run_cmd_wrapper(cmd + ["is-active", "--quiet", service_name], as_user=as_user)
                if code != 0:
                    _log("+", f"Service {service_name} stopped.")
                    return True
                else:
                    _log("!", f"Service {service_name} still active after stop attempt {attempt}. Retrying...")
                    time.sleep(1)
            else:
                return True

        _log("-", f"Failed to stop {service_name} after 3 attempts.")
        return False

    except Exception as err:
        _log("-", f"Something went wrong while stopping {service_name}: {err}")
        return False


def start_service(service_name: str, block: bool = False, as_user: bool = False) -> bool:
    """Starts or restarts a systemd service with verification and retry logic."""
    try:
        cmd = ["systemctl"]
        if as_user:
            cmd.append("--user")
        start_args = [] if block else ["--no-block"]

        # Check if active to decide between start and restart
        _, _, code = run_cmd_wrapper(cmd + ["is-active", "--quiet", service_name], as_user=as_user)
        is_active = (code == 0)
        action = "restart" if is_active else "start"

        _log("*", f"{action.capitalize()}ing {service_name}...")
        for attempt in range(1, 4):
            run_cmd_wrapper(cmd + [action] + start_args + [service_name], as_user=as_user)
            if block:
                _, _, code = run_cmd_wrapper(cmd + ["is-active", "--quiet", service_name], as_user=as_user)
                if code == 0:
                    _log("+", f"Service {service_name} {action}ed successfully.")
                    return True
                else:
                    _log("!", f"Service {service_name} failed to {action} (Attempt {attempt}). Retrying...")
                    time.sleep(1)
            else:
                return True

        _log("-", f"Failed to {action} {service_name} after 3 attempts.")
        return False

    except Exception as err:
        _log("-", f"Something went wrong while starting {service_name}: {err}")
        return False


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
    load_module("apple-bce", 4)
    load_module("hid_appletb_bl")
    load_module("hid_appletb_kbd")
    load_module("appletbdrm")
    load_module("brcmfmac_wcc", 1)
    load_module("hci_bcm4377", 1)
    rescan_pci()
    load_module("thunderbolt")
    start_service("pipewire.socket", block=False, as_user=True)
    start_service("pipewire.service", block=False, as_user=True)
    start_service("wireplumber.service", block=False, as_user=True)
    start_service("NetworkManager", block=True, as_user=False)
    start_service("bluetooth.service", block=True, as_user=False)
    start_service("tiny-dfr.service", block=False, as_user=False)
    start_service("wluma.service", block=False, as_user=True)
    _log("*", "LOAD sequence complete.")


def unload_sequence() -> None:
    _log("*", "Executing UNLOAD sequence...")
    stop_service("pipewire.socket", block=True, as_user=True)
    stop_service("wireplumber.service", block=True, as_user=True)
    stop_service("pipewire.service", block=True, as_user=True)
    stop_service("bluetooth.service", block=True, as_user=False)
    stop_service("NetworkManager.service", block=True, as_user=False)
    stop_service("tiny-dfr.service", block=True, as_user=False)
    remove_device("0000:06:00.0", "Thunderbolt Controller")
    unload_module("thunderbolt")
    unload_module("appletbdrm")
    unload_module("hid_appletb_bl")
    unload_module("hid_appletb_kbd")
    unload_module("hci_bcm4377", 2)
    unload_module("brcmfmac_wcc", 2)
    unload_module("apple-bce", 4)
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
