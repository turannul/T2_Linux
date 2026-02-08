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
    """
    Sets up and returns a standard logger that logs to stdout.
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []

    formatter = logging.Formatter("[%(levelname)s] %(message)s")

    # stdout
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger


def log_event(logger: logging.Logger, level_char: str, message: str) -> None:
    """
    Maps level characters to logging levels and logs the message.
    """
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
    """
    Checks if root and re-executes with sudo if not.
    """
    if os.geteuid() != 0:
        script_path = os.path.abspath(sys.argv[0])
        if os.access(script_path, os.X_OK):
            cmd = ["sudo", script_path] + sys.argv[1:]
        else:
            cmd = ["sudo", sys.executable, script_path] + sys.argv[1:]

        os.execvp("sudo", cmd)


def execute_command(cmd: str, env: Optional[Dict[str, str]] = None) -> Tuple[str, str, int]:
    """
    Execute a shell command synchronously using /bin/zsh.
    Returns (stdout, stderr, exitcode).
    """
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, executable='/bin/zsh', env=env, text=True)
        stdout = res.stdout.strip() if res.stdout else ""
        stderr = res.stderr.strip() if res.stderr else ""
        return stdout, stderr, res.returncode
    except Exception as err:
        # Re-raise explicit errors during execution setup
        raise err


def get_active_user() -> Tuple[str, str]:
    """
    Identifies the active user logged into the session.
    Returns (uid, username)
    """
    output: str = subprocess.check_output(["loginctl", "list-users", "--no-legend"], text=True).strip()
    parts = output.splitlines()[0].split()
    uid: str = parts[0]
    user: str = parts[1]
    _: str = parts[2]  # linger
    _: str = parts[3]  # state, This could be useful later.
    return uid, user


def execute_command_as_user(cmd: str, user: str, uid: str, env: Optional[Dict[str, str]] = None) -> Tuple[str, str, int]:
    """
    Execute a command as a specific user with their DBus/XDG environment.
    """
    if env is None:
        env = os.environ.copy()

    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"

    full_cmd = f"sudo -E -u {user} {cmd}"
    return execute_command(full_cmd, env=env)


def is_module_loaded(module_name: str) -> bool:
    """
    Checks if a kernel module is loaded.
    """
    name = module_name.replace("-", "_")
    try:
        with open("/proc/modules", "r") as f:
            for line in f:
                if line.startswith(f"{name} "):
                    return True
    except Exception:
        stdout, _, _ = execute_command("lsmod")
        return f"\n{name} " in f"\n{stdout}"
    return False


def load_module(module_name: str, logger: logging.Logger, delay: float = 0.5) -> bool:
    """
    Loads a kernel module with retry logic and logging.
    """
    if is_module_loaded(module_name):
        log_event(logger, "#", f"Module {module_name} is already loaded.")
        return True

    log_event(logger, "*", f"Loading module {module_name}...")
    for attempt in range(1, 4):
        _, _, code = execute_command(f"modprobe --verbose {module_name}")
        if code == 0:
            log_event(logger, "*", f"Module {module_name} loaded (Attempt {attempt}).")
            time.sleep(delay)
            return True
        log_event(logger, "!", f"Failed to load {module_name}. Retrying... ({attempt}/3)")
        time.sleep(1)
    log_event(logger, "-", f"CRITICAL: Failed to load module {module_name}.")
    return False


def unload_module(module_name: str, logger: logging.Logger, delay: float = 0.5) -> bool:
    """
    Unloads a kernel module with retry logic and logging.
    """
    if not is_module_loaded(module_name):
        log_event(logger, "#", f"Module {module_name} is not loaded.")
        return True

    log_event(logger, "*", f"Unloading module {module_name}...")
    for attempt in range(1, 4):
        _, stderr, code = execute_command(f"modprobe --verbose --remove --remove-holders {module_name}")

        if code == 0 and not is_module_loaded(module_name):
            log_event(logger, "*", f"Module {module_name} unloaded (Attempt {attempt}).")
            time.sleep(delay)
            return True
        else:
            if stderr:
                log_event(logger, "!", f"Unload attempt {attempt} failed: {stderr}")
        time.sleep(1)
    log_event(logger, "-", f"CRITICAL: Failed to unload module {module_name}.")
    return False


def start_service(service_name: str, logger: logging.Logger, block: bool = False, as_user: bool = False) -> bool:
    """
    Starts or restarts a systemd service with verification and retry logic.
    Handles 'start' vs 'restart' based on current state.
    """
    try:
        cmd_base = ["systemctl"]
        if as_user:
            uid, user = get_active_user()
            cmd_base.append("--user")
            runner = lambda c: execute_command_as_user(c, user, uid)
        else:
            runner = execute_command

        start_args = ["--no-block"] if not block else []
        check_cmd = " ".join(cmd_base + ["is-active", "--quiet", service_name])

        _, _, code = runner(check_cmd)
        is_active = (code == 0)
        action = "restart" if is_active else "start"

        log_event(logger, "*", f"{action.capitalize()}ing {service_name}...")

        for attempt in range(1, 4):
            act_cmd = " ".join(cmd_base + [action] + start_args + [service_name])
            runner(act_cmd)

            if block:
                _, _, code = runner(check_cmd)
                if code == 0:
                    log_event(logger, "+", f"Service {service_name} {action}ed successfully.")
                    return True
                log_event(logger, "!", f"Service {service_name} failed to {action} (Attempt {attempt}). Retrying...")
                time.sleep(1)
            else:
                return True

        log_event(logger, "-", f"Failed to {action} {service_name} after 3 attempts.")
        return False

    except Exception as err:
        log_event(logger, "-", f"Something went wrong while starting {service_name}: {err}")
        return False


def stop_service(service_name: str, logger: logging.Logger, block: bool = False, as_user: bool = False) -> bool:
    """
    Stops a systemd service with verification and retry logic.
    """
    try:
        cmd_base = ["systemctl"]
        if as_user:
            uid, user = get_active_user()
            cmd_base.append("--user")
            runner = lambda c: execute_command_as_user(c, user, uid)
        else:
            runner = execute_command

        stop_args = ["--no-block"] if not block else []

        log_event(logger, "*", f"Stopping {service_name}...")
        for attempt in range(1, 4):
            act_cmd = " ".join(cmd_base + ["stop"] + stop_args + [service_name])
            runner(act_cmd)

            if block:
                check_cmd = " ".join(cmd_base + ["is-active", "--quiet", service_name])
                _, _, code = runner(check_cmd)

                if code != 0:
                    log_event(logger, "+", f"Service {service_name} stopped.")
                    return True
                log_event(logger, "!", f"Service {service_name} still active after stop attempt {attempt}. Retrying...")
                time.sleep(1)
            else:
                return True

        log_event(logger, "-", f"Failed to stop {service_name} after 3 attempts.")
        return False

    except Exception as err:
        log_event(logger, "-", f"Something went wrong while stopping {service_name}: {err}")
        return False
