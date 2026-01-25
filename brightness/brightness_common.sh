#!/usr/bin/env bash
#
#  brightness_common.sh
#  T2_Linux
#
#  Created by turannul on 12/12/2025.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

color_red='\033[0;31m'
color_green='\033[0;32m'
color_yellow='\033[1;33m'
color_reset='\033[0m'

# --- Exit Codes ---
exit_success=0
exit_failure=1
exit_invalid_usage=2

# --- Helper Functions ---

function _find_device_path() {
    local paths=("${@}")
    for path in "${paths[@]}"; do
        if [ -d "$path" ]; then
            printf "%s\n" "$path"
            return 0
        fi
    done
    return 1
}

function _validate_device_path() {
    local device_path="$1"
    if [ ! -d "$device_path" ]; then
        printf "%sError: Device path '%s' does not exist.%s\n" "${color_red}" "$device_path" "${color_reset}" >&2
        return "$exit_failure"
    fi
    return "$exit_success"
}

function _resolve_source_file() {
    local device_path="$1"
    local source_file="$2"
    
    if [ -n "$source_file" ] && [ -f "$device_path/$source_file" ]; then
        printf "%s\n" "$source_file"
    elif [ -f "$device_path/actual_brightness" ]; then
        printf "actual_brightness\n"
    else
        printf "brightness\n"
    fi
}

function _get_max_brightness() {
    local device_path="$1"
    cat "$device_path/max_brightness"
}

function _get_current_brightness() {
    local device_path="$1"
    local source_file="$2"
    local resolved_source
    resolved_source=$(_resolve_source_file "$device_path" "$source_file")
    cat "$device_path/$resolved_source"
}

function _calculate_percentage() {
    local current="$1"
    local max="$2"
    if [ "$max" -eq 0 ]; then printf "0\n"; return; fi
    printf "%s\n" "$((current * 100 / max))"
}

function _commit_brightness() {
    local value="$1"
    local device_path="$2"
    local old_label="$3"
    local new_label="$4"

    printf "%s\n" "$value" | tee "$device_path/brightness" > /dev/null
    printf "%s%s > %s%s\n" "${color_green}" "$old_label" "$new_label" "${color_reset}"
}

function _validate_percentage() {
    local input="$1"
    local device_path="$2"
    local source_file="$3"
    
    if ! [[ "$input" =~ ^[0-9]+$ ]]; then
        printf "%sError: Invalid brightness value provided. Please use a number (e.g., 50 or 50%%).%s\n" "${color_red}" "${color_reset}" >&2
        printf "%sUsage: %s <percentage>%s\n" "${color_yellow}" "$0" "${color_reset}" >&2
        printf "%sCurrent brightness: %s%s\n" "${color_green}" "$(show_brightness "$device_path" "$source_file")" "${color_reset}"
        return "$exit_invalid_usage"
    fi

    if [ "$input" -gt 100 ]; then
        printf "%sError: Percentage cannot be greater than 100.%s\n" "${color_red}" "${color_reset}" >&2
        return "$exit_failure"
    fi
    return "$exit_success"
}

function _validate_raw_input() {
    local input="$1"
    local max_value="$2"

    if ! [[ "$input" =~ ^[0-9]+$ ]]; then
        printf "%sUsage: %s <brightness> [0-%s]%s\n" "${color_yellow}" "$0" "$max_value" "${color_reset}" >&2
        return "$exit_invalid_usage"
    fi

    if [ "$input" -gt "$max_value" ]; then
        printf "%sError: Maximum brightness is %s.%s\n" "${color_red}" "$max_value" "${color_reset}" >&2
        return "$exit_failure"
    fi
    return "$exit_success"
}

function _touchbar_calculate_new_level() {
    local percentage="$1"
    # Touchbar specific logic: 0 -> 0, 1-49 -> 1, 50-100 -> 2
    if [ "$percentage" -eq 0 ]; then
        printf "0\n"
    elif [ "$percentage" -le 49 ]; then
        printf "1\n"
    else
        printf "2\n"
    fi
}

function _touchbar_get_label() {
    local level="$1"
    if [ "$level" -eq 0 ]; then
        printf "0 (Off)\n"
    elif [ "$level" -eq 1 ]; then
        printf "1 (Dim)\n"
    else
        printf "2 (Bright)\n"
    fi
}

# --- Main Functions ---

function show_brightness() {
    local device_path="$1"
    local brightness_source_file="$2"

    _validate_device_path "$device_path" || return "$exit_failure"

    local current_raw
    current_raw=$(_get_current_brightness "$device_path" "$brightness_source_file")
    local max_value
    max_value=$(_get_max_brightness "$device_path")
    local pct
    pct=$(_calculate_percentage "$current_raw" "$max_value")
    
    printf "%s%%\n" "$pct"
}

function apply_brightness_percentage() {
    local input="$1"
    local device_path="$2"
    local brightness_source_file="$3"

    _validate_device_path "$device_path" || return "$exit_failure"

    local new_percentage=${input//%}
    _validate_percentage "$new_percentage" "$device_path" "$brightness_source_file" || return $?

    local max_value
    max_value=$(_get_max_brightness "$device_path")
    local current_raw
    current_raw=$(_get_current_brightness "$device_path" "$brightness_source_file")
    
    local old_pct
    old_pct=$(_calculate_percentage "$current_raw" "$max_value")
    local new_level=$((max_value * new_percentage / 100))

    _commit_brightness "$new_level" "$device_path" "${old_pct}%" "${new_percentage}%"
}

function apply_brightness_stepped() {
    local input="$1"
    local device_path="$2"
    local brightness_source_file="$3"

    _validate_device_path "$device_path" || return "$exit_failure"

    local percentage=${input//%}
    _validate_percentage "$percentage" "$device_path" "$brightness_source_file" || return $?

    local new_level
    new_level=$(_touchbar_calculate_new_level "$percentage")

    local current_raw
    current_raw=$(_get_current_brightness "$device_path" "$brightness_source_file")
    
    local old_label
    old_label=$(_touchbar_get_label "$current_raw")
    local new_label
    new_label=$(_touchbar_get_label "$new_level")

    _commit_brightness "$new_level" "$device_path" "$old_label" "$new_label"
}

function apply_brightness_raw() {
    local input="$1"
    local device_path="$2"
    local brightness_source_file="$3"

    _validate_device_path "$device_path" || return "$exit_failure"

    local max_value
    max_value=$(_get_max_brightness "$device_path")
    
    _validate_raw_input "$input" "$max_value" || return $?

    local current_val
    current_val=$(_get_current_brightness "$device_path" "$brightness_source_file")

    _commit_brightness "$input" "$device_path" "$current_val" "$input"
}