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
import logging
import os
import re
import subprocess
import sys
import t2
from gi.repository import Gio, GLib  # type: ignore

# Require PyGObject
gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")


# --- Configuration ---
t_lock_bat = 30
t_screen_bat = 60
t_sleep_bat = 120
ac_multiplier = 2

state_dir = os.path.expanduser("~/.local/state")
power_profile_state = os.path.join(state_dir, "power_profile_state")
kbd_brightness_state = os.path.join(state_dir, "kbd_brightness_state")


# Globals
logger = t2.setup_logging("IdleManager", level=logging.DEBUG)
loop = GLib.MainLoop()
event_process = None
timeout_process = None
on_ac = False
audio_playing = False
inhibited = False
target_user = None


def _log(char, msg) -> None:
    t2.log_event(logger, char, msg)


def setup_env() -> None:
    """Sets up XDG_RUNTIME_DIR, WAYLAND_DISPLAY, and DBUS_SESSION_BUS_ADDRESS."""
    try:
        if all(k in os.environ for k in ["XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"]):
            return

        uid = 1000
        runtime_dir = f"/run/user/{uid}"

        if os.path.exists(runtime_dir):
            if "XDG_RUNTIME_DIR" not in os.environ:
                os.environ["XDG_RUNTIME_DIR"] = runtime_dir
                _log("#", f"Set XDG_RUNTIME_DIR={runtime_dir}")

            if "WAYLAND_DISPLAY" not in os.environ:
                for item in os.listdir(runtime_dir):
                    if item.startswith("wayland-") and not item.endswith(".lock"):
                        os.environ["WAYLAND_DISPLAY"] = item
                        _log("#", f"Set WAYLAND_DISPLAY={item}")
                        break

            if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
                dbus_path = f"{runtime_dir}/bus"
                if os.path.exists(dbus_path):
                    os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={dbus_path}"
                    _log("#", f"Set DBUS_SESSION_BUS_ADDRESS=unix:path={dbus_path}")
    except Exception as e:
        logger.error(f"Failed to setup environment: {e}")


def get_target_user() -> str | None:
    try:
        import pwd
        return pwd.getpwuid(1000).pw_name
    except Exception:
        return None


target_user: str | None = get_target_user()


def run_as_user(cmd_list, scope=True) -> subprocess.Popen[bytes]:
    if not target_user:
        return subprocess.Popen(cmd_list)

    uid = 1000
    runtime_dir: str = f"/run/user/{uid}"
    prefix: list[str] = ["sudo", "-u", target_user, "env", f"XDG_RUNTIME_DIR={runtime_dir}"]

    if "WAYLAND_DISPLAY" in os.environ:
        prefix.append(f"WAYLAND_DISPLAY={os.environ['WAYLAND_DISPLAY']}")

    if "DBUS_SESSION_BUS_ADDRESS" in os.environ:
        prefix.append(f"DBUS_SESSION_BUS_ADDRESS={os.environ['DBUS_SESSION_BUS_ADDRESS']}")

    prefix += ["systemd-run", "--user"]
    if scope:
        prefix.append("--scope")

    return subprocess.Popen(prefix + cmd_list)


def run_cmd(cmd, shell=True) -> str:
    res: subprocess.CompletedProcess[str] = t2.run_command(cmd, shell=shell)
    if res.returncode != 0:
        _log("-", f"Error running '{cmd}': {res.stderr}")
    return res.stdout.strip()


# --- State ---
def save_power_profile() -> None:
    curr: str = run_cmd("powerprofilesctl get")
    if curr and curr != "power-saver":
        os.makedirs(state_dir, exist_ok=True)
        with open(power_profile_state, "w") as f:
            f.write(curr)


def restore_power_profile() -> None:
    profile = "balanced"
    if os.path.exists(power_profile_state):
        with open(power_profile_state, "r") as f:
            profile = f.read().strip() or "balanced"
    run_cmd(f"qs -c noctalia-shell ipc call powerProfile set {profile}")


def save_bkb() -> None:
    curr: str = run_cmd("bkb -s")
    if curr and curr != "0":
        os.makedirs(state_dir, exist_ok=True)
        with open(kbd_brightness_state, "w") as f:
            f.write(curr)


def restore_bkb() -> None:
    if os.path.exists(kbd_brightness_state):
        with open(kbd_brightness_state, "r") as f:
            val: str = f.read().strip()
            if val:
                run_cmd(f"bkb {val}")


