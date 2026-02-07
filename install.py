#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys

def check_sudo():
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

def install_common():
    src = "src/common/t2.py"
    dst = "/usr/local/sbin/t2.py"
    if os.path.exists(src):
        print(f"Installing common library to {dst}...")
        shutil.copy(src, dst)
        os.chmod(dst, 0o644)
    else:
        print("Error: src/common/t2.py not found.")
        sys.exit(1)

def run_installers(action):
    installers = [
        "src/brightness/install_brightness.py",
        "src/idle/install_idle.py",
        "src/suspend/install_suspend.py",
        "src/wifi/install_wifi.py"
    ]
    for installer in installers:
        if os.path.exists(installer):
            print(f"\n--- Running {installer} {action} ---")
            subprocess.run([sys.executable, installer, action])
        else:
            print(f"Warning: {installer} not found.")

def main():
    check_sudo()
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} {{install|uninstall}}")
        sys.exit(1)
    
    action = sys.argv[1]
    if action == "install":
        install_common()
        run_installers("uninstall")
        run_installers("install")
    elif action == "uninstall":
        run_installers("uninstall")
        # Optional: remove common lib?
        common_lib = "/usr/local/sbin/t2.py"
        if os.path.exists(common_lib):
            print(f"Removing {common_lib}...")
            os.remove(common_lib)
    else:
        print(f"Usage: {sys.argv[0]} {{install|uninstall}}")

if __name__ == "__main__":
    main()
