#!/bin/bash

if [ -f bot.pid ]; then
  PID=$(cat bot.pid)
  kill $PID
  rm bot.pid
  echo "Bot arrêté (PID: $PID)."
else
  echo "Le bot ne semble pas être en cours d'exécution (bot.pid introuvable)."
fi