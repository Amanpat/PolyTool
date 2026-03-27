#!/usr/bin/env python3
"""Pre-commit guard: reject files over 500KB."""
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-kb", type=int, default=500)
    args = parser.parse_args()

    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, check=True
    )
    violations = []
    for path in result.stdout.strip().split("\n"):
        if not path:
            continue
        try:
            import os
            size_kb = os.path.getsize(path) / 1024
            if size_kb > args.max_kb:
                violations.append((path, size_kb))
        except FileNotFoundError:
            continue

    if violations:
        print(f"ERROR: {len(violations)} file(s) exceed {args.max_kb}KB:")
        for path, size in sorted(violations, key=lambda x: -x[1]):
            print(f"  {size:,.0f}KB  {path}")
        return 1
    print(f"OK: all tracked files under {args.max_kb}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
