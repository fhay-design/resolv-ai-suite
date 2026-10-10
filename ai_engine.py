import os
import base64
from groq import Groq
import chromadb
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("🚨 Warnung: Kein GROQ_API_KEY gefunden!")

client = Groq(api_key=api_key)

def get_tenant_collection(tenant_id):
    db = chromadb.PersistentClient(path="./chroma_db")
    safe_tenant_id = str(tenant_id).replace("-", "")
    return db.get_or_create_collection(name=f"tenant_{safe_tenant_id}")

def analysiere_bild(image_bytes, prompt_typ="detail"):
    """
    Analysiert Immobilien-Fotos mit Hilfe der Groq Vision KI (llama-3.2-90b-vision-preview)
    und extrahiert bauliche und emotionale Details.
    """
    if not image_bytes:
        return ""
        
    try:
        # Bild in das von der API geforderte base64-Format umwandeln
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        if prompt_typ == "immo_details":
            user_prompt = "Welche Ausstattungsmerkmale, Materialien, Zustände (z.B. renoviert/sanierungsbedürftig) und Besonderheiten siehst du auf diesem Foto? Antworte in stichpunktartigen Fakten (Deutsch), die für ein Exposé wertvoll sind."
        else:
            user_prompt = "Beschreibe die Atmosphäre und visuelle Höhepunkte dieses Raumes/Objektes für ein Marketing-Skript oder Social Media (Deutsch)."

        # Wir nutzen das stärkste Vision-Modell von Meta auf Groq
        response = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.2,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"🚨 Bild-Analysefehler: {e}"

def generiere_antwort(prompt, kontext="", history=None, mode="chat"):
    if history is None: history = []
    fallback_chain = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    
    if mode == "email":
        system_prompt = "Du bist ein Top-Immobilienmakler. Antworte auf Kundenanfragen freundlich und verbindlich. Nutze NIEMALS Formatierungen wie Sterne (**) oder Rauten (#)."
        temp = 0.2
    elif mode == "extract":
        system_prompt = "Du bist ein Datenextraktor. Extrahiere Attribute in striktes JSON. Keine Erklärungen davor oder danach."
        temp = 0.0
    elif mode == "expose":
        system_prompt = "Du bist ein elitärer Immobilien-Copywriter. Schreibe ein emotionales Exposé für ImmobilienScout24. Strukturiere in: 🌟 Highlight, 🏡 Beschreibung, 🛋️ Ausstattung, 📍 Lage. WICHTIG: Gib AUSSCHLIESSLICH das fertige Exposé zurück. Schreibe KEINE Einleitung, KEIN Fazit und KEINE Kommentare wie 'Hier ist Ihr Exposé'."
        temp = 0.7
    elif mode == "video_script":
        system_prompt = "Du bist ein Social Media Producer. Schreibe ein virales Skript (max. 45 Sekunden). Unterteile strikt in [Kamera/Visuals] und [Sprecher]. WICHTIG: Gib AUSSCHLIESSLICH das Skript zurück. Keine Begrüßung, keine Verabschiedung, kein erklärender Text."
        temp = 0.7
    else:
        system_prompt = "Du bist die RESOLV.AI Core Intelligence. Ein direkter Business-Berater für Immobilienmakler. Antworte in klarem Deutsch."
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
