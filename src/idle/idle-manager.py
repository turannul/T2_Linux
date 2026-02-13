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
version = "0.0.8"
logger = t2.setup_logging("IdleManager", level=logging.DEBUG)
loop = GLib.MainLoop()
timeout_process = None
on_ac = False
audio_playing = False
inhibited = False
target_user = None
target_uid = None
user_env = {}


# --- State Management ---
def save_state(key, val) -> None:
    data = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    if key not in data:  # Don't overwrite if already saved
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
    assert target_user is not None and target_uid is not None
    curr_pp, _, _ = t2.execute_command_as_user("powerprofilesctl get", target_user, target_uid, env=user_env)
    if curr_pp and curr_pp != "power-saver":
        save_state("power_profile", curr_pp)
        t2.execute_command_as_user("qs -c noctalia-shell ipc call powerProfile set power-saver", target_user, target_uid, env=user_env)

    # Save and set Keyboard Brightness
    curr_bkb, _, _ = t2.execute_command_as_user("bkb -s", target_user, target_uid, env=user_env)
    if curr_bkb and curr_bkb != "0":
        save_state("kbd_brightness", curr_bkb)
        t2.execute_command_as_user("bkb 0", target_user, target_uid, env=user_env)

    dim_screen()


def exit_idle() -> None:
    if not os.path.exists(state_file):
        return

    t2.log_event(logger, "+", "Restoring from idle/dim mode...")

    assert target_user is not None and target_uid is not None
    pp = get_state("power_profile")
    if pp:
        t2.execute_command_as_user(f"qs -c noctalia-shell ipc call powerProfile set {pp}", target_user, target_uid, env=user_env)

    kb = get_state("kbd_brightness")
    if kb:
        t2.execute_command_as_user(f"bkb {kb}", target_user, target_uid, env=user_env)

    sc = get_state("screen_brightness")
    if sc:
        t2.execute_command_as_user(f"bdp {sc}", target_user, target_uid, env=user_env)

    clear_states()


def dim_screen() -> None:
    assert target_user is not None and target_uid is not None
    curr_bdp_raw, _, _ = t2.execute_command_as_user("bdp -s", target_user, target_uid, env=user_env)
    if curr_bdp_raw:
        try:
            val = int(curr_bdp_raw.strip().strip('%'))
            if val > 10:
                save_state("screen_brightness", str(val))
                t2.log_event(logger, "+", f"Dimming screen (from {val}% to 10%)")
                t2.execute_command_as_user("bdp 10", target_user, target_uid, env=user_env)
        except ValueError:
            pass


def get_self_cmd(action) -> str:
    return f"{sys.executable} {os.path.abspath(__file__)} {action}"


# --- Checks ---
def check_audio() -> bool:
    global audio_playing
    assert target_user is not None and target_uid is not None
    stdout, _, _ = t2.execute_command_as_user("wpctl status", target_user, target_uid, env=user_env)
    is_playing = False
    if "Streams:" in stdout:
        try:
            streams_section = stdout.split("Streams:")[1]
            for line in streams_section.splitlines():
                if "[active]" in line:
                    low = line.lower()
                    if "cava" in low or "monitor" in low:
                        continue  # Ignore: cava processes.
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
    assert target_user is not None and target_uid is not None
    stdout, _, _ = t2.execute_command_as_user(cmd, target_user, target_uid, env=user_env)
    pattern = r'"idle"\s+"[^"]*"\s+"[^"]*"\s+"block"'
    is_inhibited = bool(re.search(pattern, stdout))
    if is_inhibited != inhibited:
        inhibited = is_inhibited
        t2.log_event(logger, "+", f"Inhibitor: {'Detected' if inhibited else 'Not Detected'}")
        update_timeouts()
    return True


def update_timeouts() -> None:
    global timeout_process

    # Transition safety
    assert target_user is not None and target_uid is not None
    if os.path.exists(state_file):
        t2.log_event(logger, "#", "State change detected while idle. Restoring session.")
        exit_idle()
        t2.execute_command_as_user("niri msg action power-on-monitors", target_user, target_uid, env=user_env)

    if timeout_process:
        timeout_process.terminate()
        timeout_process.wait()

    mult = ac_multiplier if on_ac else 1
    t = {
        "lock": t_lock_bat * mult,
        "dim": (t_screen_bat * mult) - T_DIM_OFFSET,
        "screen": t_screen_bat * mult,
        "sleep": t_sleep_bat * mult
    }

    cmd_lock = "qs -c noctalia-shell ipc call lockScreen lock"
    cmd_idle = get_self_cmd("idle")
    cmd_active = get_self_cmd("active")
    cmd_dim = get_self_cmd("dim")
    mon_off = "niri msg action power-off-monitors"
    mon_on = "niri msg action power-on-monitors"

    swayidle_args = ["swayidle", "-w", "lock", f"{cmd_lock}; {cmd_idle}", "before-sleep", f"{cmd_lock}; {cmd_idle}; {mon_off}"]

    if not inhibited:
        if t['dim'] > 0:
            swayidle_args += ["timeout", str(int(t['dim'])), cmd_dim, "resume", cmd_active]

        swayidle_args += ["timeout", str(int(t['screen'])), f"{cmd_idle}; {mon_off}", "resume", f"{mon_on}; {cmd_active}"]

        if not audio_playing:
            swayidle_args += ["timeout", str(int(t['sleep'])), "systemctl sleep"]

    t2.log_event(logger, "#", f"Updating swayidle (AC={on_ac}, Inhibited={inhibited}, Audio={audio_playing})")

    # Use direct Popen with sudo -E -u for the background process
    full_cmd = f"sudo -E -u {target_user} {' '.join(swayidle_args)}"
    timeout_process = subprocess.Popen(full_cmd, shell=True, executable='/bin/zsh', env=user_env)


