import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Hier baut sich die Brücke zu deiner neuen Datenbank
supabase: Client = create_client(url, key)

def get_tenant_info(user_id):
    """Holt die Firmendaten (wie die Google Sheet URL) des eingeloggten Nutzers."""
    try:
        response = supabase.table('tenants').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Fehler beim Laden der Tenant-Daten: {e}")
        return None
