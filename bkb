#!/bin/bash

brightness_input="$1"
device_path="/sys/class/leds/apple::kbd_backlight"
current_brightness_raw=$(cat "$device_path/brightness")
brightness_path="$device_path/brightness"
max_brightness=$(cat "$device_path/max_brightness")
new_percentage=${brightness_input//%}

if ! [[ "$new_percentage" =~ ^[0-9]+$ ]]; then
    echo "Error: Invalid brightness value provided. Please use a number (e.g., 50 or 50%)." >&2
    echo "Usage: kbd-backlight <percentage>" >&2
    exit 1
fi

current_percentage=$((current_brightness_raw * 100 / max_brightness))

if [ "$new_percentage" -gt 100 ]; then
    echo "Error: Percentage cannot be greater than 100." >&2
    exit 1
fi

new_brightness_level=$((max_brightness * new_percentage / 100))

if [ -e "$brightness_path" ]; then
    echo "$new_brightness_level" >"$brightness_path"
    printf "Brightness changed from %d%% (%d) to %d%% (%d)\n" "$current_percentage" "$current_brightness_raw" "$new_percentage" "$new_brightness_level"
    exit 0
else
    echo "KB backlight device not found at $device_path." >&2
    exit 1
fi
