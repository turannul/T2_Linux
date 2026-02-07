#!/usr/bin/env python3
import datetime
import re
import subprocess
import sys

# constants
log_file = "resume_verification.log"


def log(msg):
    print(msg)
    with open(log_file, "a") as f:
        f.write(msg + "\n")


def run_and_filter(cmd, label, pattern, last_n=0):
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
            log("(no matches found)")
    except Exception as e:
        log(f"failed to run {' '.join(cmd)}: {e}")


def main():
    with open(log_file, "w") as f:
        f.write(f"--- test started at {datetime.datetime.now()} ---\n")

    log(f"--- test started at {datetime.datetime.now()} ---")
    log("setting rtc wake alarm for 30 minutes (1800s)...")
    try:
        subprocess.run(["sudo", "rtcwake", "-m", "no", "-s", "1800"], check=True)
    except Exception as e:
        log(f"failed to set rtcwake: {e}")
        sys.exit(1)

    log("suspending system via systemctl...")
    try:
        # this command blocks until the system wakes up
        subprocess.run(["sudo", "systemctl", "suspend"], check=True)
    except Exception as e:
        log(f"failed to suspend: {e}")
        sys.exit(1)

    log(f"\n--- system resumed at {datetime.datetime.now()} ---")
    log("verifying system state...")

    run_and_filter(
        ["sudo", "journalctl", "-b", "0", "-n", "100", "--no-pager"],
        "1. checking suspend fix service logs (last 100 lines of journal)",
        r"suspend|apple-bce|thunderbolt",
    )

    run_and_filter(
        ["sudo", "dmesg"],
        "2. checking for kernel errors (dmesg tail 50)",
        r"Call Trace|error|fail|warn",
        last_n=50,
    )

    run_and_filter(
        ["lsmod"],
        "3. checking loaded modules",
        r"apple_bce|thunderbolt|brcmfmac",
    )

    run_and_filter(
        ["lspci"],
        "4. checking pci devices (thunderbolt)",
        r"Titan Ridge",
    )

    log("\n--- test complete ---")
    print(f"logs saved to {log_file}")


if __name__ == "__main__":
    main()
