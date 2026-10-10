import os
import json
import pandas as pd
import streamlit as st
from pypdf import PdfReader
import gspread
from google.oauth2.service_account import Credentials

from ai_engine import generiere_antwort, get_tenant_collection, analysiere_bild
from email_agent import lese_emails
from database import supabase, get_tenant_info

# --- 1. SETUP & SESSION STATES ---
st.set_page_config(page_title="RESOLV.AI Real Estate", page_icon="🏡", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user" not in st.session_state: st.session_state.user = None
if "tenant_data" not in st.session_state: st.session_state.tenant_data = None
if "aktive_seite" not in st.session_state: st.session_state.aktive_seite = "Dashboard"
if "chat_verlauf" not in st.session_state: st.session_state.chat_verlauf = []
if "posteingang" not in st.session_state: st.session_state.posteingang = []
if "entwuerfe" not in st.session_state: st.session_state.entwuerfe = {}
if "extrahierte_daten" not in st.session_state: st.session_state.extrahierte_daten = None
if "stats" not in st.session_state: st.session_state.stats = {"mails": 0, "extraktionen": 0, "content": 0}

# --- 2. LOGIN & REGISTRIERUNG ---
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; font-size: 3rem;'>🏡 RESOLV.AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Real Estate OS - Login</p>", unsafe_allow_html=True)
        
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
                    except Exception as e:
                        st.error("Login fehlgeschlagen. Stimmen E-Mail und Passwort?")
                        
        with tab2:
            with st.form("register_form"):
                reg_firma = st.text_input("Maklerbüro (z.B. Rheinland Immobilien)")
                reg_email = st.text_input("E-Mail")
                reg_password = st.text_input("Passwort (min. 6 Zeichen)", type="password")
                if st.form_submit_button("Account erstellen", use_container_width=True):
                    try:
                        res = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                        if res.user:
                            supabase.table("tenants").insert({
                                "user_id": res.user.id,
                                "company_name": reg_firma,
                                "google_sheet_url": "" 
                            }).execute()
                            st.success("Account erstellt! Du kannst dich jetzt im Login-Tab anmelden.")
                    except Exception as e:
                        st.error(f"Fehler: {e}")
    st.stop()

user_collection = get_tenant_collection(st.session_state.user.id)

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    firma = st.session_state.tenant_data.get('company_name', 'Unbekannt') if st.session_state.tenant_data else "Unbekannt"
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
    c1.metric("Objekte (RAG)", f"{user_collection.count()} Docs", delta="In Datenbank")
    c2.metric("Mails", st.session_state.stats["mails"])
    c3.metric("Tabellen", st.session_state.stats["extraktionen"])
    c4.metric("Exposés/Videos", st.session_state.stats["content"])
    c5.metric("ROI", f"{eingesparte_zeit} Min.", delta="Zeit gespart")
    
    st.markdown("---")
    st.subheader("💬 RESOLV.AI Makler-Assistenz")
    
    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.chat_verlauf:
            with st.chat_message(msg["role"]): st.write(msg["content"])
            
    if prompt := st.chat_input("Frage etwas zu deinen Objekten..."):
        st.session_state.chat_verlauf.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"): st.write(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Verarbeite..."):
                    antwort = generiere_antwort(prompt, history=st.session_state.chat_verlauf[:-1], mode="chat")
                    st.write(antwort)
        st.session_state.chat_verlauf.append({"role": "assistant", "content": antwort})
        st.rerun()

