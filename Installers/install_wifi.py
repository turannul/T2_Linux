#!/usr/bin/env python3
#
#  install_wifi.py
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

script_src = "WiFi-Monitor.py"
script_dst = "WiFi-Monitor"
service_name = "WiFi-Monitor.service"

service_content = """[Unit]
Description=Broadcom T2 WiFi Guardian (Auto-Recovery)
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /usr/local/sbin/WiFi-Monitor daemon
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

exception_file = "/etc/sudoers.d/2-wifi-monitor"
exception_content = "{user} ALL=NOPASSWD: /usr/local/sbin/WiFi-Monitor"


def install() -> None:
    """Installs WiFi-Monitor and corresponding systemd service."""
    repo_root = _get_repo_root()
    script_dir = os.path.join(repo_root, "src", "wifi")
    changed = _install_common()
    src: str = os.path.join(script_dir, script_src)
    dst: str = os.path.join(install_bin, script_dst)
    if _install_file(src, dst):
        changed = True
    if _install_service(service_name, service_content, enable_now=True):
        changed = True
    if _install_sudo_exception(exception_file, exception_content.format(user=_get_actual_user())):
        changed = True

    if changed:
        print("Installation complete.")
    else:
        print("Nothing to update.")


def uninstall() -> None:
    """Removes WiFi-Monitor and stops/disables systemd service."""
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
    """Main entry for wifi installer."""
    _check_sudo()

    parser = argparse.ArgumentParser(description="Installer for WiFi Guardian utility.")
    parser.add_argument("action", choices=["install", "uninstall"], help="Action to perform")
    args = parser.parse_args()

    action = args.action
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()


if __name__ == "__main__":
    main()
