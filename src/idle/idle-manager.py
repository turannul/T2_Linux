#!/usr/bin/env python3
#
#  idle-manager.py
#  T2_Linux
#
#  Created by turannul on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import gi
import json
import logging
import os
import re
import subprocess
import sys
from gi.repository import Gio, GLib  # type: ignore

sys.dont_write_bytecode = True


try:
    import t2  # type: ignore
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2  # type: ignore

# Require PyGObject
gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")


# --- Configuration ---
t_lock_bat = 30
t_screen_bat = 60
t_sleep_bat = 120
ac_multiplier = 2
T_DIM_OFFSET = 15

state_file = os.path.expanduser("~/.local/state/idle-manager/state.json")


# Globals
version = "0.0.5"
logger = t2.setup_logging("IdleManager", level=logging.DEBUG)
loop = GLib.MainLoop()
timeout_process = None
on_ac = False
audio_playing = False
inhibited = False
target_user = None
user_env = {}


def run_as_user(cmd_list, scope=True) -> subprocess.Popen[bytes]:
    if not target_user:
        return subprocess.Popen(cmd_list)

    prefix: list[str] = ["sudo", "-u", target_user, "env"]
    for k, v in user_env.items():
        prefix.append(f"{k}={v}")

    prefix += ["systemd-run", "--user"]
    if scope:
        prefix.append("--scope")

    return subprocess.Popen(prefix + cmd_list)


# --- State Management ---
def save_state(key, val) -> None:
    data = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    if key not in data:  # Don't overwrite if already saved (stay at user preferred level)
        data[key] = val
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(data, f)


def get_state(key) -> str | None:
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r") as f:
            data = json.load(f)
            return data.get(key)
    except Exception:
        return None


def clear_states() -> None:
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
        except Exception:
            pass


def enter_idle() -> None:
    t2.log_event(logger, "+", "Entering idle mode (Power-save)...")

    # Save and set Power Profile
    curr_pp, _, _ = t2.execute_command("powerprofilesctl get")
    if curr_pp and curr_pp != "power-saver":
        save_state("power_profile", curr_pp)
        t2.execute_command("qs -c noctalia-shell ipc call powerProfile set power-saver")

    # Save and set Keyboard Brightness
    curr_bkb, _, _ = t2.execute_command("bkb -s")
    if curr_bkb and curr_bkb != "0":
        save_state("kbd_brightness", curr_bkb)
        t2.execute_command("bkb 0")

    # Dim screen if not already dimmed/off
    dim_screen()


def exit_idle() -> None:
    t2.log_event(logger, "+", "Restoring from idle/dim mode...")

    # Restore Power Profile
    pp = get_state("power_profile")
    if pp:
        t2.execute_command(f"qs -c noctalia-shell ipc call powerProfile set {pp}")

    # Restore Keyboard
    kb = get_state("kbd_brightness")
    if kb:
        t2.execute_command(f"bkb {kb}")

    # Restore Screen Brightness
    sc = get_state("screen_brightness")
    if sc:
        t2.execute_command(f"bdp {sc}")

    clear_states()


def dim_screen() -> None:
    curr_bdp, _, _ = t2.execute_command("bdp -s")
    if curr_bdp:
        curr_bdp = curr_bdp.strip('%')
        if curr_bdp and curr_bdp != "10":
            save_state("screen_brightness", curr_bdp)
            t2.log_event(logger, "+", f"Dimming screen (from {curr_bdp}% to 10%)")
            t2.execute_command("bdp 10")


def get_self_cmd(action) -> str:
    return f"{sys.executable} {os.path.abspath(__file__)} {action}"


# --- Checks ---
def check_ac() -> bool:
    global on_ac
    stdout, _, _ = t2.execute_command("upower -i /org/freedesktop/UPower/devices/DisplayDevice")
    is_ac = "power supply:         yes" in stdout or "state:               charging" in stdout or "state:               fully-charged" in stdout
    if is_ac != on_ac:
        on_ac = is_ac
        t2.log_event(logger, "+", f"Power Source: {'AC' if is_ac else 'Battery'}")
        update_timeouts()
    return True


