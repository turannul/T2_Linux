#!/usr/bin/env python3
#
#  install.py [batch install]
#  T2_Linux
#
#  Created by turannul on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import argparse
import os
import subprocess
from common.core import _check_sudo, install_bin, install_cmmn


def run_installers(action: str) -> None:
    """Executes installer scripts with the specified action."""
    installers: list[str] = ["Installers/install_brightness.py", "Installers/install_suspend.py", "Installers/install_wifi.py"]
    for installer in installers:
        if os.path.exists(installer):
            print(f"\n--- Running {installer} {action} ---")
            subprocess.run(["python3", installer, action])
        else:
            print(f"Warning: {installer} not found.")


def main() -> None:
    """Parses command line arguments and initiates installation or uninstallation."""
    _check_sudo()

    parser = argparse.ArgumentParser(description="Batch installer for T2 Linux utilities.")
    parser.add_argument("action", choices=["install", "uninstall", "reinstall"], help="Action to perform")
    args = parser.parse_args()

    action: str = args.action

    if action == "install":
        run_installers("install")
    elif action == "uninstall":
        run_installers("uninstall")
        common_lib = os.path.join(install_cmmn, "t2.py")
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
        else:
            print(f"Common library {common_lib} already removed.")
    elif action == "reinstall":
        print("Starting reinstallation...")
        run_installers("uninstall")
        common_lib = os.path.join(install_cmmn, "t2.py")
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
        run_installers("install")
        print("Reinstallation complete.")


if __name__ == "__main__":
    main()
