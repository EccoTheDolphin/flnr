#!/usr/bin/env python3

import sys


def main() -> None:
    sys.stdout.write("stdout output")
    sys.stdout.flush()
    sys.stderr.write("stderr output")


if __name__ == "__main__":
    main()
