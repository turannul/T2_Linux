#!/bin/bash
LOG_FILE="resume_verification.log"

log() {
    echo "$1" | tee -a "$LOG_FILE"
}

log "--- Test Started at $(date) ---"
log "Setting RTC wake alarm for 30 minutes (1800s)..."
sudo rtcwake -m no -s 1800

log "Suspending system via systemctl..."
# This command blocks until the system wakes up
sudo systemctl suspend

log "--- System Resumed at $(date) ---"
log "Verifying system state..."

log "1. Checking Suspend Fix Service Logs (Last 100 lines of journal):"
sudo journalctl -b 0 -n 100 --no-pager | grep -iE "suspend|apple-bce|thunderbolt" | tee -a "$LOG_FILE"

log "2. Checking for Kernel Errors (dmesg tail):"
sudo dmesg | tail -n 50 | grep -iE "Call Trace|error|fail|warn" | tee -a "$LOG_FILE"

log "3. Checking Loaded Modules:"
lsmod | grep -E "apple_bce|thunderbolt|brcmfmac" | tee -a "$LOG_FILE"

log "4. Checking PCI Devices (Thunderbolt):"
lspci | grep "Titan Ridge" | tee -a "$LOG_FILE"

log "--- Test Complete ---"
echo "Logs saved to $LOG_FILE"
