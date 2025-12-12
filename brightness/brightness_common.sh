#!/usr/bin/env bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

find_device_path() {
    local paths=("${@}")
    for path in "${paths[@]}"; do
        if [ -d "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

apply_brightness_percentage() {
    local input="$1"
    local device_path="$2"
    local brightness_source_file="$3"

    if [ -z "$brightness_source_file" ]; then
        brightness_source_file="actual_brightness"
    fi

    if [ ! -d "$device_path" ]; then
        echo -e "${RED}Error: Device path '$device_path' does not exist.${RESET}" >&2
        return 1
    fi

    local current_raw
    current_raw=$(cat "$device_path/$brightness_source_file")
    local max_value
    max_value=$(cat "$device_path/max_brightness")
    local target_path="$device_path/brightness"

    local new_percentage=${input//%}

    if ! [[ "$new_percentage" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Error: Invalid brightness value provided. Please use a number (e.g., 50 or 50%).${RESET}" >&2
        echo -e "${YELLOW}Usage: $0 <percentage>${RESET}" >&2
        return 1
    fi

    if [ "$new_percentage" -gt 100 ]; then
        echo -e "${RED}Error: Percentage cannot be greater than 100.${RESET}" >&2
        return 1
    fi

    local current_percentage=$((current_raw * 100 / max_value))
    local new_level=$((max_value * new_percentage / 100))

    echo "$new_level" | sudo tee "$target_path" > /dev/null
    printf "${GREEN}Brightness changed from %d%% (%d) to %d%% (%d)${RESET}\n" "$current_percentage" "$current_raw" "$new_percentage" "$new_level"
}

apply_brightness_raw() {
    local input="$1"
    local device_path="$2"
    local brightness_source_file="$3"

    if [ -z "$brightness_source_file" ]; then
        brightness_source_file="actual_brightness"
    fi

    if [ ! -d "$device_path" ]; then
        echo -e "${RED}Error: Device path '$device_path' does not exist.${RESET}" >&2
        return 1
    fi

    local current_val
    current_val=$(cat "$device_path/$brightness_source_file")
    local max_value
    max_value=$(cat "$device_path/max_brightness")
    local target_path="$device_path/brightness"

    if ! [[ "$input" =~ ^[0-9]+$ ]]; then
        echo -e "${YELLOW}Usage: $0 <brightness> [0-$max_value]${RESET}" >&2
        return 1
    fi

    if [ "$input" -gt "$max_value" ]; then
        echo -e "${RED}Maximum brightness is $max_value.${RESET}" >&2
        return 1
    fi

    echo "$input" | sudo tee "$target_path" > /dev/null
    printf "${GREEN}Brightness changed from %d to %d${RESET}\n" "$current_val" "$input"
}