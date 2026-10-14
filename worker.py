import time
import os
import re
from dotenv import load_dotenv

# 1. ZUERST die Umgebungsvariablen (.env) laden, BEVOR irgendetwas anderes passiert!
load_dotenv()

# 2. DANACH erst die eigenen Module laden, die diese Passwörter benötigen
from database import supabase
from email_agent import lese_emails, sende_email, loesche_email, markiere_als_beantwortet
from ai_engine import qualifiziere_lead, generiere_antwort

print("🚀 RESOLV.AI Worker bootet. Initialisiere 24/7 Matrix...")

def run_worker():
    # Hole deinen Makler-Account aus der Datenbank
    res = supabase.table("tenants").select("user_id", "company_name").limit(1).execute()
    if not res.data:
        print("🚨 Kein Account gefunden. Bitte logge dich erst einmal im Dashboard ein!")
        return
        
    tenant_id = res.data[0]["user_id"]
    firma = res.data[0]["company_name"]
    print(f"✅ Verbunden mit Tenant: {firma}")
    print("📡 Radar aktiv. Überwache Posteingang...")

    while True:
        mails = lese_emails(limit=5)
        
        if isinstance(mails, str):
            print(f"⚠️ {mails}")
        elif mails:
            for mail in mails:
                # Sicherheits-Check: Haben wir diese Mail schon in der Datenbank?
                check = supabase.table("leads").select("id").eq("mail_id", mail['id']).execute()
                if check.data:
                    continue 
                    
                print(f"\n📬 Neue Anfrage detektiert: {mail['betreff']}")
                print("🧠 KI qualifiziert den Lead...")
                
                q = qualifiziere_lead(mail['text'])
                if not q: continue
                    
                kat = q.get("kategorie", "B")
                
                if kat == "C":
                    print("🗑️ C-Lead erkannt. Feuere HTML-Absage und archiviere...")
                    absage = (
                        "Sehr geehrte Damen und Herren,\n\n"
                        "vielen Dank für Ihr Interesse an der angefragten Immobilie.\n\n"
                        "Da die Vermarktung für dieses Objekt bereits sehr weit fortgeschritten ist, "
                        "müssen wir Ihnen heute leider mitteilen, dass die Immobilie bereits vergeben ist.\n\n"
                        "Wir bitten um Ihr Verständnis und wünschen Ihnen für die weitere Wohnungssuche "
                        "alles Gute und viel Erfolg.\n\n"
                        f"Mit freundlichen Grüßen\nIhr Team von {firma}"
                    )
                    match = re.search(r'[\w\.-]+@[\w\.-]+', mail.get('absender', ''))
                    if match:
                        sende_email(match.group(0), f"Re: {mail['betreff']}", absage, firmenname=firma)
                        
                    loesche_email(mail['id'])
                    
                    # Für die Statistik in die Datenbank schreiben
                    supabase.table("leads").insert({
                        "tenant_id": tenant_id,
                        "mail_id": mail['id'],
                        "absender": mail['absender'],
                        "betreff": mail['betreff'],
                        "nachricht": mail['text'],
                        "kategorie": "C",
                        "begruendung": q.get('begruendung', ''),
                        "ki_entwurf": "Automatisch abgesagt.",
                        "status": "abgesagt"
                    }).execute()
                    
                else:
                    print(f"⭐ {kat}-Lead detektiert! Generiere Premium-Antwort...")
                    if kat == "A":
                        anweisung = (
                            "Top-Lead. Bedanke dich extrem freundlich für die Anfrage und das starke Profil. "
                            "Erfinde keine Anhänge. Schlage zwei konkrete Termine nächste Woche vor. "
                            f"Beende STRIKT mit 'Mit freundlichen Grüßen, Ihr Team von {firma}'"
                        )
                    else:
                        anweisung = (
                            "Bedanke dich für das Interesse, fordere aber höflich eine Vorab-Selbstauskunft an. "
                            f"Beende STRIKT mit 'Mit freundlichen Grüßen, Ihr Team von {firma}'"
                        )
                        
                    entwurf = generiere_antwort(f"ANWEISUNG: {anweisung}\n\nKundenmail: {mail['text']}", mode="email")
                    
                    supabase.table("leads").insert({
                        "tenant_id": tenant_id,
                        "mail_id": mail['id'],
                        "absender": mail['absender'],
                        "betreff": mail['betreff'],
                        "nachricht": mail['text'],
                        "kategorie": kat,
                        "begruendung": q.get('begruendung', ''),
                        "ki_entwurf": entwurf,
                        "status": "offen"
                    }).execute()
                    
                    markiere_als_beantwortet(mail['id'])
                    print("✅ Lead sicher in der Datenbank gespeichert.")
        
        # 15 Sekunden Pause, um Google nicht zu überlasten
        time.sleep(15)

if __name__ == "__main__":
    run_worker()
