#!/usr/bin/env python3
#
#  install_brightness.py
#  T2_Linux
#
#  Created by turannul on 12/12/2025.
#  Rewritten in Python on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import os
import shutil
import sys

SCRIPTS = [
    "brightness_common.py",
    "bdp",
    "bkb",
    "btb"
]

INSTALL_DIR = "/usr/local/bin"
EXCEPTION_FILE = "/etc/sudoers.d/0-brightness-control"


def check_sudo():
    if os.geteuid() != 0:
        args = ["sudo", sys.executable] + sys.argv
        os.execvp("sudo", args)


def install_sudo_exception():
    if os.path.exists(EXCEPTION_FILE):
        print(f"Removing old exception file: {EXCEPTION_FILE}")
        os.remove(EXCEPTION_FILE)

    sudo_user = os.environ.get("SUDO_USER")
    actual_user = sudo_user if sudo_user else os.environ.get("USER")

    if not actual_user:
        print("Error: Could not determine user.")
        return

    print(f"Creating sudoers exception... for user: {actual_user}")

    content = ""
    for script in SCRIPTS:
        content += f"{actual_user} ALL=NOPASSWD: {os.path.join(INSTALL_DIR, script)}\n"

    try:
        with open(EXCEPTION_FILE, "w") as f:
            f.write(content)
        os.chmod(EXCEPTION_FILE, 0o440)
        print("Password exception created successfully. || Commands should not require a password now.")
    except Exception as e:
        print(f"Error creating sudoers exception: {e}")


def uninstall_sudo_exception():
    if os.path.exists(EXCEPTION_FILE):
        print(f"Removing exception file: {EXCEPTION_FILE}")
        os.remove(EXCEPTION_FILE)


def install():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    for script in SCRIPTS:
        src = os.path.join(script_dir, script)
        dst = os.path.join(INSTALL_DIR, script)

        if os.path.exists(src):
            print(f"Installing {script} to {dst}...")
            shutil.copy(src, dst)

            # chmod 755
            os.chmod(dst, 0o755)

            # chown root:root
            try:
                os.chown(dst, 0, 0)
            except Exception as e:
                print(f"Warning: Failed to chown {dst}: {e}")

        else:
            print(f"Warning: {script} not found in current directory.")

    install_sudo_exception()
    print("Installed successfully.")


def uninstall():
    for script in SCRIPTS:
        dst = os.path.join(INSTALL_DIR, script)
        if os.path.exists(dst):
            print(f"Removing {dst}...")
            os.remove(dst)

    uninstall_sudo_exception()
    print("Uninstalled successfully.")


def main():
    check_sudo()

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} {{install|uninstall}}")
        sys.exit(1)

    action = sys.argv[1]

    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    else:
        print(f"Usage: {sys.argv[0]} {{install|uninstall}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
