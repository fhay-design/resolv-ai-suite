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

# --- 1. SETUP & SICHERHEIT ---
st.set_page_config(page_title="RESOLV.AI Enterprise", page_icon="🚀", layout="wide")

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
email_adresse = os.getenv("EMAIL_ADRESSE")
email_passwort = os.getenv("EMAIL_PASSWORT")
imap_server = os.getenv("IMAP_SERVER")
smtp_server = os.getenv("SMTP_SERVER")
smtp_port = int(os.getenv("SMTP_PORT", 587))
app_password = os.getenv("APP_PASSWORD")

if not api_key or not app_password:
    st.error("🚨 Kritischer Fehler: .env Datei nicht vollständig! Bitte GROQ_API_KEY und APP_PASSWORD prüfen.")
    st.stop()

# Session States
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "posteingang" not in st.session_state: st.session_state.posteingang = []
if "entwuerfe" not in st.session_state: st.session_state.entwuerfe = {}
if "chat_verlauf" not in st.session_state: st.session_state.chat_verlauf = []
if "mails_gesendet" not in st.session_state: st.session_state.mails_gesendet = 0
if "extraktionen" not in st.session_state: st.session_state.extraktionen = 0 
if "aktive_seite" not in st.session_state: st.session_state.aktive_seite = "Dashboard"
if "extrahierte_daten" not in st.session_state: st.session_state.extrahierte_daten = None

# --- 2. LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🔒 RESOLV.AI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Enterprise Suite &mdash; Authentifizierung erforderlich</p><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        passwort_eingabe = st.text_input("Master-Passwort", type="password", placeholder="Passwort eingeben...")
        if st.button("🚀 System entsperren", use_container_width=True, type="primary"):
            if passwort_eingabe == app_password:
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("❌ Zugriff verweigert.")
    st.stop()

# --- 3. INITIALISIERUNG ---
client = Groq(api_key=api_key)

@st.cache_resource
def init_db():
    db = chromadb.PersistentClient(path="./chroma_db")
    return db.get_or_create_collection(name="firmenwissen")

collection = init_db()

# --- 4. ENGINE ---
def generiere_antwort(prompt, kontext="", history=None, is_email=False, is_extraction=False):
    if history is None: history = []
    fallback_modelle = ["llama3-70b-8192", "mixtral-8x7b-32768", "gemma-7b-it"]
    
    if is_email:
        system_prompt = "Du bist ein professioneller Kundenservice-Agent. Antworte auf Deutsch. KEIN Markdown (**), KEINE Betreffzeile. Erfinde NIEMALS Namen; nutze bei unbekannten Namen 'Sehr geehrte Damen und Herren'."
        temperatur = 0.1
    elif is_extraction:
        system_prompt = "Du bist ein präziser Daten-Extraktor. Analysiere den Text und gib die geforderten Werte AUSSCHLIESSLICH als reines JSON-Format zurück, ohne zusätzlichen Text."
        temperatur = 0.0
    else:
        system_prompt = "Du bist der intelligente KI-Berater von RESOLV.AI. Antworte professionell und auf Deutsch. Du darfst Markdown nutzen."
        temperatur = 0.5
        
    if kontext: system_prompt += f"\n\nFirmenwissen:\n{kontext}"

    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]: api_messages.append({"role": msg["role"], "content": msg["content"]})
    api_messages.append({"role": "user", "content": prompt})

    for model_name in fallback_modelle:
        try:
            kwargs = {"response_format": {"type": "json_object"}} if is_extraction else {}
            response = client.chat.completions.create(
                model=model_name, messages=api_messages, temperature=temperatur, max_tokens=2000, **kwargs
            )
            return response.choices[0].message.content
        except: continue
    return "🚨 Systemfehler. Kein Groq-Modell erreichbar."

# --- 5. E-MAIL PIPELINES ---
def lese_letzte_emails(limit=3):
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_adresse, email_passwort)
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()[-limit:]
        
        gefundene_emails = []
        for e_id in reversed(email_ids):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes): subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                    sender = msg.get("From")
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                break
                    else: body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                    gefundene_emails.append({"id": e_id.decode(), "absender": sender, "betreff": subject, "text": body[:2000]})
        mail.logout()
        return gefundene_emails
    except Exception as e: return f"Fehler bei Postfach-Verbindung: {e}"

