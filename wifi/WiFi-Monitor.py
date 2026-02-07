#!/usr/bin/env python3
import datetime
import logging
import os
import re
import subprocess
import sys
import time
from typing import Pattern

log_file = "/var/log/wifi-guardian.log"

# Configure root logger directly
logging.basicConfig(level=logging.DEBUG)
logger: logging.Logger = logging.getLogger("WiFi-Guardian")
# Clear existing handlers to avoid duplication if re-run
logger.handlers.clear()


def _log(log_level: str, event_msg: str) -> None:
    """Log a message with a specific log level format."""
    timestamp: str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    level_str = "INFO"

    match log_level:
        case "-":
            level_str = "ERROR"
        case "!":
            level_str = "WARNING"
        case "*":
            level_str = "INFO"
        case "+":
            level_str = "INFO"
        case "#":
            level_str = "DEBUG"
        case _:
            level_str = "INFO"

    log_entry: str = f"[{timestamp}] [{level_str}] {event_msg}"

    # Print to stdout (for journalctl)
    print(log_entry, flush=True)

    # Append to log file
    try:
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
    except OSError as e:
        print(f"[{timestamp}] [ERROR] Failed to write to log file: {e}", file=sys.stderr)


services: list[str] = ["NetworkManager", "bluetooth"]
modules: list[str] = ["brcmfmac", "hci_bcm4377"]
cd_time = 30

# Regex pattern to match fatal errors (from my own experience):
patterns: list[str] = [
    r"CMD_TRIGGER_SCAN.*error.*\(5\)",  # - CMD_TRIGGER_SCAN error (5): I/O Error during scan start
    r"brcmf_msgbuf_query_dcmd",  # - query_dcmd: Firmware timeout (Hang)
    r"set wpa_auth failed",  # - set wpa_auth failed: Crypto offload failure
    r"error \(-12\)"  # - error (-12): ENOMEM (Memory allocation failure)
]


def _exec_cmd(command: str) -> bool:
    """Execute a shell command and return success status."""
    try:
        _log("#", f"Executing: {command}")
        subprocess.run(command, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        _log("!", f"Command failed: {command}")
        return False


def _unload() -> bool:
    try:
        _log("+", "STAGE 1: Unloading...")
        # Stop service first then, unload driver.
        for s in reversed(services):
            _log("+", f"Stopping Service: {s}")
            _exec_cmd(f"systemctl stop {s}")
        for m in reversed(modules):
            _log("+", f"Unloading module {m}...")
            # Using --remove-holders to be safe, similar to modprobe --remove
            _exec_cmd(f"modprobe --remove --remove-holders {m}")
        # Unloaded waiting hw to power off. (5 seconds)
        time.sleep(5)
        return True
    except Exception as err:
        _log("-", f"Unload unsucessful: {err}")
        return False


def _load() -> bool:
    try:
        _log("+", "STAGE 2: Loading...")
        # Load driver first then, [re]start service
        for m in modules:
            _log("+", f"Loading module {m}...")
            _exec_cmd(f"modprobe --verbose {m}")
        for s in services:
            _log("+", f"Starting Service: {s}")
            _exec_cmd(f"systemctl start {s}")
        return True
    except Exception as err:
        _log("-", f"Load unsucessful: {err}")
        return False


# If you know you know ;) [tip: deadpool movie reference]
def Al_is_watching() -> None:
    """Monitors the kernel ring buffer in real-time via journalctl."""
    _log("+", "Starting WiFi Guardian Monitor...")
    _log("#", f"Watching for patterns: {patterns}")

    compiled_patterns: list[Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in patterns]
    last_recovery_time = 0

    try:
        p = subprocess.Popen(['journalctl', '-k', '-f', '-n', '0', '--no-pager'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        if p.stdout is None:
            _log("-", f"Failed to open journalctl stdout. Error: {p.stderr}")
            return

        for line in p.stdout:
            if not line:
                continue

            for pattern in compiled_patterns:
                if pattern.search(line):
                    # Check if we are in a post-recovery cooldown period.
                    if time.time() - last_recovery_time < cd_time:
                        _log("+", "Error detected, but cooldown is active. Skipping reset.")
                        break

                    _log("#", f"PATTERN MATCHED: {pattern}")
                    _log("-", f"TRIGGER MATCHED: {line.strip()}")
                    _log("-", "CRITICAL HARDWARE HANG DETECTED. Initiating Nuclear Reset...")
                    _unload()
                    _load()
                    _log("+", "Reset sequence complete. Monitoring for stability...")

                    last_recovery_time = time.time()
                    break

    except PermissionError:
        _log("-", "Error: Permission denied. Run as root?")
    except Exception as err:
        _log("!", f"Unexpected monitor error: {err}")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root to reload kernel modules.")
        sys.exit(1)

    Al_is_watching()
