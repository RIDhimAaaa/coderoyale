#!/bin/sh
# Materialise the submission (passed as an env var so its contents are never
# parsed by a shell) into the tmpfs, then hand over to the interpreter.
# -I = isolated mode: ignore env vars like PYTHONPATH and the user site-dir.
set -e
printf '%s' "$CODEROYALE_SOURCE" > /box/main.py
exec python3 -I -B /box/main.py
