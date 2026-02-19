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
import sys

sys.dont_write_bytecode = True

try:
    import base_installer as base
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import base_installer as base

scripts: list[str] = ["brightness_common.py", "bdp.py", "bkb.py", "btb.py"]

exception_file = "/etc/sudoers.d/0-brightness-control"


def install_sudo_exception() -> None:
    """ Manages sudoers NOPASSWD exception for brightness control. """
    actual_user = base.get_actual_user()
    if not actual_user:
        print("Error: Could not determine user.")
        return

    content = ""
    for script in scripts:
        if script == "brightness_common.py":
            continue
        cmd_name = script.replace(".py", "")
        content += f"{actual_user} ALL=NOPASSWD: {os.path.join(base.INSTALL_BIN, cmd_name)}\n"

    base.install_sudo_exception(exception_file, content)


def install() -> None:
    """ Installs brightness tools and common library. """
    repo_root = base.get_repo_root()
    script_dir = os.path.join(repo_root, "src", "brightness")
    common_src_dir = os.path.join(repo_root, "src", "common")

    base.install_common()

    for script in scripts:
        if script == "brightness_common.py":
            src = os.path.join(common_src_dir, script)
            dst = os.path.join(base.INSTALL_COMMON, script)
        else:
            src = os.path.join(script_dir, script)
            dst_name = script.replace(".py", "")
            dst = os.path.join(base.INSTALL_BIN, dst_name)
        
        base.install_file(src, dst)

    install_sudo_exception()
    print("Installation complete.")


def uninstall() -> None:
    """ Removes installed brightness tools and sudoers exception. """
    for script in scripts:
        if script == "brightness_common.py":
            dst = os.path.join(base.INSTALL_COMMON, script)
        else:
            dst_name = script.replace(".py", "")
            dst = os.path.join(base.INSTALL_BIN, dst_name)
        
        if os.path.exists(dst):
            print(f"Removing {dst}...")
            os.remove(dst)

    if os.path.exists(exception_file):
        print(f"Removing exception file: {exception_file}")
        os.remove(exception_file)
    print("Uninstallation complete.")


def main() -> None:
    """Main entry for brightness installer."""
    base.check_sudo()
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
