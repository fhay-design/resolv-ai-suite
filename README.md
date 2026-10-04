# LogiBot – mein erster Agent

Ein einfacher Konsolen-Chat-Agent auf Basis des [Anthropic Python SDK](https://docs.claude.com).
LogiBot stellt sich beim Start kurz vor und beantwortet deine Fragen in einer
interaktiven Chat-Schleife.

## Voraussetzungen

- Python 3.11 oder neuer
- Ein Anthropic API-Schlüssel (von <https://console.anthropic.com>)

## Einrichtung

1. **Abhängigkeiten installieren:**

   ```bash
   python3 -m pip install --break-system-packages -r requirements.txt
   ```

2. **API-Schlüssel hinterlegen** – Vorlage kopieren und eintragen:

   ```bash
   cp .env.example .env
   nano .env   # Schlüssel eintragen (ohne Anführungszeichen), speichern
   ```

   Die Datei `.env` wird durch `.gitignore` von Git ausgeschlossen und sollte
   **niemals** committet oder geteilt werden.

## Starten

```bash
./run.sh
```

Das Skript lädt den Schlüssel aus `.env` und startet LogiBot. Zum Beenden
`exit`, `quit` oder `ende` eingeben.

Alternativ ohne Skript:

```bash
ANTHROPIC_API_KEY=dein-schluessel python3 agent.py
```

## Projektstruktur

| Datei              | Zweck                                      |
| ------------------ | ------------------------------------------ |
| `agent.py`         | Der LogiBot-Agent                          |
| `run.sh`           | Startskript (lädt `.env` und startet)      |
| `requirements.txt` | Python-Abhängigkeiten                      |
| `.env.example`     | Vorlage für den API-Schlüssel              |
| `.env`             | Dein echter Schlüssel (nicht im Git)       |
| `.gitignore`       | Schließt Secrets & Python-Artefakte aus    |

## Modell

LogiBot nutzt `claude-opus-4-8` und streamt die Antworten für sofortige Ausgabe.