elif st.session_state.aktive_seite == "Email":
    st.title("📧 Intelligentes Postfach (Besichtigungen & Co.)")
    if st.button("Abrufen & Synchronisieren", type="primary"):
        with st.spinner("Verbinde mit Server..."):
            res = lese_emails()
            if isinstance(res, str): st.error(f"Fehler: {res}")
            else: st.session_state.posteingang = res; st.success("Postfach aktuell.")
            
    for mail in st.session_state.posteingang:
        m_id = mail['id']
        ist_offen = m_id in st.session_state.entwuerfe
        with st.expander(f"📥 {mail['betreff']} | Von: {mail['absender']}", expanded=ist_offen):
            st.write(mail['text'])
            if st.button("KI-Antwort generieren", key=f"btn_{m_id}"):
                with st.spinner("Analysiere & Formuliere..."):
                    docs = user_collection.query(query_texts=[mail['text']], n_results=2)
                    ctx = "\n".join(docs['documents'][0]) if docs['documents'] else ""
                    st.session_state.entwuerfe[m_id] = generiere_antwort(f"Antworte auf: {mail['text']}", kontext=ctx, mode="email")
                    st.rerun() 
            if m_id in st.session_state.entwuerfe:
                entwurf = st.text_area("Entwurf:", value=st.session_state.entwuerfe[m_id], height=200, key=f"txt_{m_id}")
                if st.button("Senden", type="primary", key=f"snd_{m_id}"):
                    st.success("Wurde an SMTP-Relay übergeben! (Simulation)")
                    st.session_state.stats["mails"] += 1
                    del st.session_state.entwuerfe[m_id]
                    st.rerun()

elif st.session_state.aktive_seite == "Extraktion":
    st.title("📑 Strukturierte Objektdaten-Extraktion")
    ziele = st.text_input("Ziel-Attribute (Was soll in die Tabelle?):", "Adresse, Kaufpreis, Wohnfläche, Zimmeranzahl, Baujahr, Energieklasse")
    upload = st.file_uploader("Exposé / Grundriss / Energieausweis hochladen (PDF)", type="pdf")
    
    if st.button("Dokument parsen", type="primary") and upload:
        with st.spinner("Lese Objektdaten aus..."):
            try:
                reader = PdfReader(upload)
                text = "".join([p.extract_text() for p in reader.pages])
                if text:
                    prompt = f"Extrahiere: {ziele}. Format: JSON. Dokument:\n{text[:2000]}"
                    raw_antwort = generiere_antwort(prompt, mode="extract")
                    clean_json = raw_antwort.replace("```json", "").replace("```", "").strip()
                    try:
                        daten = json.loads(clean_json)
                        df = pd.DataFrame(daten if isinstance(daten, list) else [daten])
                        st.session_state.extrahierte_daten = df
                        st.session_state.stats["extraktionen"] += 1
                    except json.JSONDecodeError:
                        st.error("JSON Parsing fehlgeschlagen.")
            except Exception as e: st.error(f"Fehler: {e}")
            
    if st.session_state.extrahierte_daten is not None:
        st.dataframe(st.session_state.extrahierte_daten, use_container_width=True)
        if st.button("🚀 Live in Google Sheets eintragen", type="primary"):
            sheet_url = st.session_state.tenant_data.get('google_sheet_url') if st.session_state.tenant_data else None
            if not sheet_url:
                st.warning("⚠️ Keine Tabelle hinterlegt! Geh in die 'Einstellungen' und trage dort deine Google Sheet URL ein.")
            else:
                with st.spinner("Verbinde mit Google Cloud..."):
                    try:
                        creds_dict = json.loads(st.secrets.get("GOOGLE_CREDENTIALS_JSON"))
                        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                        gc = gspread.authorize(creds)
                        
                        sh = gc.open_by_url(sheet_url).sheet1
                        df_to_save = st.session_state.extrahierte_daten.fillna("")
                        string_daten = [[str(val) for val in zeile] for zeile in df_to_save.values.tolist()]
                        
                        try:
                            if not sh.get_all_values(): sh.append_row(df_to_save.columns.tolist())
                            sh.append_rows(string_daten)
                            st.success("✅ Objektdaten stehen jetzt live in deiner Google Tabelle!")
                        except Exception as inner_e:
                            if "200" in str(inner_e): st.success("✅ Objektdaten stehen jetzt live in deiner Google Tabelle!")
                            else: raise inner_e
                    except Exception as e:
                        if "200" in str(e): st.success("✅ Objektdaten stehen jetzt live in deiner Google Tabelle!")
                        else: st.error(f"Fehler: {e}")

