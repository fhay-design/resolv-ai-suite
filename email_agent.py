import imaplib
import email
from email.header import decode_header
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# HIER IST DER FIX: Wir nutzen den offiziellen Streamlit-Weg für die Cloud
def hole_zugangsdaten(schluessel, default=None):
    try:
        return st.secrets[schluessel]
    except:
        return os.getenv(schluessel, default)

IMAP_SERVER = hole_zugangsdaten("IMAP_SERVER", "imap.gmail.com")
EMAIL_ACCOUNT = hole_zugangsdaten("EMAIL_ACCOUNT")
EMAIL_PASSWORD = hole_zugangsdaten("EMAIL_PASSWORD")

def lese_emails(limit=5):
    """
    Verbindet sich über IMAP mit einem echten Postfach und lädt die neuesten Mails herunter.
    """
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        return "🚨 Fehler: Zugangsdaten (EMAIL_ACCOUNT / EMAIL_PASSWORD) fehlen in den Streamlit Secrets!"
        
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
        
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return []
            
        email_ids = messages[0].split()
        latest_ids = email_ids[-limit:]
        latest_ids.reverse()
        
        posteingang = []
        
        for m_id in latest_ids:
            res, msg_data = mail.fetch(m_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors='ignore')
                        
                    from_ = msg.get("From")
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode(errors='ignore')
                                    break
                                except:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode(errors='ignore')
                        except:
                            body = msg.get_payload()
                            
                    posteingang.append({
                        "id": m_id.decode("utf-8"),
                        "absender": str(from_),
                        "betreff": str(subject),
                        "text": str(body).strip()[:1500]
                    })
        
        mail.logout()
        return posteingang
        
    except Exception as e:
        return f"🚨 IMAP Verbindungsfehler: {e}"
