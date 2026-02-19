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

import os
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Installers"))

try:
    import base_installer as base
except ImportError:
    print("Error: Could not import base_installer from Installers directory.")
    sys.exit(1)


def run_installers(action: str) -> None:
    """ Executes installer scripts with the specified action. """
    installers: list[str] = ["Installers/install_brightness.py", "Installers/install_suspend.py", "Installers/install_wifi.py"]
    for installer in installers:
        if os.path.exists(installer):
            print(f"\n--- Running {installer} {action} ---")
            subprocess.run([sys.executable, installer, action])
        else:
            print(f"Warning: {installer} not found.")


def main() -> None:
    """Parses command line arguments and initiates installation or uninstallation."""
    base.check_sudo()

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} {{install|uninstall|reinstall}}")
        sys.exit(1)

    action: str = sys.argv[1]

    if action == "install":
        run_installers("install")
    elif action == "uninstall":
        run_installers("uninstall")
        common_lib = os.path.join(base.INSTALL_BIN, "t2.py")
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
    elif action == "reinstall":
        run_installers("uninstall")
        common_lib = os.path.join(base.INSTALL_BIN, "t2.py")
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
        run_installers("install")
    else:
        print(f"Usage: {sys.argv[0]} {{install|uninstall|reinstall}}")


if __name__ == "__main__":
    main()