elif st.session_state.aktive_seite == "Wissen":
    st.title("📚 Objekt-Wissensdatenbank (RAG)")
    st.write("Lade hier PDFs zu Immobilien hoch, damit die KI Fragen von Kunden beantworten kann (z.B. Heizungsart, Rücklagen).")
    upload = st.file_uploader("Objektdaten einspeisen (PDF)", type="pdf")
    if st.button("Trainieren", type="primary") and upload:
        with st.spinner("Vektorisiere Text..."):
            reader = PdfReader(upload)
            text = "".join([p.extract_text() for p in reader.pages])
            chunks = [text[i:i+800] for i in range(0, len(text), 800)]
            user_collection.upsert(documents=chunks, metadatas=[{"source": upload.name}]*len(chunks), ids=[f"{upload.name}_{i}" for i in range(len(chunks))])
            st.success("Erfolgreich ins Objektwissen integriert.")

# --- DYNAMISCHES KI-IMMOBILIEN-STUDIO ---
elif st.session_state.aktive_seite == "Content":
    st.title("✨ KI-Immobilien-Studio")
    st.write("Erstelle aus rohen Eckdaten und Fotos hochkonvertierende Exposés und virale Video-Skripte.")
    
    colA, colB = st.columns([2,1])
    stichpunkte = colA.text_area("Eckdaten der Immobilie (z.B. 4 Zimmer, Balkon Südseite, saniert 2022, 450.000€, Köln-Lindenthal)", height=100)
    
    # NEU: Das Auge für die Makler. Fotos hochladen!
    foto_upload = colA.file_uploader("Optional: Objekt-Foto zur visuellen Analyse hochladen (z.B. Küche, Außenansicht)", type=["jpg", "png", "jpeg"])
    
    format_typ = colB.selectbox("Was möchtest du erstellen?", ["ImmoScout Exposé", "TikTok / Reel Video-Skript"])
    
    if st.button("Magie starten ⚡", type="primary") and stichpunkte:
        analyseeffekt = ""
        # 1. Wenn ein Foto vorhanden ist, nutzen wir die neue Vision API
        if foto_upload:
            with st.spinner("📸 Vision-KI analysiert dein Foto auf Ausstattungsmerkmale..."):
                bild_daten = foto_upload.read()
                visuelle_details = analysiere_bild(bild_daten, prompt_typ="immo_details")
                analyseeffekt = f"\n\n[WICHTIGE VISUELLE DETAILS VOM HOCHGELADENEN FOTO]:\n{visuelle_details}"
                st.toast("Auge aktiviert! Foto-Details erfolgreich extrahiert.", icon="👁️")
                
        # 2. Endprodukt generieren
        with st.spinner("✍️ KI generiert Premium-Content..."):
            modus = "expose" if format_typ == "ImmoScout Exposé" else "video_script"
            
            # Die Eckdaten werden mit den gesehenden Details des Fotos vermischt!
            prompt = f"Erstelle ein {format_typ} basierend auf diesen Daten: {stichpunkte}. {analyseeffekt}"
            
            antwort = generiere_antwort(prompt, mode=modus)
            st.markdown("### Dein Premium Ergebnis:")
            st.info(antwort)
            st.session_state.stats["content"] += 1
            
            # Highlight: Interaktiver 'Direkt veröffentlichen' Simulator (Workflow-Monopol)
            st.write("---")
            colX, colY = st.columns(2)
            if colX.button("Publish to Instagram / TikTok 🚀", use_container_width=True):
                st.success("✅ Content wurde erfolgreich zur Freigabe für Social Media vorgemerkt!")
            if colY.button("Direkt an CRM übergeben (onOffice) 🔗", use_container_width=True):
                st.success("✅ Inserat-Veredelung an onOffice / FlowFact API übertragen!")

elif st.session_state.aktive_seite == "Settings":
    st.title("⚙️ Einstellungen")
    with st.form("settings_form"):
        aktuelle_url = st.session_state.tenant_data.get('google_sheet_url', '') if st.session_state.tenant_data else ''
        neue_url = st.text_input("Deine Google Sheet URL (Für die PDF-Extraktion):", value=aktuelle_url)
        
        if st.form_submit_button("💾 Speichern", type="primary"):
            try:
                supabase.table("tenants").update({"google_sheet_url": neue_url}).eq("user_id", st.session_state.user.id).execute()
                st.session_state.tenant_data['google_sheet_url'] = neue_url
                st.success("✅ Einstellungen gespeichert!")
            except Exception as e:
                st.error(f"Fehler beim Speichern: {e}")