def sende_email(empfaenger, betreff, text_inhalt):
    try:
        msg = MIMEMultipart()
        msg['From'] = email_adresse
        msg['To'] = empfaenger
        msg['Subject'] = betreff
        msg.attach(MIMEText(text_inhalt, 'plain', 'utf-8'))
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_adresse, email_passwort)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e: return str(e)


# ==========================================
# --- 6. NAVIGATION (SIDEBAR) ---
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/space-shuttle.png", width=60)
    st.markdown("### RESOLV.AI Suite")
    st.markdown("---")
    
    def btn_type(seite): return "primary" if st.session_state.aktive_seite == seite else "secondary"
    
    if st.button("📊 Dashboard & Chat", use_container_width=True, type=btn_type("Dashboard")): 
        st.session_state.aktive_seite = "Dashboard"; st.rerun()
    if st.button("📧 Support-Postfach", use_container_width=True, type=btn_type("Postfach")): 
        st.session_state.aktive_seite = "Postfach"; st.rerun()
    if st.button("📚 Firmenwissen (RAG)", use_container_width=True, type=btn_type("Wissen")): 
        st.session_state.aktive_seite = "Wissen"; st.rerun()
    if st.button("📑 Daten-Extraktion", use_container_width=True, type=btn_type("Extraktion")): 
        st.session_state.aktive_seite = "Extraktion"; st.rerun()
    
    st.markdown("---")
    st.caption(f"Eingeloggt als Admin\n\nSystemstatus: Nominal")


# ==========================================
# --- 7. DIE SEITEN ---
# ==========================================

# --- SEITE 1: DASHBOARD & CHAT ---
if st.session_state.aktive_seite == "Dashboard":
    st.title("📊 Übersicht & KI-Assistent")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    eingesparte_zeit = (st.session_state.mails_gesendet * 5) + (st.session_state.extraktionen * 10)
    
    col_m1.metric(label="Wissensbausteine", value=f"{collection.count()}", delta="In Datenbank")
    col_m2.metric(label="Mails versendet", value=f"{st.session_state.mails_gesendet}", delta="+1 diese Session" if st.session_state.mails_gesendet > 0 else "")
    col_m3.metric(label="Dokumente ausgelesen", value=f"{st.session_state.extraktionen}", delta="+1 diese Session" if st.session_state.extraktionen > 0 else "")
    col_m4.metric(label="Eingesparte Arbeitszeit", value=f"{eingesparte_zeit} Min.", delta="ROI generiert" if eingesparte_zeit > 0 else "")
    st.markdown("---")
    
    st.subheader("KI-Berater")
    for message in st.session_state.chat_verlauf:
        with st.chat_message(message["role"]): st.markdown(message["content"])

    if prompt := st.chat_input("Deine Nachricht an RESOLV.AI..."):
        st.session_state.chat_verlauf.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Agent denkt nach..."):
                antwort = generiere_antwort(prompt, history=st.session_state.chat_verlauf[:-1], is_email=False)
                st.markdown(antwort)
        st.session_state.chat_verlauf.append({"role": "assistant", "content": antwort})
        st.rerun()

# --- SEITE 2: POSTFACH ---
elif st.session_state.aktive_seite == "Postfach":
    st.title("📧 Support-Postfach")
    if st.button("📬 Postfach abrufen"):
        with st.spinner("Synchronisiere..."):
            ergebnis = lese_letzte_emails(3)
            if isinstance(ergebnis, str): st.error(ergebnis)
            else: st.session_state.posteingang = ergebnis; st.success("Erfolgreich!")

    for i, mail in enumerate(st.session_state.posteingang):
        with st.expander(f"📧 {mail['betreff']} (Von: {mail['absender']})"):
            st.info(mail['text'])
            mail_id = mail['id']
            if st.button("✨ Entwurf generieren", key=f"gen_{mail_id}"):
                with st.spinner("KI recherchiert in Dokumenten..."):
                    results = collection.query(query_texts=[mail['text']], n_results=3)
                    kontext = "\n\n".join(results['documents'][0]) if results['documents'] else ""
                    prompt = f"Schreibe eine Antwort auf diese Mail:\n'{mail['text']}'"
                    st.session_state.entwuerfe[mail_id] = generiere_antwort(prompt, kontext, is_email=True)

            if mail_id in st.session_state.entwuerfe:
                st.markdown("---")
                finaler_text = st.text_area("Bearbeite den Entwurf:", value=st.session_state.entwuerfe[mail_id], height=250, key=f"edit_{mail_id}")
                if st.button("🚀 Freigeben & Senden", key=f"send_{mail_id}", type="primary"):
                    with st.spinner("Sende E-Mail..."):
                        antwort_betreff = f"Re: {mail['betreff']}" if not str(mail['betreff']).startswith("Re:") else mail['betreff']
                        erfolg = sende_email(mail['absender'], antwort_betreff, finaler_text)
                        if erfolg is True:
                            st.success(f"✅ E-Mail gesendet!")
                            st.session_state.mails_gesendet += 1
                            del st.session_state.entwuerfe[mail_id]
                            st.rerun()
                        else: st.error(f"Fehler: {erfolg}")

