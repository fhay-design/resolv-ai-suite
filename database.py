import os
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Versuch: Lade lokale Passwörter aus der .env Datei (für den Worker im Terminal)
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# 2. Fallback: Wenn lokal nichts da ist, nimm die Cloud-Secrets (für Streamlit)
if not url or not key:
    import streamlit as st
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

# Erstelle die finale Verbindung
supabase: Client = create_client(url, key)

# Hilfsfunktion für das Dashboard
def get_tenant_info(user_id):
    try:
        res = supabase.table("tenants").select("*").eq("user_id", user_id).limit(1).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        print(f"Fehler beim Abrufen der Tenant-Info: {e}")
        return None
