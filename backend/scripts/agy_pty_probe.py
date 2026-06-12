"""Probe: can a ConPTY host capture agy --print output? (one-off diagnostic)"""

import re
import sys
import time

from winpty import PtyProcess

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]")


def main() -> int:
    proc = PtyProcess.spawn(
        'agy.exe -p "Reply with exactly: OK"',
        dimensions=(40, 120),
    )
    chunks: list[str] = []
    deadline = time.monotonic() + 120
    while proc.isalive() and time.monotonic() < deadline:
        try:
            chunks.append(proc.read(4096))
        except (EOFError, ConnectionAbortedError):
            break
    raw = "".join(chunks)
    clean = ANSI.sub("", raw).replace("\r", "")
    print("=== RAW (last 800 repr) ===")
    print(repr(raw[-800:]))
    print("=== CLEAN (last 800) ===")
    print(clean[-800:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
