#!/usr/bin/env python3
#
#  bdp
#  T2_Linux
#
#  Created by turannul on 07/12/2025.
#  Rewritten in Python on 07/02/2026.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  See the LICENSE file for more details.

import argparse
from common.t2 import _apply_brightness_percentage, _check_root, _find_device_path, _show_brightness, cRed, cReset, e_invalid_usage


def main() -> None:
    """Controls display backlight brightness."""
    _check_root()

    parser = argparse.ArgumentParser(description="Controls display backlight brightness.")
    parser.add_argument("percentage", nargs="?", help="Brightness percentage (0-100)")
    parser.add_argument("-s", "--show", action="store_true", help="Show current brightness")
    args = parser.parse_args()

    device_paths: list[str] = [
        "/sys/class/backlight/intel_backlight",
        "/sys/class/backlight/acpi_video0"
    ]
    device_path = _find_device_path(device_paths)
    if not device_path:
        print(f"{cRed}Error: No supported display backlight found.{cReset}")
        exit(e_invalid_usage)

    if args.show:
        _show_brightness(device_path)
        exit(0)

    if args.percentage:
        _apply_brightness_percentage(args.percentage, device_path)
    else:
        parser.print_usage()
        exit(e_invalid_usage)


if __name__ == "__main__":
    main()
