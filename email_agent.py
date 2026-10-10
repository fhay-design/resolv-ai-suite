import os
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv

# Lade die Umgebungsvariablen
load_dotenv()
email_adresse = os.getenv("EMAIL_ADRESSE")
email_passwort = os.getenv("EMAIL_PASSWORT")
imap_server = os.getenv("IMAP_SERVER")

def lese_emails():
    """
    Verbindet sich mit dem Postfach, ruft die neuesten E-Mails ab 
    und extrahiert Betreff, Absender und Textkörper.
    """
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_adresse, email_passwort)
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")
        
        if not messages[0]: 
            return []
            
        email_ids = messages[0].split()[-3:] # Lädt die letzten 3 Mails
        gefundene_emails = []
        
        for e_id in reversed(email_ids):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes): 
                        subject = subject.decode(encoding or "utf-8", errors="ignore")
                    
                    sender = msg.get("From")
                    body = ""
                    
                    if msg.is_multipart():
                        for p in msg.walk():
                            if p.get_content_type() == "text/plain":
                                body = p.get_payload(decode=True).decode("utf-8", errors="ignore")
                                break
                    else: 
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                        
                    gefundene_emails.append({
                        "id": e_id.decode(), 
                        "absender": sender, 
                        "betreff": subject, 
                        "text": body[:1500]
                    })
        mail.logout()
        return gefundene_emails
    except Exception as e: 
        return str(e)
