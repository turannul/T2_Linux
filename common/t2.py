#!/usr/bin/env python3
import datetime
import logging
import os
import subprocess
import sys
from typing import List, Optional, Union


def setup_logging(log_file: str, name: str = "T2Linux", level: int = logging.INFO):
    """
    Sets up and returns a standard logger that logs to both stdout and a file.
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            pass

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # stdout
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # file
    try:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except OSError:
        pass

    return logger


def log_event(logger: logging.Logger, level_char: str, message: str):
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


def check_root():
    """
    Checks if root and re-executes with sudo if not.
    """
    if os.geteuid() != 0:
        # If the script is executable and has a shebang, we can run it directly with sudo
        # to match NOPASSWD entries in sudoers.
        script_path = os.path.abspath(sys.argv[0])
        if os.access(script_path, os.X_OK):
            cmd = ["sudo", script_path] + sys.argv[1:]
        else:
            cmd = ["sudo", sys.executable, script_path] + sys.argv[1:]

        os.execvp("sudo", cmd)


def run_command(cmd: Union[str, List[str]], shell: bool = False, check: bool = False):
    """
    Wrapper for subprocess.run.
    """
    try:
        if shell and isinstance(cmd, list):
            cmd = " ".join(cmd)
        return subprocess.run(cmd, shell=shell, check=check, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if check:
            raise e
        return subprocess.CompletedProcess(cmd, e.returncode, stdout="", stderr=str(e))


def setup_xdg_env(logger: Optional[logging.Logger] = None):
    """
    Sets up XDG_RUNTIME_DIR and WAYLAND_DISPLAY for root to interact with user session.
    """
    try:
        if os.environ.get("XDG_RUNTIME_DIR") and os.environ.get("WAYLAND_DISPLAY"):
            return

        uid = 1000
        runtime_dir = f"/run/user/{uid}"

        if os.path.exists(runtime_dir):
            if "XDG_RUNTIME_DIR" not in os.environ:
                os.environ["XDG_RUNTIME_DIR"] = runtime_dir
                if logger:
                    logger.info(f"Set XDG_RUNTIME_DIR={runtime_dir}")

            if "WAYLAND_DISPLAY" not in os.environ:
                for item in os.listdir(runtime_dir):
                    if item.startswith("wayland-") and not item.endswith(".lock"):
                        os.environ["WAYLAND_DISPLAY"] = item
                        if logger:
                            logger.info(f"Set WAYLAND_DISPLAY={item}")
                        break
    except Exception as e:
        if logger:
            logger.error(f"Failed to setup environment: {e}")
