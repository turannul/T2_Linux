#!/usr/bin/env python3
import datetime
import re
import subprocess
import sys

LOG_FILE = "resume_verification.log"


def log(msg: str):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


def run_and_filter(cmd: list[str], label: str, pattern: str, last_n: int = 0):
    log(f"\n{label}:")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        lines = res.stdout.splitlines()
        if last_n > 0:
            lines = lines[-last_n:]

        regex = re.compile(pattern, re.IGNORECASE)
        found = False
        for line in lines:
            if regex.search(line):
                log(line)
                found = True
        if not found:
            log("(No matches found)")
    except Exception as e:
        log(f"Failed to run {' '.join(cmd)}: {e}")


def main():
    with open(LOG_FILE, "w") as f:
        f.write(f"--- Test Started at {datetime.datetime.now()} ---\n")

    log(f"--- Test Started at {datetime.datetime.now()} ---")
    log("Setting RTC wake alarm for 30 minutes (1800s)...")
    try:
        subprocess.run(["sudo", "rtcwake", "-m", "no", "-s", "1800"], check=True)
    except Exception as e:
        log(f"Failed to set rtcwake: {e}")
        sys.exit(1)

    log("Suspending system via systemctl...")
    try:
        # This command blocks until the system wakes up
        subprocess.run(["sudo", "systemctl", "suspend"], check=True)
    except Exception as e:
        log(f"Failed to suspend: {e}")
        sys.exit(1)

    log(f"\n--- System Resumed at {datetime.datetime.now()} ---")
    log("Verifying system state...")

    run_and_filter(
        ["sudo", "journalctl", "-b", "0", "-n", "100", "--no-pager"],
        "1. Checking Suspend Fix Service Logs (Last 100 lines of journal)",
        r"suspend|apple-bce|thunderbolt",
    )

    run_and_filter(
        ["sudo", "dmesg"],
        "2. Checking for Kernel Errors (dmesg tail 50)",
        r"Call Trace|error|fail|warn",
        last_n=50,
    )

    run_and_filter(
        ["lsmod"],
        "3. Checking Loaded Modules",
        r"apple_bce|thunderbolt|brcmfmac",
    )

    run_and_filter(
        ["lspci"],
        "4. Checking PCI Devices (Thunderbolt)",
        r"Titan Ridge",
    )

    log("\n--- Test Complete ---")
    print(f"Logs saved to {LOG_FILE}")


if __name__ == "__main__":
    main()
