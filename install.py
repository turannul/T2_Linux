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
import shutil
import subprocess
import sys


def check_sudo() -> None:
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)


def install_common() -> None:
    src = "src/t2.py"
    dst = "/usr/local/sbin/t2.py"
    if os.path.exists(src):
        print(f"Installing common library to {dst}...")
        shutil.copy(src, dst)
        os.chmod(dst, 0o644)
    else:
        print("Error: src/t2.py not found.")
        sys.exit(1)


def run_installers(action) -> None:
    installers: list[str] = [
        "src/brightness/install_brightness.py",
        "src/idle/install_idle.py",
        "src/suspend/install_suspend.py",
        "src/wifi/install_wifi.py"
    ]
    for installer in installers:
        if os.path.exists(installer):
            print(f"\n--- Running {installer} {action} ---")
            subprocess.run([sys.executable, installer, action])
        else:
            print(f"Warning: {installer} not found.")


def main() -> None:
    check_sudo()
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} {{install|uninstall}}")
        sys.exit(1)

    action: str = sys.argv[1]
    if action == "install":
        install_common()
        run_installers("install")
    elif action == "uninstall":
        run_installers("uninstall")
        common_lib = "/usr/local/sbin/t2.py"
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
    elif action == "reinstall":
        run_installers("uninstall")
        common_lib = "/usr/local/sbin/t2.py"
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
        install_common()
        run_installers("install")
    else:
        print(f"Usage: {sys.argv[0]} {{install|uninstall|reinstall}}")


if __name__ == "__main__":
    main()
