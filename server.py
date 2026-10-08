import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from groq import Groq

# --- KONFIGURATION ---
GROQ_API_KEY = "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"
EMAIL_USER = "resolv.ai.service@gmail.com"
EMAIL_PASS = "cklv ibso gsez dajb" # Ohne Leerzeichen!

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"

# Governance & Richtlinien für RESOLV.AI
SYSTEM_PROMPT = """
Du bist der autonome KI-Kundenservice-Agent von RESOLV.AI.
Deine Aufgabe: Beantworte eingehende Kundenanfragen strikt nach folgenden Vorgaben:

- Sprache: Strikte und reine deutsche Sprache. Es dürfen absolut KEINE englischen Wörter oder Begriffe (wie 'sincerely', 'damages', etc.) verwendet werden.
- Anrede: Sie (Formell)
- Tonfall: Professionell, lösungsorientiert & empathisch
- Firmen-Regeln:
  * Rückgabefrist: Nur 7 Tage ab Kauf.
  * Erstattung: Kein Geld zurück auf Bankkonten, nur Gutscheine.
  * Beschädigungen: Foto der Beschädigung ist zwingend PFLICHT.
  * Rabatte: Keine Rabatte für Lieferverzögerungen.

Formuliere die Antwort versandfertig ohne Platzhalter.
"""

def generate_ai_reply(mail_body):
    """Holt dynamisch ein verfuegbares Text-Modell bei Groq, um 404-Fehler zu vermeiden."""
    client = Groq(api_key=GROQ_API_KEY)
    
    # Modelle abfragen und Filtern (Guard, Whisper, Vision ausschliessen)
    available_models = [
        m.id for m in client.models.list().data 
        if not any(x in m.id.lower() for x in ["guard", "whisper", "vision"])
    ]
    
    # Bevorzugt Llama/Mixtral wählen, sonst das erste verfuegbare Modell
    model = next((m for m in available_models if "llama" in m.lower() or "mixtral" in m.lower()), available_models[0])
    print(f"🤖 Nutze aktives Groq-Modell: {model}")

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Kundenanfrage:\n{mail_body}"}
        ],
        model=model
    )
    return response.choices[0].message.content

def create_gmail_draft(subject, sender, reply_body):
    """Speichert die KI-Antwort mit dem Flag '\\Draft', damit sie in Gmail sichtbar wird."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        
        # 1. Ermittle den exakten Namen des Entwurfs-Ordners von Gmail
        draft_folder = None
        _, folders = mail.list()
        for f in folders:
            folder_str = f.decode('utf-8', errors='ignore')
            if '\\Drafts' in folder_str or 'Entwürfe' in folder_str:
                parts = folder_str.split(' "/" ')
                if len(parts) > 1:
                    draft_folder = parts[-1].strip('"')
                break
        
        if not draft_folder:
            draft_folder = '[Gmail]/Entwürfe'

        msg = MIMEMultipart()
        msg['To'] = sender
        msg['Subject'] = f"Re: {subject}"
        msg['From'] = EMAIL_USER
        msg.attach(MIMEText(reply_body, 'plain', 'utf-8'))

        now = imaplib.Time2Internaldate(time.time())
        
        # 2. WICHTIG: '\\Draft' als Flag mitsenden
        try:
            mail.append(draft_folder, '\\Draft', now, msg.as_bytes())
            print(f"✅ Entwurf erfolgreich in Gmail ({draft_folder}) erstellt für: {sender}")
        except Exception:
            # Fallback auf englischen Standardordner
            mail.append('[Gmail]/Drafts', '\\Draft', now, msg.as_bytes())
            print(f"✅ Entwurf im Fallback-Ordner ([Gmail]/Drafts) erstellt für: {sender}")
            
        mail.logout()
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Entwurfs: {e}")

def check_and_process_emails():
    """Liest ungelesene E-Mails aus und startet den KI-Workflow."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('inbox')

        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()

        if not email_ids:
            print("💤 Keine neuen ungelesenen Mails...")
            return

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = msg["subject"]
                    sender = msg["from"]
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors='ignore')

                    print(f"\n📩 Neue Mail von: {sender} | Betreff: {subject}")
                    print("🤖 Generiere KI-Antwort...")

                    ai_reply = generate_ai_reply(body)
                    create_gmail_draft(subject, sender, ai_reply)

        mail.logout()
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Mails: {e}")

if __name__ == "__main__":
    print("🚀 RESOLV.AI Autopilot-Server gestartet...")
    print("Überwache Posteingang alle 15 Sekunden auf neue Mails...\n")
    
    while True:
        check_and_process_emails()
        time.sleep(15)
