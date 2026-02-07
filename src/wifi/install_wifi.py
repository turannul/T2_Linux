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

import filecmp
import os
import shutil
import subprocess
import sys

script_src = "WiFi-Monitor.py"
script_dst = "WiFi-Monitor"
service_name = "WiFi-Monitor.service"
install_bin = "/usr/local/sbin"
install_svc = "/etc/systemd/system"


def check_sudo() -> None:
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)


def install_common() -> None:
    common_dst = "/usr/local/sbin/t2.py"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    common_src = os.path.join(repo_root, "src", "t2.py")

    if os.path.exists(common_src):
        if os.path.exists(common_dst) and filecmp.cmp(common_src, common_dst, shallow=False):
            print(f"Common library at {common_dst} is identical. Skipping update.")
            return

        print(f"Installing common library to {common_dst}...")
        shutil.copy(common_src, common_dst)
    else:
        print("Warning: Common library not found in repo.")


def install() -> None:
    script_dir: str = os.path.dirname(os.path.realpath(__file__))
    install_common()

    src: str = os.path.join(script_dir, script_src)
    dst: str = os.path.join(install_bin, script_dst)
    if os.path.exists(src):
        print(f"Installing {script_src} to {dst}...")
        shutil.copy(src, dst)
        os.chmod(dst, 0o755)
    else:
        print(f"Error: {script_src} not found.")
        return

    svc_src: str = os.path.join(script_dir, service_name)
    svc_dst: str = os.path.join(install_svc, service_name)
    if os.path.exists(svc_src):
        print(f"Installing {service_name} to {svc_dst}...")
        shutil.copy(svc_src, svc_dst)
        print("Reloading systemd...")
        subprocess.run(["systemctl", "daemon-reload"])
        print(f"Enabling and starting {service_name}...")
        subprocess.run(["systemctl", "enable", "--now", service_name])
    else:
        print(f"Warning: {service_name} not found.")

    print("Installation complete.")


def uninstall() -> None:
    dst: str = os.path.join(install_bin, script_dst)
    svc_dst: str = os.path.join(install_svc, service_name)

    if os.path.exists(svc_dst):
        print(f"Disabling and removing {service_name}...")
        subprocess.run(["systemctl", "disable", "--now", service_name])
        os.remove(svc_dst)
        subprocess.run(["systemctl", "daemon-reload"])

    if os.path.exists(dst):
        print(f"Removing {dst}...")
        os.remove(dst)

    print("Uninstallation complete.")


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


if __name__ == "__main__":
    main()
