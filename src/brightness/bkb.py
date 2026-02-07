#!/usr/bin/env python3
#
#  bkb
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

import brightness_common
import os
import sys

try:
    import t2
except ImportError:
    # Add parent directory to sys.path to find t2 when running from repo
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import t2


def main() -> None:
    t2.check_root()

    device_paths: list[str] = [
        "/sys/class/leds/apple::kbd_backlight"
    ]

    device_path = brightness_common.find_device_path(device_paths)

    if not device_path:
        print(f"{brightness_common.cRed}Error: No supported keyboard backlight found.{brightness_common.cReset}", file=sys.stderr)
        sys.exit(brightness_common.e_invalid_usage)

    if len(sys.argv) < 2:
        print(f"{brightness_common.cYellow}Usage: {os.path.basename(sys.argv[0])} <percentage> | --show | -s{brightness_common.cReset}", file=sys.stderr)
        sys.exit(brightness_common.e_invalid_usage)

    arg = sys.argv[1]

    if arg == "--show" or arg == "-s":
        brightness_common.show_brightness(device_path)
        sys.exit(0)

    brightness_common.apply_brightness_percentage(arg, device_path)


if __name__ == "__main__":
    main()
