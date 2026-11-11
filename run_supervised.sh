#!/bin/bash
# Keeps the finder bot running: reinstalls deps if the environment was reset,
# then restarts the bot automatically if it exits for any reason.
#
# Only one supervisor may run at a time (flock) and it kills any stray bot
# before starting a new one, so the Pyrogram sqlite session never ends up
# locked by two processes.
cd /workspace/project/Anime || exit 1

exec 9>".supervisor.lock"
if ! flock -n 9; then
  echo "[supervisor] another instance is already running; exiting" >> bot.log
  exit 0
fi

while true; do
  if ! python3 -c "import dotenv, pyrogram, libtorrent, motor, static_ffmpeg" 2>/dev/null; then
    echo "[supervisor] reinstalling deps $(date)" >> bot.log
    pip install -r requirements.txt -q >> bot.log 2>&1
    pip install libtorrent -q >> bot.log 2>&1
  fi
  pkill -f "python3 -m bot" 2>/dev/null
  sleep 2
  echo "[supervisor] starting bot $(date)" >> bot.log
  python3 -m bot >> bot.log 2>&1
  rc=$?
  echo "[supervisor] bot exited rc=$rc at $(date); restarting in 10s" >> bot.log
  sleep 10
done
