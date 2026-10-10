import os
import time
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
import chromadb
from pypdf import PdfReader
import imaplib
import email
from email.header import decode_header
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SETUP ---
st.set_page_config(page_title="RESOLV.AI Enterprise", page_icon="⚡", layout="wide")

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
email_adresse = os.getenv("EMAIL_ADRESSE")
email_passwort = os.getenv("EMAIL_PASSWORT")
imap_server = os.getenv("IMAP_SERVER")
smtp_server = os.getenv("SMTP_SERVER")
smtp_port = int(os.getenv("SMTP_PORT", 587))
app_password = os.getenv("APP_PASSWORD")

# Google Credentials laden (Aus Secrets)
try:
    google_json_str = st.secrets.get("GOOGLE_CREDENTIALS_JSON")
except:
    google_json_str = None

if not api_key or not app_password:
    st.error("🚨 Kritischer Fehler: .env Datei (oder Secrets) nicht vollständig!")
    st.stop()

# --- SESSION STATES ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "aktive_seite" not in st.session_state: st.session_state.aktive_seite = "Dashboard"
if "chat_verlauf" not in st.session_state: st.session_state.chat_verlauf = []
if "posteingang" not in st.session_state: st.session_state.posteingang = []
if "entwuerfe" not in st.session_state: st.session_state.entwuerfe = {}
if "extrahierte_daten" not in st.session_state: st.session_state.extrahierte_daten = None
if "stats" not in st.session_state: st.session_state.stats = {"mails": 0, "extraktionen": 0, "content": 0}

# --- 2. LOGIN SCREEN (Neu mit Enter-Support) ---
if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; font-size: 3rem;'>⚡ RESOLV.AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray; margin-bottom: 30px;'>Secure Enterprise Workspace</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            passwort_eingabe = st.text_input("Authentifizierung", type="password", placeholder="Master-Key eingeben...", label_visibility="collapsed")
            submitted = st.form_submit_button("System starten", use_container_width=True, type="primary")
            
            if submitted:
                if passwort_eingabe == app_password:
                    st.session_state.logged_in = True
                    st.rerun()
                else: 
                    st.error("Zugriff verweigert.")
    st.stop()

# --- 3. CORE ENGINE ---
client = Groq(api_key=api_key)

@st.cache_resource
def init_db():
    db = chromadb.PersistentClient(path="./chroma_db")
    return db.get_or_create_collection(name="firmenwissen")
collection = init_db()

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
        
    if kontext: system_prompt += f"\n\nUnternehmenswissen:\n{kontext}"

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

# --- E-Mail Funktionen ---
def lese_emails():
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_adresse, email_passwort)
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")
        if not messages[0]: return []
        email_ids = messages[0].split()[-3:]
        gefundene_emails = []
        for e_id in reversed(email_ids):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes): subject = subject.decode(encoding or "utf-8", errors="ignore")
                    sender = msg.get("From")
                    body = ""
                    if msg.is_multipart():
                        for p in msg.walk():
                            if p.get_content_type() == "text/plain":
                                body = p.get_payload(decode=True).decode("utf-8", errors="ignore"); break
                    else: body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                    gefundene_emails.append({"id": e_id.decode(), "absender": sender, "betreff": subject, "text": body[:1500]})
        mail.logout()
        return gefundene_emails
    except Exception as e: return str(e)


# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("## ⚡ RESOLV.AI")
    st.markdown("---")
    
    nav_btn = lambda icon, text, target: st.button(f"{icon} {text}", use_container_width=True, type="primary" if st.session_state.aktive_seite == target else "secondary")
    
    if nav_btn("📊", "Dashboard", "Dashboard"): st.session_state.aktive_seite = "Dashboard"; st.rerun()
    if nav_btn("📧", "E-Mail Agent", "Email"): st.session_state.aktive_seite = "Email"; st.rerun()
    if nav_btn("📑", "Extraktion", "Extraktion"): st.session_state.aktive_seite = "Extraktion"; st.rerun()
    if nav_btn("📚", "Firmenwissen", "Wissen"): st.session_state.aktive_seite = "Wissen"; st.rerun()
    if nav_btn("✍️", "Content Creation", "Content"): st.session_state.aktive_seite = "Content"; st.rerun()
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.caption("System Status: 🟢 Online\n\nModelle: GPT-OSS / Qwen")


# --- 5. SEITEN LOGIK ---

