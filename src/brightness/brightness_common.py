#!/usr/bin/env python3
#
#  brightness_common.py
#  T2_Linux
#
#  Created by turannul on 12/12/2025.
#  Rewritten in Python on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import os
import sys
from typing import Any, Literal

sys.dont_write_bytecode = True


# --- Colors ---
cRed = '\033[0;31m'
cGreen = '\033[0;32m'
cYellow = '\033[1;33m'
cReset = '\033[0m'

# --- Exit Codes ---
e_success = 0
e_failure = 1
e_invalid_usage = 2


def find_device_path(paths) -> Any | None:
    """Finds the first existing directory from a list of paths."""
    for path in paths:
        if os.path.isdir(path):
            return path
    return None


def validate_device_path(device_path) -> bool:
    """Validates if the device path exists."""
    if not device_path or not os.path.isdir(device_path):
        print(f"{cRed}Error: Device path '{device_path}' does not exist.{cReset}", file=sys.stderr)
        return False
    return True


def resolve_source_file(device_path, source_file=None) -> Any | Literal['actual_brightness'] | Literal['brightness']:
    """Resolves the brightness source file."""
    if source_file and os.path.isfile(os.path.join(device_path, source_file)):
        return source_file
    elif os.path.isfile(os.path.join(device_path, "actual_brightness")):
        return "actual_brightness"
    else:
        return "brightness"


def get_max_brightness(device_path) -> int:
    """Reads the max_brightness value."""
    try:
        with open(os.path.join(device_path, "max_brightness"), "r") as f:
            return int(f.read().strip())
    except (IOError, ValueError):
        return 0


def get_current_brightness(device_path, source_file=None) -> int:
    """Reads the current brightness value."""
    resolved_source = resolve_source_file(device_path, source_file)
    try:
        with open(os.path.join(device_path, resolved_source), "r") as f:
            return int(f.read().strip())
    except (IOError, ValueError):
        return 0


def calculate_percentage(current, max_val) -> int:
    """Calculates the percentage of brightness."""
    if max_val == 0:
        return 0
    return int((current * 100) / max_val)


def commit_brightness(value, device_path, old_label, new_label) -> bool:
    """Writes the new brightness value and prints the change."""
    try:
        # Using tee-like behavior manually, but just writing to file is enough for logic
        # bash: echo val | tee file
        brightness_file = os.path.join(device_path, "brightness")
        with open(brightness_file, "w") as f:
            f.write(str(value))

        print(f"{cGreen}{old_label} > {new_label}{cReset}")
        return True
    except FileNotFoundError:
        print(f"{cRed}Error: Brightness file not found in {device_path}.{cReset}", file=sys.stderr)
        return False
    except PermissionError:
        print(f"{cRed}Error: Permission denied. Please run with sudo.{cReset}", file=sys.stderr)
        return False
    except IOError as e:
        print(f"{cRed}Error writing to brightness file: {e}{cReset}", file=sys.stderr)
        return False


def validate_percentage(input_str, device_path, source_file) -> int:
    """Validates the input percentage string."""
    # Remove % if present
    clean_input = input_str.replace('%', '')

    if not clean_input.isdigit():
        print(f"{cRed}Error: Invalid brightness value provided. Please use a number (e.g., 50 or 50%).{cReset}", file=sys.stderr)
        script_name = os.path.basename(sys.argv[0])
        print(f"{cYellow}Usage: {script_name} <percentage>{cReset}", file=sys.stderr)

        current_pct = show_brightness(device_path, source_file, print_output=False)
        print(f"{cGreen}Current brightness: {current_pct}%{cReset}")
        return -1

    val = int(clean_input)
    if val > 100:
        print(f"{cRed}Error: Percentage cannot be greater than 100.{cReset}", file=sys.stderr)
        return -1

    return val


def validate_raw_input(input_str, max_value) -> int:
    """Validates raw integer input."""
    if not input_str.isdigit():
        script_name = os.path.basename(sys.argv[0])
        print(f"{cYellow}Usage: {script_name} <brightness> [0-{max_value}]{cReset}", file=sys.stderr)
        return -1

    val = int(input_str)
    if val > max_value:
        print(f"{cRed}Error: Maximum brightness is {max_value}.{cReset}", file=sys.stderr)
        return -1

    return val


def touchbar_calculate_new_level(percentage) -> Literal[0] | Literal[1] | Literal[2]:
    """Calculates stepped level for touchbar."""
    if percentage == 0:
        return 0
    elif percentage <= 49:
        return 1
    else:
        return 2


def touchbar_get_label(level) -> Literal['0 (Off)'] | Literal['1 (Dim)'] | Literal['2 (Bright)']:
    """Returns label for touchbar level."""
    if level == 0:
        return "0 (Off)"
    elif level == 1:
        return "1 (Dim)"
    else:
        return "2 (Bright)"


def show_brightness(device_path, brightness_source_file=None, print_output=True) -> int:
    """Displays current brightness percentage."""
    if not validate_device_path(device_path):
        sys.exit(e_failure)

    current_raw = get_current_brightness(device_path, brightness_source_file)
    max_value = get_max_brightness(device_path)
    pct = calculate_percentage(current_raw, max_value)

    if print_output:
        print(f"{pct}%")

    return pct


def apply_brightness_percentage(input_str, device_path, brightness_source_file=None) -> None:
    """Applies brightness based on percentage."""
    if not validate_device_path(device_path):
        sys.exit(e_failure)

    percentage = validate_percentage(input_str, device_path, brightness_source_file)
    if percentage is None:
        if input_str.replace('%', '').isdigit() and int(input_str.replace('%', '')) > 100:
            sys.exit(e_failure)
        sys.exit(e_invalid_usage)

    max_value = get_max_brightness(device_path)
    current_raw = get_current_brightness(device_path, brightness_source_file)
    old_pct = calculate_percentage(current_raw, max_value)

    new_level = int((max_value * percentage) / 100)

    commit_brightness(new_level, device_path, f"{old_pct}%", f"{percentage}%")


def apply_brightness_stepped(input_str, device_path, brightness_source_file=None) -> None:
    """Applies stepped brightness (used for touchbar)."""
    if not validate_device_path(device_path):
        sys.exit(e_failure)

    percentage = validate_percentage(input_str, device_path, brightness_source_file)
    if percentage is None:
        if input_str.replace('%', '').isdigit() and int(input_str.replace('%', '')) > 100:
            sys.exit(e_failure)
        sys.exit(e_invalid_usage)

    new_level = touchbar_calculate_new_level(percentage)
    current_raw = get_current_brightness(device_path, brightness_source_file)
    old_label = touchbar_get_label(current_raw)
    new_label = touchbar_get_label(new_level)
    commit_brightness(new_level, device_path, old_label, new_label)


def apply_brightness_raw(input_str, device_path, brightness_source_file=None) -> None:
    """Applies raw brightness value."""
    if not validate_device_path(device_path):
        sys.exit(e_failure)

    max_value = get_max_brightness(device_path)
    val = validate_raw_input(input_str, max_value)
    if val is None:
        if input_str.isdigit() and int(input_str) > max_value:
            sys.exit(e_failure)
        sys.exit(e_invalid_usage)

    current_val = get_current_brightness(device_path, brightness_source_file)
    commit_brightness(val, device_path, str(current_val), str(val))
