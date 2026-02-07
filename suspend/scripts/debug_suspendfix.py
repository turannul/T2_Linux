#!/usr/bin/env python3
import datetime
import os
import subprocess
import sys
from typing import Optional

LOG_FILE = "suspend_debug_report.txt"
# Calculate path to suspendfix relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUSPEND_FIX = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "suspendfix"))



def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_refcount(module: str) -> str:
    path = f"/sys/module/{module}/refcnt"
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            return "Error reading refcnt"
    return "N/A"


def get_holders(module: str) -> str:
    path = f"/sys/module/{module}/holders/"
    if os.path.exists(path):
        try:
            holders = os.listdir(path)
            return ", ".join(holders) if holders else "None"
        except Exception:
            return "Error reading holders"
    return "N/A"


def get_pci_driver(device_id: str) -> str:
    path = f"/sys/bus/pci/devices/{device_id}/driver"
    if os.path.exists(path):
        try:
            return os.path.realpath(path)
        except Exception:
            return "Error reading driver"
    return "N/A"


def print_state(label: str):
    log(f"--- {label} ---")
    log(f"apple-bce Refcount: {get_refcount('apple_bce')}")
    log(f"Holders of apple_bce: {get_holders('apple_bce')}")
    log(f"Driver for Audio (02:00.3): {get_pci_driver('0000:02:00.3')}")
    log(f"Driver for Bridge (02:00.1): {get_pci_driver('0000:02:00.1')}")


def run_suspend_fix(action: str):
    log(f"--- Executing {action.capitalize()} ---")
    cmd = ["sudo", "python3", SUSPEND_FIX, action]
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if process.stdout:
            for line in process.stdout:
                log(line.strip())
        process.wait()
    except Exception as e:
        log(f"Error running suspendfix: {e}")


def main():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    log("Starting Suspend Fix Debugging...")
    log(f"Target Script: {SUSPEND_FIX}")

    if not os.path.exists(SUSPEND_FIX):
        log(f"ERROR: suspendfix script not found at {SUSPEND_FIX}")
        sys.exit(1)

    print_state("Pre-Unload State")
    run_suspend_fix("unload")
    print_state("Post-Unload State")

    # Check if apple-bce is still loaded
    res = subprocess.run(["lsmod"], capture_output=True, text=True)
    if "apple_bce" in res.stdout:
        log("FAILURE: apple-bce is still loaded.")
        log("Checking for other open files on apple-bce...")
        try:
            lsof_res = subprocess.run(
                ["sudo", "lsof"], capture_output=True, text=True
            )
            for line in lsof_res.stdout.splitlines():
                if "apple_bce" in line:
                    log(line)
        except Exception as e:
            log(f"Error running lsof: {e}")
    else:
        log("SUCCESS: apple-bce was unloaded.")

    run_suspend_fix("load")

    log(f"Debugging Complete. Report saved to {LOG_FILE}")


if __name__ == "__main__":
    main()
