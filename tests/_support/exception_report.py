import re


def normalize_traceback_report(text: str) -> str:
    phase1 = re.sub(
        r'File ".*?", line \d+, in \w+',
        'File "<file>", line <n>, in <func>',
        text,
    )
    phase1_lines = phase1.splitlines()
    kept = [
        line
        for line in phase1_lines
        # Remove python traceback source-underlining lines added by some
        # versions. Example: `    ~~~~~~~~^`
        if not re.fullmatch(r"[ \t]*[~^]+[ \t]*", line)
    ]
    return "\n".join(kept)
