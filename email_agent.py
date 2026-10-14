import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def sende_email(empfaenger_email, betreff, nachricht_text, firmenname="RESOLV.AI"):
    # SMTP Setup
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not smtp_user:
        try:
            import streamlit as st
            smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(st.secrets.get("SMTP_PORT", 587))
            smtp_user = st.secrets.get("SMTP_USER")
            smtp_pass = st.secrets.get("SMTP_PASS")
        except Exception:
            pass

    if not smtp_user or not smtp_pass:
        return False, "E-Mail-Zugangsdaten (SMTP) fehlen in .env oder Secrets."

    msg = MIMEMultipart("alternative")
    msg['Subject'] = betreff
    msg['From'] = f"{firmenname} <{smtp_user}>"
    msg['To'] = empfaenger_email

    # Text formatieren (Zeilenumbrüche für HTML übersetzen)
    html_nachricht = nachricht_text.replace('\n', '<br>')
    
    # Der Kalender-Link (Fürs MVP ein Platzhalter, den Makler später im Dashboard eintragen können)
    buchungs_link = "https://calendly.com" 

    # Premium HTML Template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                background-color: #f4f7f6;
                color: #333333;
                line-height: 1.6;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }}
            .header {{
                background-color: #1a2b3c;
                color: #ffffff;
                padding: 25px 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            .content {{
                padding: 30px;
                font-size: 16px;
            }}
            .button-container {{
                text-align: center;
                margin: 35px 0;
            }}
            .button {{
                background-color: #e53e3e;
                color: #ffffff !important;
                text-decoration: none;
                padding: 14px 28px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 16px;
                display: inline-block;
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 20px 30px;
                text-align: center;
                font-size: 12px;
                color: #718096;
                border-top: 1px solid #e2e8f0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{firmenname}</h1>
            </div>
            
            <div class="content">
                {html_nachricht}
                
                <div class="button-container">
                    <a href="{buchungs_link}" class="button">📅 Hier Besichtigungstermin sichern</a>
                </div>
            </div>
            
            <div class="footer">
                Diese E-Mail wurde im Auftrag von <strong>{firmenname}</strong> gesendet.<br><br>
                <em>Automatisierte Kommunikation via RESOLV.AI</em>
            </div>
        </div>
    </body>
    </html>
    """

    # Sicherheits-Fallback (falls ein Mail-Client kein HTML unterstützt, sieht er den reinen Text)
    part1 = MIMEText(nachricht_text + f"\n\nTermin buchen: {buchungs_link}", 'plain')
    part2 = MIMEText(html, 'html')
    
    msg.attach(part1)
    msg.attach(part2)

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, empfaenger_email, msg.as_string())
        server.quit()
        return True, ""
    except Exception as e:
        return False, str(e)
