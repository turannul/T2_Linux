#!/usr/bin/env python3
import datetime
import os
import subprocess
import sys

# constants
log_file = "suspend_debug_report.txt"

# calculate path to suspendfix relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
suspend_fix = os.path.abspath(os.path.join(script_dir, "..", "suspendfix"))


def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(log_file, "a") as f:
        f.write(line + "\n")


def get_refcount(module):
    path = f"/sys/module/{module}/refcnt"
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            return "error reading refcnt"
    return "n/a"


def get_holders(module):
    path = f"/sys/module/{module}/holders/"
    if os.path.exists(path):
        try:
            holders = os.listdir(path)
            return ", ".join(holders) if holders else "none"
        except Exception:
            return "error reading holders"
    return "n/a"


def get_pci_driver(device_id):
    path = f"/sys/bus/pci/devices/{device_id}/driver"
    if os.path.exists(path):
        try:
            return os.path.realpath(path)
        except Exception:
            return "error reading driver"
    return "n/a"


def print_state(label):
    log(f"--- {label} ---")
    log(f"apple-bce refcount: {get_refcount('apple_bce')}")
    log(f"holders of apple_bce: {get_holders('apple_bce')}")
    log(f"driver for audio (02:00.3): {get_pci_driver('0000:02:00.3')}")
    log(f"driver for bridge (02:00.1): {get_pci_driver('0000:02:00.1')}")


def run_suspend_fix(action):
    log(f"--- executing {action} ---")
    # match the NOPASSWD re-exec logic: run the script directly with sudo
    cmd = ["sudo", suspend_fix, action]
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if process.stdout:
            for line in process.stdout:
                log(line.strip())
        process.wait()
    except Exception as e:
        log(f"error running suspendfix: {e}")


def main():
    if os.path.exists(log_file):
        os.remove(log_file)

    log("starting suspend fix debugging...")
    log(f"target script: {suspend_fix}")

    if not os.path.exists(suspend_fix):
        log(f"error: suspendfix script not found at {suspend_fix}")
        sys.exit(1)

    print_state("pre-unload state")
    run_suspend_fix("unload")
    print_state("post-unload state")

    # check if apple-bce is still loaded
    res = subprocess.run(["lsmod"], capture_output=True, text=True)
    if "apple_bce" in res.stdout:
        log("failure: apple-bce is still loaded.")
        log("checking for other open files on apple-bce...")
        try:
            lsof_res = subprocess.run(
                ["sudo", "lsof"], capture_output=True, text=True
            )
            for line in lsof_res.stdout.splitlines():
                if "apple_bce" in line:
                    log(line)
        except Exception as e:
            log(f"error running lsof: {e}")
    else:
        log("success: apple-bce was unloaded.")

    run_suspend_fix("load")
    log(f"debugging complete. report saved to {log_file}")


if __name__ == "__main__":
    main()
