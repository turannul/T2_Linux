#!/usr/bin/env python3
import datetime
import gi
import logging
import os
import re
import signal
import subprocess
import sys
from gi.repository import Gio, GLib  # type: ignore

# Require PyGObject
gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")

# --- Configuration ---
# Base Timeouts (Battery)
t_lock_bat = 30
t_screen_bat = 60
t_sleep_bat = 120

# AC Multiplier
ac_multiplier = 2

state_directory = os.path.expanduser("~/.local/state")
power_profile_state = os.path.join(state_directory, "power_profile_state")
keyboard_brightness_state = os.path.join(state_directory, "kbd_brightness_state")

log_file = "/var/log/idle_mgmr.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file)]
)
logger = logging.getLogger(__name__)


# --- Environment Setup (Fix for Root/Sudo) ---
def setup_environment():
    """Ensure XDG_RUNTIME_DIR and WAYLAND_DISPLAY are set, enabling root to talk to Niri."""
    try:
        # 1. Trust existing env if set
        if os.environ.get("XDG_RUNTIME_DIR") and os.environ.get("WAYLAND_DISPLAY"):
            return

        # 2. Try to find the primary user's session (assuming UID 1000 for single-user system)
        # In a multi-user setup, we'd need more complex logic (e.g., checking logind).
        uid = 1000
        runtime_dir = f"/run/user/{uid}"

        if os.path.exists(runtime_dir):
            if "XDG_RUNTIME_DIR" not in os.environ:
                os.environ["XDG_RUNTIME_DIR"] = runtime_dir
                logger.info(f"Set XDG_RUNTIME_DIR={runtime_dir}")

            # 3. Find Wayland Display
            if "WAYLAND_DISPLAY" not in os.environ:
                # Look for wayland-* socket in runtime_dir
                for item in os.listdir(runtime_dir):
                    if item.startswith("wayland-") and not item.endswith(".lock"):
                        os.environ["WAYLAND_DISPLAY"] = item
                        logger.info(f"Set WAYLAND_DISPLAY={item}")
                        break
    except Exception as e:
        logger.error(f"Failed to setup environment: {e}")


setup_environment()


def _log(log_level: str, event_msg: str) -> None:
    """Log a message with a specific log level format."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    level_str = "INFO"

    match log_level:
        case "-":
            level_str = "ERROR"
            logger.error(f"[{timestamp}] [{level_str}] {event_msg}")
        case "!":
            level_str = "WARNING"
            logger.warning(f"[{timestamp}] [{level_str}] {event_msg}")
        case "#":
            level_str = "DEBUG"
            logger.debug(f"[{timestamp}] [{level_str}] {event_msg}")
        case _:
            level_str = "INFO"
            logger.info(f"[{timestamp}] [{level_str}] {event_msg}")


def run_cmd(cmd):
    """Run a shell command and return its output (stripped)."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.stdout.strip()
    except Exception as e:
        _log("-", f"Error running '{cmd}': {e}")
        return ""


# --- State Management Functions ---
def ensure_state_directory():
    try:
        if not os.path.exists(state_directory):
            os.makedirs(state_directory, exist_ok=True)
        return True
    except Exception:
        return False


def save_power_profile():
    try:
        current = run_cmd("powerprofilesctl get")
        if current and current != "power-saver":
            ensure_state_directory()
            with open(power_profile_state, "w") as f:
                f.write(current)
    except Exception:
        pass


def set_power_saver():
    try:
        run_cmd("qs -c noctalia-shell ipc call powerProfile set power-saver")
    except Exception:
        pass


def restore_power_profile():
    try:
        profile = "balanced"
        if os.path.exists(power_profile_state):
            with open(power_profile_state, "r") as f:
                c = f.read().strip()
                if c:
                    profile = c
        run_cmd(f"qs -c noctalia-shell ipc call powerProfile set {profile}")
    except Exception:
        pass


def save_bkb():
    try:
        current = run_cmd("bkb -s")
        if current and current != "0":
            ensure_state_directory()
            with open(keyboard_brightness_state, "w") as f:
                f.write(current)
    except Exception:
        pass


def set_bkb_off():
    try:
        run_cmd("bkb 0")
    except Exception:
        pass


def restore_bkb():
    try:
        if os.path.exists(keyboard_brightness_state):
            with open(keyboard_brightness_state, "r") as f:
                val = f.read().strip()
                if val:
                    run_cmd(f"bkb {val}")
    except Exception:
        pass


