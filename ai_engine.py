import os
from groq import Groq
import chromadb
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("🚨 Warnung: Kein GROQ_API_KEY gefunden!")

client = Groq(api_key=api_key)

# HIER IST DIE MAGIE: Dynamische Ordner pro Kunde
def get_tenant_collection(tenant_id):
    """Erstellt oder lädt einen strikt isolierten Datentresor für den jeweiligen Kunden."""
    db = chromadb.PersistentClient(path="./chroma_db")
    # ChromaDB mag keine Bindestriche im Namen, wir bereinigen die ID kurz
    safe_tenant_id = str(tenant_id).replace("-", "")
    return db.get_or_create_collection(name=f"tenant_{safe_tenant_id}")

def generiere_antwort(prompt, kontext="", history=None, mode="chat"):
    if history is None: history = []
    fallback_chain = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    
    if mode == "email":
        system_prompt = "Du bist ein professioneller Customer Success Manager. Antworte in perfektem Deutsch als fließender Text. Nutze NIEMALS Formatierungen wie Sterne (**) oder Rauten (#)."
        temp = 0.2
    elif mode == "extract":
        system_prompt = "Du bist ein präziser API-Datenextraktor. Gib AUSSCHLIESSLICH reines JSON zurück. Keine Erklärungen, kein Markdown vor oder nach dem JSON."
        temp = 0.0
    elif mode == "content":
        system_prompt = "Du bist ein kreativer Copywriter. Schreibe fesselnd, modern und strukturiert. Nutze Absätze und Emojis gezielt."
        temp = 0.7
    else:
        system_prompt = "Du bist die RESOLV.AI Core Intelligence. Ein hochgradig effizienter, direkter Business-Berater. Antworte in klarem Deutsch."
        temp = 0.5
        
    if kontext: 
        system_prompt += f"\n\nUnternehmenswissen:\n{kontext}"

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-5:]: messages.append(msg)
    messages.append({"role": "user", "content": prompt})

    fehler_log = []
    for model in fallback_chain:
        try:
            res = client.chat.completions.create(model=model, messages=messages, temperature=temp, max_tokens=2500)
            antwort_text = res.choices[0].message.content
            if mode == "email":
                antwort_text = antwort_text.replace("**", "").replace("*", "").replace("###", "").replace("##", "")
            return antwort_text
        except Exception as e:
            fehler_log.append(f"{model}: {e}")
            continue
            
    return f"🚨 Systemausfall. Log: {fehler_log}"
