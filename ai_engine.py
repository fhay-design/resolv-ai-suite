import os
import base64
import json
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

def transkribiere_audio(audio_bytes):
    if not audio_bytes: return ""
    try:
        completion = client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model="whisper-large-v3",
            response_format="text",
            language="de"
        )
        return completion
    except Exception as e:
        return f"🚨 Fehler bei der Audio-Erkennung: {e}"

def analysiere_bild(image_bytes, prompt_typ="immo_details"):
    if not image_bytes: return ""
    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        user_prompt = "Analysiere dieses Immobilienfoto. Nenne AUSSCHLIESSLICH Merkmale, die auf dem Bild zweifelsfrei sichtbar sind. Erfinde KEINE Räume oder Zustände, die verdeckt sind. Gib eine stichpunktartige Liste sichtbarer Fakten zurück."

        # Hinweis: Sollte dieses Vision-Modell später auch 404 werfen, müssen wir es anpassen.
        response = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            temperature=0.1, max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"🚨 Bild-Analysefehler: {e}"

def qualifiziere_lead(email_text):
    """Scannt Mails und kategorisiert sie als A, B oder C-Lead für Makler."""
    if not email_text: return None
    try:
        system_prompt = (
            "Du bist ein analytischer Immobilien-Lead-Filter. Bewerte diese Anfrage strikt:\n"
            "- A-Lead: Finanzierung/Eigenkapital ist geklärt, hohe Bonität (z.B. Ärzte, Beamte, gutverdiener), sehr seriös.\n"
            "- B-Lead: Potenzial vorhanden, aber wichtige Infos (Gehaltsnachweis) fehlen oder Tiere sind dabei.\n"
            "- C-Lead: Unseriös, Spam, 'letzte Preis', extrem kurze Sätze.\n\n"
            "Antworte AUSSCHLIESSLICH in diesem exakten JSON-Format (nichts anderes!):\n"
            "{\"kategorie\": \"A\", \"label\": \"🟢 A-Lead\", \"begruendung\": \"Sehr hohe Bonität durch...\"}"
        )
        # HIER IST DER FIX: Wir nutzen das ausgelesene, verifizierte Qwen-Modell
        res = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": email_text}
            ],
            temperature=0.1, max_tokens=200
        )
        raw = res.choices[0].message.content
        clean_json = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"kategorie": "B", "label": "⚪ Unbekannt", "begruendung": f"Fehler: {e}"}

def generiere_antwort(prompt, kontext="", history=None, mode="chat"):
    if history is None: history = []
    fallback_chain = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    
    if mode == "email":
        system_prompt = "Du bist ein Immobilien-Assistent auf Enterprise-Niveau. Beantworte Kundenanfragen präzise, höflich und verbindlich. Nutze keine Markdown-Sternchen."
        temp = 0.2
    elif mode == "extract":
        system_prompt = "Du bist ein Enterprise-Datenextraktor. Extrahiere Objektmerkmale in valides JSON."
        temp = 0.0
    elif mode == "expose":
        system_prompt = "Du bist ein elitärer Immobilien-Copywriter. Schreibe Exposés. STRIKTE REGEL: Nutze AUSSCHLIESSLICH belegte Fakten. Erfinde nichts."
        temp = 0.3
    elif mode == "video_script":
        system_prompt = "Du bist ein Social-Media-Producer. Schreibe ein 45-Sekunden-Skript. Erwähne nur belegte Fakten."
        temp = 0.4
    else:
        system_prompt = "Du bist RESOLV.AI Core. Ein präziser B2B-Berater."
        temp = 0.4
        
    if kontext: system_prompt += f"\n\nObjekt- und Firmenwissen:\n{kontext}"

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-5:]: messages.append(msg)
    messages.append({"role": "user", "content": prompt})

    for model in fallback_chain:
        try:
            res = client.chat.completions.create(model=model, messages=messages, temperature=temp, max_tokens=2500)
            return res.choices[0].message.content.replace("**", "") if mode == "email" else res.choices[0].message.content
        except Exception:
            continue
    return "🚨 Systemausfall."
