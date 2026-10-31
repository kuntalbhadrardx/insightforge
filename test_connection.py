import os
from dotenv import load_dotenv
from supabase import create_client

# 1. Load variables from .env
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("--- Checking Environment Variables ---")
print(f"SUPABASE_URL: {supabase_url if supabase_url else '❌ MISSING'}")
print(f"SUPABASE_KEY: {'[DETECTED]' if supabase_key else '❌ MISSING'}")

if not supabase_url or not supabase_key:
    print("\n❌ Error: Missing URL or Key in .env file. Check your .env file!")
    exit(1)

# 2. Test Connection
print("\n--- Connecting to Supabase ---")
try:
    client = create_client(supabase_url, supabase_key)
    
    # Try querying the documents table
    res = client.table("documents").select("id").limit(1).execute()
    print("✅ SUCCESS! Connected to Supabase and queried the 'documents' table successfully.")
    
except Exception as e:
    print("\n❌ Connection Failed!")
    print(f"Details: {e}")