#!/bin/bash

# Active l'environnement virtuel
source .venv/bin/activate

# Va dans le dossier du projet
cd ~/Ruber

# Lance le bot avec nohup, redirige la sortie vers bot.log et stocke le PID dans bot.pid
nohup python main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "Bot démarré. PID:" $(cat bot.pid)