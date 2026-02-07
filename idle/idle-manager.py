#!/usr/bin/env python3
import gi
import os
import re
import signal
import subprocess
import sys
from gi.repository import Gio, GLib  # type: ignore

# Require PyGObject
gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")

# import common utils
sys.path.append("/usr/local/lib/t2linux")
try:
    import t2
except ImportError:
    # fallback for dev environment
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.join(script_dir, "..", "common"))
    try:
        import t2
    except ImportError:
        print("Error: Could not import t2.py.")
        sys.exit(1)

# --- Configuration ---
t_lock_bat = 30
t_screen_bat = 60
t_sleep_bat = 120
ac_multiplier = 2

state_dir = os.path.expanduser("~/.local/state")
power_profile_state = os.path.join(state_dir, "power_profile_state")
kbd_brightness_state = os.path.join(state_dir, "kbd_brightness_state")
log_file = "/var/log/idle_mgmr.log"

# Globals
logger = t2.setup_logging(log_file, "IdleManager")
loop = GLib.MainLoop()
event_process = None
timeout_process = None
on_ac = False
audio_playing = False
inhibited = False


def _log(char, msg):
    t2.log_event(logger, char, msg)


def run_cmd(cmd, shell=True):
    res = t2.run_command(cmd, shell=shell)
    if res.returncode != 0:
        _log("-", f"Error running '{cmd}': {res.stderr}")
    return res.stdout.strip()


# --- State ---
def save_power_profile():
    curr = run_cmd("powerprofilesctl get")
    if curr and curr != "power-saver":
        os.makedirs(state_dir, exist_ok=True)
        with open(power_profile_state, "w") as f:
            f.write(curr)


def restore_power_profile():
    profile = "balanced"
    if os.path.exists(power_profile_state):
        with open(power_profile_state, "r") as f:
            profile = f.read().strip() or "balanced"
    run_cmd(f"qs -c noctalia-shell ipc call powerProfile set {profile}")


def save_bkb():
    curr = run_cmd("bkb -s")
    if curr and curr != "0":
        os.makedirs(state_dir, exist_ok=True)
        with open(kbd_brightness_state, "w") as f:
            f.write(curr)


def restore_bkb():
    if os.path.exists(kbd_brightness_state):
        with open(kbd_brightness_state, "r") as f:
            val = f.read().strip()
            if val:
                run_cmd(f"bkb {val}")


def enter_idle():
    _log("+", "Entering idle mode...")
    save_power_profile()
    save_bkb()
    run_cmd("qs -c noctalia-shell ipc call powerProfile set power-saver")
    run_cmd("bkb 0")


def exit_idle():
    _log("+", "Exiting idle mode...")
    restore_power_profile()
    restore_bkb()


def get_self_cmd(action):
    return f"{sys.executable} {os.path.abspath(__file__)} {action}"


# --- Checks ---
def check_ac():
    global on_ac
    ac_path = "/sys/class/power_supply/ADP1/online"
    if os.path.exists(ac_path):
        with open(ac_path, "r") as f:
            is_ac = (f.read().strip() == "1")
            if is_ac != on_ac:
                on_ac = is_ac
                _log("+", f"Power Source: {'AC' if is_ac else 'Battery'}")
                update_timeouts()
    return True


def check_audio():
    global audio_playing
    res = t2.run_command("wpctl status", shell=True)
    is_playing = False
    if "Streams:" in res.stdout:
        streams = res.stdout.split("Streams:")[1].splitlines()
        ignored = False
        for line in streams:
            if line and not line.startswith(" "):
                ignored = "cava" in line.lower()
            elif "[active]" in line and not ignored and "monitor" not in line.lower():
                is_playing = True
                break
    if is_playing != audio_playing:
        audio_playing = is_playing
        _log("+", f"Audio: {'Playing' if is_playing else 'Silent'}")
        update_timeouts()
    return True


def check_inhibitor():
    global inhibited
    res = t2.run_command(["busctl", "call", "org.freedesktop.login1", "/org/freedesktop/login1",
                          "org.freedesktop.login1.Manager", "ListInhibitors"])
    pattern = r'"idle"\s+"[^"]*"\s+"[^"]*"\s+"block"'
    is_inhibited = bool(re.search(pattern, res.stdout))
    if is_inhibited != inhibited:
        inhibited = is_inhibited
        _log("#", f"Inhibitor: {'Detected' if inhibited else 'Cleared'}")
        update_timeouts()
    return True


def update_timeouts():
    global timeout_process
    if timeout_process:
        timeout_process.terminate()
        timeout_process.wait()
    if inhibited:
        return

    mult = ac_multiplier if on_ac else 1
    t = {"lock": t_lock_bat * mult, "screen": t_screen_bat * mult, "sleep": t_sleep_bat * mult}

    cmd_lock = "qs -c noctalia-shell ipc call lockScreen lock"
    cmd_idle = get_self_cmd("idle")
    cmd_active = get_self_cmd("active")
    mon_off = "niri msg action power-off-monitors"
    mon_on = "niri msg action power-on-monitors"

    base = ["swayidle", "-w", "timeout", str(t['lock']), cmd_lock,
            "timeout", str(t['screen']), f"{cmd_idle}; {mon_off}",
            "resume", f"{mon_on}; {cmd_active}"]

    if not audio_playing:
        base += ["timeout", str(t['sleep']), "systemctl suspend"]

    _log("+", f"Timeouts updated: lock={t['lock']}s, screen={t['screen']}s, "
         f"suspend={'OFF' if audio_playing else f'{t['sleep']}s'}")
    timeout_process = subprocess.Popen(base)


def on_sleep(connection, sender, path, iface, signal, params, data):
    if params.unpack()[0]:
        _log("!", "Suspending...")
        enter_idle()
        t2.run_command("qs -c noctalia-shell ipc call lockScreen lock", shell=True)
    else:
        _log("!", "Resuming...")
        t2.run_command("niri msg action power-on-monitors", shell=True)
        exit_idle()


def start_daemon():
    t2.check_root()
    t2.setup_xdg_env(logger)

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
                             "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, on_sleep, None)
    except Exception as e:
        _log("-", f"DBus Error: {e}")

    subprocess.Popen(["swayidle", "-w", "lock", "qs -c noctalia-shell ipc call lockScreen lock",
                      "before-sleep", f"qs -c noctalia-shell ipc call lockScreen lock; {get_self_cmd('idle')}"])

    check_ac()
    check_audio()
    check_inhibitor()
    GLib.timeout_add_seconds(5, check_ac)
    GLib.timeout_add_seconds(10, check_audio)
    GLib.timeout_add_seconds(3, check_inhibitor)

    _log("+", "Idle Manager Started")
    loop.run()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    if len(sys.argv) > 1:
        if sys.argv[1] == "idle":
            enter_idle()
        elif sys.argv[1] == "active":
            exit_idle()
    else:
        start_daemon()