# --- SEITE 3: FIRMENWISSEN ---
elif st.session_state.aktive_seite == "Wissen":
    st.title("📚 Lokales Unternehmenswissen")
    uploaded_file = st.file_uploader("Trainiere die KI mit neuen Dokumenten (PDF):", type="pdf")
    if st.button("📄 Einspeisen") and uploaded_file:
        with st.spinner("Verarbeite Dokument..."):
            reader = PdfReader(uploaded_file)
            text = "".join([page.extract_text() + "\n" for page in reader.pages])
            if text.strip():
                chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
                ids = [f"{uploaded_file.name}_chunk_{i}" for i in range(len(chunks))]
                
                collection.upsert(documents=chunks, metadatas=[{"source": uploaded_file.name} for _ in chunks], ids=ids)
                
                st.success(f"✅ Dokument gespeichert/aktualisiert ({len(chunks)} Bausteine)!")
                time.sleep(1.5); st.rerun() 
            else: st.error("Kein lesbarer Text.")
    st.divider()
    rag_frage = st.text_area("Stelle eine Test-Frage an deine Dokumente:")
    if st.button("Dokumente durchsuchen", type="primary"):
        if rag_frage:
            with st.spinner("Durchsuche lokales Firmenwissen..."):
                results = collection.query(query_texts=[rag_frage], n_results=3)
                if results['documents'] and results['documents'][0]:
                    kontext = "\n\n".join(results['documents'][0])
                    st.write(generiere_antwort(rag_frage, kontext=kontext, is_email=False))
                else: st.warning("Keine passenden Informationen gefunden.")

# --- SEITE 4: DATEN-EXTRAKTION ---
elif st.session_state.aktive_seite == "Extraktion":
    st.title("📑 Intelligente Daten-Extraktion")
    st.write("Lade Rechnungen, Lieferscheine oder Verträge (PDF) hoch. Die KI wandelt unstrukturierten Text in saubere Tabellen um.")
    
    gesuchte_daten = st.text_input("Was soll ausgelesen werden?", "Name des Absenders, Rechnungsnummer, Datum, Gesamtsumme, Steuerbetrag")
    extraktions_datei = st.file_uploader("Dokument hochladen:", type="pdf", key="extract_upload")
    
    if st.button("🧠 Daten auslesen & Tabelle erstellen", type="primary") and extraktions_datei:
        with st.spinner("Analysiere Dokument und strukturiere Daten..."):
            try:
                reader = PdfReader(extraktions_datei)
                text = "".join([page.extract_text() + "\n" for page in reader.pages])
                
                if text.strip():
                    prompt = f"Lies den folgenden Text und extrahiere diese Informationen: {gesuchte_daten}. Antworte ausschließlich in einem sauberen JSON-Format, wobei die gesuchten Daten die Schlüssel sind. Text:\n\n{text[:3000]}"
                    antwort_json_string = generiere_antwort(prompt, is_extraction=True)
                    
                    try:
                        daten_dict = json.loads(antwort_json_string)
                        df = pd.DataFrame([daten_dict])
                        st.session_state.extrahierte_daten = df
                        st.session_state.extraktionen += 1
                        st.success("Erfolgreich extrahiert!")
                    except json.JSONDecodeError:
                        st.error("Die KI konnte kein gültiges Tabellenformat generieren. Bitte versuche es erneut.")
                else:
                    st.error("Das Dokument enthält keinen lesbaren Text.")
            except Exception as e:
                st.error(f"Fehler bei der Verarbeitung: {e}")
                
    if st.session_state.extrahierte_daten is not None:
        st.markdown("### 📊 Extrahierte Daten")
        st.dataframe(st.session_state.extrahierte_daten, use_container_width=True)
        
        csv = st.session_state.extrahierte_daten.to_csv(index=False).encode('utf-8')
        st.download_button(label="💾 Als CSV herunterladen", data=csv, file_name=f"extrahierte_daten.csv", mime="text/csv") 
