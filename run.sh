#!/usr/bin/env bash
# Lädt den API-Schlüssel aus .env und startet LogiBot.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Fehler: keine .env-Datei gefunden."
  echo "Erstelle sie mit:  cp .env.example .env"
  echo "und trage dann deinen Schluessel ein."
  exit 1
fi

set -a
source .env
set +a

python3 agent.py
