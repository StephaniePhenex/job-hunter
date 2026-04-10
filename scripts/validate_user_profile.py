#!/usr/bin/env python3
"""Validate ``user_profile.yaml`` (keyword regexes + optional LLM ``profile``).

Run from repo root::

    python scripts/validate_user_profile.py
    python scripts/validate_user_profile.py /path/to/user_profile.yaml

Exit code 0 if there are no errors; warnings are printed to stderr.
Exit code 1 if any error (fix YAML before restarting uvicorn).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root = parent of scripts/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.utils.user_profile_validate import validate_user_profile_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=_ROOT / "user_profile.yaml",
        help="Path to user_profile.yaml (default: ./user_profile.yaml)",
    )
    args = parser.parse_args()
    path = args.path.resolve()

    errors, warnings = validate_user_profile_yaml(path)

    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"Error: {e}", file=sys.stderr)

    if errors:
        print(f"\nValidation failed: {len(errors)} error(s).", file=sys.stderr)
        return 1

    print(f"OK: {path} — no errors." + (f" ({len(warnings)} warning(s).)" if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
