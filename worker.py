import time
import os
import re
from dotenv import load_dotenv

load_dotenv()

from database import supabase
from email_agent import lese_emails, sende_email, loesche_email, markiere_als_beantwortet
# HIER ist der neue Import für die Datenbank-Suche
from ai_engine import qualifiziere_lead, generiere_antwort, hole_objekt_kontext 

print("🚀 RESOLV.AI Worker bootet. Initialisiere 24/7 Matrix...")

def run_worker():
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
                check = supabase.table("leads").select("id").eq("mail_id", mail['id']).execute()
                if check.data:
                    continue 
                    
                print(f"\n📬 Neue Nachricht detektiert: {mail['betreff']}")
                
                print("🛡️ Türsteher prüft Relevanz...")
                router_prompt = (
                    "Du bist ein strenger Filter für ein Maklerbüro. Prüfe diese E-Mail. "
                    "Handelt es sich um eine konkrete Immobilien-Anfrage eines Interessenten (Kauf, Miete, Besichtigung)? "
                    "Antworte AUSSCHLIESSLICH mit dem Wort JA oder NEIN. Keine Begründung.\n\n"
                    f"Betreff: {mail['betreff']}\nNachricht: {mail['text'][:1000]}"
                )
                
                router_entscheidung = generiere_antwort(router_prompt, mode="email").strip().upper()
                
                if "JA" not in router_entscheidung or "NEIN" in router_entscheidung:
                    print("🛑 Irrelevante E-Mail (Spam/Newsletter/Intern) erkannt. Wird ignoriert.")
                    markiere_als_beantwortet(mail['id'])
                    continue
                    
                print("🧠 Ist ein Lead! KI qualifiziert...")
                
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
                    
                    # --- HIER IST DER MAGISCHE RAG-MOMENT ---
                    print("🔍 Durchsuche Objekt-Datenbank nach relevanten Fakten...")
                    kontext = hole_objekt_kontext(f"{mail['betreff']} {mail['text']}", tenant_id)
                    
                    if kontext:
                        print("📚 Objekt-Fakten gefunden! KI wird mit Fachwissen geladen.")
                    else:
                        print("⚠️ Keine spezifischen Objekt-Fakten in der Datenbank gefunden.")

                    if kat == "A":
                        anweisung = (
                            "Top-Lead. Bedanke dich extrem freundlich für die Anfrage. "
                            "Verweise höflich auf den untenstehenden Link zur Buchung eines Besichtigungstermins. "
                            f"Beende STRIKT mit 'Mit freundlichen Grüßen, Ihr Team von {firma}'"
                        )
                    else:
                        anweisung = (
                            "Bedanke dich für das Interesse. Gehe auf die Fakten des Objekts ein, falls relevant. "
                            "Fordere höflich eine Vorab-Selbstauskunft an, bevor ein Termin gebucht werden kann. "
                            f"Beende STRIKT mit 'Mit freundlichen Grüßen, Ihr Team von {firma}'"
                        )
                    
                    # Der Kontext wird jetzt nahtlos in den Prompt injiziert
                    voller_prompt = f"ANWEISUNG: {anweisung}\n\nOBJEKT-FAKTEN (Nutze diese Infos):\n{kontext}\n\nKundenmail: {mail['text']}"
                    entwurf = generiere_antwort(voller_prompt, mode="email")
                    
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
                    print("✅ Lead sicher im CRM Dashboard gespeichert.")
        
        time.sleep(15)

if __name__ == "__main__":
    run_worker()
