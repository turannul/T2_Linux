#!/usr/bin/env bash
# shellcheck source="/dev/null" # https://www.shellcheck.net/wiki/SC1091
# shellcheck disable=SC2154     # https://www.shellcheck.net/wiki/SC2154#
#  btb
#  T2_Linux
#
#  Created by turannul on 07/12/2025.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

if [ "$EUID" -ne 0 ]; then
    exec sudo "$(command -v "$0")" "$@"
fi

source "$(dirname "$0")/brightness_common.sh"

device_paths=(
    "/sys/class/backlight/appletb_backlight"
    # Feel free to add more paths here if needed
)

device_path=$(_find_device_path "${device_paths[@]}")

if [ -z "$device_path" ]; then
    printf "%sError: No supported touchbar backlight found.%s\n" "${color_red}" "${color_reset}" >&2
    exit "$exit_failure"
fi

if [ "$1" == "--show" ] || [ "$1" == "-s" ]; then
    show_brightness "$device_path"
    exit $?
fi

apply_brightness_stepped "$1" "$device_path"
exit $?
