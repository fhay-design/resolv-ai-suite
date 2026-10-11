import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def hole_zugangsdaten(schluessel, default=None):
    try:
        return st.secrets[schluessel]
    except:
        return os.getenv(schluessel, default)

IMAP_SERVER = hole_zugangsdaten("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = hole_zugangsdaten("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(hole_zugangsdaten("SMTP_PORT", 587))
EMAIL_ACCOUNT = hole_zugangsdaten("EMAIL_ACCOUNT")
EMAIL_PASSWORD = hole_zugangsdaten("EMAIL_PASSWORD")

def lese_emails(limit=5):
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        return "🚨 Fehler: Zugangsdaten (EMAIL_ACCOUNT / EMAIL_PASSWORD) fehlen!"
        
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
        
        status, messages = mail.search(None, "ALL")
        if status != "OK": return []
            
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
                        
                    from_ = str(msg.get("From"))
                    
                    # ULTIMATIVER ROBOTER-FILTER
                    from_lower = from_.lower()
                    bots = ["noreply", "no-reply", "daemon", "postmaster", "mailer", "system", "support"]
                    if any(b in from_lower for b in bots):
                        continue 
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode(errors='ignore')
                                    break
                                except: pass
                    else:
                        try: body = msg.get_payload(decode=True).decode(errors='ignore')
                        except: body = msg.get_payload()
                            
                    posteingang.append({
                        "id": m_id.decode("utf-8"),
                        "absender": from_,
                        "betreff": str(subject),
                        "text": str(body).strip()[:1500]
                    })
        mail.logout()
        return posteingang
    except Exception as e:
        return f"🚨 IMAP Verbindungsfehler: {e}"

def sende_email(empfaenger, betreff, text):
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD: return False, "Keine Zugangsdaten"
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = empfaenger
        msg['Subject'] = betreff
        msg.attach(MIMEText(text, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True, "Gesendet"
    except Exception as e:
        return False, str(e)

def loesche_email(mail_id_str):
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
        # Bei Google Mail explizit das Spam-Label anheften
        try:
            mail.store(mail_id_str.encode('utf-8'), '+X-GM-LABELS', '\\Spam')
        except: pass
        # Aus der Inbox löschen
        mail.store(mail_id_str.encode('utf-8'), '+FLAGS', '\\Deleted')
        mail.expunge()
        mail.logout()
        return True
    except Exception as e:
        return False