# --- DBus Signal Handlers ---
def on_sleep(con, sender, path, iface, sig, p, log):
    _, _, _= con, path, iface
    going_sleep = bool(p.unpack()[0])
    assert target_user is not None and target_uid is not None
    if going_sleep:
        t2.log_event(log, "!", f"System going to sleep... (Signal: {sig} from {sender})")
        enter_idle()
        t2.execute_command_as_user("qs -c noctalia-shell ipc call lockScreen lock", target_user, target_uid, env=user_env)
        t2.execute_command_as_user("niri msg action power-off-monitors", target_user, target_uid, env=user_env)
    else:
        t2.log_event(log, "!", "System waking up...")
        exit_idle()
        t2.execute_command_as_user("niri msg action power-on-monitors", target_user, target_uid, env=user_env)
    return True


def on_unlock(con, sender, path, iface, sig, p, log):
    _, _, _, _ = con, path, iface, p
    t2.log_event(log, "+", f"Session unlocked (Signal: {sig} from {sender}). Restoring state.")
    exit_idle()
    return True


def on_ac_changed(con, sender, path, iface, sig, p, log):
    _, _, _, _ = con, path, iface, sig
    global on_ac
    # PropertiesChanged signature: (interface_name, changed_properties, invalidated_properties)
    target_iface, changed, _ = p.unpack()
    if target_iface == "org.freedesktop.UPower" and "OnBattery" in changed:
        is_ac = not changed["OnBattery"]
        if is_ac != on_ac:
            on_ac = is_ac
            t2.log_event(log, "+", f"Power Source: {'AC' if is_ac else 'Battery'} (Signal from {sender})")
            update_timeouts()
    return True


def start_daemon() -> None:
    t2.check_root()
    # If state exists on boot/restart, restore it first to be safe
    # But wait, target_user is not set yet.

    global target_user, target_uid, user_env, on_ac
    try:
        target_uid, target_user = t2.get_active_user()
        user_env = t2.get_user_env(target_uid)
        os.environ.update(user_env)
    except Exception as e:
        t2.log_event(logger, "-", f"Critical: Failed to identify active user session: {e}")
        sys.exit(1)

    exit_idle()
    clear_states()

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        # Sleep/Wake
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep", "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, on_sleep, logger)
        # Unlock
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Session", "Unlock", None, None, Gio.DBusSignalFlags.NONE, on_unlock, logger)
        # AC (UPower)
        bus.signal_subscribe("org.freedesktop.UPower", "org.freedesktop.DBus.Properties", "PropertiesChanged", "/org/freedesktop/UPower", None, Gio.DBusSignalFlags.NONE, on_ac_changed, logger)
    except Exception as e:
        t2.log_event(logger, "-", f"DBus Error: {e}")

    # Initial state
    # Synchronous check for OnBattery
    res, _, _ = t2.execute_command("busctl get-property org.freedesktop.UPower /org/freedesktop/UPower org.freedesktop.UPower OnBattery")
    if "b true" in res:
        on_ac = False
    elif "b false" in res:
        on_ac = True

    t2.log_event(logger, "+", f"Initial Power Source: {'AC' if on_ac else 'Battery'}")

    check_audio()
    check_inhibitor()

    # Periodic checks for non signal-friendly attributes
    GLib.timeout_add_seconds(2, check_audio)
    GLib.timeout_add_seconds(3, check_inhibitor)

    t2.log_event(logger, "+", "Idle Manager Started (v" + version + ")")
    loop.run()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # For idle/active/dim actions called via swayidle/sudo, we need user context if not already set.
        # But when called as subprocess, we inherit env and target_user is usually root unless we handle it.
        # Actually, when 'idle' is called, it's run as root (via sys.executable).
        # We need to ensure it can still restore state.

        # Re-fetch user if needed for standalone actions
        try:
            target_uid, target_user = t2.get_active_user()
            user_env = t2.get_user_env(target_uid)
        except Exception:
            pass

        action = sys.argv[1]
        if action == "idle":
            enter_idle()
        elif action == "active":
            exit_idle()
        elif action == "dim":
            dim_screen()
    else:
        start_daemon()
