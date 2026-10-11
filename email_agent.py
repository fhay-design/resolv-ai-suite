import imaplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv

load_dotenv()

# Wir holen uns die echten Zugangsdaten aus den Umgebungsvariablen (.env / st.secrets)
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com") # Standard: Gmail
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def lese_emails(limit=5):
    """
    Verbindet sich über IMAP mit einem echten Postfach und lädt die neuesten Mails herunter.
    """
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        return "🚨 Fehler: Zugangsdaten (EMAIL_ACCOUNT / EMAIL_PASSWORD) fehlen in den System-Einstellungen!"
        
    try:
        # Sichere SSL-Verbindung zum Mailserver aufbauen
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
        
        # Alle Mails suchen und die neuesten X extrahieren
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return []
            
        email_ids = messages[0].split()
        latest_ids = email_ids[-limit:]  # Nur die letzten 'limit' Mails
        latest_ids.reverse()             # Neueste nach oben
        
        posteingang = []
        
        for m_id in latest_ids:
            res, msg_data = mail.fetch(m_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Betreff sauber decodieren (wegen Umlauten)
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors='ignore')
                        
                    # Absender
                    from_ = msg.get("From")
                    
                    # Textkörper der Mail extrahieren (nur reinen Text, kein HTML-Code)
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
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
                        "text": str(body).strip()[:1500] # Begrenzung auf 1500 Zeichen für die KI
                    })
        
        mail.logout()
        return posteingang
        
    except Exception as e:
        return f"🚨 IMAP Verbindungsfehler: {e}"
