#!/usr/bin/env python3
#
#  base_installer.py
#  T2_Linux
#
#  Shared installation helpers for T2 Linux scripts.
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

__all__: list[str] = ["_check_sudo", "_get_repo_root", "_install_common", "_install_file", "_install_service", "_install_sudo_exception", "_uninstall_service", "install_bin", "install_cmmn", "install_svc", "_get_actual_user"]

install_bin = "/usr/local/sbin"
install_svc = "/etc/systemd/system"
install_cmmn = "/usr/local/sbin/common"


def _get_args() -> list[str]:
    """Retrieves command line arguments manually."""
    with open("/proc/self/cmdline", "r") as f:
        cmdline = f.read()
    return [arg for arg in cmdline.split('\0') if arg]


def _check_sudo() -> None:
    """Re-executes the script with sudo if not already running as root."""
    if os.geteuid() != 0:
        args: list[str] = ["sudo", "python3"] + _get_args()
        os.execvp("sudo", args)


def _get_repo_root() -> str:
    """Returns the absolute path to the repository root."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_file(src: str, dst: str, mode: int = 0o755, quiet: bool = False) -> bool:
    """Installs a file if it differs from destination or if destination is a symlink."""
    if not os.path.exists(src):
        print(f"Error: Source file {src} not found.")
        return False

    # Ensure destination directory exists
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        print(f"Creating directory {dst_dir}...")
        os.makedirs(dst_dir, mode=0o755, exist_ok=True)
        os.chown(dst_dir, 0, 0)

    is_symlink = os.path.islink(dst)

    if not is_symlink and os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        if not quiet:
            print(f"File {dst} is identical. Skipping update.")
        return False
    else:
        if is_symlink:
            print(f"Replacing symlink {dst} with physical file...")
            os.remove(dst)
        else:
            print(f"Installing {src} to {dst}...")

        try:
            shutil.copy(src, dst)
            os.chmod(dst, mode)
            os.chown(dst, 0, 0)
            return True
        except Exception as e:
            print(f"Error installing {dst}: {e}")
            return False


def _install_common() -> bool:
    """Installs the common t2.py library."""
    repo_root = _get_repo_root()
    src = os.path.join(repo_root, "src", "common", "t2.py")
    dst = os.path.join(install_cmmn, "t2.py")
    return _install_file(src, dst, mode=0o644, quiet=True)


def _install_service(service_name: str, content: str, enable_now: bool = True, quiet: bool = False) -> bool:
    """Creates and manages systemd service."""
    dst = os.path.join(install_svc, service_name)
    content = content.strip() + "\n"

    if os.path.exists(dst):
        with open(dst, "r") as f:
            if f.read().strip() == content.strip():
                if not quiet:
                    print(f"Service {service_name} is identical. Skipping update.")
                return False

    print(f"Creating {service_name} at {dst}...")
    try:
        with open(dst, "w") as f:
            f.write(content)

        print("Reloading systemd...")
        subprocess.run(["systemctl", "daemon-reload"])

        if enable_now:
            print(f"Enabling and starting {service_name}...")
            subprocess.run(["systemctl", "enable", "--now", service_name])
        else:
            print(f"Enabling {service_name}...")
            subprocess.run(["systemctl", "enable", service_name])

        return True
    except Exception as e:
        print(f"Error: Failed to create {service_name}: {e}")
        return False


def _install_sudo_exception(exception_file: str, content: str) -> bool:
    """Installs a sudoers exception if content differs or file is missing."""
    content = content.strip() + "\n"

    if os.path.exists(exception_file):
        with open(exception_file, "r") as f:
            if f.read().strip() == content.strip():
                print(f"Sudoers exception {exception_file} is identical. Skipping update.")
                return False
        print(f"Updating sudoers exception: {exception_file}")
        os.remove(exception_file)
    else:
        print(f"Creating sudoers exception: {exception_file}")

    try:
        with open(exception_file, "w") as f:
            f.write(content)
        os.chmod(exception_file, 0o440)
        print("Sudoers exception installed successfully.")
        return True
    except Exception as e:
        print(f"Error creating sudoers exception: {e}")
        return False


def _uninstall_service(service_name: str) -> bool:
    """Stops, disables, and removes a systemd service."""
    dst = os.path.join(install_svc, service_name)
    if os.path.exists(dst):
        print(f"Disabling and removing {service_name}...")
        subprocess.run(["systemctl", "disable", "--now", service_name], capture_output=True)
        os.remove(dst)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        return True
    return False


def _get_actual_user() -> str:
    """Identifies the active user logged into the session."""
    sudo_user = os.environ.get("SUDO_USER")
    loginctl_user = subprocess.check_output(["loginctl", "list-users", "--no-legend"], text=True).splitlines()[0].split()[1]
    return sudo_user or loginctl_user
