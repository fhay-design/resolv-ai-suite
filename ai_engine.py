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

def analysiere_bild(image_bytes, prompt_typ="immo_details"):
    """
    Analysiert Bilder strikt faktenbasiert ohne Spekulation.
    """
    if not image_bytes:
        return ""
        
    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        user_prompt = (
            "Analysiere dieses Immobilienfoto. Nenne AUSSCHLIESSLICH Merkmale, "
            "die auf dem Bild zweifelsfrei sichtbar sind (z. B. Fliesenart, Fensterform, Sanitärobjekte, Deckenhöhe). "
            "Erfinde KEINE Räume, Materialien oder Zustände, die verdeckt oder nicht im Bildausschnitt sind. "
            "Gib eine stichpunktartige Liste sichtbarer Fakten zurück."
        )

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
            temperature=0.1,
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"🚨 Bild-Analysefehler: {e}"

def generiere_antwort(prompt, kontext="", history=None, mode="chat"):
    if history is None: history = []
    fallback_chain = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    
    if mode == "email":
        system_prompt = (
            "Du bist ein Immobilien-Assistent auf Enterprise-Niveau. Beantworte Kundenanfragen präzise, "
            "höflich und verbindlich. Nutze keine Markdown-Sternchen (**) oder Rauten (#). "
            "Halte dich strikt an vorhandene Objektfakten."
        )
        temp = 0.2

    elif mode == "extract":
        system_prompt = (
            "Du bist ein Enterprise-Datenextraktor. Extrahiere Objektmerkmale in valides JSON. "
            "Keine Erklärungen, kein Markdown-Wrapper, nur valides JSON."
        )
        temp = 0.0

    elif mode == "expose":
        # DIE ZERO-HALLUCINATION LEITPLANKE:
        system_prompt = (
            "Du bist ein elitärer Immobilien-Copywriter für Luxus- und Anlageobjekte. "
            "Schreibe ein verkaufsstarkes Exposé für ImmobilienScout24 mit den Abschnitten: "
            "🌟 Highlight, 🏡 Beschreibung, 🛋️ Ausstattung, 📍 Lage. "
            "\n"
            "STRIKTE COMPLIANCE-REGELN:\n"
            "1. Nutze AUSSCHLIESSLICH Fakten, die in den übergebenen Eckdaten oder Bild-Details belegt sind.\n"
            "2. Wenn Bodenbeläge, Heizungsarten, Balkone oder Abstellräume NICHT explizit genannt oder im Bild zu sehen sind, darfst du sie UNTER KEINEN UMSTÄNDEN erwähnen oder erraten.\n"
            "3. Gib AUSSCHLIESSLICH das fertige Exposé zurück. Keine Einleitungs- oder Höflichkeitsfloskeln."
        )
        temp = 0.3  # Reduziert von 0.7 auf 0.3 für maximale Faktentreue

    elif mode == "video_script":
        system_prompt = (
            "Du bist ein Social-Media-Producer für Immobilienmakler. Schreibe ein 45-Sekunden-Skript für Instagram Reels. "
            "Gliedere in [Visuell/Kamera] und [Audio/Sprecher]. Starte mit einer messerscharfen Hook. "
            "Erwähne nur belegte Fakten. Gib AUSSCHLIESSLICH das Skript zurück."
        )
        temp = 0.4

    else:
        system_prompt = "Du bist RESOLV.AI Core. Ein hochgradig effizienter, präziser B2B-Berater für Immobilienunternehmen."
        temp = 0.4
        
    if kontext: 
        system_prompt += f"\n\nObjekt- und Firmenwissen:\n{kontext}"

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-5:]: messages.append(msg)
    messages.append({"role": "user", "content": prompt})

    fehler_log = []
    for model in fallback_chain:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=2500
            )
            antwort_text = res.choices[0].message.content
            if mode == "email":
                antwort_text = antwort_text.replace("**", "").replace("*", "").replace("###", "").replace("##", "")
            return antwort_text
        except Exception as e:
            fehler_log.append(f"{model}: {e}")
            continue
            
    return f"🚨 Systemausfall. Log: {fehler_log}"
