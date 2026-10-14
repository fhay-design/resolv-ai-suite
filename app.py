import os
import json
import re
import time
import pandas as pd
import streamlit as st
from pypdf import PdfReader

from ai_engine import generiere_antwort, get_tenant_collection, analysiere_bild, transkribiere_audio
from email_agent import sende_email
from database import supabase, get_tenant_info

# --- 1. SETUP & SESSION STATES ---
st.set_page_config(page_title="RESOLV.AI Real Estate", page_icon="🏡", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user" not in st.session_state: st.session_state.user = None
if "tenant_data" not in st.session_state: st.session_state.tenant_data = None
if "aktive_seite" not in st.session_state: st.session_state.aktive_seite = "Dashboard"
if "extrahierte_daten" not in st.session_state: st.session_state.extrahierte_daten = None
if "stats" not in st.session_state: st.session_state.stats = {"mails": 0, "extraktionen": 0, "content": 0}

# --- 2. LOGIN & REGISTRIERUNG ---
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; font-size: 3rem;'>🏡 RESOLV.AI</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Registrieren"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("E-Mail")
                password = st.text_input("Passwort", type="password")
                if st.form_submit_button("Einloggen", use_container_width=True, type="primary"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.user = res.user
                        st.session_state.tenant_data = get_tenant_info(res.user.id)
                        st.session_state.logged_in = True
                        st.rerun()
                    except Exception: 
                        st.error("Login fehlgeschlagen.")
                        
        with tab2:
            with st.form("register_form"):
                reg_firma = st.text_input("Maklerbüro")
                reg_email = st.text_input("E-Mail")
                reg_password = st.text_input("Passwort (min. 6 Zeichen)", type="password")
                if st.form_submit_button("Account erstellen", use_container_width=True):
                    try:
                        res = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                        if res.user:
                            supabase.table("tenants").insert({"user_id": res.user.id, "company_name": reg_firma, "google_sheet_url": "" }).execute()
                            st.success("Account erstellt!")
                    except Exception as e: 
                        st.error(f"Fehler: {e}")
    st.stop()

user_collection = get_tenant_collection(st.session_state.user.id)
firma = st.session_state.tenant_data.get('company_name', 'RESOLV.AI') if st.session_state.tenant_data else "RESOLV.AI"

# --- 3. SIDEBAR ---
with st.sidebar:
    st.markdown(f"## 🏡 RESOLV.AI\n**🏢 {firma}**")
    st.markdown("---")
    nav_btn = lambda icon, text, target: st.button(f"{icon} {text}", use_container_width=True, type="primary" if st.session_state.aktive_seite == target else "secondary")
    
    if nav_btn("📊", "Dashboard", "Dashboard"): st.session_state.aktive_seite = "Dashboard"; st.rerun()
    if nav_btn("📧", "Kunden-Mails", "Email"): st.session_state.aktive_seite = "Email"; st.rerun()
    if nav_btn("📑", "Daten-Extraktion", "Extraktion"): st.session_state.aktive_seite = "Extraktion"; st.rerun()
    if nav_btn("📚", "Objekt-Wissen", "Wissen"): st.session_state.aktive_seite = "Wissen"; st.rerun()
    if nav_btn("✨", "Immo-Studio", "Content"): st.session_state.aktive_seite = "Content"; st.rerun()
    if nav_btn("⚙️", "Einstellungen", "Settings"): st.session_state.aktive_seite = "Settings"; st.rerun()
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# --- 4. SEITEN LOGIK ---

if st.session_state.aktive_seite == "Dashboard":
    st.title("Makler-Dashboard")
    eingesparte_zeit = (st.session_state.stats["mails"] * 5) + (st.session_state.stats["extraktionen"] * 10) + (st.session_state.stats["content"] * 25)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Objekte", f"{user_collection.count()} Docs")
    c2.metric("Mails", st.session_state.stats["mails"])
    c3.metric("Tabellen", st.session_state.stats["extraktionen"])
    c4.metric("Exposés", st.session_state.stats["content"])
    c5.metric("ROI", f"{eingesparte_zeit} Min.")

elif st.session_state.aktive_seite == "Email":
    st.title("📧 Speed-to-Lead Postfach")
    st.write("Die KI qualifiziert im Hintergrund (24/7). Hier siehst du nur die wertvollen Leads, die deine Freigabe brauchen.")
    
    c1, c2 = st.columns([4, 1])
    with c2:
        live_radar = st.toggle("📡 Live-Radar", value=st.session_state.get("live_sync", False))
        st.session_state.live_sync = live_radar

    # Hole alle offenen Leads aus der Datenbank
    res = supabase.table("leads").select("*").eq("status", "offen").order("created_at", desc=True).execute()
    offene_leads = res.data if res.data else []

    if not offene_leads:
        st.info("🎉 Postfach ist leer. Der Worker hat alles im Griff!")
    else:
        for lead in offene_leads:
            kat = lead.get('kategorie', 'Unbekannt')
            badge = "🔥 Top-Käufer" if kat == "A" else "⚠️ Dokumente fehlen"
            
            with st.expander(f"✉️ {lead.get('betreff')} | {badge}", expanded=True):
                st.info(f"**🧠 KI-Analyse:** {lead.get('begruendung', '')}")
                st.write(f"**Von:** {lead.get('absender')}")
                st.write(f"**Nachricht:** {lead.get('nachricht')}")
                
                # Entwurf bearbeiten
                key = f"txt_{lead['id']}"
                if key not in st.session_state:
                    st.session_state[key] = lead.get('ki_entwurf', '')
                
                entwurf = st.text_area("Vorbereitete KI-Antwort:", height=150, key=key)
                
                if st.button("🚀 Senden & im CRM loggen", type="primary", key=f"snd_{lead['id']}"):
                    match = re.search(r'[\w\.-]+@[\w\.-]+', lead.get('absender', ''))
                    if match:
                        ziel_email = match.group(0)
                        aktueller_entwurf = st.session_state[key] # Nimmt sicher den bearbeiteten Text
                        erfolg, fehlermeldung = sende_email(ziel_email, f"Re: {lead.get('betreff')}", aktueller_entwurf, firmenname=firma)
                        
                        if erfolg:
                            st.success("✅ Versendet im HTML-Premium Design!")
                            # Lead in der Datenbank als erledigt markieren
                            supabase.table("leads").update({"status": "beantwortet"}).eq("id", lead['id']).execute()
                            st.session_state.stats["mails"] += 1
                            time.sleep(1) # Kurzer Puffer für die Erfolgsmeldung
                            st.rerun()
                        else:
                            st.error(f"🚨 Fehler beim Senden: {fehlermeldung}")
                    else:
                        st.error("🚨 Keine gültige E-Mail-Adresse im Absender gefunden!")

    if st.session_state.get("live_sync", False):
        time.sleep(10)
        st.rerun()

elif st.session_state.aktive_seite == "Extraktion":
    st.title("📑 Strukturierte Objektdaten-Extraktion")
    ziele = st.text_input("Ziel-Attribute:", "Adresse, Kaufpreis, Wohnfläche, Zimmeranzahl, Baujahr")
    upload = st.file_uploader("PDF hochladen", type="pdf")
    if st.button("Dokument parsen", type="primary") and upload:
        with st.spinner("Lese Objektdaten aus..."):
            try:
                reader = PdfReader(upload)
                text = "".join([p.extract_text() for p in reader.pages])
                raw = generiere_antwort(f"Extrahiere: {ziele}. Format JSON. Doc:\n{text[:2000]}", mode="extract")
                df = pd.DataFrame(json.loads(raw.replace("```json", "").replace("```", "").strip()) if isinstance(json.loads(raw.replace("```json", "").replace("```", "").strip()), list) else [json.loads(raw.replace("```json", "").replace("```", "").strip())])
                st.session_state.extrahierte_daten = df
                st.session_state.stats["extraktionen"] += 1
            except Exception as e: 
                st.error(f"Fehler: {e}")
            
    if st.session_state.extrahierte_daten is not None:
        st.dataframe(st.session_state.extrahierte_daten, use_container_width=True)

elif st.session_state.aktive_seite == "Wissen":
    st.title("📚 Objekt-Wissensdatenbank (RAG)")
    upload = st.file_uploader("Objektdaten einspeisen (PDF)", type="pdf")
    if st.button("Trainieren", type="primary") and upload:
        with st.spinner("Vektorisiere Text..."):
            reader = PdfReader(upload)
            text = "".join([p.extract_text() for p in reader.pages])
            chunks = [text[i:i+800] for i in range(0, len(text), 800)]
            user_collection.upsert(documents=chunks, metadatas=[{"source": upload.name}]*len(chunks), ids=[f"{upload.name}_{i}" for i in range(len(chunks))])
            st.success("Erfolgreich ins Objektwissen integriert.")

elif st.session_state.aktive_seite == "Content":
    st.title("✨ KI-Immobilien-Studio")
    colA, colB = st.columns([2,1])
    
    st.markdown("### 🎙️ Voice Concierge")
    audio_aufnahme = colA.audio_input("Direkt hier reinsprechen")
    audio_upload = colA.file_uploader("Oder WhatsApp-Sprachnachricht hochladen", type=["mp3", "wav", "m4a"])
    stichpunkte = colA.text_area("Schriftliche Eckdaten (optional)", height=80)
    foto_uploads = colA.file_uploader("Fotos hochladen", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    format_typ = colB.selectbox("Format:", ["ImmoScout Exposé", "TikTok / Reel Video-Skript"])
    
    if st.button("Magie starten ⚡", type="primary"):
        daten_basis = stichpunkte
        analyseeffekt = ""
        if audio_aufnahme or audio_upload:
            with st.spinner("Transkribiere..."):
                daten_basis += f"\n[AUDIO]: {transkribiere_audio((audio_aufnahme if audio_aufnahme else audio_upload).read())}"
        if foto_uploads:
            with st.spinner("Analysiere Fotos..."):
                analyseeffekt = "\n[FOTOS]:\n" + "\n".join([analysiere_bild(f.read()) for f in foto_uploads])
                
        if daten_basis or analyseeffekt:
            with st.spinner("Erstelle Content..."):
                st.info(generiere_antwort(f"Daten: {daten_basis} {analyseeffekt}", mode="expose" if format_typ == "ImmoScout Exposé" else "video_script"))
                st.session_state.stats["content"] += 1
        else:
            st.error("Bitte gib Daten ein!")

elif st.session_state.aktive_seite == "Settings":
    st.title("⚙️ Einstellungen")
    with st.form("settings_form"):
        akt = st.session_state.tenant_data.get('google_sheet_url', '') if st.session_state.tenant_data else ''
        neue = st.text_input("Google Sheet URL:", value=akt)
        if st.form_submit_button("💾 Speichern", type="primary"):
            supabase.table("tenants").update({"google_sheet_url": neue}).eq("user_id", st.session_state.user.id).execute()
            st.session_state.tenant_data['google_sheet_url'] = neue
            st.success("Gespeichert!")
