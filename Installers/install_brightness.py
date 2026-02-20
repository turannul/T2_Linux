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

import argparse
import os
from common.core import _check_sudo, _get_actual_user, _get_repo_root, _install_common, _install_file, _install_sudo_exception, install_bin, install_cmmn

scripts: list[str] = ["bdp.py", "bkb.py", "btb.py", "__init__.py"]
exception_file = "/etc/sudoers.d/0-brightness-control"
exception_content = "{user} ALL=NOPASSWD: /usr/local/sbin/bdp, /usr/local/sbin/bkb, /usr/local/sbin/btb"


def install() -> None:
    """Installs brightness tools and common library."""
    repo_root = _get_repo_root()
    script_dir = os.path.join(repo_root, "src", "brightness")
    common_src_dir = os.path.join(repo_root, "src", "common")

    changed = _install_common()

    for script in scripts:
        if script == "__init__.py":
            src = os.path.join(common_src_dir, script)
            dst = os.path.join(install_cmmn, script)
        else:
            src = os.path.join(script_dir, script)
            dst_name = script.replace(".py", "")
            dst = os.path.join(install_bin, dst_name)

        if _install_file(src, dst):
            changed = True

    if _install_sudo_exception(exception_file, exception_content.format(user=_get_actual_user())):
        changed = True

    if changed:
        print("Installation complete.")
    else:
        print("Nothing to update.")


def uninstall() -> None:
    """Removes installed brightness tools and sudoers exception."""
    changed = False
    for script in scripts:
        if script == "__init__.py":
            dst = os.path.join(install_cmmn, script)
        else:
            dst_name = script.replace(".py", "")
            dst = os.path.join(install_bin, dst_name)

        if os.path.exists(dst):
            print(f"Removing {dst}...")
            os.remove(dst)
            changed = True

    if os.path.exists(exception_file):
        print(f"Removing exception file: {exception_file}")
        os.remove(exception_file)
        changed = True

    if changed:
        print("Uninstallation complete.")
    else:
        print("Nothing to uninstall.")


def main() -> None:
    """Main entry point for brightness installer."""
    _check_sudo()

    parser = argparse.ArgumentParser(description="Installer for brightness control tools.")
    parser.add_argument("action", choices=["install", "uninstall"], help="Action to perform")
    args = parser.parse_args()

    action = args.action
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()


if __name__ == "__main__":
    main()
