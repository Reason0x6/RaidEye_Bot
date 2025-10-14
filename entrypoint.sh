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
    # Export each property as an environment variable
    set -a
    source "$file"
    set +a
    # Run the bot in the background
    python bot.py &
    pids+=("$!")
  fi

done

# Wait for all background bots to finish
for pid in "${pids[@]}"; do
  wait $pid
done
