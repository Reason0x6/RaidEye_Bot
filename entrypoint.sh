#!/bin/bash
# Entrypoint script to launch a RaidEye bot for each .properties file in bots/
set -e

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
    stdbuf -oL python bot.py "$file" 2>&1 | sed "s/^/[$prefix] /" &
    pids+=("$!")
  fi

done

# Wait for all background bots to finish
for pid in "${pids[@]}"; do
  wait $pid
done
