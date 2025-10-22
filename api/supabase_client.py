import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Custom Supabase Client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Create Supabase client with proper error handling
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized successfully")
    else:
        print(f"Missing environment variables: URL={bool(SUPABASE_URL)}, KEY={bool(SUPABASE_KEY)}")
        supabase = None
except Exception as e:
    print(f"Error creating Supabase client: {e}")
    supabase = None
