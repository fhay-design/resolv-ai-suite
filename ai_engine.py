import os
from groq import Groq
import chromadb
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("🚨 Warnung: Kein GROQ_API_KEY gefunden!")

client = Groq(api_key=api_key)

def get_tenant_collection(tenant_id):
    """Erstellt oder lädt einen strikt isolierten Datentresor für den jeweiligen Kunden."""
    db = chromadb.PersistentClient(path="./chroma_db")
    safe_tenant_id = str(tenant_id).replace("-", "")
    return db.get_or_create_collection(name=f"tenant_{safe_tenant_id}")

def generiere_antwort(prompt, kontext="", history=None, mode="chat"):
    if history is None: history = []
    fallback_chain = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    
    # HIER SIND DIE NEUEN IMMOBILIEN-PROMPTS
    if mode == "email":
        system_prompt = "Du bist ein Top-Immobilienmakler. Antworte auf Kundenanfragen (z.B. Besichtigungstermine) freundlich, verbindlich und höchst professionell. Nutze NIEMALS Formatierungen wie Sterne (**) oder Rauten (#)."
        temp = 0.2
    elif mode == "extract":
        system_prompt = "Du bist ein Datenextraktor für Immobilien-Software. Extrahiere Attribute wie Kaufpreis, Wohnfläche, Zimmeranzahl, Baujahr und Energieklasse in striktes JSON. Keine Erklärungen davor oder danach."
        temp = 0.0
    elif mode == "expose":
        system_prompt = "Du bist ein elitärer Immobilien-Copywriter. Schreibe ein emotionales, verkaufsstarkes Exposé für ImmobilienScout24. Strukturiere in: 🌟 Highlight, 🏡 Beschreibung, 🛋️ Ausstattung, 📍 Lage. Mache dem Leser Lust auf eine Besichtigung."
        temp = 0.7
    elif mode == "video_script":
        system_prompt = "Du bist ein Social Media Producer für Immobilien. Schreibe ein virales Skript für ein Instagram Reel/TikTok (max. 45 Sekunden). Unterteile strikt in [Kamera/Visuals] und [Sprecher]. Starte mit einer starken Hook!"
        temp = 0.7
    else:
        system_prompt = "Du bist die RESOLV.AI Core Intelligence. Ein hochgradig effizienter, direkter Business-Berater für Immobilienmakler. Antworte in klarem Deutsch."
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
