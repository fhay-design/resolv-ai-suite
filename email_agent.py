def lese_emails():
    """
    Simuliert den Posteingang eines Maklers mit 3 typischen Anfragen 
    (A-Lead, C-Lead/Spam, B-Lead), perfekt für die Live-Demo.
    """
    return [
        {
            "id": "mail_1",
            "absender": "dr.m.weber@klinikum-nrw.de",
            "betreff": "Kaufinteresse: 3-Zimmer Wohnung Opladen",
            "text": "Sehr geehrte Damen und Herren, meine Frau und ich (beide Fachärzte) interessieren uns sehr für das Objekt. Eine Finanzierungsbestätigung unserer Hausbank über 500.000 € liegt uns bereits vor. Wir könnten jederzeit besichtigen. MfG Dr. Weber"
        },
        {
            "id": "mail_2",
            "absender": "kevin_xy99@gmx.de",
            "betreff": "wohnung",
            "text": "hallo ist die noch da? was letzte preis? bitte anrufen 0176..."
        },
        {
            "id": "mail_3",
            "absender": "s.mueller@gmail.com",
            "betreff": "Besichtigung",
            "text": "Guten Tag, die Wohnung sieht toll aus. Ich bin unbefristet angestellt (Netto ca. 2.400€). Wäre die Wohnung auch für mich und meine zwei kleinen Hunde geeignet? Freue mich auf Rückmeldung."
        }
    ]