if st.session_state.aktive_seite == "Dashboard":
    st.title("Unternehmens-Übersicht")
    eingesparte_zeit = (st.session_state.stats["mails"] * 5) + (st.session_state.stats["extraktionen"] * 10) + (st.session_state.stats["content"] * 15)
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Wissen", f"{collection.count()} Docs", delta="In Datenbank")
    c2.metric("Mails", st.session_state.stats["mails"], delta=f"+{st.session_state.stats['mails']}" if st.session_state.stats['mails']>0 else "")
    c3.metric("Tabellen", st.session_state.stats["extraktionen"], delta=f"+{st.session_state.stats['extraktionen']}" if st.session_state.stats['extraktionen']>0 else "")
    c4.metric("Content", st.session_state.stats["content"], delta=f"+{st.session_state.stats['content']}" if st.session_state.stats['content']>0 else "")
    c5.metric("ROI", f"{eingesparte_zeit} Min.", delta="Gespart" if eingesparte_zeit > 0 else "")
    
    st.markdown("---")
    st.subheader("💬 RESOLV.AI Core Chat")
    
    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.chat_verlauf:
            with st.chat_message(msg["role"]): st.write(msg["content"])
            
    if prompt := st.chat_input("Frage das System..."):
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
    st.title("📧 Intelligentes Postfach")
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
                    docs = collection.query(query_texts=[mail['text']], n_results=2)
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
    st.title("📑 Strukturierte Datenextraktion")
    st.write("Wandelt unstrukturierte PDF-Dokumente (z.B. Materialrechnungen, Lieferscheine) in saubere Datenbank-Tabellen um.")
    
    ziele = st.text_input("Ziel-Attribute (z.B. Firma, Rechnungsnummer, Datum, Netto):", "Firma, Rechnungsnummer, Gesamtbetrag")
    upload = st.file_uploader("Dokument hochladen", type="pdf")
    
    if st.button("Dokument parsen", type="primary") and upload:
        with st.spinner("Lese aus..."):
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
        
        col_csv, col_sheet = st.columns(2)
        csv = st.session_state.extrahierte_daten.to_csv(index=False).encode('utf-8')
        col_csv.download_button("💾 Als CSV exportieren", csv, "extrakt.csv", "text/csv")
        
        if col_sheet.button("🚀 Live in Google Sheets eintragen", type="primary"):
            if not google_json_str:
                st.error("🚨 Der Google API Schlüssel in den Secrets fehlt oder ist fehlerhaft.")
            else:
                with st.spinner("Verbinde mit Google Cloud..."):
                    try:
                        creds_dict = json.loads(google_json_str)
                        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                        gc = gspread.authorize(creds)
                        
                        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1PmPtL_ymo-5I1bikslJHlJj34TFiCYVzBUEUCWgh-GE/edit?gid=0#gid=0").sheet1
                        
                        df_to_save = st.session_state.extrahierte_daten.fillna("")
                        string_daten = [[str(val) for val in zeile] for zeile in df_to_save.values.tolist()]
                        
                        try:
                            if not sh.get_all_values():
                                sh.append_row(df_to_save.columns.tolist())
                            
                            sh.append_rows(string_daten)
                            st.success("✅ Magie erfolgreich: Daten stehen jetzt live in deiner Google Tabelle!")
                        except Exception as inner_e:
                            if "200" in str(inner_e):
                                st.success("✅ Magie erfolgreich: Daten stehen jetzt live in deiner Google Tabelle!")
                            else:
                                raise inner_e
                    except Exception as e:
                        if "200" in str(e):
                            st.success("✅ Magie erfolgreich: Daten stehen jetzt live in deiner Google Tabelle!")
                        else:
                            st.error(f"Verbindungsfehler zur Tabelle: {e}")

elif st.session_state.aktive_seite == "Wissen":
    st.title("📚 RAG Wissensdatenbank")
    st.info(f"Aktuelle Vektoren in Datenbank: {collection.count()}")
    upload = st.file_uploader("Unternehmensdaten einspeisen (PDF)", type="pdf")
    if st.button("Trainieren", type="primary") and upload:
        with st.spinner("Vektorisiere Text..."):
            reader = PdfReader(upload)
            text = "".join([p.extract_text() for p in reader.pages])
            chunks = [text[i:i+800] for i in range(0, len(text), 800)]
            collection.upsert(documents=chunks, metadatas=[{"source": upload.name}]*len(chunks), ids=[f"{upload.name}_{i}" for i in range(len(chunks))])
            st.success("Erfolgreich ins Firmenwissen integriert.")

elif st.session_state.aktive_seite == "Content":
    st.title("✍️ Content Creation Engine")
    st.write("Generiere markenkonforme Texte für Marketing und Kommunikation.")
    
    colA, colB = st.columns([2,1])
    thema = colA.text_area("Worum soll es gehen?", height=100, placeholder="Wir haben einen neuen LKW für unsere Speditions-Flotte gekauft...")
    format_typ = colB.selectbox("Format", ["LinkedIn Post", "Instagram Caption", "Kunden-Newsletter", "Blog-Artikel", "Pressemitteilung"])
    tonality = colB.selectbox("Tonalität", ["Professionell & Seriös", "Locker & Nahbar", "Visionär & Innovativ", "Aggressiv (Sales)"])
    
    if st.button("Magie starten ⚡", type="primary"):
        if thema:
            with st.spinner("Content wird generiert..."):
                prompt = f"Erstelle einen {format_typ} zum Thema: '{thema}'. Die Tonalität soll {tonality} sein. Mach es hochwertig und direkt verwendbar."
                ergebnis = generiere_antwort(prompt, mode="content")
                st.session_state.stats["content"] += 1
                st.markdown("### Dein Ergebnis:")
                st.info(ergebnis)
