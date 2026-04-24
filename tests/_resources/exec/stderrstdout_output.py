import sys


def main() -> None:
    sys.stderr.write("stderr output")
    sys.stderr.flush()
    sys.stdout.write("stdout output")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
