#!/usr/bin/env python3
#
#  t2.py
#  T2_Linux
#
#  Created by turannul on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Tuple

cRed = "\033[0;31m"
cGreen = "\033[0;32m"
cYellow = "\033[1;33m"
cReset = "\033[0m"

e_success = 0
e_failure = 1
e_invalid_usage = 2


def _setup_logging(name: str = "T2Linux", level: int = logging.INFO) -> logging.Logger:
    """Sets up and returns a standard logger that logs to stdout."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger


def _log_event(logger: logging.Logger, level_char: str, message: str) -> None:
    """Maps level characters to logging levels and logs the message."""
    level_map: Dict[str, int] = {"-": logging.ERROR, "!": logging.WARNING, "*": logging.INFO, "+": logging.INFO, "#": logging.DEBUG, "_": logging.INFO}
    level = level_map.get(level_char, logging.INFO)
    if level_char == "_":
        print(message)
        logger.info(message)
    else:
        logger.log(level, message)


def _get_args() -> List[str]:
    """Retrieves command line arguments manually."""
    with open("/proc/self/cmdline", "r") as f:
        cmdline = f.read()
    # cmdline is null-separated
    return [arg for arg in cmdline.split('\0') if arg]


def _check_root() -> None:
    """Checks if root and re-executes with sudo if not."""
    if os.geteuid() != 0:
        argv = _get_args()
        script_path = os.path.abspath(argv[0])
        if os.access(script_path, os.X_OK):
            cmd = ["sudo", script_path] + argv[1:]
        else:
            cmd = ["sudo", "python3", script_path] + argv[1:]
        os.execvp("sudo", cmd)


def _get_active_user() -> Tuple[int, str]:
    """Identifies the active user logged into the session."""
    output = subprocess.check_output(["loginctl", "list-users", "--no-legend"], text=True).strip()
    parts = output.splitlines()[0].split()
    return int(parts[0]), parts[1]


def _get_user_env(uid: int) -> Dict[str, str]:
    """Returns a dictionary of environment variables for the specified user UID."""
    env = os.environ.copy()
    runtime_dir = f"/run/user/{uid}"
    if os.path.exists(runtime_dir):
        env["XDG_RUNTIME_DIR"] = runtime_dir
        if "DBUS_SESSION_BUS_ADDRESS" not in env:
            dbus_path = f"{runtime_dir}/bus"
            if os.path.exists(dbus_path):
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={dbus_path}"
        if "WAYLAND_DISPLAY" not in env:
            for item in os.listdir(runtime_dir):
                if item.startswith("wayland-") and not item.endswith(".lock"):
                    env["WAYLAND_DISPLAY"] = item
                    break
    return env


def _execute_command(cmd: str, as_user: bool = False, env: Optional[Dict[str, str]] = None) -> Tuple[str, str, int]:
    """Execute a shell command synchronously using /bin/zsh."""
    target_env: Dict[str, str] = env.copy() if env else os.environ.copy()
    if as_user:
        uid, user = _get_active_user()
        user_env = _get_user_env(uid)
        target_env.update(user_env)
        cmd = f"sudo -E -n -u {user} {cmd}"
    try:
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, executable="/bin/zsh", env=target_env, text=True)
        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        return stdout, stderr, proc.returncode
    except Exception as err:
        raise err


def _is_module_loaded(module_name: str) -> bool:
    """Checks if a kernel module is loaded using lsmod."""
    name = module_name.replace("-", "_")
    _, _, code = _execute_command(f"lsmod | grep -q '^{name} '")
    return code == 0


def _manage_module(action: str, module: str, logger: logging.Logger, delay: float) -> bool:
    """Internal helper to load or unload a kernel module."""
    is_load = action == "load"
    if _is_module_loaded(module) == is_load:
        _log_event(logger, "#", f"Module {module} is already {'loaded' if is_load else 'unloaded'}.")
        return True
    _log_event(logger, "*", f"{action.capitalize()}ing module {module}...")
    cmd = f"modprobe --verbose {module}" if is_load else f"modprobe --verbose --remove --remove-holders {module}"
    for attempt in range(1, 4):
        _, stderr, code = _execute_command(cmd)
        if code == 0 and _is_module_loaded(module) == is_load:
            _log_event(logger, "*", f"Module {module} {action}ed.")
            time.sleep(delay)
            return True
        _log_event(logger, "!", f"Attempt {attempt} failed: {stderr if stderr else 'check failed'}")
        time.sleep(1)
    _log_event(logger, "-", f"CRITICAL: Failed to {action} {module}.")
    return False


def _load_module(module_name: str, logger: logging.Logger, delay: float = 0.5) -> bool:
    """Loads a kernel module with retries."""
    return _manage_module("load", module_name, logger, delay)


def _unload_module(module_name: str, logger: logging.Logger, delay: float = 0.5) -> bool:
    """Unloads a kernel module with retries."""
    return _manage_module("unload", module_name, logger, delay)


def _manage_service(action: str, service: str, logger: logging.Logger, block: bool, as_user: bool) -> bool:
    """Internal helper to manage a systemd service."""
    user_flag = "--user" if as_user else ""
    check_cmd = f"systemctl {user_flag} is-active --quiet {service}"
    verb_ing = "Stopping" if action == "stop" else f"{action.capitalize()}ing"
    verb_ed = "stopped" if action == "stop" else f"{action}ed"
    _log_event(logger, "*", f"{verb_ing} {service}...")
    for attempt in range(1, 4):
        _execute_command(f"systemctl {user_flag} {action} {'--no-block' if not block else ''} {service}", as_user=as_user)
        if not block:
            return True
        _, _, code = _execute_command(check_cmd, as_user=as_user)
        if (action == "stop" and code != 0) or (action != "stop" and code == 0):
            _log_event(logger, "+", f"Service {service} {verb_ed}.")
            return True
        _log_event(logger, "!", f"{action.capitalize()} attempt {attempt} failed for {service}. Retrying...")
        time.sleep(1)
    _log_event(logger, "-", f"Failed to {action} {service} after 3 attempts.")
    return False


def _start_service(service_name: str, logger: logging.Logger, block: bool = False, as_user: bool = False) -> bool:
    """Starts or restarts a systemd service."""
    _, _, code = _execute_command(f"systemctl {'--user' if as_user else ''} is-active --quiet {service_name}", as_user=as_user)
    return _manage_service("restart" if code == 0 else "start", service_name, logger, block, as_user)


def _stop_service(service_name: str, logger: logging.Logger, block: bool = False, as_user: bool = False) -> bool:
    """Stops a systemd service."""
    return _manage_service("stop", service_name, logger, block, as_user)


def _find_device_path(paths: List[str]) -> Optional[str]:
    """Finds the first existing directory from a list of paths."""
    for path in paths:
        if os.path.isdir(path):
            return path
    return None


def _validate_device_path(device_path: str) -> bool:
    """Validates if the device path exists."""
    if not device_path or not os.path.isdir(device_path):
        print(f"{cRed}Error: Device path '{device_path}' does not exist.{cReset}")
        return False
    return True


def _resolve_source_file(device_path: str, source_file: Optional[str] = None) -> str:
    """Resolves the brightness source file."""
    if source_file and os.path.isfile(os.path.join(device_path, source_file)):
        return source_file
    elif os.path.isfile(os.path.join(device_path, "actual_brightness")):
        return "actual_brightness"
    else:
        return "brightness"


def _get_max_brightness(device_path: str) -> int:
    """Reads the max_brightness value."""
    try:
        with open(os.path.join(device_path, "max_brightness"), "r") as f:
            return int(f.read().strip())
    except (IOError, ValueError):
        return 0


def _get_current_brightness(device_path: str, source_file: Optional[str] = None) -> int:
    """Reads the current brightness value."""
    resolved_source = _resolve_source_file(device_path, source_file)
    try:
        with open(os.path.join(device_path, resolved_source), "r") as f:
            return int(f.read().strip())
    except (IOError, ValueError):
        return 0


def _calculate_percentage(current: int, max_val: int) -> int:
    """Calculates the percentage of brightness."""
    if max_val == 0:
        return 0
    return int((current * 100) / max_val)


def _commit_brightness(value: int, device_path: str, old_label: str, new_label: str) -> bool:
    """Writes the new brightness value and prints the change."""
    try:
        brightness_file = os.path.join(device_path, "brightness")
        with open(brightness_file, "w") as f:
            f.write(str(value))
        print(f"{cGreen}{old_label} > {new_label}{cReset}")
        return True
    except FileNotFoundError:
        print(f"{cRed}Error: Brightness file not found in {device_path}.{cReset}")
        return False
    except PermissionError:
        print(f"{cRed}Error: Permission denied. Please run with sudo.{cReset}")
        return False
    except IOError as e:
        print(f"{cRed}Error writing to brightness file: {e}{cReset}")
        return False


def _validate_percentage(input_str: str, device_path: str, source_file: Optional[str]) -> int:
    """Validates the input percentage string."""
    clean_input = input_str.replace("%", "")
    if not clean_input.isdigit():
        print(f"{cRed}Error: Invalid brightness value provided.{cReset}")
        current_pct = _show_brightness(device_path, source_file, print_output=False)
        print(f"{cGreen}Current brightness: {current_pct}%{cReset}")
        return -1
    val = int(clean_input)
    if val > 100:
        print(f"{cRed}Error: Percentage cannot be greater than 100.{cReset}")
        return -1
    return val


def _validate_raw_input(input_str: str, max_value: int) -> int:
    """Validates raw integer input."""
    if not input_str.isdigit():
        return -1
    val = int(input_str)
    if val > max_value:
        print(f"{cRed}Error: Maximum brightness is {max_value}.{cReset}")
        return -1
    return val


def _touchbar_calculate_new_level(percentage: int) -> int:
    """Calculates stepped level for touchbar."""
    if percentage == 0:
        return 0
    elif percentage <= 49:
        return 1
    else:
        return 2


def _touchbar_get_label(level: int) -> str:
    """Returns label for touchbar level."""
    if level == 0:
        return "0 (Off)"
    elif level == 1:
        return "1 (Dim)"
    else:
        return "2 (Bright)"


def _show_brightness(device_path: str, brightness_source_file: Optional[str] = None, print_output: bool = True) -> int:
    """Displays current brightness percentage."""
    if not _validate_device_path(device_path):
        exit(e_failure)
    current_raw = _get_current_brightness(device_path, brightness_source_file)
    max_value = _get_max_brightness(device_path)
    pct = _calculate_percentage(current_raw, max_value)
    if print_output:
        print(f"{pct}%")
    return pct


def _apply_brightness_percentage(input_str: str, device_path: str, brightness_source_file: Optional[str] = None) -> None:
    """Applies brightness based on percentage."""
    if not _validate_device_path(device_path):
        exit(e_failure)
    percentage = _validate_percentage(input_str, device_path, brightness_source_file)
    if percentage == -1:
        exit(e_failure)
    max_value = _get_max_brightness(device_path)
    current_raw = _get_current_brightness(device_path, brightness_source_file)
    old_pct = _calculate_percentage(current_raw, max_value)
    new_level = int((max_value * percentage) / 100)
    _commit_brightness(new_level, device_path, f"{old_pct}%", f"{percentage}%")


def _apply_brightness_stepped(input_str: str, device_path: str, brightness_source_file: Optional[str] = None) -> None:
    """Applies stepped brightness for touchbar."""
    if not _validate_device_path(device_path):
        exit(e_failure)
    percentage = _validate_percentage(input_str, device_path, brightness_source_file)
    if percentage == -1:
        exit(e_failure)
    new_level = _touchbar_calculate_new_level(percentage)
    current_raw = _get_current_brightness(device_path, brightness_source_file)
    old_label = _touchbar_get_label(current_raw)
    new_label = _touchbar_get_label(new_level)
    _commit_brightness(new_level, device_path, old_label, new_label)


def _apply_brightness_raw(input_str: str, device_path: str, brightness_source_file: Optional[str] = None) -> None:
    """Applies raw brightness value."""
    if not _validate_device_path(device_path):
        exit(e_failure)
    max_value = _get_max_brightness(device_path)
    val = _validate_raw_input(input_str, max_value)
    if val == -1:
        exit(e_failure)
    current_val = _get_current_brightness(device_path, brightness_source_file)
    _commit_brightness(val, device_path, str(current_val), str(val))
