#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys


def decode_ros_unicode(text):
    return re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        text,
    )


def main():
    sys.stdout.write(decode_ros_unicode(sys.stdin.read()))


if __name__ == "__main__":
    main()
