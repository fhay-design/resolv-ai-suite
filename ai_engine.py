import os
import json
import base64
import tempfile
import re
from dotenv import load_dotenv
from groq import Groq
import chromadb

# --- 1. ZUGANGSDATEN KUGELSICHER LADEN ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    try:
        import streamlit as st
        GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
    except Exception:
        pass

if not GROQ_API_KEY:
    print("🚨 FEHLER: GROQ_API_KEY fehlt! Bitte in die .env eintragen.")

# Initialisiere Clients
groq_client = Groq(api_key=GROQ_API_KEY)
chroma_client = chromadb.PersistentClient(path="./vector_db")

def get_tenant_collection(user_id):
    return chroma_client.get_or_create_collection(name=f"tenant_{user_id}")


# --- 2. SICHERHEITS-ROUTER & FALLBACKS ---

def parse_json_safely(text):
    """Fängt halluzinierte Markdown-Blöcke ab und extrahiert nur das saubere JSON."""
    try:
        return json.loads(text)
    except:
        # Sucht mit Regex nach allem, was zwischen geschweiften Klammern steht
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
    return {"kategorie": "B", "begruendung": "System-Fallback: KI hat ungültiges Format geliefert."}


def call_llm_with_fallback(messages, mode, response_format=None, temperature=0.1):
    """Der unsichtbare Router: Mit den EXAKTEN Modell-Namen von Groq."""
    
    # Standard-Setup für E-Mails (Große Modelle)
    primary_model = "openai/gpt-oss-120b"
    fallback_model = "qwen/qwen3.8-27b"
    
    # Für schnelle Analyse-Aufgaben
    if mode in ["extract", "qualify"]:
        primary_model = "openai/gpt-oss-20b"
        fallback_model = "qwen/qwen3.8-27b"

    try:
        # Versuch 1: Hauptmodell
        response = groq_client.chat.completions.create(
            model=primary_model,
            messages=messages,
            response_format=response_format,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️ Warnung: Hauptmodell ({primary_model}) blockiert. Wechsle zu Fallback ({fallback_model})...")
        try:
            # Versuch 2: Reserve-Modell
            response = groq_client.chat.completions.create(
                model=fallback_model,
                messages=messages,
                response_format=response_format,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e2:
            print(f"🚨 KRITISCHER FEHLER: Provider-Totalausfall. {e2}")
            raise e2


# --- 3. KERNFUNKTIONEN ---

def qualifiziere_lead(text):
    sys_prompt = (
        "Du bist ein Immobilien-Assistent. Analysiere die E-Mail des Kunden. "
        "Klassifiziere in A (Top-Lead, z.B. Barzahler, Chefarzt, sehr seriös), "
        "B (Normal, braucht Infos) oder C (Spam, Jobcenter, absurd). "
        "Antworte AUSSCHLIESSLICH im JSON-Format: {\"kategorie\": \"A\", \"begruendung\": \"kurzer Text\"}"
    )
    try:
        raw_response = call_llm_with_fallback(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": text}
            ],
            mode="qualify",
            response_format={"type": "json_object"}
        )
        return parse_json_safely(raw_response)
    except Exception as e:
        print("🛡️ Fallback aktiviert: Lead wurde unqualifiziert als B gespeichert.")
        return {"kategorie": "B", "begruendung": "System-Fallback nach KI-Totalausfall."}


def generiere_antwort(prompt, mode="email"):
    fmt = {"type": "json_object"} if mode == "extract" else None
    sys_prompt = "Du bist ein professioneller Immobilien-Assistent für RESOLV.AI."
    if mode == "extract": 
        sys_prompt += " Antworte AUSSCHLIESSLICH im gültigen JSON-Format."
        
    try:
        return call_llm_with_fallback(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            mode=mode,
            response_format=fmt,
            temperature=0.3
        )
    except Exception as e:
        return "Entwurf konnte aufgrund eines temporären Provider-Ausfalls nicht generiert werden. Bitte manuell antworten."


def analysiere_bild(image_bytes):
    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        response = groq_client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Beschreibe dieses Immobilienfoto professionell in 3 Sätzen für ein Exposé."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Bildanalyse fehlgeschlagen: {e}"


def transkribiere_audio(audio_bytes):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
            
        with open(tmp_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(tmp_path, f.read()),
                model="whisper-large-v3-turbo",
                language="de"
            )
            
        os.remove(tmp_path)
        return transcription.text
    except Exception as e:
        return f"Audio-Transkription fehlgeschlagen: {e}"
