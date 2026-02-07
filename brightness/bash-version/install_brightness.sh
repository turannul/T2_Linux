#!/usr/bin/env bash
#
#  install_brightness.sh
#  T2_Linux
#
#  Created by turannul on 12/12/2025.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

if [ "$EUID" -ne 0 ]; then
    exec sudo "$(command -v "$0")" "$@"
fi

scripts=(
    "brightness_common.sh"
    "bdp"
    "bkb"
    "btb"
)

install_dir="/usr/local/bin"
exception_file="/etc/sudoers.d/0-brightness-control"

function install_sudo_exception() {
    [ -f "$exception_file" ] && sudo rm -fv "$exception_file"
    actual_user=${SUDO_USER:-$USER}
    echo "Creating sudoers exception... for user: $actual_user"
    cat <<EOF | tee "$exception_file" > /dev/null
${SUDO_USER:-$USER} ALL=NOPASSWD: $install_dir/bdp
${SUDO_USER:-$USER} ALL=NOPASSWD: $install_dir/btb
${SUDO_USER:-$USER} ALL=NOPASSWD: $install_dir/bkb
${SUDO_USER:-$USER} ALL=NOPASSWD: $install_dir/brightness_common.sh
EOF

    chmod -v 0440 "$exception_file"
    for script in "${scripts[@]}"; do
        sudo -U "$actual_user" -l | grep -q "$install_dir/$script" && echo "Password exception added for $script." || echo "Failed to add password exception for $script"
    done
    echo "Password exception created successfully. || Commands should not require a password now."
}

function uninstall_sudo_exception() {
    if [ -f "$exception_file" ]; then
        rm -fv "$exception_file"
    fi
}

function install() {
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            cp -v "$script" "$install_dir/"
            chmod -v 755 "$install_dir/$script"
            chown -v root:root "$install_dir/$script"
        else
            echo "Warning: $script not found in current directory."
        fi
    done
    install_sudo_exception
    echo "Installed successfully."
}

function uninstall() {
    for script in "${scripts[@]}"; do
        rm -fv "$install_dir/$script"
    done
    uninstall_sudo_exception
    echo "Uninstalled successfully."
}

case "$1" in
    install)    install ;;
    uninstall)  uninstall ;;
    *)
        echo "Usage: $0 {install|uninstall}"
        exit 1
        ;;
esac