def check_audio() -> bool:
    global audio_playing
    stdout, _, _ = t2.execute_command("wpctl status")
    is_playing = False
    if "Streams:" in stdout:
        try:
            streams_section = stdout.split("Streams:")[1]
            for line in streams_section.splitlines():
                if "[active]" in line:
                    low = line.lower()
                    # Ignore cava and monitor streams explicitly
                    if "cava" in low or "monitor" in low:
                        continue
                    is_playing = True
                    break
        except IndexError:
            pass

    if is_playing != audio_playing:
        audio_playing = is_playing
        t2.log_event(logger, "+", f"Audio: {'Playing' if is_playing else 'Not Playing'}")
        update_timeouts()
    return True


def check_inhibitor() -> bool:
    global inhibited
    cmd = "busctl call org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager ListInhibitors"
    stdout, _, _ = t2.execute_command(cmd)
    pattern = r'"idle"\s+"[^"]*"\s+"[^"]*"\s+"block"'
    is_inhibited = bool(re.search(pattern, stdout))
    if is_inhibited != inhibited:
        inhibited = is_inhibited
        t2.log_event(logger, "+", f"Inhibitor: {'Detected' if inhibited else 'Not Detected'}")
        update_timeouts()
    return True


def update_timeouts() -> None:
    global timeout_process
    if timeout_process:
        timeout_process.terminate()
        timeout_process.wait()

    mult = ac_multiplier if on_ac else 1
    t = {
        "lock": t_lock_bat * mult,
        "dim": (t_screen_bat - T_DIM_OFFSET) * mult,
        "screen": t_screen_bat * mult,
        "sleep": t_sleep_bat * mult
    }

    cmd_lock = "qs -c noctalia-shell ipc call lockScreen lock"
    cmd_idle = get_self_cmd("idle")
    cmd_active = get_self_cmd("active")
    cmd_dim = get_self_cmd("dim")
    mon_off = "niri msg action power-off-monitors"
    mon_on = "niri msg action power-on-monitors"

    # Base swayidle command (merged static events)
    base = ["swayidle", "-w",
            "lock", cmd_lock,
            "before-sleep", f"{cmd_lock}; {cmd_idle}; {mon_off}"]

    if not inhibited:
        # Dimming
        if t['dim'] > 0:
            base += ["timeout", str(t['dim']), cmd_dim,
                     "resume", cmd_active]

        # Screen off + Idle states
        base += ["timeout", str(t['screen']), f"{cmd_idle}; {mon_off}",
                 "resume", f"{mon_on}; {cmd_active}"]

        # Suspend (if no audio)
        if not audio_playing:
            base += ["timeout", str(t['sleep']), "systemctl sleep"]

    t2.log_event(logger, "#", f"Updating swayidle (AC={on_ac}, Inhibited={inhibited}, Audio={audio_playing})")
    timeout_process = run_as_user(base)


def on_sleep(con, sender, path, iface, sig, p, d) -> bool:
    going_sleep = bool(p.unpack()[0])
    if going_sleep:
        t2.log_event(logger, "!", "System going to sleep...")
        enter_idle()
        t2.execute_command("qs -c noctalia-shell ipc call lockScreen lock")
        t2.execute_command("niri msg action power-off-monitors")
    else:
        t2.log_event(logger, "!", "System waking up...")
        exit_idle()
        t2.execute_command("niri msg action power-on-monitors")
    return True


def start_daemon() -> None:
    t2.check_root()
    clear_states()  # Start fresh

    # Initialize Session
    global target_user, user_env
    try:
        uid, target_user = t2.get_active_user()
        user_env = t2.get_user_env(uid)
        os.environ.update(user_env)
    except Exception as e:
        t2.log_event(logger, "-", f"Critical: Failed to identify active user session: {e}")
        sys.exit(1)

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep", "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, on_sleep, None)
    except Exception as e:
        t2.log_event(logger, "-", f"DBus Error: {e}")

    # Initial state check
    check_ac()
    check_audio()
    check_inhibitor()

    # Periodic checks
    GLib.timeout_add_seconds(5, check_ac)
    GLib.timeout_add_seconds(2, check_audio)
    GLib.timeout_add_seconds(3, check_inhibitor)

    t2.log_event(logger, "+", "Idle Manager Started")
    loop.run()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "idle":
            enter_idle()
        elif action == "active":
            exit_idle()
        elif action == "dim":
            dim_screen()
    else:
        start_daemon()
