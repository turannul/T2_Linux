#!/usr/bin/env bash

scripts=(
    brightness_common.sh
    bdp
    bkb
    btb
)

function install() {
    for script in "${scripts[@]}"; do
        sudo cp -v "$script" "/usr/local/bin/"
        sudo chmod -v +x "/usr/local/bin/$script"
    done
}

function uninstall() {
    for script in "${scripts[@]}"; do
        sudo rm -fv "/usr/local/bin/$script"
    done
}

case "$1" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    *)
        echo "Usage: $0 install | uninstall"
        exit 1
        ;;
esac