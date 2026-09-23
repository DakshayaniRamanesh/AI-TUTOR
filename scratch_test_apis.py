import os
import urllib.request
import urllib.error
import json
from dotenv import load_dotenv

load_dotenv('backend/.env')

print("--- Testing API Keys ---")

# 1. Test Groq
groq_key = os.getenv('GROQ_API_KEY')
if groq_key:
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {groq_key}"}
        )
        urllib.request.urlopen(req)
        print("✅ GROQ_API_KEY: Valid")
    except urllib.error.HTTPError as e:
        print(f"❌ GROQ_API_KEY: Invalid ({e.code})")
    except Exception as e:
        print(f"❌ GROQ_API_KEY: Error - {e}")
else:
    print("❌ GROQ_API_KEY: Not found in .env")

# 2. Test Google Gemini
google_key = os.getenv('GOOGLE_API_KEY')
if google_key:
    try:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}",
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)
        print("✅ GOOGLE_API_KEY: Valid")
    except urllib.error.HTTPError as e:
        print(f"❌ GOOGLE_API_KEY: Invalid ({e.code})")
    except Exception as e:
        print(f"❌ GOOGLE_API_KEY: Error - {e}")
else:
    print("❌ GOOGLE_API_KEY: Not found in .env")

# 3. Test Qdrant
qdrant_url = os.getenv('QDRANT_URL')
qdrant_key = os.getenv('QDRANT_API_KEY')
if qdrant_url and qdrant_key:
    try:
        req = urllib.request.Request(
            f"{qdrant_url}/collections",
            headers={"api-key": qdrant_key}
        )
        urllib.request.urlopen(req)
        print("✅ QDRANT_API_KEY: Valid")
    except urllib.error.HTTPError as e:
        print(f"❌ QDRANT_API_KEY: Invalid ({e.code})")
    except Exception as e:
        print(f"❌ QDRANT_API_KEY: Error - {e}")
else:
    print("❌ QDRANT_API_KEY: Not found in .env")
