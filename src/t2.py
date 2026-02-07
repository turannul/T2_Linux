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
from typing import List, Union


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


def run_command(cmd: Union[str, List[str]], shell: bool = False, check: bool = False) -> subprocess.CompletedProcess[str]:
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
