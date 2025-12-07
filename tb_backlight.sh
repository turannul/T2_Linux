#!/bin/bash

new_brightness_level="$1"
device_path="/sys/class/backlight/appletb_backlight"
current_brightness=$(cat "$device_path/actual_brightness")
brightness_path="$device_path/brightness"
max_brightness=$(cat "$device_path/max_brightness")

# 0: off, 1: low, 2: full
if ! [[ "$new_brightness_level" =~ ^[0-9]+$ ]]; then
    echo "Usage: tb-backlight <brightness> [0-$max_brightness]" >&2
    exit 1
fi

if [ "$new_brightness_level" -gt "$max_brightness" ]; then
    echo "Maximum brightness is $max_brightness." >&2
    exit 1
fi

if [ -e "$brightness_path" ]; then
    echo "$new_brightness_level" >"$brightness_path"
    printf "Brightness changed from %d to %d\n" "$current_brightness" "$new_brightness_level"
    exit 0
else
    echo "Touchbar backlight device not found at $device_path." >&2
    exit 1
fi
