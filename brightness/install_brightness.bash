#!/usr/bin/env bash

scripts=(
    brightness_common.sh
    bdp
    bkb
    btb
)

install_dir="/usr/local/bin"
exception_file="/etc/sudoers.d/00-sudo-rule-brightness-control"

function install_sudo_exception() {
    actual_user=${SUDO_USER:-$USER}
    echo "Creating sudoers exception... for user: $actual_user"
    cat <<EOF | sudo tee "$exception_file" > /dev/null
$actual_user ALL=(ALL) NOPASSWD: $install_dir/bdp
$actual_user ALL=(ALL) NOPASSWD: $install_dir/btb
$actual_user ALL=(ALL) NOPASSWD: $install_dir/bkb
$actual_user ALL=(ALL) NOPASSWD: $install_dir/brightness_common.sh
EOF

    sudo chmod 0440 "$exception_file"
    for script in "${scripts[@]}"; do
        sudo -l | grep -q "$install_dir/$script" && echo "Sudoers exception added for $script." || echo "Failed to add sudoers exception for $script"
    done
    echo "Sudoers exception creation complete. || Commands should not require a password now."
}

function uninstall_sudo_exception() {
    if [ -f "$exception_file" ]; then
        sudo rm -fv "$exception_file"
    fi
}

function install() {
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            sudo cp -v "$script" "$install_dir/"
            sudo chmod -v 755 "$install_dir/$script"
            sudo chown -v root:root "$install_dir/$script"
        else
            echo "Warning: $script not found in current directory."
        fi
    done
    install_sudo_exception
    echo "Installation complete."
}

function uninstall() {
    for script in "${scripts[@]}"; do
        sudo rm -fv "$install_dir/$script"
    done
    uninstall_sudo_exception
    echo "Uninstallation complete."
}

case "$1" in
    install)    install ;;
    uninstall)  uninstall ;;
    *)
        echo "Usage: $0 {install|uninstall}"
        exit 1
        ;;
esac