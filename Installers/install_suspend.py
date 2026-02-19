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

import os
import sys

sys.dont_write_bytecode = True

try:
    import base_installer as base
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import base_installer as base

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


def install() -> None:
    """Installs suspendfix and corresponding systemd service."""
    repo_root = base.get_repo_root()
    script_dir = os.path.join(repo_root, "src", "suspend")
    base.install_common()
    src: str = os.path.join(script_dir, script_src)
    dst: str = os.path.join(base.INSTALL_BIN, script_dst)
    if not base.install_file(src, dst):
        return
    base.install_service(service_name, service_content, enable_now=False)
    print("Installation complete.")


def uninstall() -> None:
    """Removes suspendfix and stops/disables systemd service."""
    dst: str = os.path.join(base.INSTALL_BIN, script_dst)
    base.uninstall_service(service_name)
    if os.path.exists(dst):
        print(f"Removing {dst}...")
        os.remove(dst)
    print("Uninstallation complete.")


def main() -> None:
    """Main entry for suspend installer."""
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


if __name__ == "__main__":
    main()