def enter_idle() -> None:
    _log("+", "Entering idle mode...")
    save_power_profile()
    save_bkb()
    run_cmd("qs -c noctalia-shell ipc call powerProfile set power-saver")
    run_cmd("bkb 0")


def exit_idle() -> None:
    _log("+", "Exiting idle mode...")
    restore_power_profile()
    restore_bkb()


def get_self_cmd(action) -> str:
    return f"{sys.executable} {os.path.abspath(__file__)} {action}"


# --- Checks ---
def check_ac() -> bool:
    global on_ac
    is_ac: bool = False
    ac_path = "/sys/class/power_supply/ADP1/online"
    if os.path.exists(ac_path):
        with open(ac_path, "r") as f:
            is_ac = (f.read().strip() == "1")
            if is_ac != on_ac:
                on_ac = is_ac
                _log("+", f"Power Source: {'AC' if is_ac else 'Battery'}")
                update_timeouts()
    return True if is_ac else False


def check_audio() -> bool:
    global audio_playing
    res: subprocess.CompletedProcess[str] = t2.run_command("wpctl status", shell=True)
    is_playing = False
    if "Streams:" in res.stdout:
        streams: list[str] = res.stdout.split("Streams:")[1].splitlines()
        ignored = False
        for line in streams:
            if line and not line.startswith(" "):
                ignored: bool = "cava" in line.lower()
            elif "[active]" in line and not ignored and "monitor" not in line.lower():
                is_playing = True
                break
    if is_playing != audio_playing:
        audio_playing = is_playing
        _log("+", f"Audio: {'Playing' if is_playing else 'Not Playing'}")
        update_timeouts()
    return True if is_playing else False


def check_inhibitor() -> bool:
    global inhibited
    res: subprocess.CompletedProcess[str] = t2.run_command(["busctl", "call", "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "ListInhibitors"])
    pattern = r'"idle"\s+"[^"]*"\s+"[^"]*"\s+"block"'
    is_inhibited = bool(re.search(pattern, res.stdout))
    if is_inhibited != inhibited:
        inhibited = is_inhibited
        _log("+", f"Inhibitor: {'Detected' if inhibited else 'Not Detected'}")
        update_timeouts()
    return True if is_inhibited else False


def update_timeouts() -> None:
    global timeout_process
    if timeout_process:
        timeout_process.terminate()
        timeout_process.wait()

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
        base += ["timeout", str(t['sleep']), "systemctl sleep"]  # systemctl sleep i think better than suspend.

    _log("+", "Swayidle configured with:")
    _log("+", f"- Lock after: {t['lock']}s")
    _log("+", f"- Screen off after: {t['screen']}s")
    _log("+", f"- Suspend after: {'OFF' if audio_playing else f'{t['sleep']}s'}")

    timeout_process = run_as_user(base)


def on_sleep(con, sender, path, iface, sig, p, d) -> bool:
    _, _, _, _, _, _ = con, sender, path, iface, sig, d  # Discard useless info, meantime make pyright happy.
    going_sleep = bool(p.unpack()[0])
    # Current issue where going_sleep signals correct | but screen do light up. a few times?
    if going_sleep:
        _log("!", "Suspending...")
        enter_idle()
        t2.run_command("qs -c noctalia-shell ipc call lockScreen lock", shell=True)  # Lock the screen before-sleep
        t2.run_command("niri msg action power-off-monitors")  # Explicitly turn off?
        return True
    return True  # Can add else: to revert power-off-monitors action if required
    #  TODO: No multi-monitor supported yet?


def start_daemon() -> None:
    t2.check_root()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep", "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, on_sleep, None)
    except Exception as e:
        _log("-", f"DBus Error: {e}")

    run_as_user(["swayidle", "-w", "lock", "qs -c noctalia-shell ipc call lockScreen lock", "before-sleep", f"qs -c noctalia-shell ipc call lockScreen lock; {get_self_cmd('idle')}"])

    check_ac()
    check_audio()
    check_inhibitor()
    GLib.timeout_add_seconds(2, check_ac)
    GLib.timeout_add_seconds(2, check_audio)
    GLib.timeout_add_seconds(2, check_inhibitor)

    _log("+", "Idle Manager Started")
    loop.run()
    _log("+", "Idle Manager Stopped")


if __name__ == "__main__":
    setup_env()
    if len(sys.argv) > 1:
        if sys.argv[1] == "idle":
            enter_idle()
        elif sys.argv[1] == "active":
            exit_idle()
    else:
        start_daemon()