def enter_idle_mode() -> bool:
    """Called when screen timeout triggers or before sleep."""
    try:
        _log("+", "Entering idle mode sequence...")
        save_power_profile()
        save_bkb()
        set_power_saver()
        set_bkb_off()
        return True
    except Exception as e:
        _log("-", f"Error entering idle mode: {e}")
        return False


def exit_idle_mode() -> bool:
    """Called when activity resumes or after sleep."""
    try:
        _log("+", "Exiting idle mode sequence...")
        restore_power_profile()
        restore_bkb()
        return True
    except Exception as e:
        _log("-", f"Error exiting idle mode: {e}")
        return False


def get_self_cmd(action):
    return f"{sys.executable} {os.path.abspath(__file__)} {action}"


# --- Logic Manager ---

class IdleManager:
    def __init__(self):
        self.loop = GLib.MainLoop()
        self.event_process = None
        self.timeout_process = None

        # State
        self.on_ac = False
        self.audio_playing = False
        self.inhibited = False

        # Config
        self.cmd_idle = get_self_cmd("idle")
        self.cmd_active = get_self_cmd("active")
        self.cmd_lock = "qs -c noctalia-shell ipc call lockScreen lock"
        self.mon_off = "niri msg action power-off-monitors"
        self.mon_on = "niri msg action power-on-monitors"

        # D-Bus Connection for Signals
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.bus.signal_subscribe(
                "org.freedesktop.login1",
                "org.freedesktop.login1.Manager",
                "PrepareForSleep",
                "/org/freedesktop/login1",
                None,
                Gio.DBusSignalFlags.NONE,
                self.on_prepare_for_sleep,
                None
            )
            _log("#", "Connected to DBus for PrepareForSleep")
        except Exception as e:
            _log("-", f"Failed to connect to DBus: {e}")

    def on_prepare_for_sleep(
        self, connection, sender_name, object_path, interface_name,
        signal_name, parameters, user_data
    ):
        """Handle system suspend/resume signals instantly."""
        try:
            sleeping = parameters.unpack()[0]
            if sleeping:
                _log("!", "System Suspending (Signal Received)")
                enter_idle_mode()
                # Ensure lock screen is triggered
                run_cmd(self.cmd_lock)
            else:
                _log("!", "System Resuming (Signal Received)")
                run_cmd(self.mon_on)
                exit_idle_mode()
        except Exception as e:
            _log("-", f"Error handling PrepareForSleep: {e}")

    def check_ac_power(self):
        """Check if AC power is connected via /sys/class/power_supply."""
        try:
            ac_path = "/sys/class/power_supply/ADP1/online"
            if os.path.exists(ac_path):
                with open(ac_path, "r") as f:
                    val = f.read().strip()
                    is_ac = (val == "1")
                    if is_ac != self.on_ac:
                        self.on_ac = is_ac
                        _log("+", f"Power Source Changed: {'AC' if is_ac else 'Battery'}")
                        self.update_timeouts()
        except Exception:
            pass
        return True

    def check_audio(self):
        """Check if audio is playing using wpctl (PipeWire), ignoring visualizers like cava."""
        try:
            res = subprocess.run("wpctl status", shell=True, capture_output=True, text=True)

            # We need to find the Streams section and check for active playback
            # while excluding monitor streams (like cava)
            is_playing = False
            if "Streams:" in res.stdout:
                streams_section = res.stdout.split("Streams:")[1]
                # Split into blocks by stream name (which aren't indented)
                # This is a bit brittle but wpctl output is hierarchical
                lines = streams_section.splitlines()
                current_stream_ignored = False

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue

                    # If line starts with non-whitespace, it's a new stream header
                    if not line.startswith(" "):
                        # Check if this stream is something we ignore (like cava)
                        current_stream_ignored = "cava" in line.lower()
                    else:
                        # This is a sub-line (channel/link)
                        if "[active]" in line and not current_stream_ignored:
                            # Also ignore monitor links which are used by visualizers
                            if "monitor" not in line.lower():
                                is_playing = True
                                break

            if is_playing != self.audio_playing:
                self.audio_playing = is_playing
                _log("+", f"Audio State Changed: {'Playing' if is_playing else 'Silent'}")
                self.update_timeouts()
        except Exception as e:
            _log("-", f"Error checking audio: {e}")
        return True

    def check_inhibitor(self):
        """
        Check for external inhibitors (video, etc).
        Specifically looks for (What: "idle", Mode: "block").
        """
        try:
            # We use a more precise regex check on the raw output.
            # busctl ListInhibitors returns an array of structs:
            # (string "What", string "Who", string "Why", string "Mode", uint32 "UID", uint32 "PID")
            res = subprocess.run(
                ["busctl", "call", "org.freedesktop.login1", "/org/freedesktop/login1",
                 "org.freedesktop.login1.Manager", "ListInhibitors"],
                capture_output=True, text=True
            )

            # Regex explanation:
            # We look for "idle" followed by three other strings, where the third string
            # after "idle" is "block".
            # Struct format: "what" "who" "why" "mode"
            # Example match: "idle" "firefox" "video" "block"
            pattern = r'"idle"\s+"[^"]*"\s+"[^"]*"\s+"block"'
            is_inhibited = bool(re.search(pattern, res.stdout))

            if is_inhibited != self.inhibited:
                self.inhibited = is_inhibited
                if is_inhibited:
                    _log("#", "Inhibitor Detected (Video/Game/etc)")
                else:
                    _log("#", "Inhibitor Cleared")
                self.update_timeouts()

        except Exception as e:
            _log("-", f"Error checking inhibitors: {e}")
        return True

    def get_current_timeouts(self):
        """Calculate timeout values based on AC status."""
        mult = ac_multiplier if self.on_ac else 1
        return {
            "lock": t_lock_bat * mult,
            "screen": t_screen_bat * mult,
            "sleep": t_sleep_bat * mult
        }

    def update_timeouts(self):
        """Kill and restart the swayidle timeout process with current rules."""
        if self.timeout_process:
            self.timeout_process.terminate()
            self.timeout_process.wait()
            self.timeout_process = None

        if self.inhibited:
            _log("+", "State: INHIBITED. No timeouts active.")
            return

        times = self.get_current_timeouts()

        if self.audio_playing:
            _log("+", f"State: AUDIO PLAYING. Lock: {times['lock']}s, "
                      f"Screen: {times['screen']}s. (Suspend Disabled)")
            cmd_list = [
                "swayidle", "-w",
                "timeout", str(times['lock']), self.cmd_lock,
                "timeout", str(times['screen']), f"{self.cmd_idle}; {self.mon_off}",
                "resume", f"{self.mon_on}; {self.cmd_active}"
            ]
        else:
            _log("+", f"State: NORMAL ({'AC' if self.on_ac else 'BAT'}). "
                      f"Lock: {times['lock']}s, Screen: {times['screen']}s, "
                      f"Sleep: {times['sleep']}s")
            cmd_list = [
                "swayidle", "-w",
                "timeout", str(times['lock']), self.cmd_lock,
                "timeout", str(times['screen']), f"{self.cmd_idle}; {self.mon_off}",
                "resume", f"{self.mon_on}; {self.cmd_active}",
                "timeout", str(times['sleep']), "systemctl suspend"
            ]

        try:
            self.timeout_process = subprocess.Popen(cmd_list)
        except Exception as e:
            _log("-", f"Failed to start swayidle timeouts: {e}")

    def start_persistent_events(self):
        """Start the always-running swayidle instance for manual events."""
        cmd_list = [
            "swayidle", "-w",
            "lock", self.cmd_lock,
            "before-sleep", f"{self.cmd_lock}; {self.cmd_idle}",
        ]

        _log("#", "Starting persistent event process (Lock/Sleep hooks)")
        self.event_process = subprocess.Popen(cmd_list)

    def run(self):
        self.check_ac_power()
        self.check_audio()
        self.check_inhibitor()

        self.start_persistent_events()

        GLib.timeout_add_seconds(5, self.check_ac_power)
        GLib.timeout_add_seconds(10, self.check_audio)
        GLib.timeout_add_seconds(3, self.check_inhibitor)

        _log("+", "Idle Manager Started (Event Loop)")
        try:
            self.loop.run()
        except KeyboardInterrupt:
            _log("!", "Stopping...")
            if self.event_process:
                self.event_process.terminate()
            if self.timeout_process:
                self.timeout_process.terminate()


if __name__ == "__main__":
    # Handle termination signals for clean shutdown
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "idle":
            enter_idle_mode()
        elif action == "active":
            exit_idle_mode()
    else:
        app = IdleManager()
        app.run()
