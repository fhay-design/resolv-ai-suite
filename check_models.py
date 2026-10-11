import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("🚨 Kein API Key gefunden!")
else:
    client = Groq(api_key=api_key)
    print("🟢 Aktuell verfügbare Groq Modelle:")
    try:
        modelle = client.models.list()
        for m in modelle.data:
            print(f"- {m.id}")
    except Exception as e:
        print(f"Fehler beim Abrufen: {e}")
