#!/bin/bash
# Entrypoint script to launch a RaidEye bot for each .properties file in bots/
set -e

apt update
apt install -y nano

cd /app

if [ ! -d "bots" ]; then
  echo "No bots directory found!"
  exit 1
fi

pids=()

for file in bots/*.properties; do
  if [ -f "$file" ]; then
  echo "Starting bot with config $file"
  prefix=$(basename "$file")
  # Force Python to run unbuffered so prints are emitted immediately
  # and make sure sed is line-buffered as well so the pipeline doesn't
  # introduce additional buffering.
  # Ensure Python runs unbuffered and force the downstream prefixer to be unbuffered
  # Use sed -u for unbuffered line output so async prints from cogs appear promptly.
  PYTHONUNBUFFERED=1 stdbuf -oL python -u bot.py "$file" 2>&1 | sed -u "s/^/[$prefix] /" &
    pids+=("$!")
  fi

done

# Wait for all background bots to finish
for pid in "${pids[@]}"; do
  wait $pid
done
