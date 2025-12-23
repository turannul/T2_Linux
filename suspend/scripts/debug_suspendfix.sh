#!/bin/bash

SUSPEND_FIX="./Documents/backlight/suspend/suspendfix"
LOG_FILE="suspend_debug_report.txt"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting Suspend Fix Debugging..."
log "Target Script: $SUSPEND_FIX"

if [ ! -f "$SUSPEND_FIX" ]; then
    log "ERROR: suspendfix script not found at $SUSPEND_FIX"
    exit 1
fi

chmod +x "$SUSPEND_FIX"

log "--- Pre-Unload State ---"
log "apple-bce Refcount: $(cat /sys/module/apple_bce/refcnt 2>/dev/null)"
log "Holders of apple_bce: $(ls /sys/module/apple_bce/holders/ 2>/dev/null)"
log "Driver for Audio (02:00.3): $(readlink -f /sys/bus/pci/devices/0000:02:00.3/driver 2>/dev/null)"
log "Driver for Bridge (02:00.1): $(readlink -f /sys/bus/pci/devices/0000:02:00.1/driver 2>/dev/null)"

log "--- Executing Unload ---"
sudo "$SUSPEND_FIX" unload | sudo tee -a "$LOG_FILE" 2>&1

log "--- Post-Unload State ---"
log "apple-bce Refcount: $(cat /sys/module/apple_bce/refcnt 2>/dev/null)"
log "Holders of apple_bce: $(ls /sys/module/apple_bce/holders/ 2>/dev/null)"
log "Driver for Audio (02:00.3): $(readlink -f /sys/bus/pci/devices/0000:02:00.3/driver 2>/dev/null)"
log "Driver for Bridge (02:00.1): $(readlink -f /sys/bus/pci/devices/0000:02:00.1/driver 2>/dev/null)"

if lsmod | grep -q "apple_bce"; then
    log "FAILURE: apple-bce is still loaded."
    log "Checking for other open files on apple-bce..."
    # Attempt to find processes holding open files in /dev or /sys related to the module (best effort)
    sudo lsof | grep "apple_bce" >> "$LOG_FILE" 2>&1
else
    log "SUCCESS: apple-bce was unloaded."
fi

log "--- Executing Load ---"
sudo "$SUSPEND_FIX" load | sudo tee -a "$LOG_FILE" 2>&1

log "Debugging Complete. Report saved to $LOG_FILE"
