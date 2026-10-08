import os
from dotenv import load_dotenv
from groq import Groq

# Lade den Key aus der .env
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("Lade verfügbare Modelle von Groq...\n")
try:
    models = client.models.list()
    for m in models.data:
        print(f"✅ {m.id}")
except Exception as e:
    print(f"Fehler: {e}")
