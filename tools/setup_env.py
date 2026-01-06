#!/usr/bin/env python3
"""Interactive .env helper

Usage: run this locally to add required keys (Twilio or others) to your .env
It will preserve existing entries and only add/update the keys you confirm.

Example:
    python tools/setup_env.py

This script runs locally and will not print secrets to remote logs.
"""
from __future__ import annotations
from pathlib import Path
from getpass import getpass

BASE = Path(__file__).resolve().parent.parent
ENVFILE = BASE / ".env"

DEFAULT_KEYS = [
    ("TEST_PHONE", "Optional test phone (digits only, ex: 5516992089829)"),
]


def read_env_map(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def write_env_map(path: Path, mapping: dict):
    # preserve existing non-updated lines: we'll rebuild file with existing comments removed
    lines = []
    for k, v in mapping.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def interactive_update():
    env = read_env_map(ENVFILE)
    print(f".env file: {ENVFILE}\n(press Enter to keep current value; input 'NONE' to clear)")

    for key, prompt in DEFAULT_KEYS:
        cur = env.get(key, "")
        if key.endswith("TOKEN"):
            # secret: ask via getpass
            print(f"{prompt}")
            val = getpass(f"{key} [{('set' if cur else 'not set')}]: ")
        else:
            val = input(f"{prompt} [{cur}]: ")

        if val == "":
            # keep existing
            continue
        if val.upper() == 'NONE':
            if key in env:
                del env[key]
        else:
            env[key] = val

    # write back merged env (keep other existing keys)
    # merge: keep keys not in DEFAULT_KEYS untouched
    existing = read_env_map(ENVFILE)
    existing.update(env)
    write_env_map(ENVFILE, existing)
    print(f"Updated {ENVFILE} (review before committing).")


if __name__ == '__main__':
    interactive_update()
