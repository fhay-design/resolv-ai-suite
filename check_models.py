import os
from dotenv import load_dotenv
from groq import Groq

# Lade deinen API Key aus der .env
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("🔍 Frage Groq Server ab...")
try:
    models = client.models.list()
    print("\n✅ Aktuell verfügbare Modelle:")
    for model in models.data:
        print(f" - {model.id}")
except Exception as e:
    print(f"🚨 Fehler bei der Abfrage: {e}")
