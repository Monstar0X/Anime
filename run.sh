#!/usr/bin/env bash
# Start the Finder / Leecher bot. Safe to run inside a container:
# no sudo, no pip installs, no self-update.
set -euo pipefail

# ffmpeg: prefer a system install, otherwise let static-ffmpeg provide it.
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found; static-ffmpeg will provide it at runtime."
fi

exec python3 -m bot
