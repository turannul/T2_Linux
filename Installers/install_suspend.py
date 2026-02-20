#!/usr/bin/env python3
#
#  install_suspend.py
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
from common.core import _check_sudo, _get_actual_user, _get_repo_root, _install_common, _install_file, _install_service, _install_sudo_exception, _uninstall_service, install_bin

script_src = "suspendfix.py"
script_dst = "suspendfix"
service_name = "suspend_fix_T2.service"

service_content = """[Unit]
Description=Reset Apple BCE Module (Fix Wi-Fi/BT/Touchbar on Wake)
Before=sleep.target
StopWhenUnneeded=yes

[Service]
Type=oneshot
RemainAfterExit=yes

ExecStart=/usr/bin/python3 /usr/local/sbin/suspendfix unload
ExecStop=/usr/bin/python3 /usr/local/sbin/suspendfix load

[Install]
WantedBy=sleep.target
"""

exception_file = "/etc/sudoers.d/1-suspendfix"
exception_content = "{user} ALL=NOPASSWD: /usr/local/sbin/suspendfix"


def install() -> None:
    """Installs suspendfix and corresponding systemd service."""
    repo_root = _get_repo_root()
    script_dir = os.path.join(repo_root, "src", "suspend")
    changed = _install_common()
    src: str = os.path.join(script_dir, script_src)
    dst: str = os.path.join(install_bin, script_dst)
    if _install_file(src, dst):
        changed = True
    if _install_service(service_name, service_content, enable_now=False):
        changed = True
    if _install_sudo_exception(exception_file, exception_content.format(user=_get_actual_user())):
        changed = True

    if changed:
        print("Installation complete.")
    else:
        print("Nothing to update.")


def uninstall() -> None:
    """Removes suspendfix and stops/disables systemd service."""
    dst: str = os.path.join(install_bin, script_dst)
    changed = _uninstall_service(service_name)
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
    """Main entry for suspend installer."""
    _check_sudo()

    parser = argparse.ArgumentParser(description="Installer for suspend fix utility.")
    parser.add_argument("action", choices=["install", "uninstall"], help="Action to perform")
    args = parser.parse_args()

    action = args.action
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()


if __name__ == "__main__":
    main()
