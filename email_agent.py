import os
import imaplib
import email
from email.header import decode_header
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# --- 1. ZUGANGSDATEN KUGELSICHER LADEN ---
load_dotenv()

# Wir checken verschiedene mögliche Namen, egal wie du sie in der .env genannt hast
EMAIL_USER = os.getenv("EMAIL_USER") or os.getenv("EMAIL_ADRESSE")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") or os.getenv("EMAIL_PASSWORT")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")

# Fallback für die Cloud (Streamlit Dashboard)
if not EMAIL_USER or not EMAIL_PASSWORD:
    try:
        import streamlit as st
        EMAIL_USER = st.secrets.get("EMAIL_USER") or st.secrets.get("EMAIL_ADRESSE")
        EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD") or st.secrets.get("EMAIL_PASSWORT")
        IMAP_SERVER = st.secrets.get("IMAP_SERVER", "imap.gmail.com")
        SMTP_SERVER = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    except Exception:
        pass

if not EMAIL_USER or not EMAIL_PASSWORD:
    print("🚨 FEHLER: E-Mail Zugangsdaten fehlen! Bitte in der .env Datei eintragen.")

# --- 2. VERBINDUNGS-MOTOR ---
def verbinde_imap():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        return mail
    except Exception as e:
        print(f"🚨 IMAP Verbindungsfehler: {e}")
        return None

# --- 3. KERNFUNKTIONEN FÜR RESOLV.AI ---
def lese_emails(limit=5):
    mail = verbinde_imap()
    if not mail: return "Verbindungsfehler"
    
    mail.select("inbox")
    status, messages = mail.search(None, "UNSEEN")
    
    if status != "OK":
        return []
        
    mail_ids = messages[0].split()
    emails_data = []
    
    for num in mail_ids[-limit:]:
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status == "OK":
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Betreff sauber entschlüsseln
                    betreff_raw, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(betreff_raw, bytes):
                        betreff = betreff_raw.decode(encoding if encoding else "utf-8")
                    else:
                        betreff = betreff_raw
                        
                    absender = msg.get("From")
                    
                    # Nachrichtentext auslesen
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode()
                                    break
                                except:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode()
                        except:
                            pass
                            
                    emails_data.append({
                        "id": num.decode(),
                        "betreff": betreff,
                        "absender": absender,
                        "text": body
                    })
    mail.logout()
    return emails_data

def markiere_als_beantwortet(mail_id):
    mail = verbinde_imap()
    if not mail: return
    mail.select("inbox")
    mail.store(mail_id.encode(), '+FLAGS', '\\Answered')
    mail.store(mail_id.encode(), '+FLAGS', '\\Seen')
    mail.logout()

def loesche_email(mail_id):
    mail = verbinde_imap()
    if not mail: return
    mail.select("inbox")
    mail.store(mail_id.encode(), '+FLAGS', '\\Deleted')
    mail.expunge()
    mail.logout()

def sende_email(empfaenger, betreff, nachricht_text, firmenname="RESOLV.AI"):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{firmenname} <{EMAIL_USER}>"
        msg['To'] = empfaenger
        msg['Subject'] = betreff
        msg.attach(MIMEText(nachricht_text, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True, ""
    except Exception as e:
        print(f"🚨 SMTP Fehler beim Senden: {e}")
        return False, str(e)
