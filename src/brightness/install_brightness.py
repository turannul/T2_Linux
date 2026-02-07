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

import filecmp
import os
import shutil
import sys

scripts: list[str] = [
    "brightness_common.py",
    "bdp",
    "bkb",
    "btb"
]

install_dir = "/usr/local/sbin"
exception_file = "/etc/sudoers.d/0-brightness-control"


def check_sudo() -> None:
    if os.geteuid() != 0:
        args: list[str] = ["sudo", sys.executable] + sys.argv
        os.execvp("sudo", args)


def install_sudo_exception() -> None:
    if os.path.exists(exception_file):
        print(f"Removing old exception file: {exception_file}")
        os.remove(exception_file)

    sudo_user: str | None = os.environ.get("SUDO_USER")
    actual_user: str | None = sudo_user if sudo_user else os.environ.get("USER")

    if not actual_user:
        print("Error: Could not determine user.")
        return

    print(f"Creating sudoers exception... for user: {actual_user}")

    content = ""
    for script in scripts:
        content += f"{actual_user} ALL=NOPASSWD: {os.path.join(install_dir, script)}\n"

    try:
        with open(exception_file, "w") as f:
            f.write(content)
        os.chmod(exception_file, 0o440)
        print("Password exception created successfully. || Commands should not require a password now.")
    except Exception as e:
        print(f"Error creating sudoers exception: {e}")


def uninstall_sudo_exception() -> None:
    if os.path.exists(exception_file):
        print(f"Removing exception file: {exception_file}")
        os.remove(exception_file)


# ... (other imports)

def install_common() -> None:
    common_dst = "/usr/local/sbin/t2.py"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    common_src = os.path.join(repo_root, "src", "common", "t2.py")

    if os.path.exists(common_src):
        if os.path.exists(common_dst) and filecmp.cmp(common_src, common_dst, shallow=False):
            print(f"Common library at {common_dst} is identical. Skipping update.")
            return

        print(f"Installing common library to {common_dst}...")
        shutil.copy(common_src, common_dst)
    else:
        print("Warning: Common library not found in repo.")



def install() -> None:
    # Resolve script_dir to the actual location of this script
    script_dir: str = os.path.dirname(os.path.realpath(__file__))

    install_common()

    for script in scripts:
        src: str = os.path.join(script_dir, script)
        dst: str = os.path.join(install_dir, script)

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
            print(f"Warning: {src} not found.")

    install_sudo_exception()
    print("Installed successfully.")


def uninstall() -> None:
    for script in scripts:
        dst: str = os.path.join(install_dir, script)
        if os.path.exists(dst):
            print(f"Removing {dst}...")
            os.remove(dst)

    uninstall_sudo_exception()
    print("Uninstalled successfully.")


def main() -> None:
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
