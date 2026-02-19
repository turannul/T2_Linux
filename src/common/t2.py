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
import sys
import time
from typing import Dict, Optional, Tuple

sys.dont_write_bytecode = True


def setup_logging(name: str = "T2Linux", level: int = logging.INFO) -> logging.Logger:
    """Sets up and returns a standard logger that logs to stdout."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger


def log_event(logger: logging.Logger, level_char: str, message: str) -> None:
    """Maps level characters to logging levels and logs the message."""
    level_map = {
        "-": logging.ERROR,
        "!": logging.WARNING,
        "*": logging.INFO,
        "+": logging.INFO,
        "#": logging.DEBUG,
        "_": logging.INFO,
    }
    level = level_map.get(level_char, logging.INFO)
    if level_char == "_":
        print(message)
        logger.info(message)
    else:
        logger.log(level, message)


def check_root() -> None:
    """Checks if root and re-executes with sudo if not."""
    if os.geteuid() != 0:
        script_path = os.path.abspath(sys.argv[0])
        if os.access(script_path, os.X_OK):
            cmd = ["sudo", script_path] + sys.argv[1:]
        else:
            cmd = ["sudo", sys.executable, script_path] + sys.argv[1:]
        os.execvp("sudo", cmd)


def get_active_user() -> Tuple[int, str]:
    """Identifies the active user logged into the session."""
    output: str = subprocess.check_output(["loginctl", "list-users", "--no-legend"], text=True).strip()
    parts: list[str] = output.splitlines()[0].split()
    uid: int = int(parts[0])
    user: str = parts[1]
    return uid, user


def get_user_env(uid: int) -> Dict[str, str]:
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


def execute_command(cmd: str, as_user: bool = False, env: Optional[Dict[str, str]] = None) -> Tuple[str, str, int]:
    """ Execute a shell command synchronously using /bin/zsh. """
    target_env: Dict[str, str] = env.copy() if env else os.environ.copy()
    if as_user:
        uid, user = get_active_user()
        user_env = get_user_env(uid)
        target_env.update(user_env)
        cmd = f"sudo -E -u {user} {cmd}"
    try:
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, executable="/bin/zsh", env=target_env, text=True)
        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        return stdout, stderr, proc.returncode
    except Exception as err:
        raise err


def is_module_loaded(module_name: str) -> bool:
    """Checks if a kernel module is loaded using lsmod."""
    name = module_name.replace("-", "_")
    _, _, code = execute_command(f"lsmod | grep -q '^{name} '")
    return code == 0


def _manage_module(action: str, module: str, logger: logging.Logger, delay: float) -> bool:
    """ Internal helper to load or unload a kernel module. """
    is_load = action == "load"
    if is_module_loaded(module) == is_load:
        log_event(logger, "#", f"Module {module} is already {'loaded' if is_load else 'unloaded'}.")
        return True
    log_event(logger, "*", f"{action.capitalize()}ing module {module}...")
    cmd = f"modprobe --verbose {module}" if is_load else f"modprobe --verbose --remove --remove-holders {module}"
    for attempt in range(1, 4):
        _, stderr, code = execute_command(cmd)
        if code == 0 and is_module_loaded(module) == is_load:
            log_event(logger, "*", f"Module {module} {action}ed.")
            time.sleep(delay)
            return True
        log_event(logger, "!", f"Attempt {attempt} failed: {stderr if stderr else 'check failed'}")
        time.sleep(1)
    log_event(logger, "-", f"CRITICAL: Failed to {action} {module}.")
    return False


def load_module(module_name: str, logger: logging.Logger, delay: float = 0.5) -> bool:
    """Loads a kernel module with retries."""
    return _manage_module("load", module_name, logger, delay)


def unload_module(module_name: str, logger: logging.Logger, delay: float = 0.5) -> bool:
    """Unloads a kernel module with retries."""
    return _manage_module("unload", module_name, logger, delay)


def _manage_service(action: str, service: str, logger: logging.Logger, block: bool, as_user: bool) -> bool:
    """ Internal helper to manage a systemd service. """
    user_flag = "--user" if as_user else ""
    check_cmd = f"systemctl {user_flag} is-active --quiet {service}"
    verb_ing = "Stopping" if action == "stop" else f"{action.capitalize()}ing"
    verb_ed = "stopped" if action == "stop" else f"{action}ed"
    log_event(logger, "*", f"{verb_ing} {service}...")
    for attempt in range(1, 4):
        execute_command(f"systemctl {user_flag} {action} {'--no-block' if not block else ''} {service}", as_user=as_user)
        if not block:
            return True
        _, _, code = execute_command(check_cmd, as_user=as_user)
        if (action == "stop" and code != 0) or (action != "stop" and code == 0):
            log_event(logger, "+", f"Service {service} {verb_ed}.")
            return True
        log_event(logger, "!", f"{action.capitalize()} attempt {attempt} failed for {service}. Retrying...")
        time.sleep(1)
    log_event(logger, "-", f"Failed to {action} {service} after 3 attempts.")
    return False


def start_service(service_name: str, logger: logging.Logger, block: bool = False, as_user: bool = False) -> bool:
    """ Starts or restarts a systemd service. """
    _, _, code = execute_command(f"systemctl {'--user' if as_user else ''} is-active --quiet {service_name}", as_user=as_user)
    return _manage_service("restart" if code == 0 else "start", service_name, logger, block, as_user)


def stop_service(service_name: str, logger: logging.Logger, block: bool = False, as_user: bool = False) -> bool:
    """ Stops a systemd service. """
    return _manage_service("stop", service_name, logger, block, as_user)
