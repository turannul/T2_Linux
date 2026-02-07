#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys

script_src = "suspendfix"
script_dst = "suspendfix"
service_name = "suspend_fix_T2.service"
install_bin = "/usr/local/sbin"
install_svc = "/etc/systemd/system"


def check_sudo():
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)


def install_common():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    common_src = os.path.join(repo_root, "common", "t2.py")
    common_dir = "/usr/local/lib/t2linux"

    if os.path.exists(common_src):
        print(f"Installing common library to {common_dir}...")
        os.makedirs(common_dir, exist_ok=True)
        shutil.copy(common_src, os.path.join(common_dir, "t2.py"))
    else:
        print("Warning: Common library not found in repo.")


def install():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    install_common()

    src = os.path.join(script_dir, script_src)
    dst = os.path.join(install_bin, script_dst)
    if os.path.exists(src):
        print(f"Installing {script_src} to {dst}...")
        shutil.copy(src, dst)
        os.chmod(dst, 0o755)
    else:
        print(f"Error: {script_src} not found.")
        return

    svc_src = os.path.join(script_dir, service_name)
    svc_dst = os.path.join(install_svc, service_name)
    if os.path.exists(svc_src):
        print(f"Installing {service_name} to {svc_dst}...")
        shutil.copy(svc_src, svc_dst)
        print("Reloading systemd...")
        subprocess.run(["systemctl", "daemon-reload"])
    else:
        print(f"Warning: {service_name} not found.")

    print("Installation complete.")


def uninstall():
    dst = os.path.join(install_bin, script_dst)
    svc_dst = os.path.join(install_svc, service_name)

    if os.path.exists(svc_dst):
        print(f"Disabling and removing {service_name}...")
        subprocess.run(["systemctl", "disable", "--now", service_name])
        os.remove(svc_dst)
        subprocess.run(["systemctl", "daemon-reload"])

    if os.path.exists(dst):
        print(f"Removing {dst}...")
        os.remove(dst)

    print("Uninstallation complete.")


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


if __name__ == "__main__":
    main()
