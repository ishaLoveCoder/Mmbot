#!/bin/bash

echo "🎬 CineVault Bot Starting..."

while true; do
    echo "▶️  Starting bot.py at $(date)"
    python bot.py
    EXIT_CODE=$?
    echo "⚠️  Bot exited with code $EXIT_CODE at $(date)"
    echo "🔄 Restarting in 5 seconds..."
    sleep 5
done
